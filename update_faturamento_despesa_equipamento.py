#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roda LOCALMENTE com a planilha "Faturamento e Despesa por Equipamento"
(traz só código de equipamento + valores agregados - sem nome de cliente ou
CNPJ, então é seguro publicar). Gera faturamento_despesa_equipamento.csv:
Nº de série (AF) -> Faturamento e Despesa acumulados, usados na aba Saúde
da Frota para calcular lucro e ROI por equipamento.

Uso:
    python3 update_faturamento_despesa_equipamento.py "Faturamento e Despesa por Equipamento.xlsx"
"""
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
OUT_FILE = BASE / "faturamento_despesa_equipamento.csv"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else BASE / "Faturamento e Despesa por Equipamento.xlsx"
    df = pd.read_excel(path)

    out = df.rename(columns={
        "Série_Equipamento": "Nº de série",
        "Valor_Faturamento": "Faturamento Acumulado",
        "Valor_Despesas": "Despesas Acumuladas",
    })[["Nº de série", "Faturamento Acumulado", "Despesas Acumuladas"]]
    out = out.drop_duplicates(subset=["Nº de série"])

    out.to_csv(OUT_FILE, index=False)

    print(f"{OUT_FILE} gerado. {len(out)} equipamentos.")
    print(f"Faturamento acumulado total: R$ {out['Faturamento Acumulado'].sum():,.2f}")
    print(f"Despesas acumuladas total: R$ {out['Despesas Acumuladas'].sum():,.2f}")


if __name__ == "__main__":
    main()
