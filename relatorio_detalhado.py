import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from openpyxl import load_workbook
from resources import OUTPUT_FOLDER, OUTPUT_REPORT, TIMEFRAMES, START_YEAR, END_YEAR

# Mapeamento manual dos meses
MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
}

def gerar_relatorios_detalhados_por_cripto():
    os.makedirs(OUTPUT_REPORT, exist_ok=True)

    arquivos = glob.glob(os.path.join(OUTPUT_FOLDER, "*.xlsx"))

    for file in arquivos:
        cripto = os.path.basename(file).replace(".xlsx", "")
        pdf_path = os.path.join(OUTPUT_REPORT, f"{cripto}_detalhado.pdf")

        with PdfPages(pdf_path) as pdf:
            for ano in range(START_YEAR, END_YEAR + 1):
                for tf in TIMEFRAMES:
                    wb = load_workbook(file)
                    if tf not in wb.sheetnames:
                        continue

                    df = pd.read_excel(file, sheet_name=tf)
                    df["Data"] = pd.to_datetime(df["Data"])
                    df["Ano"] = df["Data"].dt.year
                    df["Mês"] = df["Data"].dt.month.map(MESES_PT)

                    df_ano = df[df["Ano"] == ano]

                    if df_ano.empty:
                        continue

                    colunas_desejadas = [
                        "Mês",
                        "Total Return [%]",
                        "Benchmark Return [%]",
                        "Total Trades",
                        "Total Closed Trades",
                        "Total Open Trades",
                        "Open Trade PnL"
                    ]

                    tabela = df_ano[colunas_desejadas].copy()

                    # Ordenar corretamente os meses
                    tabela["Mês"] = pd.Categorical(
                        tabela["Mês"],
                        categories=[
                            "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                            "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
                        ],
                        ordered=True
                    )
                    tabela.sort_values(by="Mês", inplace=True)

                    # Formatar colunas
                    tabela["Total Return [%]"] = tabela["Total Return [%]"].map(lambda x: f"{x:.2f}%")
                    tabela["Benchmark Return [%]"] = tabela["Benchmark Return [%]"].map(lambda x: f"{x:.2f}%")
                    tabela["Open Trade PnL"] = tabela["Open Trade PnL"].map(lambda x: f"{x:.2f}")
                    tabela["Total Trades"] = tabela["Total Trades"].astype(int)
                    tabela["Total Closed Trades"] = tabela["Total Closed Trades"].astype(int)
                    tabela["Total Open Trades"] = tabela["Total Open Trades"].astype(int)

                    # Gerar a tabela visual
                    fig, ax = plt.subplots(figsize=(10, 6))
                    ax.axis("off")
                    ax.axis("tight")
                    table_data = [tabela.columns.tolist()] + tabela.values.tolist()
                    tabela_plot = ax.table(cellText=table_data, colLabels=None, loc='center', cellLoc='center')
                    tabela_plot.scale(1.1, 1.3)
                    plt.title(f"{cripto} - {tf} - {ano}", fontsize=14)
                    plt.tight_layout()
                    pdf.savefig()
                    plt.close()

        print(f"📄 Relatório detalhado gerado: {pdf_path}")
