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
# 1) CARGA DOS DADOS - API da LOC1 por padrão; LOC1_SOURCE=xlsx volta a ler
#    as 3 planilhas locais (útil para comparação/depuração).
# ---------------------------------------------------------------------------
import os

quality_notes = []  # cada item: {icon, title, detail}
FONTE_DADOS = os.environ.get("LOC1_SOURCE", "api").lower()

if FONTE_DADOS == "api":
    from loc1_extract import get_client, get_status_df, get_occupancy_df, get_faturamento_df

    _client = get_client()
    status = get_status_df(_client)
    occ = get_occupancy_df(status)
    fat = get_faturamento_df(_client, since=os.environ.get("LOC1_FATURAMENTO_DESDE", "2025-01-01"))

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
    quality_notes.append({
        "icon": "🟡",
        "title": "Dados conectados via API da LOC1 (não mais planilha manual)",
        "detail": "Esta versão lê direto da API da LOC1 em vez das 3 planilhas .xlsx. Ressalva adicional: \"Desconto\" "
                  "e \"IRF\" ainda não vêm da API e aparecem como zero (\"Total Documento\" é aproximado como igual a "
                  "\"Total Faturado\"). \"Total Faturado\" e \"Data Faturamento\" por nota individual estão corretos "
                  "(validado nota a nota) — o problema é só a inclusão de notas canceladas, tratado no alerta acima."
    })
else:
    fat = pd.read_excel(FAT_FILE)
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

# ---------------------------------------------------------------------------
# 2) QUALIDADE DOS DADOS - checagens (antes de calcular os KPIs)
# ---------------------------------------------------------------------------
fat["Data Faturamento"] = pd.to_datetime(fat["Data Faturamento"])

# Nunca deixar "hoje" apontar para um dia à frente do último lançamento real
# (protege execuções automáticas contra planilha desatualizada / relógio adiantado).
HOJE = min(HOJE, fat["Data Faturamento"].max().normalize())

# a) lote de migração / abertura em 31/05/2024
migracao = fat[fat["Data Faturamento"] == pd.Timestamp("2024-05-31")]
if len(migracao) > 0:
    quality_notes.append({
        "icon": "🟡",
        "title": "Lote de abertura/migração em 31/05/2024",
        "detail": f"{len(migracao)} lançamentos de Faturamento estão todos datados em 31/05/2024 e sem o campo \"Tipo\" preenchido "
                  f"(total líquido de {brl(migracao['Total Faturado'].sum())}), consistente com uma carga inicial de saldos no SAP B1 e não com faturamento diário real. "
                  f"Para não distorcer a evolução mensal, este dia foi excluído do gráfico de evolução e das médias mensais (mantido apenas no acumulado geral da base)."
    })

# b) linhas sem Tipo preenchido (fora a migração)
sem_tipo = fat[fat["Tipo"].isna() & (fat["Data Faturamento"] != pd.Timestamp("2024-05-31"))]
if len(sem_tipo) > 0:
    quality_notes.append({
        "icon": "🟡",
        "title": "Documentos sem classificação de \"Tipo\"",
        "detail": f"{len(sem_tipo)} lançamentos de Faturamento (fora o lote de 31/05/2024) não têm o campo \"Tipo\" preenchido "
                  f"(ex.: Fatura, NFse Serviço, NF de débito). Foram mantidos no cálculo de faturamento líquido, mas recomendamos "
                  f"validar com o financeiro se representam estornos/ajustes manuais."
    })

# c) valores líquidos negativos (estornos)
negativos = fat[fat["Total Faturado"] < 0]
if len(negativos) > 0:
    quality_notes.append({
        "icon": "🟡",
        "title": "Lançamentos com Faturamento Líquido negativo",
        "detail": f"{len(negativos)} registros têm \"Total Faturado\" negativo, somando {brl(negativos['Total Faturado'].sum())} "
                  f"(prováveis estornos/notas de crédito). Estão incluídos nos totais líquidos apresentados."
    })

# d) inconsistência Documento - Desconto - IRF != Total Faturado
calc = fat["Total Documento"] - fat["Desconto"] - fat["IRF"]
mismatch = fat[(calc - fat["Total Faturado"]).abs() > 0.02]
if len(mismatch) > 0:
    quality_notes.append({
        "icon": "🟡",
        "title": "Diferença entre \"Total Documento - Desconto - IRF\" e \"Total Faturado\"",
        "detail": f"{len(mismatch)} registros ({len(mismatch)/len(fat)*100:.1f}% da base de Faturamento) têm essa conta divergente "
                  f"(inclui casos de \"Total Documento\" = 0 com \"Total Faturado\" preenchido). O painel usa sempre o campo "
                  f"\"Total Faturado\" (líquido) da própria planilha como fonte oficial, sem recalcular."
    })

# e) CNPJ/CPF ausente
sem_doc = fat["CNPJ/ CPF"].isna().sum()
if sem_doc > 0:
    quality_notes.append({
        "icon": "🟡",
        "title": "CNPJ/CPF não preenchido",
        "detail": f"{sem_doc} lançamentos de Faturamento não têm CNPJ/CPF do cliente preenchido. Não afeta os totais financeiros."
    })

# f) N NF duplicado
dup_nf = fat["N NF"].duplicated().sum()
if dup_nf > 0:
    quality_notes.append({
        "icon": "🟡",
        "title": "Número de NF repetido",
        "detail": f"{dup_nf} registros compartilham o mesmo \"N NF\" com outro lançamento. Pode ser normal (parcelas/itens da mesma nota) "
                  f"mas vale checagem pontual se for usado como chave única."
    })

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
# 5) FATURAMENTO (Faturamento Eleva Brasil.xlsx)
# ---------------------------------------------------------------------------
fat_sem_migracao = fat[fat["Data Faturamento"] != pd.Timestamp("2024-05-31")]


def liquido(mask_df):
    return float(mask_df["Total Faturado"].sum())


def bruto(mask_df):
    return float(mask_df["Total Documento"].sum())


ano_atual, mes_atual, dia_atual = HOJE.year, HOJE.month, HOJE.day

ytd_atual = fat[(fat["Data Faturamento"] >= pd.Timestamp(f"{ano_atual}-01-01")) & (fat["Data Faturamento"] <= HOJE)]
ytd_ant = fat[(fat["Data Faturamento"] >= pd.Timestamp(f"{ano_atual-1}-01-01")) & (fat["Data Faturamento"] <= HOJE.replace(year=ano_atual - 1))]

mtd_atual = fat[(fat["Data Faturamento"] >= pd.Timestamp(year=ano_atual, month=mes_atual, day=1)) & (fat["Data Faturamento"] <= HOJE)]
mtd_ant = fat[(fat["Data Faturamento"] >= pd.Timestamp(year=ano_atual - 1, month=mes_atual, day=1)) & (fat["Data Faturamento"] <= HOJE.replace(year=ano_atual - 1))]

mes_fechado_num = mes_atual - 1 if mes_atual > 1 else 12
mes_fechado_ano = ano_atual if mes_atual > 1 else ano_atual - 1
ini_fechado = pd.Timestamp(year=mes_fechado_ano, month=mes_fechado_num, day=1)
fim_fechado = (ini_fechado + pd.offsets.MonthEnd(0))
mes_fechado_atual = fat[(fat["Data Faturamento"] >= ini_fechado) & (fat["Data Faturamento"] <= fim_fechado)]
ini_fechado_ant = ini_fechado.replace(year=ini_fechado.year - 1)
fim_fechado_ant = (ini_fechado_ant + pd.offsets.MonthEnd(0))
mes_fechado_ant = fat[(fat["Data Faturamento"] >= ini_fechado_ant) & (fat["Data Faturamento"] <= fim_fechado_ant)]

liq_ytd_atual, liq_ytd_ant = liquido(ytd_atual), liquido(ytd_ant)
liq_mtd_atual, liq_mtd_ant = liquido(mtd_atual), liquido(mtd_ant)
liq_fechado_atual, liq_fechado_ant = liquido(mes_fechado_atual), liquido(mes_fechado_ant)

MESES_PT = ["", "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

faturamento = {
    "ytd_liquido": liq_ytd_atual,
    "ytd_liquido_ant": liq_ytd_ant,
    "ytd_var_pct": (liq_ytd_atual / liq_ytd_ant - 1) * 100 if liq_ytd_ant else None,
    "ytd_bruto": bruto(ytd_atual),
    "ytd_deducoes": bruto(ytd_atual) - liq_ytd_atual,
    "mtd_liquido": liq_mtd_atual,
    "mtd_liquido_ant": liq_mtd_ant,
    "mtd_var_pct": (liq_mtd_atual / liq_mtd_ant - 1) * 100 if liq_mtd_ant else None,
    "mes_fechado_label": f"{MESES_PT[mes_fechado_num]}/{str(mes_fechado_ano)[2:]}",
    "mes_fechado_liquido": liq_fechado_atual,
    "mes_fechado_liquido_ant": liq_fechado_ant,
    "mes_fechado_var_pct": (liq_fechado_atual / liq_fechado_ant - 1) * 100 if liq_fechado_ant else None,
    "corte_label": HOJE.strftime("%d/%m/%Y"),
}

# série mensal (líquido) - exclui o lote de migração de 31/05/2024
serie = fat_sem_migracao.copy()
serie["ym"] = serie["Data Faturamento"].dt.to_period("M")
serie_mensal = serie.groupby("ym")["Total Faturado"].sum().sort_index()
# manter só os últimos 24 meses com dado
serie_mensal = serie_mensal.tail(24)
serie_json = [{"mes": str(idx), "valor": float(v)} for idx, v in serie_mensal.items()]

# ---------------------------------------------------------------------------
# 5b) COMPARATIVO ANUAL - ANO ATUAL x ANO ANTERIOR, mês a mês
# ---------------------------------------------------------------------------
# Mesma base (fat_sem_migracao), agrupada por (ano, mês), para comparar
# "o momento atual" com "o mesmo momento do ano passado" - só até o mês
# corrente do ano atual (meses futuros não existem, não são zero).
serie_ano = fat_sem_migracao.copy()
serie_ano["ano_"] = serie_ano["Data Faturamento"].dt.year
serie_ano["mes_"] = serie_ano["Data Faturamento"].dt.month
por_mes = serie_ano.groupby(["ano_", "mes_"])["Total Faturado"].sum()

comparativo_meses = []
for m in range(1, 13):
    v_atual = float(por_mes.get((ano_atual, m), 0.0)) if m <= mes_atual else None
    v_ant = float(por_mes.get((ano_atual - 1, m), 0.0))
    comparativo_meses.append({
        "mes": m,
        "mes_label": MESES_PT[m],
        "atual": v_atual,
        "anterior": v_ant if (ano_atual - 1, m) in por_mes.index else None,
    })

total_ano_anterior_completo = float(por_mes.loc[ano_atual - 1].sum()) if (ano_atual - 1) in por_mes.index.get_level_values(0) else None
dias_decorridos_ano = (HOJE - pd.Timestamp(f"{ano_atual}-01-01")).days + 1
dias_no_ano = 366 if pd.Timestamp(f"{ano_atual}-12-31").is_leap_year else 365
projecao_fechamento_ano = liq_ytd_atual / dias_decorridos_ano * dias_no_ano

comparativo_anual = {
    "ano_atual": ano_atual,
    "ano_anterior": ano_atual - 1,
    "meses": comparativo_meses,
    "total_ano_anterior_completo": total_ano_anterior_completo,
    "ytd_atual": liq_ytd_atual,
    "ytd_anterior_mesmo_periodo": liq_ytd_ant,
    "projecao_fechamento_ano": projecao_fechamento_ano,
    "projecao_vs_ano_anterior_pct": (projecao_fechamento_ano / total_ano_anterior_completo - 1) * 100 if total_ano_anterior_completo else None,
}

# ---------------------------------------------------------------------------
# 6) ALERTAS GERENCIAIS (derivados dos dados, sem inventar)
# ---------------------------------------------------------------------------
alertas = []

if frota["manutencao_pct"] >= 30:
    alertas.append({
        "nivel": "critical",
        "texto": f"{frota['manutencao']} máquinas em manutenção — {pct(frota['manutencao_pct'])} da frota parada, "
                 f"equivalente a {brl_m(potencial['receita_perdida_manut'])}/mês em receita potencial não capturada."
    })

if faturamento["ytd_var_pct"] is not None and faturamento["ytd_var_pct"] <= -5:
    alertas.append({
        "nivel": "warning",
        "texto": f"Faturamento líquido acumulado no ano caiu {pct(abs(faturamento['ytd_var_pct']))} vs. mesmo período de {ano_atual-1} "
                 f"({brl_m(faturamento['ytd_liquido'])} vs {brl_m(faturamento['ytd_liquido_ant'])})."
    })

if faturamento["mes_fechado_var_pct"] is not None and faturamento["mes_fechado_var_pct"] <= -5:
    alertas.append({
        "nivel": "warning",
        "texto": f"Faturamento de {faturamento['mes_fechado_label']} fechou {pct(abs(faturamento['mes_fechado_var_pct']))} abaixo do mesmo mês do ano anterior."
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
