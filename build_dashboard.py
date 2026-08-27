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
    occ = pd.read_excel(OCC_FILE)
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
