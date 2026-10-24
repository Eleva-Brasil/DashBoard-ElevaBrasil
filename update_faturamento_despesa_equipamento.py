#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roda LOCALMENTE com a planilha "Faturamento e Despesa por Equipamento"
(traz só código de equipamento + valores agregados - sem nome de cliente ou
CNPJ, então é seguro publicar). Atualiza faturamento_despesa_equipamento.csv,
usado na aba Saúde da Frota para calcular lucro e ROI por equipamento.

Hoje esta planilha só vale para DESPESAS: a coluna Valor_Faturamento dela
soma todos os tipos de nota (Fatura, NFse Serviço, ...), mas o Faturamento
por equipamento conta só "Fatura" e vem de update_faturamento_por_equipamento.py.
Por isso o Faturamento Acumulado já gravado no CSV é mantido; daqui só entra
Despesas Acumuladas. Equipamento novo (ainda sem faturamento "Fatura") entra
com Faturamento Acumulado = 0.

Aceita .xlsx ou texto separado por TAB (colado do Excel, números no
formato brasileiro "1.234,56").

Uso:
    python3 update_faturamento_despesa_equipamento.py "Faturamento e Despesa por Equipamento.xlsx"
"""
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
OUT_FILE = BASE / "faturamento_despesa_equipamento.csv"


def ler_planilha(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    df = pd.read_csv(path, sep="\t", dtype=str)
    df["Valor_Despesas"] = (
        df["Valor_Despesas"].str.strip().str.replace(".", "", regex=False).str.replace(",", ".", regex=False).astype(float)
    )
    return df


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "Faturamento e Despesa por Equipamento.xlsx"
    df = ler_planilha(path)

    despesas = (
        df.rename(columns={"Série_Equipamento": "Nº de série", "Valor_Despesas": "Despesas Acumuladas"})
        .drop_duplicates(subset=["Nº de série"])
        .set_index("Nº de série")["Despesas Acumuladas"]
        .astype(float)
    )

    atual = pd.read_csv(OUT_FILE, dtype={"Nº de série": str}).set_index("Nº de série")
    antes = atual["Despesas Acumuladas"].sum()

    out = atual[["Faturamento Acumulado"]].join(despesas, how="outer")
    out["Faturamento Acumulado"] = out["Faturamento Acumulado"].fillna(0.0)
    # Equipamento que sumiu da planilha nova mantém a despesa que já tinha.
    out["Despesas Acumuladas"] = out["Despesas Acumuladas"].fillna(atual["Despesas Acumuladas"]).fillna(0.0)
    out.index.name = "Nº de série"
    out = out.reset_index()[["Nº de série", "Faturamento Acumulado", "Despesas Acumuladas"]]

    out.to_csv(OUT_FILE, index=False)

    novos = sorted(set(despesas.index) - set(atual.index))
    print(f"{OUT_FILE} atualizado. {len(out)} equipamentos ({len(novos)} novos: {', '.join(novos) or '-'}).")
    print(f"Despesas acumuladas total: R$ {antes:,.2f} -> R$ {out['Despesas Acumuladas'].sum():,.2f}")
    print(f"Faturamento acumulado (só Fatura, mantido): R$ {out['Faturamento Acumulado'].sum():,.2f}")


if __name__ == "__main__":
    main()
