#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roda LOCALMENTE com a planilha real de Ativo Fixo (tem só código de
equipamento e valor - sem dado de cliente, então é seguro publicar).
Gera valor_aquisicao_mapping.csv: Nº do item + Nº de série -> Valor de Compra.

O status/contagem de máquinas continua vindo ao vivo da API (mesma fonte do
dashboard de Frota); esta planilha só acrescenta o valor de aquisição.

Uso:
    python3 update_ativo_fixo_manual.py "Ativo Fixo 27-08.xlsx"
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
    path = sys.argv[1] if len(sys.argv) > 1 else BASE / "Ativo Fixo.xlsx"
    df = pd.read_excel(path)

    out = df[["Nº do item", "AF", "Valor de Compra"]].rename(columns={"AF": "Nº de série"})
    out["Valor de Compra"] = out["Valor de Compra"].apply(parse_valor)
    out = out.drop_duplicates(subset=["Nº do item", "Nº de série"])

    out.to_csv(OUT_FILE, index=False)

    sem_valor = (out["Valor de Compra"] <= 0).sum()
    print(f"{OUT_FILE} gerado. {len(out)} equipamentos, {sem_valor} sem valor de compra registrado.")
    print(f"Valor total: R$ {out['Valor de Compra'].sum():,.2f}")


if __name__ == "__main__":
    main()
