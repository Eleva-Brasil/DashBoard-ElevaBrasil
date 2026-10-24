#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roda LOCALMENTE com a planilha "Faturamento e Despesa por Equipamento"
(traz só código de equipamento + valores agregados - sem nome de cliente ou
CNPJ, então é seguro publicar). Gera faturamento_despesa_equipamento.csv,
usado SÓ na aba Saúde da Frota (faturamento, despesa, lucro e ROI por
equipamento) - não mexe no Faturamento geral (faturamento_manual.json).

Desde 23/10/2026 esta planilha é a fonte oficial dos dois valores, por
decisão do usuário: Valor_Faturamento soma todos os tipos de nota do
equipamento (Fatura + NFse Serviço etc.), que é o faturamento real dele -
a regra antiga "só Fatura" subestimava equipamentos faturados por NFse.
Equipamento que sumir da planilha nova mantém os valores que já tinha.

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
    for col in ("Valor_Faturamento", "Valor_Despesas"):
        df[col] = df[col].str.strip().str.replace(".", "", regex=False).str.replace(",", ".", regex=False).astype(float)
    return df


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "Faturamento e Despesa por Equipamento.xlsx"
    df = ler_planilha(path)

    novo = (
        df.rename(columns={
            "Série_Equipamento": "Nº de série",
            "Valor_Faturamento": "Faturamento Acumulado",
            "Valor_Despesas": "Despesas Acumuladas",
        })
        .drop_duplicates(subset=["Nº de série"])
        .set_index("Nº de série")[["Faturamento Acumulado", "Despesas Acumuladas"]]
        .astype(float)
    )

    atual = pd.read_csv(OUT_FILE, dtype={"Nº de série": str}).set_index("Nº de série")
    antes = atual.sum()

    # Equipamento que sumiu da planilha nova mantém os valores que já tinha.
    out = novo.combine_first(atual).fillna(0.0)
    out.index.name = "Nº de série"
    out = out.reset_index()[["Nº de série", "Faturamento Acumulado", "Despesas Acumuladas"]]

    out.to_csv(OUT_FILE, index=False)

    novos = sorted(set(novo.index) - set(atual.index))
    print(f"{OUT_FILE} atualizado. {len(out)} equipamentos ({len(novos)} novos: {', '.join(novos) or '-'}).")
    print(f"Faturamento acumulado total: R$ {antes['Faturamento Acumulado']:,.2f} -> R$ {out['Faturamento Acumulado'].sum():,.2f}")
    print(f"Despesas acumuladas total: R$ {antes['Despesas Acumuladas']:,.2f} -> R$ {out['Despesas Acumuladas'].sum():,.2f}")


if __name__ == "__main__":
    main()
