#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roda LOCALMENTE (nunca no GitHub Actions) com a planilha nota-a-nota de
Faturamento por Equipamento (tem nome/código de cliente - por isso NUNCA é
commitada nem processada em CI, igual à planilha de Faturamento geral).

Mantém uma base mestra local (faturamento_por_equipamento_master.csv, fora
do git) com o histórico completo, usando a mesma lógica de "janela de datas
substituída" do Faturamento geral (update_faturamento_manual.py) - a
planilha recebida é tratada como fonte de verdade para o intervalo de DATA
que ela cobre. A ideia é receber isso mensalmente, só com o mês atualizado.

Só o tipo "Fatura" conta como Faturamento por equipamento - mesma regra de
negócio do Faturamento geral, mas aplicada aqui porque esta planilha traz o
detalhe nota-a-nota (a antiga "Faturamento e Despesa por Equipamento.xlsx"
já vinha somada, sem essa discriminação, e por isso inflava o ROI por
equipamento com NFse Serviço/NF de débito misturados).

Gera faturamento_despesa_equipamento.csv: Nº de série -> Faturamento
Acumulado (recalculado aqui, só "Fatura") + Despesas Acumuladas (mantida da
planilha antiga - esta planilha nova só traz receita, não despesa).

Uso:
    python3 update_faturamento_por_equipamento.py "Faturamento por Equipamento - Setembro.xlsx"
"""
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
MASTER_FILE = BASE / "faturamento_por_equipamento_master.csv"
OUT_FILE = BASE / "faturamento_despesa_equipamento.csv"


def load_master() -> pd.DataFrame:
    if not MASTER_FILE.exists():
        return pd.DataFrame()
    df = pd.read_csv(MASTER_FILE)
    df["DATA"] = pd.to_datetime(df["DATA"])
    return df


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else BASE / "Faturamento por Equipamento.xlsx"
    novo = pd.read_excel(path)
    novo["DATA"] = pd.to_datetime(novo["DATA"])

    master = load_master()
    if len(master) > 0:
        antes = len(master)
        novo_min, novo_max = novo["DATA"].min(), novo["DATA"].max()
        # A planilha nova é a fonte de verdade pro intervalo [novo_min, novo_max] -
        # mesma lógica do Faturamento geral (tira da base tudo que tiver DATA
        # nesse intervalo e recoloca com o conteúdo da planilha nova).
        fora_da_janela = master[(master["DATA"] < novo_min) | (master["DATA"] > novo_max)]
        removidas_da_janela = len(master) - len(fora_da_janela)
        combinado = pd.concat([fora_da_janela, novo], ignore_index=True)
        combinado = combinado.drop_duplicates(keep="last")
        print(f"Janela {novo_min.date()} a {novo_max.date()}: {removidas_da_janela} linhas antigas substituídas por {len(novo)} da planilha nova.")
        print(f"Base mestra: {antes} linhas -> {len(combinado)} linhas ({len(combinado) - antes:+d}).")
        dados = combinado
    else:
        print(f"Nenhuma base mestra encontrada - usando esta planilha ({len(novo)} lançamentos) como base inicial.")
        dados = novo

    dados.to_csv(MASTER_FILE, index=False)

    # Só "Fatura" conta como Faturamento por equipamento.
    fatura = dados[dados["Tipo"] == "Fatura"]
    excluidos = dados[dados["Tipo"] != "Fatura"]
    fat_por_equip = fatura.groupby("AF")["VALOR"].sum().rename("Faturamento Acumulado")

    # Despesas ainda vêm da planilha antiga "Faturamento e Despesa por
    # Equipamento.xlsx" (processada antes por update_faturamento_despesa_equipamento.py) -
    # esta planilha nova só traz receita (TIPO = RECEITA em todas as linhas até agora).
    if OUT_FILE.exists():
        despesas = pd.read_csv(OUT_FILE, dtype={"Nº de série": str}).set_index("Nº de série")["Despesas Acumuladas"]
    else:
        despesas = pd.Series(dtype=float, name="Despesas Acumuladas")

    out = pd.DataFrame({"Faturamento Acumulado": fat_por_equip}).join(despesas, how="outer")
    out["Faturamento Acumulado"] = out["Faturamento Acumulado"].fillna(0.0)
    out["Despesas Acumuladas"] = out["Despesas Acumuladas"].fillna(0.0)
    out.index.name = "Nº de série"
    out = out.reset_index()[["Nº de série", "Faturamento Acumulado", "Despesas Acumuladas"]]

    out.to_csv(OUT_FILE, index=False)

    print(f"{OUT_FILE} gerado. {len(out)} equipamentos.")
    print(f"Faturamento acumulado total (só Fatura): R$ {out['Faturamento Acumulado'].sum():,.2f}")
    print(f"Excluídos por Tipo != Fatura: {len(excluidos)} lançamentos, R$ {excluidos['VALOR'].sum():,.2f} "
          f"({excluidos['Tipo'].value_counts().to_dict()})")


if __name__ == "__main__":
    main()
