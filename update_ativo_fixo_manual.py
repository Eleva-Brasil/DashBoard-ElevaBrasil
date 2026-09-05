#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roda LOCALMENTE com a planilha real de Ativo Fixo (tem só código de
equipamento, datas e valor - sem dado de cliente, então é seguro publicar).
Gera valor_aquisicao_mapping.csv: Nº de série (AF/patrimônio) -> Valor de
Compra + Data de Compra (usada para calcular idade de operação na aba Saúde
da Frota). Quando "Data de Compra" não vem preenchida, usa "Data de ano"
(ano de fabricação) como aproximação.

O status/contagem de máquinas continua vindo ao vivo da API (mesma fonte do
dashboard de Frota); esta planilha só acrescenta valor e data de aquisição.
O join com o status ao vivo é feito só por "Nº de série" (AF) - esta
planilha não traz "Nº do item" (ItemCode do SAP).

Uso:
    python3 update_ativo_fixo_manual.py "Ativo - Fixo - Eleva.xlsx"
"""
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
OUT_FILE = BASE / "valor_aquisicao_mapping.csv"


def parse_valor(v):
    """A planilha normalmente traz número puro (ex: 27360), mas algumas linhas
    vêm como texto tipo "R$ 538,572,50" (R$ + vírgula em vez de ponto nos
    milhares). Trata os dois casos: o último grupo separado por vírgula é
    sempre a parte decimal (centavos), o resto é a parte inteira."""
    if pd.isna(v):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("R$", "").replace(" ", "").strip()
    if "," in s:
        partes = s.split(",")
        s = "".join(partes[:-1]) + "." + partes[-1]
    try:
        return float(s)
    except ValueError:
        return 0.0


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else BASE / "Ativo - Fixo - Eleva.xlsx"
    df = pd.read_excel(path)

    out = df[["AF", "Valor de Compra"]].rename(columns={"AF": "Nº de série"})
    out["Valor de Compra"] = df["Valor de Compra"].apply(parse_valor)
    out["Data de Compra"] = df["Data de Compra"].fillna(df["Data de ano"])
    out["Data de Compra"] = pd.to_datetime(out["Data de Compra"]).dt.strftime("%Y-%m-%d")
    out = out.drop_duplicates(subset=["Nº de série"])

    out.to_csv(OUT_FILE, index=False)

    sem_valor = (out["Valor de Compra"] <= 0).sum()
    sem_data = out["Data de Compra"].isna().sum()
    print(f"{OUT_FILE} gerado. {len(out)} equipamentos, {sem_valor} sem valor de compra, {sem_data} sem data de compra/fabricação.")
    print(f"Valor total: R$ {out['Valor de Compra'].sum():,.2f}")


if __name__ == "__main__":
    main()
