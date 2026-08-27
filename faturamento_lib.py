#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lógica de cálculo do Faturamento, compartilhada entre:
- build_dashboard.py (quando lê a planilha/API diretamente)
- update_faturamento_manual.py (rodado localmente com a planilha real,
  gera faturamento_manual.json com só os números agregados - sem nome de
  cliente, CNPJ ou nota individual - seguro para ir no repositório público)
"""
import pandas as pd

MESES_PT = ["", "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def brl(v, casas=0):
    s = f"{v:,.{casas}f}"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return "R$ " + s


def compute_faturamento(fat: pd.DataFrame, hoje: pd.Timestamp):
    """Recebe o DataFrame bruto de Faturamento (nota a nota) + a data de corte
    desejada, e devolve tudo que o dashboard precisa, já agregado:
    quality_notes, faturamento (cards), serie_mensal (grafico), comparativo_anual,
    alertas (só os 2 derivados de faturamento) e hoje_efetivo (capado à ultima
    data com dado real)."""
    fat = fat.copy()
    fat["Data Faturamento"] = pd.to_datetime(fat["Data Faturamento"])

    hoje = min(hoje, fat["Data Faturamento"].max().normalize())

    quality_notes = []

    migracao = fat[fat["Data Faturamento"] == pd.Timestamp("2024-05-31")]
    if len(migracao) > 0:
        quality_notes.append({
            "icon": "🟡",
            "title": "Lote de abertura/migração em 31/05/2024",
            "detail": f"{len(migracao)} lançamentos de Faturamento estão todos datados em 31/05/2024 e sem o campo \"Tipo\" preenchido "
                      f"(total líquido de {brl(migracao['Total Faturado'].sum())}), consistente com uma carga inicial de saldos no SAP B1 e não com faturamento diário real. "
                      f"Para não distorcer a evolução mensal, este dia foi excluído do gráfico de evolução e das médias mensais (mantido apenas no acumulado geral da base)."
        })

    sem_tipo = fat[fat["Tipo"].isna() & (fat["Data Faturamento"] != pd.Timestamp("2024-05-31"))]
    if len(sem_tipo) > 0:
        quality_notes.append({
            "icon": "🟡",
            "title": "Documentos sem classificação de \"Tipo\"",
            "detail": f"{len(sem_tipo)} lançamentos de Faturamento (fora o lote de 31/05/2024) não têm o campo \"Tipo\" preenchido "
                      f"(ex.: Fatura, NFse Serviço, NF de débito). Foram mantidos no cálculo de faturamento líquido, mas recomendamos "
                      f"validar com o financeiro se representam estornos/ajustes manuais."
        })

    negativos = fat[fat["Total Faturado"] < 0]
    if len(negativos) > 0:
        quality_notes.append({
            "icon": "🟡",
            "title": "Lançamentos com Faturamento Líquido negativo",
            "detail": f"{len(negativos)} registros têm \"Total Faturado\" negativo, somando {brl(negativos['Total Faturado'].sum())} "
                      f"(prováveis estornos/notas de crédito). Estão incluídos nos totais líquidos apresentados."
        })

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

    sem_doc = fat["CNPJ/ CPF"].isna().sum()
    if sem_doc > 0:
        quality_notes.append({
            "icon": "🟡",
            "title": "CNPJ/CPF não preenchido",
            "detail": f"{sem_doc} lançamentos de Faturamento não têm CNPJ/CPF do cliente preenchido. Não afeta os totais financeiros."
        })

    dup_nf = fat["N NF"].duplicated().sum()
    if dup_nf > 0:
        quality_notes.append({
            "icon": "🟡",
            "title": "Número de NF repetido",
            "detail": f"{dup_nf} registros compartilham o mesmo \"N NF\" com outro lançamento. Pode ser normal (parcelas/itens da mesma nota) "
                      f"mas vale checagem pontual se for usado como chave única."
        })

    fat_sem_migracao = fat[fat["Data Faturamento"] != pd.Timestamp("2024-05-31")]

    def liquido(df):
        return float(df["Total Faturado"].sum())

    def bruto(df):
        return float(df["Total Documento"].sum())

    ano_atual, mes_atual = hoje.year, hoje.month

    ytd_atual = fat[(fat["Data Faturamento"] >= pd.Timestamp(f"{ano_atual}-01-01")) & (fat["Data Faturamento"] <= hoje)]
    ytd_ant = fat[(fat["Data Faturamento"] >= pd.Timestamp(f"{ano_atual-1}-01-01")) & (fat["Data Faturamento"] <= hoje.replace(year=ano_atual - 1))]

    mtd_atual = fat[(fat["Data Faturamento"] >= pd.Timestamp(year=ano_atual, month=mes_atual, day=1)) & (fat["Data Faturamento"] <= hoje)]
    mtd_ant = fat[(fat["Data Faturamento"] >= pd.Timestamp(year=ano_atual - 1, month=mes_atual, day=1)) & (fat["Data Faturamento"] <= hoje.replace(year=ano_atual - 1))]

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
        "corte_label": hoje.strftime("%d/%m/%Y"),
    }

    serie = fat_sem_migracao.copy()
    serie["ym"] = serie["Data Faturamento"].dt.to_period("M")
    serie_mensal = serie.groupby("ym")["Total Faturado"].sum().sort_index().tail(24)
    serie_json = [{"mes": str(idx), "valor": float(v)} for idx, v in serie_mensal.items()]

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
    dias_decorridos_ano = (hoje - pd.Timestamp(f"{ano_atual}-01-01")).days + 1
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

    alertas = []
    if faturamento["ytd_var_pct"] is not None and faturamento["ytd_var_pct"] <= -5:
        alertas.append({
            "nivel": "warning",
            "texto": f"Faturamento líquido acumulado no ano caiu {abs(faturamento['ytd_var_pct']):.1f}% vs. mesmo período de {ano_atual-1} "
                     f"({brl(faturamento['ytd_liquido'])} vs {brl(faturamento['ytd_liquido_ant'])})."
        })
    if faturamento["mes_fechado_var_pct"] is not None and faturamento["mes_fechado_var_pct"] <= -5:
        alertas.append({
            "nivel": "warning",
            "texto": f"Faturamento de {faturamento['mes_fechado_label']} fechou {abs(faturamento['mes_fechado_var_pct']):.1f}% abaixo do mesmo mês do ano anterior."
        })

    return {
        "hoje_efetivo": hoje.strftime("%Y-%m-%d"),
        "quality_notes": quality_notes,
        "faturamento": faturamento,
        "serie_mensal": serie_json,
        "comparativo_anual": comparativo_anual,
        "alertas": alertas,
    }
