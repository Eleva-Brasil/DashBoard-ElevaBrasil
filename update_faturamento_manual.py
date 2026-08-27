#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roda LOCALMENTE (nunca no GitHub Actions) com a planilha real de Faturamento.
Gera faturamento_manual.json contendo só os números agregados que o dashboard
precisa (totais do ano/mês, série mensal, comparativo anual) - sem nome de
cliente, CNPJ ou nota individual. Esse JSON é seguro para o repositório
público; a planilha em si nunca é commitada.

Uso:
    python3 update_faturamento_manual.py "Faturamento Eleva Brasil.xlsx"
"""
import json
import sys
from pathlib import Path

import pandas as pd

from faturamento_lib import compute_faturamento

BASE = Path(__file__).parent
OUT_FILE = BASE / "faturamento_manual.json"


def main():
    fat_path = sys.argv[1] if len(sys.argv) > 1 else BASE / "Faturamento Eleva Brasil.xlsx"
    fat = pd.read_excel(fat_path)
    hoje = pd.Timestamp.now().normalize()

    resultado = compute_faturamento(fat, hoje)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"{OUT_FILE} gerado.")
    print(f"YTD líquido: R$ {resultado['faturamento']['ytd_liquido']:,.2f}")
    print(f"Mês fechado ({resultado['faturamento']['mes_fechado_label']}): R$ {resultado['faturamento']['mes_fechado_liquido']:,.2f}")


if __name__ == "__main__":
    main()
