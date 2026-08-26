#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrai e transforma dados da API da LOC1 no mesmo formato que build_dashboard.py
espera das 3 planilhas .xlsx (Faturamento, Status de Maquinas, Taxa de Ocupação).

Limitações conhecidas desta v1 (a API ainda não expõe estes campos - ver
loc1_pending_fields.md): sem filtro de notas canceladas confiável (usa uma
heurística por texto), "Desconto"/"IRF"/"Total Documento" não vêm da API
(ficam como aproximação) e "Tipo do Modelo" vem de uma tabela local
(tipo_modelo_mapping.csv) em vez de vir do SAP B1 diretamente.
"""
import json
import re
import time
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from loc1_client import Loc1Client

BASE = Path(__file__).parent
TIPO_MODELO_FILE = BASE / "tipo_modelo_mapping.csv"
BP_CACHE_FILE = BASE / ".loc1_cache_business_partners.json"
BP_CACHE_TTL_SECONDS = 24 * 3600

TIPO_POR_SEQCODE = {
    "33": "Fatura",
    "28": "NFse Serviço",
    "34": "NF de débito",
    "27": "NFe DANFe",
}

STATUS_POR_CODIGO = {
    "A": "Disponivel",
    "C": "Em Contrato",
    "M": "Em Manutenção",
    # "I" (Inativo) é descartado - ver SerialNumberDetails/List
}

VALOR_POR_TIPO_MODELO = {
    "MANIPULADOR TELESCÓPICO ROTATIVO": 55000.00,
    "MANIPULADOR TELESCÓPICO": 28166.44,
    "PLATAFORMA ARTIC. COMBUSTAO": 15000.00,
    "PLATAFORMA ARTIC. ELETRICA": 9000.00,
    "PLATAFORMA TESOURA ELETRICA": 3700.00,
    "RETROESCAVADEIRA": 14900.00,
}


def get_client() -> Loc1Client:
    client = Loc1Client.from_env()
    client.login()
    return client


# ---------------------------------------------------------------------------
# Status de Maquinas <- SerialNumberDetails/List
# ---------------------------------------------------------------------------
def get_status_df(client: Optional[Loc1Client] = None) -> pd.DataFrame:
    client = client or get_client()
    records = client.list_all("SerialNumberDetails")

    tipo_modelo = pd.read_csv(TIPO_MODELO_FILE, dtype=str).set_index("Nº do item")["Tipo do Modelo"]

    rows = []
    for r in records:
        codigo = r.get("U_LOC1_Status", "")
        status_pt = STATUS_POR_CODIGO.get(codigo)
        if status_pt is None:
            continue  # exclui "I" (inativo) e qualquer código desconhecido
        item_code = r.get("ItemCode", "")
        rows.append({
            "Nº do item": item_code,
            "Modelo": r.get("ItemName", ""),
            "Nº de série": r.get("DistNumber", ""),
            "Nº de série do fabricante": r.get("MnfSerial", ""),
            "Status": status_pt,
            "Tipo do Modelo": tipo_modelo.get(item_code, "Não classificado"),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Taxa de Ocupação <- Status de Maquinas (agregado) + tabela de valores fixos
# Replica a query SQL: INNER JOIN contra a tabela de valores, então Tipos de
# Modelo fora de VALOR_POR_TIPO_MODELO são excluídos do resultado.
# ---------------------------------------------------------------------------
def get_occupancy_df(status_df: Optional[pd.DataFrame] = None,
                      client: Optional[Loc1Client] = None) -> pd.DataFrame:
    status_df = status_df if status_df is not None else get_status_df(client)
    df = status_df[status_df["Tipo do Modelo"].isin(VALOR_POR_TIPO_MODELO)]

    rows = []
    for tipo, grupo in df.groupby("Tipo do Modelo"):
        total = len(grupo)
        disp = int((grupo["Status"] == "Disponivel").sum())
        contr = int((grupo["Status"] == "Em Contrato").sum())
        manut = int((grupo["Status"] == "Em Manutenção").sum())
        valor = VALOR_POR_TIPO_MODELO[tipo]
        rows.append({
            "Tipo do Modelo": tipo,
            "Total de Equipamentos": float(total),
            "Disponível": float(disp),
            "Em Contrato": float(contr),
            "Em Manutenção": float(manut),
            "Taxa Disponível (%)": round(disp / total * 100, 2) if total else 0.0,
            "Taxa Em Contrato (%)": round(contr / total * 100, 2) if total else 0.0,
            "Taxa Manutenção (%)": round(manut / total * 100, 2) if total else 0.0,
            "Receita Disponível": round(disp * valor, 2),
            "Receita Em Contrato": round(contr * valor, 2),
            "Receita Em Manutenção": round(manut * valor, 2),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Faturamento <- DocMkt/List (Document=AR-Invoice) + BusinessPartner/List (CNPJ)
# ---------------------------------------------------------------------------
def _load_business_partner_tax_ids(client: Loc1Client) -> Dict[str, str]:
    if BP_CACHE_FILE.exists():
        cached = json.loads(BP_CACHE_FILE.read_text())
        if time.time() - cached.get("fetched_at", 0) < BP_CACHE_TTL_SECONDS:
            return cached["tax_ids"]

    partners = client.list_all("BusinessPartner")
    tax_ids = {}
    for p in partners:
        code = p.get("CardCode")
        if not code:
            continue
        tax_ids[code] = p.get("TaxId0") or p.get("TaxId4") or ""

    BP_CACHE_FILE.write_text(json.dumps({"fetched_at": time.time(), "tax_ids": tax_ids}))
    return tax_ids


def _fetch_invoices_since(client: Loc1Client, since: Optional[str], page_size: int = 50,
                           workers: int = 8, batch_pages: int = 16):
    """Busca AR-Invoice mais recentes primeiro (Order DESC por DocDate), em lotes
    de páginas buscados em paralelo, e para assim que um lote inteiro já está
    abaixo de `since` (AAAA-MM-DD). Sem `since`, busca tudo (mais lento)."""
    from concurrent.futures import ThreadPoolExecutor

    since_ts = pd.Timestamp(since) if since else None
    order = {"Field": "DocDate", "Value": "DESC"}
    extra = {"Document": "AR-Invoice"}

    def fetch_page(page_idx: int):
        start = 1 + page_idx * page_size
        data = client.list_page("DocMkt", results_from=start, results_to=start + page_size - 1,
                                 extra=extra, order=order)
        return client._extract_records(data)

    invoices = []
    page_idx = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            batch_indices = list(range(page_idx, page_idx + batch_pages))
            results = list(pool.map(fetch_page, batch_indices))
            reached_end = False
            stop_by_date = False
            for page in results:
                if not page:
                    reached_end = True
                    break
                invoices.extend(page)
                if since_ts is not None:
                    page_dates = pd.to_datetime([p.get("DocDate", "") for p in page],
                                                 format="%d/%m/%Y", errors="coerce")
                    if page_dates.max() < since_ts:
                        stop_by_date = True
                if len(page) < page_size:
                    reached_end = True
                    break
            if reached_end or stop_by_date:
                break
            page_idx += batch_pages

    if since_ts is not None:
        invoices = [
            inv for inv in invoices
            if pd.to_datetime(inv.get("DocDate", ""), format="%d/%m/%Y", errors="coerce") >= since_ts
        ]
    return invoices


DEVOLUCAO_NF_RE = re.compile(r"Nota Fiscal de Sa.da\s*-\s*(?:CA\s*-\s*)?(\d+)", re.IGNORECASE)

TIPOS_FATURAMENTO_OFICIAL = {"Fatura", "NFse Serviço", "NFe DANFe"}  # "NF de débito" fica fora - confirmado com o usuário


def _fetch_notas_devolvidas(client: Loc1Client) -> set:
    """Busca AR-Credit-Memo (Notas de Devolução) e extrai, do texto do JrnlMemo,
    o número da nota fiscal original devolvida - replica o NOT IN contra
    ORIN/RIN1 (BaseType=13) da query original, já que a API não expõe essas
    tabelas diretamente."""
    notas = client.list_all("DocMkt", extra={"Document": "AR-Credit-Memo"})
    devolvidas = set()
    for n in notas:
        m = DEVOLUCAO_NF_RE.search(n.get("JrnlMemo") or "")
        if m:
            devolvidas.add(m.group(1))
    return devolvidas


def get_faturamento_df(client: Optional[Loc1Client] = None, since: Optional[str] = "2025-01-01",
                        include_cnpj: bool = False, apenas_tipos_oficiais: bool = True) -> pd.DataFrame:
    """`since`: AAAA-MM-DD, limita aos documentos a partir dessa data (mais rápido).
    Passe since=None para buscar o histórico completo.
    `include_cnpj`: busca CNPJ/CPF via BusinessPartner/List (12k+ registros, ~126
    páginas, cacheado 24h em disco). Desligado por padrão porque esse campo só
    alimenta um contador de qualidade de dados, não entra em nenhum cálculo.
    `apenas_tipos_oficiais`: mantém só Fatura/NFse Serviço/NFe DANFe (exclui
    "NF de débito"), conforme definição de Faturamento confirmada com o usuário."""
    client = client or get_client()
    invoices = _fetch_invoices_since(client, since)
    tax_ids = _load_business_partner_tax_ids(client) if include_cnpj else {}
    notas_devolvidas = _fetch_notas_devolvidas(client)

    rows = []
    canceladas = 0
    devolvidas_excluidas = 0
    for inv in invoices:
        memo = (inv.get("JrnlMemo") or "")
        if memo.strip().lower() == "cancelado":
            canceladas += 1
            continue

        serial = inv.get("Serial", "")
        if serial and serial in notas_devolvidas:
            devolvidas_excluidas += 1
            continue

        total_faturado = sum(float(i.get("InsTotal", 0) or 0) for i in inv.get("Installments", []))
        total_documento = sum(float(i.get("PriceBefDi", 0) or 0) for i in inv.get("Items", []))
        card_code = inv.get("CardCode", "")
        tipo = TIPO_POR_SEQCODE.get(inv.get("SeqCode", ""))

        if apenas_tipos_oficiais and tipo not in TIPOS_FATURAMENTO_OFICIAL:
            continue

        rows.append({
            "TELA": "NF de saída",
            "Nº interno": inv.get("DocEntry", ""),
            "Código do cliente/fornecedor": card_code,
            "CNPJ/ CPF": tax_ids.get(card_code) or None,
            "Nome_PN": inv.get("CardName", ""),
            "Data Faturamento": pd.to_datetime(inv.get("DocDate", ""), format="%d/%m/%Y", errors="coerce"),
            "N NF": inv.get("Serial", ""),
            # "Total Documento" e "Desconto"/"IRF" não vêm da API ainda (ver
            # loc1_pending_fields.md) - aproximação: Total Documento = Total
            # Faturado e Desconto/IRF = 0, até DiscSum/WTSum serem liberados.
            "Total Documento": total_documento if total_documento else total_faturado,
            "Desconto": 0.0,
            "IRF": 0.0,
            "Total Faturado": total_faturado,
            "Tipo": tipo,
        })

    df = pd.DataFrame(rows)
    df.attrs["devolvidas_excluidas"] = devolvidas_excluidas
    df.attrs["canceladas_excluidas"] = canceladas
    return df


if __name__ == "__main__":
    c = get_client()
    print("Login OK.")

    status_df = get_status_df(c)
    print(f"Status de Maquinas: {len(status_df)} equipamentos (ativos, exclui status 'I')")
    print(status_df["Status"].value_counts())

    occ_df = get_occupancy_df(status_df)
    print(f"\nTaxa de Ocupação: {len(occ_df)} tipos de modelo")
    print(occ_df)

    fat_df = get_faturamento_df(c)
    print(f"\nFaturamento: {len(fat_df)} notas (excluídas {fat_df.attrs['canceladas_excluidas']} marcadas 'Cancelado')")
    print(fat_df.head())
