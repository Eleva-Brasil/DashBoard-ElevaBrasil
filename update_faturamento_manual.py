#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roda LOCALMENTE (nunca no GitHub Actions) com a planilha de Faturamento.
Gera faturamento_manual.json contendo só os números agregados que o dashboard
precisa (totais do ano/mês, série mensal, comparativo anual) - sem nome de
cliente, CNPJ ou nota individual. Esse JSON é seguro para o repositório
público; a planilha em si e a base mestra NUNCA são commitadas.

Mantém uma base mestra local (faturamento_master.csv, fora do git) com o
histórico completo. A cada execução, MESCLA a planilha recebida com essa
base (por "Nº interno", a nota mais recente vence em caso de repetição) -
então a partir de agora dá pra mandar só a planilha do mês, sem perder o
histórico anterior nem duplicar notas repetidas.

Uso:
    python3 update_faturamento_manual.py "Faturamento Eleva Brasil - mes.xlsx"
"""
import json
import sys
from pathlib import Path

import pandas as pd

from faturamento_lib import compute_faturamento

BASE = Path(__file__).parent
OUT_FILE = BASE / "faturamento_manual.json"
MASTER_FILE = BASE / "faturamento_master.csv"


def load_master() -> pd.DataFrame:
    if not MASTER_FILE.exists():
        return pd.DataFrame()
    df = pd.read_csv(MASTER_FILE)
    df["Data Faturamento"] = pd.to_datetime(df["Data Faturamento"])
    return df


def save_master(df: pd.DataFrame):
    df.to_csv(MASTER_FILE, index=False)


def main():
    fat_path = sys.argv[1] if len(sys.argv) > 1 else BASE / "Faturamento Eleva Brasil.xlsx"
    novo = pd.read_excel(fat_path)
    novo["Data Faturamento"] = pd.to_datetime(novo["Data Faturamento"])

    master = load_master()
    if len(master) > 0:
        antes = len(master)
        combinado = pd.concat([master, novo], ignore_index=True)
        # "Nº interno" NÃO é único (uma nota pode ter mais de uma linha com
        # itens/valores diferentes) - dedup pela linha inteira, que só remove
        # repetição exata (ex: mesma nota reenviada num arquivo com intervalo
        # sobreposto), preservando linhas legítimas que só compartilham o
        # mesmo "Nº interno".
        combinado = combinado.drop_duplicates(keep="last")
        novas_notas = len(combinado) - antes
        print(f"Base mestra: {antes} linhas -> {len(combinado)} linhas ({novas_notas:+d}).")
        fat = combinado
    else:
        print(f"Nenhuma base mestra encontrada - usando esta planilha ({len(novo)} notas) como base inicial.")
        fat = novo

    save_master(fat)

    hoje = pd.Timestamp.now().normalize()
    resultado = compute_faturamento(fat, hoje)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"{OUT_FILE} gerado.")
    print(f"YTD líquido: R$ {resultado['faturamento']['ytd_liquido']:,.2f}")
    print(f"Mês fechado ({resultado['faturamento']['mes_fechado_label']}): R$ {resultado['faturamento']['mes_fechado_liquido']:,.2f}")


if __name__ == "__main__":
    main()
