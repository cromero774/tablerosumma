import pandas as pd
import os

# Siempre en la carpeta donde está este script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
hist_path = os.path.join(BASE_DIR, "../data/horas_historicas.csv")
actual_path = os.path.join(BASE_DIR, "../data/horas_con_proyecto.csv")

# Cargar el CSV histórico (o crear uno vacío si no existe)
if os.path.exists(hist_path):
    df_hist = pd.read_csv(hist_path)
else:
    df_hist = pd.DataFrame()

# Cargar el CSV nuevo (últimos 3 meses descargado de Tempo)
df_nuevo = pd.read_csv(actual_path)

# Unir ambos y eliminar duplicados (ahora usando también Issue si está)
subset_cols = ["Usuario", "Proyecto", "Fecha", "Horas"]
if "Issue" in df_nuevo.columns:
    subset_cols.append("Issue")

df_total = pd.concat([df_hist, df_nuevo]).drop_duplicates(
    subset=subset_cols, keep="last"
)

# Guardar el histórico actualizado
df_total.to_csv(hist_path, index=False, encoding="utf-8")
print("Histórico actualizado. Filas totales:", len(df_total))


