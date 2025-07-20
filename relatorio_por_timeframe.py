import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from openpyxl import load_workbook
from resources import OUTPUT_FOLDER, OUTPUT_REPORT, TIMEFRAMES, START_YEAR, END_YEAR

# Mapeamento manual dos meses para o eixo X
MESES_PT = {
    1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
    7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"
}

def gerar_relatorio_por_timeframe():
    os.makedirs(OUTPUT_REPORT, exist_ok=True)

    # Caminho do PDF
    pdf_path = os.path.join(OUTPUT_REPORT, "retorno_por_timeframe.pdf")

    with PdfPages(pdf_path) as pdf:
        # Para cada timeframe
        for tf in TIMEFRAMES:
            print(f"\n📊 Gerando gráficos para o período: {tf}")

            for file in glob.glob(os.path.join(OUTPUT_FOLDER, "*.xlsx")):
                cripto = os.path.basename(file).replace(".xlsx", "")
                wb = load_workbook(file)

                if tf not in wb.sheetnames:
                    continue

                df = pd.read_excel(file, sheet_name=tf)
                df["Data"] = pd.to_datetime(df["Data"])
                df["Ano"] = df["Data"].dt.year
                df["Mês"] = df["Data"].dt.month.map(MESES_PT)

                for ano in range(START_YEAR, END_YEAR + 1):
                    df_ano = df[df["Ano"] == ano]
                    if df_ano.empty:
                        continue

                    retorno_mes = df_ano.groupby("Mês")["Total Return [%]"].sum()
                    retorno_mes = retorno_mes.reindex(MESES_PT.values())

                    plt.figure(figsize=(10, 5))
                    retorno_mes.plot(kind="bar", color="mediumseagreen", edgecolor="black")
                    plt.title(f"{cripto} - {tf} - Retorno Mensal - {ano}")
                    plt.ylabel("Retorno [%]")
                    plt.xlabel("Mês")
                    plt.axhline(0, color='black', linewidth=0.8)
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    pdf.savefig()
                    plt.close()

    print(f"\n📄 Relatório PDF gerado com sucesso: {pdf_path}")
