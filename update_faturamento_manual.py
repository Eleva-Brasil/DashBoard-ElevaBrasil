#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roda LOCALMENTE (nunca no GitHub Actions) com a planilha de Faturamento.
Gera faturamento_manual.json contendo só os números agregados que o dashboard
precisa (totais do ano/mês, série mensal, comparativo anual) - sem nome de
cliente, CNPJ ou nota individual. Esse JSON é seguro para o repositório
público; a planilha em si e a base mestra NUNCA são commitadas.

Mantém uma base mestra local (faturamento_master.csv, fora do git) com o
histórico completo. A cada execução, a planilha recebida é tratada como
fonte de verdade para a JANELA DE DATAS que ela cobre (do min ao max de
"Data Faturamento" nela) - tudo que a base mestra tinha nesse intervalo é
substituído pelo conteúdo da planilha nova. Datas fora dessa janela na
base mestra não são tocadas. Isso evita tanto duplicar notas repetidas
quanto deixar "presa" pra sempre uma nota que foi cancelada e sumiu de
uma reexportação mais recente.

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
        novo_min, novo_max = novo["Data Faturamento"].min(), novo["Data Faturamento"].max()
        # A planilha nova é a fonte de verdade pro intervalo [novo_min, novo_max]:
        # tira da base tudo que tiver data nesse intervalo e recoloca com o
        # conteúdo da planilha nova (pega nota nova E derruba nota cancelada
        # que sumiu). Datas fora do intervalo ficam intocadas.
        fora_da_janela = master[(master["Data Faturamento"] < novo_min) | (master["Data Faturamento"] > novo_max)]
        removidas_da_janela = len(master) - len(fora_da_janela)
        combinado = pd.concat([fora_da_janela, novo], ignore_index=True)
        combinado = combinado.drop_duplicates(keep="last")
        delta = len(combinado) - antes
        print(f"Janela {novo_min.date()} a {novo_max.date()}: {removidas_da_janela} linhas antigas substituídas por {len(novo)} da planilha nova.")
        print(f"Base mestra: {antes} linhas -> {len(combinado)} linhas ({delta:+d}).")
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
