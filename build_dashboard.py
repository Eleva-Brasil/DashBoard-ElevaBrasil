#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline de geração do Dashboard Gerencial - Eleva Brasil (Visão Executiva).

Como atualizar o dashboard quando novas planilhas chegarem:
    1. Substitua os 3 arquivos .xlsx nesta mesma pasta, mantendo os NOMES:
         - "Faturamento Eleva Brasil.xlsx"
         - "Status de Maquinas.xlsx"
         - "Taxa de Ocupação - Eleva Brasil.xlsx"
    2. Rode:  python3 build_dashboard.py
    3. O arquivo "dashboard_eleva.html" será regerado com os números novos,
       mantendo o mesmo layout.

Nada nas planilhas originais é alterado. Todos os cálculos ficam nesta camada.
"""
import json
import base64
import unicodedata
from pathlib import Path
from datetime import date
from zoneinfo import ZoneInfo

import pandas as pd

BASE = Path(__file__).parent
FUSO_BR = ZoneInfo("America/Sao_Paulo")
# Horário real da execução (para mostrar "Atualizado em" no painel e permitir
# conferir se o agendamento automático está rodando no horário certo) -
# sempre o relógio de verdade, nunca capado pelos dados.
AGORA_BR = pd.Timestamp.now(tz=FUSO_BR)

# "Hoje" é calculado dinamicamente a cada execução (nunca fixo), e limitado à
# última data realmente presente na planilha de Faturamento — assim, se a
# planilha ainda não tiver sido atualizada no dia da execução automática, o
# painel usa a data mais recente disponível nos dados em vez do relógio do
# sistema (evita "MTD" e "corte" enganosos apontando para um dia sem dado).
HOJE = pd.Timestamp.now().normalize()

FAT_FILE = BASE / "Faturamento Eleva Brasil.xlsx"
STATUS_FILE = BASE / "Status de Maquinas.xlsx"
OCC_FILE = BASE / "Taxa de Ocupação - Eleva Brasil.xlsx"
LOGO_FILE = BASE / "eleva_logo.png"
OUT_FILE = BASE / "dashboard_eleva.html"


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")


def brl(v, casas=0):
    s = f"{v:,.{casas}f}"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return "R$ " + s


def brl_m(v):
    return f"R$ {v/1_000_000:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".") + " M"


def pct(v, casas=1):
    s = f"{v:,.{casas}f}"
    return s.replace(".", ",") + "%"


# ---------------------------------------------------------------------------
# 1) CARGA DOS DADOS
#    LOC1_SOURCE=api (padrão): Frota/Ocupação vêm da API.
#    LOC1_SOURCE=xlsx: as 3 planilhas locais (comparação/depuração).
#    FATURAMENTO_SOURCE=manual (padrão por enquanto): Faturamento vem de
#    faturamento_manual.json (números já agregados, gerados localmente por
#    update_faturamento_manual.py a partir da planilha real - a planilha em
#    si nunca é lida aqui nem commitada). FATURAMENTO_SOURCE=xlsx le a
#    planilha direto (só funciona rodando localmente). FATURAMENTO_SOURCE=api
#    usa a API da LOC1 (ainda superestima - ver alerta).
# ---------------------------------------------------------------------------
import os

from faturamento_lib import compute_faturamento

quality_notes = []  # cada item: {icon, title, detail}
FONTE_DADOS = os.environ.get("LOC1_SOURCE", "api").lower()
FONTE_FATURAMENTO = os.environ.get("FATURAMENTO_SOURCE", "manual").lower()

if FONTE_DADOS == "api":
    from loc1_extract import get_client, get_status_df, get_occupancy_df

    _client = get_client()
    status = get_status_df(_client)
    occ = get_occupancy_df(status)
    quality_notes.append({
        "icon": "🟡",
        "title": "Frota e Ocupação conectadas via API da LOC1 (não mais planilha manual)",
        "detail": "Esta versão lê Status de Máquinas e Taxa de Ocupação direto da API da LOC1."
    })
else:
    status = pd.read_excel(STATUS_FILE)
    occ = pd.read_excel(OCC_FILE).dropna(subset=["Tipo do Modelo"])
    # A planilha .xlsx usa nomes de coluna abreviados mais antigos; o restante
    # do script já foi escrito para os nomes completos (iguais à query SQL).
    occ = occ.rename(columns={
        "T.Equipamentos": "Total de Equipamentos",
        "Disp.": "Disponível", "Contr.": "Em Contrato", "Manut.": "Em Manutenção",
        "Disp. (%)": "Taxa Disponível (%)", "Contr. (%)": "Taxa Em Contrato (%)", "Manut.(%)": "Taxa Manutenção (%)",
        "Rec. Disp.": "Receita Disponível", "Rec. Contr.": "Receita Em Contrato", "Rec. Manut.": "Receita Em Manutenção",
    })

# --- Faturamento: separado da Frota/Ocupação acima (fonte independente) ---
if FONTE_FATURAMENTO == "manual":
    with open(BASE / "faturamento_manual.json", encoding="utf-8") as f:
        FAT_BUNDLE = json.load(f)
    quality_notes.append({
        "icon": "🟡",
        "title": "Faturamento vem de planilha manual (modo híbrido)",
        "detail": "Frota e Taxa de Ocupação são atualizadas automaticamente pela API da LOC1. O Faturamento, "
                  "porém, vem de uma planilha enviada manualmente e processada à parte — a API não filtra notas "
                  "canceladas corretamente (ver histórico do projeto). Os valores de Faturamento só atualizam "
                  "quando uma planilha nova for enviada e reprocessada."
    })
elif FONTE_FATURAMENTO == "xlsx":
    FAT_BUNDLE = compute_faturamento(pd.read_excel(FAT_FILE), pd.Timestamp.now().normalize())
else:
    from loc1_extract import get_client as _get_client, get_faturamento_df
    _fclient = _get_client()
    fat_api = get_faturamento_df(_fclient, since=os.environ.get("LOC1_FATURAMENTO_DESDE", "2025-01-01"))
    FAT_BUNDLE = compute_faturamento(fat_api, pd.Timestamp.now().normalize())
    quality_notes.append({
        "icon": "🔴",
        "title": "FATURAMENTO SUPERESTIMADO — API não filtra notas canceladas",
        "detail": "A API da LOC1 não expõe o campo de cancelamento (\"CANCELED\") no endpoint de notas fiscais, então "
                  "os cards de Faturamento deste painel somam notas canceladas junto com as válidas. Validado com dados "
                  "reais: o valor mostrado fica superestimado em cerca de 30-40% acima do faturamento líquido real. "
                  "NÃO usar os números de Faturamento deste painel para decisão ou apresentação até esse campo ser "
                  "liberado pela LOC1 — os cards de Frota, Status de Máquinas e Taxa de Ocupação não são afetados "
                  "por esse problema."
    })

quality_notes.extend(FAT_BUNDLE["quality_notes"])
faturamento = FAT_BUNDLE["faturamento"]
serie_json = FAT_BUNDLE["serie_mensal"]
comparativo_anual = FAT_BUNDLE["comparativo_anual"]
alertas_faturamento = FAT_BUNDLE["alertas"]
HOJE = pd.Timestamp(FAT_BUNDLE["hoje_efetivo"])

# ---------------------------------------------------------------------------
# 2) QUALIDADE DOS DADOS - checagens adicionais (as de Faturamento já vieram
#    de FAT_BUNDLE["quality_notes"], calculadas em faturamento_lib.py)
# ---------------------------------------------------------------------------

# g) planilhas de Contas a Pagar / Compras ainda não fornecidas
quality_notes.append({
    "icon": "🔴",
    "title": "Contas a Pagar e Compras ainda não fornecidas",
    "detail": "O escopo do projeto prevê cards de Contas a Pagar e Compras. Como essas planilhas ainda não foram enviadas, "
              "esses indicadores não aparecem nesta versão — para não estimar valores sem base. Assim que os arquivos chegarem, "
              "os cards são adicionados sem alterar o restante do layout."
})

# h) sem histórico para comparar frota com período anterior
quality_notes.append({
    "icon": "🔴",
    "title": "Sem histórico para comparar a frota com período anterior",
    "detail": "Os dados de status de máquinas (Disponível/Em Contrato/Manutenção) são uma fotografia do momento atual (não têm "
              "data). Por isso, os cards de frota mostram a situação de agora, mas não uma variação \"vs. período anterior\" — "
              "isso exigiria salvar snapshots ao longo do tempo, o que passa a ser possível agora que a atualização é automática."
})

# ---------------------------------------------------------------------------
# 3) FROTA / MÁQUINAS  (Status de Maquinas.xlsx)
# ---------------------------------------------------------------------------
total_maquinas = len(status)
disp = int((status["Status"] == "Disponivel").sum())
contr = int((status["Status"] == "Em Contrato").sum())
manut = int((status["Status"] == "Em Manutenção").sum())

frota = {
    "total": total_maquinas,
    "disponivel": disp,
    "disponivel_pct": disp / total_maquinas * 100,
    "contrato": contr,
    "contrato_pct": contr / total_maquinas * 100,
    "manutencao": manut,
    "manutencao_pct": manut / total_maquinas * 100,
    "ocupacao_pct": contr / total_maquinas * 100,
}

# Disponibilidade por modelo (contagem status x modelo)
piv = status.pivot_table(index=["Modelo", "Tipo do Modelo"], columns="Status", values="Nº do item", aggfunc="count", fill_value=0)
for col in ["Disponivel", "Em Contrato", "Em Manutenção"]:
    if col not in piv.columns:
        piv[col] = 0
piv["Total"] = piv["Disponivel"] + piv["Em Contrato"] + piv["Em Manutenção"]
piv["Ocupacao_pct"] = piv["Em Contrato"] / piv["Total"] * 100
piv["Disponibilidade_pct"] = piv["Disponivel"] / piv["Total"] * 100
piv["Manutencao_pct"] = piv["Em Manutenção"] / piv["Total"] * 100
piv = piv.reset_index().sort_values("Total", ascending=False)

modelos_tabela = []
for _, r in piv.iterrows():
    modelos_tabela.append({
        "modelo": r["Modelo"],
        "tipo": r["Tipo do Modelo"],
        "disponivel": int(r["Disponivel"]),
        "contrato": int(r["Em Contrato"]),
        "manutencao": int(r["Em Manutenção"]),
        "total": int(r["Total"]),
        "ocupacao_pct": round(r["Ocupacao_pct"], 1),
        "disponibilidade_pct": round(r["Disponibilidade_pct"], 1),
        "manutencao_pct": round(r["Manutencao_pct"], 1),
    })

# ---------------------------------------------------------------------------
# 3b) EQUIPAMENTOS DISPONÍVEIS PARA LOCAÇÃO (lista individual, unidade a unidade)
# ---------------------------------------------------------------------------
# Diferente da tabela "Disponibilidade por Modelo" (que só soma quantidades),
# esta é a lista unidade a unidade de tudo que está com Status = "Disponivel"
# agora - o que a equipe comercial pode efetivamente oferecer para locação hoje.
# Não há campo de data/local nas planilhas fornecidas, então NÃO é possível
# calcular "há quantos dias está disponível" nem "localização" - isso é
# sinalizado no dashboard em vez de estimado.
disponiveis_df = status[status["Status"] == "Disponivel"].sort_values(["Tipo do Modelo", "Modelo", "Nº de série"])
equipamentos_disponiveis = []
for _, r in disponiveis_df.iterrows():
    equipamentos_disponiveis.append({
        "patrimonio": r["Nº do item"],
        "modelo": r["Modelo"],
        "tipo": r["Tipo do Modelo"],
        "serie": r["Nº de série"],
        "serie_fabricante": r["Nº de série do fabricante"],
    })

# ---------------------------------------------------------------------------
# 3c) VALOR DE AQUISIÇÃO / OCUPAÇÃO FINANCEIRA DA FROTA
#    Status/contagem vêm ao vivo da API (mesma fonte da Frota, seção 3);
#    o Valor de Compra vem de valor_aquisicao_mapping.csv (planilha "Ativo
#    Fixo" enviada manualmente, processada localmente por
#    update_ativo_fixo_manual.py - só tem código de equipamento e valor,
#    sem dado de cliente, por isso pode ficar no repositório público).
# ---------------------------------------------------------------------------
valores_af = pd.read_csv(BASE / "valor_aquisicao_mapping.csv", dtype={"Nº de série": str})
status_af = status.merge(valores_af, on="Nº de série", how="left")
status_af["Valor de Compra"] = status_af["Valor de Compra"].fillna(0.0)

sem_registro = status_af[status_af["Valor de Compra"] <= 0]

af_por_status = status_af.groupby("Status")["Valor de Compra"].agg(["count", "sum"])


def _af_status(nome):
    if nome in af_por_status.index:
        return int(af_por_status.loc[nome, "count"]), float(af_por_status.loc[nome, "sum"])
    return 0, 0.0

af_disp_n, af_disp_v = _af_status("Disponivel")
af_contr_n, af_contr_v = _af_status("Em Contrato")
af_manut_n, af_manut_v = _af_status("Em Manutenção")
af_total_n = len(status_af)
af_total_v = float(status_af["Valor de Compra"].sum())

ativo_fixo = {
    "gerado_em": AGORA_BR.strftime("%d/%m/%Y %H:%M"),
    "total_maquinas": af_total_n,
    "total_valor": af_total_v,
    "disponivel_n": af_disp_n, "disponivel_pct": af_disp_n / af_total_n * 100 if af_total_n else 0, "disponivel_v": af_disp_v,
    "contrato_n": af_contr_n, "contrato_pct": af_contr_n / af_total_n * 100 if af_total_n else 0, "contrato_v": af_contr_v,
    "manutencao_n": af_manut_n, "manutencao_pct": af_manut_n / af_total_n * 100 if af_total_n else 0, "manutencao_v": af_manut_v,
    "ocupacao_fisica_pct": af_contr_n / af_total_n * 100 if af_total_n else 0,
    "ocupacao_financeira_pct": af_contr_v / af_total_v * 100 if af_total_v else 0,
    "sem_registro_qtd": len(sem_registro),
    "sem_registro_pct": len(sem_registro) / af_total_n * 100 if af_total_n else 0,
    "sem_registro_lista": sorted(sem_registro["Nº de série"].tolist()),
}

af_piv = status_af.pivot_table(index="Tipo do Modelo", columns="Status", values="Nº do item", aggfunc="count", fill_value=0)
for col in ["Disponivel", "Em Contrato", "Em Manutenção"]:
    if col not in af_piv.columns:
        af_piv[col] = 0
af_valor_tipo = status_af.groupby("Tipo do Modelo")["Valor de Compra"].sum()
af_piv["Valor"] = af_valor_tipo
af_piv["Total"] = af_piv["Disponivel"] + af_piv["Em Contrato"] + af_piv["Em Manutenção"]
af_piv = af_piv.reset_index().sort_values("Total", ascending=False)

ativo_fixo_tipos = []
for _, r in af_piv.iterrows():
    ativo_fixo_tipos.append({
        "tipo": r["Tipo do Modelo"],
        "total": int(r["Total"]),
        "disponivel": int(r["Disponivel"]),
        "contrato": int(r["Em Contrato"]),
        "manutencao": int(r["Em Manutenção"]),
        "valor": float(r["Valor"]),
    })

# ---------------------------------------------------------------------------
# 3d) SAÚDE DA FROTA (por equipamento)
#    Cruza status ao vivo + Valor de Compra/Data de Compra (já unidos acima,
#    em status_af) com Faturamento e Despesas acumulados por equipamento -
#    planilha manual separada (faturamento_despesa_equipamento.csv, gerada
#    por update_faturamento_despesa_equipamento.py a partir da planilha
#    "Faturamento e Despesa por Equipamento" - só tem código de equipamento
#    e valores agregados, sem nome de cliente ou CNPJ, por isso pode ficar
#    no repositório público).
# ---------------------------------------------------------------------------
fd_equip = pd.read_csv(BASE / "faturamento_despesa_equipamento.csv", dtype={"Nº de série": str})
saude = status_af.merge(fd_equip, on="Nº de série", how="left")
saude["tem_registro_financeiro"] = saude["Faturamento Acumulado"].notna()
saude["Faturamento Acumulado"] = saude["Faturamento Acumulado"].fillna(0.0)
saude["Despesas Acumuladas"] = saude["Despesas Acumuladas"].fillna(0.0)
saude["Lucro Acumulado"] = saude["Faturamento Acumulado"] - saude["Despesas Acumuladas"]

data_compra = pd.to_datetime(saude["Data de Compra"], errors="coerce")
saude["Idade (anos)"] = (HOJE - data_compra).dt.days / 365.25


def _roi(row):
    return row["Lucro Acumulado"] / row["Valor de Compra"] * 100 if row["Valor de Compra"] > 0 else None


def _despesa_pct(row):
    return row["Despesas Acumuladas"] / row["Faturamento Acumulado"] * 100 if row["Faturamento Acumulado"] > 0 else None


saude["ROI (%)"] = saude.apply(_roi, axis=1)
saude["Despesa/Faturamento (%)"] = saude.apply(_despesa_pct, axis=1)
saude["recuperou_investimento"] = saude["Valor de Compra"].gt(0) & saude["Faturamento Acumulado"].ge(saude["Valor de Compra"])

fat_saude_total = float(saude["Faturamento Acumulado"].sum())
desp_saude_total = float(saude["Despesas Acumuladas"].sum())
lucro_saude_total = fat_saude_total - desp_saude_total
valor_compra_saude_total = float(saude["Valor de Compra"].sum())
com_valor_compra = saude[saude["Valor de Compra"] > 0]
sem_registro_fin = saude[~saude["tem_registro_financeiro"]]
despesa_alta = saude[(saude["Faturamento Acumulado"] > 0) & (saude["Despesa/Faturamento (%)"] >= 50)]
nao_recuperou = com_valor_compra[(~com_valor_compra["recuperou_investimento"]) & (com_valor_compra["Idade (anos)"] >= 3)]
# "nunca alugado" = nenhum faturamento acumulado registrado (nem 0 explícito, nem
# ausência na planilha) - é o maior sinal de capital parado por equipamento.
nunca_alugado = saude[saude["Faturamento Acumulado"] <= 0]

saude_frota = {
    "gerado_em": AGORA_BR.strftime("%d/%m/%Y %H:%M"),
    "total_equipamentos": len(saude),
    "valor_compra_total": valor_compra_saude_total,
    "faturamento_acumulado_total": fat_saude_total,
    "despesas_acumuladas_total": desp_saude_total,
    "lucro_acumulado_total": lucro_saude_total,
    "roi_medio_pct": (lucro_saude_total / valor_compra_saude_total * 100) if valor_compra_saude_total else 0.0,
    "pct_recuperou_investimento": (com_valor_compra["recuperou_investimento"].sum() / len(com_valor_compra) * 100) if len(com_valor_compra) else 0.0,
    "idade_media_anos": float(saude["Idade (anos)"].mean(skipna=True)) if saude["Idade (anos)"].notna().any() else None,
    "qtd_sem_registro_financeiro": int(len(sem_registro_fin)),
    "qtd_despesa_alta": int(len(despesa_alta)),
    "qtd_nao_recuperou": int(len(nao_recuperou)),
    "qtd_nunca_alugado": int(len(nunca_alugado)),
    "qtd_nunca_alugado_disponivel": int((nunca_alugado["Status"] == "Disponivel").sum()),
    "valor_nunca_alugado": float(nunca_alugado["Valor de Compra"].sum()),
}

# Buckets de idade da frota (histograma) - só equipamentos com data conhecida.
# Limites em "meio aberto" ([lo, hi)) pra não perder idades fracionárias (ex:
# 2,5 anos) que cairiam num buraco entre faixas com limites inteiros fechados.
_faixas_idade = [(0, 3, "0–2 anos"), (3, 6, "3–5 anos"), (6, 11, "6–10 anos"),
                  (11, 16, "11–15 anos"), (16, 21, "16–20 anos"), (21, float("inf"), "+20 anos")]
saude_idade_hist = []
idades_validas = saude["Idade (anos)"].dropna()
for lo, hi, label in _faixas_idade:
    qtd = int(((idades_validas >= lo) & (idades_validas < hi)).sum())
    saude_idade_hist.append({"faixa": label, "qtd": qtd})

# Lista para o alerta "nunca alugado" - maior valor de compra parado primeiro.
saude_nunca_alugado_lista = []
for _, r in nunca_alugado.sort_values("Valor de Compra", ascending=False).head(15).iterrows():
    saude_nunca_alugado_lista.append({
        "patrimonio": r["Nº de série"],
        "modelo": r["Modelo"],
        "tipo": r["Tipo do Modelo"],
        "status": r["Status"],
        "idade_anos": round(r["Idade (anos)"], 1) if pd.notna(r["Idade (anos)"]) else None,
        "valor_compra": float(r["Valor de Compra"]),
    })

saude_por_tipo_rows = []
for tipo, grupo in saude.groupby("Tipo do Modelo"):
    v_compra = float(grupo["Valor de Compra"].sum())
    fat = float(grupo["Faturamento Acumulado"].sum())
    desp = float(grupo["Despesas Acumuladas"].sum())
    lucro = fat - desp
    saude_por_tipo_rows.append({
        "tipo": tipo,
        "total": len(grupo),
        "valor_compra": v_compra,
        "faturamento": fat,
        "despesas": desp,
        "lucro": lucro,
        "roi_pct": (lucro / v_compra * 100) if v_compra else None,
    })
saude_por_tipo = sorted(saude_por_tipo_rows, key=lambda r: r["valor_compra"], reverse=True)

saude_tabela = []
for _, r in saude.sort_values("Lucro Acumulado", ascending=False).iterrows():
    saude_tabela.append({
        "patrimonio": r["Nº de série"],
        "modelo": r["Modelo"],
        "tipo": r["Tipo do Modelo"],
        "status": r["Status"],
        "idade_anos": round(r["Idade (anos)"], 1) if pd.notna(r["Idade (anos)"]) else None,
        "valor_compra": float(r["Valor de Compra"]),
        "faturamento": float(r["Faturamento Acumulado"]),
        "despesas": float(r["Despesas Acumuladas"]),
        "lucro": float(r["Lucro Acumulado"]),
        "roi_pct": round(r["ROI (%)"], 1) if pd.notna(r["ROI (%)"]) else None,
        "tem_registro_financeiro": bool(r["tem_registro_financeiro"]),
    })

if fat_saude_total > 0 and faturamento.get("ytd_liquido"):
    _diff_pct = abs(fat_saude_total - faturamento["ytd_liquido"]) / faturamento["ytd_liquido"] * 100
    if _diff_pct > 20:
        quality_notes.append({
            "icon": "🟡",
            "title": "Faturamento por Equipamento não bate com o Faturamento oficial",
            "detail": f"A soma do Faturamento Acumulado por equipamento na aba Saúde da Frota (R$ {fat_saude_total:,.2f}) "
                      f"é {_diff_pct:.0f}% diferente do Faturamento líquido oficial (YTD, R$ {faturamento['ytd_liquido']:,.2f}). "
                      "Combinado com a Eleva: os dois deveriam olhar o mesmo período - a diferença pode indicar um ajuste "
                      "necessário na query de origem dessa planilha. Tratar os números desta aba como direcionais até "
                      "essa diferença ser explicada."
        })

if saude_frota["qtd_sem_registro_financeiro"] > 0:
    quality_notes.append({
        "icon": "🟡",
        "title": "Equipamentos sem Faturamento/Despesa registrado",
        "detail": f"{saude_frota['qtd_sem_registro_financeiro']} de {saude_frota['total_equipamentos']} equipamentos não "
                  "aparecem na planilha de Faturamento e Despesa por Equipamento (entram na aba Saúde da Frota com "
                  "R$ 0,00 nesses campos, mas continuam contados normalmente na Frota e no Valor de Compra)."
    })

# ---------------------------------------------------------------------------
# 4) TAXA DE OCUPAÇÃO / RECEITA POR TIPO DO MODELO (Taxa de Ocupação...xlsx)
# ---------------------------------------------------------------------------
occ_sorted = occ.sort_values("Total de Equipamentos", ascending=False)
tipos_tabela = []
for _, r in occ_sorted.iterrows():
    tipos_tabela.append({
        "tipo": r["Tipo do Modelo"],
        "total": int(r["Total de Equipamentos"]),
        "disponivel": int(r["Disponível"]),
        "contrato": int(r["Em Contrato"]),
        "manutencao": int(r["Em Manutenção"]),
        "disp_pct": round(r["Taxa Disponível (%)"], 1),
        "contrato_pct": round(r["Taxa Em Contrato (%)"], 1),
        "manut_pct": round(r["Taxa Manutenção (%)"], 1),
        "receita_disponivel": float(r["Receita Disponível"]),
        "receita_contrato": float(r["Receita Em Contrato"]),
        "receita_manutencao": float(r["Receita Em Manutenção"]),
    })

receita_parada = float(occ["Receita Disponível"].sum())
receita_ativa = float(occ["Receita Em Contrato"].sum())
receita_perdida_manut = float(occ["Receita Em Manutenção"].sum())
receita_potencial_total = receita_parada + receita_ativa + receita_perdida_manut

potencial = {
    "receita_parada": receita_parada,
    "receita_ativa": receita_ativa,
    "receita_perdida_manut": receita_perdida_manut,
    "receita_potencial_total": receita_potencial_total,
    "pct_parada": receita_parada / receita_potencial_total * 100,
    "pct_ativa": receita_ativa / receita_potencial_total * 100,
    "pct_perdida_manut": receita_perdida_manut / receita_potencial_total * 100,
}

# ---------------------------------------------------------------------------
# 5) FATURAMENTO e 5b) COMPARATIVO ANUAL já vieram prontos de FAT_BUNDLE
#    (calculados em faturamento_lib.py, ver seção 1 acima).
# ---------------------------------------------------------------------------
ano_atual = HOJE.year

# ---------------------------------------------------------------------------
# 6) ALERTAS GERENCIAIS (derivados dos dados, sem inventar)
# ---------------------------------------------------------------------------
alertas = list(alertas_faturamento)

if frota["manutencao_pct"] >= 30:
    alertas.append({
        "nivel": "critical",
        "texto": f"{frota['manutencao']} máquinas em manutenção — {pct(frota['manutencao_pct'])} da frota parada, "
                 f"equivalente a {brl_m(potencial['receita_perdida_manut'])}/mês em receita potencial não capturada."
    })

if potencial["pct_parada"] >= 10:
    alertas.append({
        "nivel": "warning" if potencial["pct_parada"] < 20 else "critical",
        "texto": f"{frota['disponivel']} máquinas disponíveis sem contrato ({pct(frota['disponivel_pct'])} da frota) representam "
                 f"{brl_m(potencial['receita_parada'])}/mês de potencial de receita parado (capital ocioso)."
    })

# modelos com alta ocupação (oportunidade / demanda forte)
altos = [t for t in tipos_tabela if t["contrato_pct"] >= 60]
if altos:
    txt = ", ".join(f"{t['tipo']} ({pct(t['contrato_pct'])})" for t in altos)
    alertas.append({
        "nivel": "good",
        "texto": f"Tipos de equipamento com alta ocupação — possível oportunidade de ampliar frota: {txt}."
    })

if not alertas:
    alertas.append({"nivel": "good", "texto": "Nenhum ponto crítico identificado nos dados disponíveis nesta atualização."})

# ---------------------------------------------------------------------------
# 7) MONTAGEM DO PACOTE DE DADOS FINAL
# ---------------------------------------------------------------------------
data = {
    "gerado_em": AGORA_BR.strftime("%d/%m/%Y %H:%M"),
    "frota": frota,
    "modelos_tabela": modelos_tabela,
    "equipamentos_disponiveis": equipamentos_disponiveis,
    "tipos_tabela": tipos_tabela,
    "potencial": potencial,
    "ativo_fixo": ativo_fixo,
    "ativo_fixo_tipos": ativo_fixo_tipos,
    "saude_frota": saude_frota,
    "saude_por_tipo": saude_por_tipo,
    "saude_tabela": saude_tabela,
    "saude_idade_hist": saude_idade_hist,
    "saude_nunca_alugado_lista": saude_nunca_alugado_lista,
    "faturamento": faturamento,
    "serie_mensal": serie_json,
    "comparativo_anual": comparativo_anual,
    "alertas": alertas,
    "quality_notes": quality_notes,
}

with open(BASE / "dashboard_data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("dashboard_data.json gerado.")
print(json.dumps({k: v for k, v in data.items() if k in ("frota", "faturamento", "potencial")}, ensure_ascii=False, indent=2))
