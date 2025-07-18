import pandas as pd
import os

# Rutas correctas a los archivos
hist_path = "data/horas_historicas.csv"
actual_path = "data/horas_con_proyecto.csv"

# Cargar histórico existente
if os.path.exists(hist_path):
    df_hist = pd.read_csv(hist_path)
else:
    df_hist = pd.DataFrame()

# Cargar nuevas horas (junio en adelante)
df_nuevo = pd.read_csv(actual_path)

# Unir ambos dataframes
df_total = pd.concat([df_hist, df_nuevo], ignore_index=True)

# Eliminar duplicados en base a estas columnas (ajustá si necesitas)
df_total = df_total.drop_duplicates(subset=["Usuario", "Fecha", "Proyecto", "Issue", "Horas"])

# Guardar el histórico actualizado sobrescribiendo el archivo original
df_total.to_csv(hist_path, index=False, encoding="utf-8")

print("Histórico actualizado sin duplicados.")





