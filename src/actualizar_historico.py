# -*- coding: utf-8 -*-
"""
actualizar_historico.py

Une el histórico con las nuevas horas traídas desde Tempo y aplica una
deduplicación fuerte para evitar dobles conteos (incluye un colapso por día).
"""

from pathlib import Path
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------
# Rutas (igual que venías usando: /src/actualizar_historico.py -> ../data)
# ---------------------------------------------------------------------
DATA_DIR = (Path(__file__).parent / "../data").resolve()
HIST_PATH = DATA_DIR / "horas_historicas.csv"
ACT_PATH  = DATA_DIR / "horas_con_proyecto.csv"

print(f"HIST: {HIST_PATH}")
print(f"ACT : {ACT_PATH}")

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
REPLACE_NULLS = {"", " ", "nan", "none", "null", None}

def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8", low_memory=False)
    # Normalizo nombres esperados
    for col in ["Usuario", "Fecha", "Mes", "Horas", "Issue", "Proyecto", "Cuenta", "IssueId", "TempoWorklogId"]:
        if col not in df.columns:
            df[col] = np.nan
    # Limpio strings "nulos"
    for col in ["IssueId", "TempoWorklogId", "Issue", "Proyecto", "Cuenta", "Usuario"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace(REPLACE_NULLS, np.nan)
    # Fecha -> datetime
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", utc=False)
    # Mes (si falta o hay nulos)
    nulos_mes = df["Mes"].isna() | (df["Mes"].astype(str).str.strip().isin(REPLACE_NULLS))
    if "Fecha" in df.columns:
        df.loc[nulos_mes, "Mes"] = df["Fecha"].dt.strftime("%B %Y")
    # Horas -> numérico
    df["Horas"] = pd.to_numeric(df["Horas"], errors="coerce").fillna(0.0)
    return df[["Usuario", "Fecha", "Mes", "Horas", "Issue", "Proyecto", "Cuenta", "IssueId", "TempoWorklogId"]]

# ---------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------
df_hist = _read_csv(HIST_PATH)
df_act  = _read_csv(ACT_PATH)

print(f"Filas histórico antes: {len(df_hist)}")
print(f"Filas nuevas a integrar: {len(df_act)}")

# Si no hay nuevas, solo ordeno/limpio el histórico y grabo
if df_act.empty and df_hist.empty:
    print("No hay datos. Nada para hacer.")
    raise SystemExit(0)

df_all = pd.concat([df_hist, df_act], ignore_index=True)
print(f"Filas combinadas antes de dedupe: {len(df_all)}")

# ---------------------------------------------------------------------
# 1) DEDUPE por identificadores (prioriza TempoWorklogId, luego firma compuesta)
# ---------------------------------------------------------------------
# normalizo 'nulos' de ids
for col in ["IssueId", "TempoWorklogId"]:
    if col in df_all.columns:
        df_all[col] = df_all[col].astype(str).str.strip()
        df_all[col] = df_all[col].replace(REPLACE_NULLS, np.nan)

# Dedup con TempoWorklogId si existe, luego por firma compuesta
if "TempoWorklogId" in df_all.columns:
    con_id = df_all["TempoWorklogId"].notna()

    # Con worklog id: dedup por ese id
    df_id = (
        df_all[con_id]
        .sort_values(["TempoWorklogId", "Fecha"])
        .drop_duplicates(subset=["TempoWorklogId"], keep="first")
    )

    # Sin worklog id: dedup por firma
    firma_cols = [c for c in ["IssueId", "Usuario", "Fecha", "Issue", "Proyecto", "Cuenta", "Horas"] if c in df_all.columns]
    df_noid = (
        df_all[~con_id]
        .drop_duplicates(subset=firma_cols, keep="first")
    )

    df_all = pd.concat([df_id, df_noid], ignore_index=True)
else:
    firma_cols = [c for c in ["IssueId", "Usuario", "Fecha", "Issue", "Proyecto", "Cuenta", "Horas"] if c in df_all.columns]
    df_all = df_all.drop_duplicates(subset=firma_cols, keep="first")

# ---------------------------------------------------------------------
# 2) DEDUPE fuerte por día (colapso por Usuario + Fecha + Horas)
#    Nos quedamos con la fila de mayor "calidad" (TempoWorklogId > IssueId > Issue)
#    Esto elimina duplicados gemelos que venían del histórico + nuevo.
# ---------------------------------------------------------------------
def _quality(row) -> int:
    if pd.notna(row.get("TempoWorklogId")): return 3
    if pd.notna(row.get("IssueId")):       return 2
    if pd.notna(row.get("Issue")):         return 1
    return 0

df_all["__quality__"] = df_all.apply(_quality, axis=1)

# Ordeno por calidad descendente y colapso por día
df_all = (
    df_all
    .sort_values(["Usuario", "Fecha", "Horas", "__quality__"], ascending=[True, True, True, False])
    .drop_duplicates(subset=["Usuario", "Fecha", "Horas"], keep="first")
    .drop(columns="__quality__", errors="ignore")
)

# ---------------------------------------------------------------------
# Recalculo Mes por las dudas, ordeno y grabo
# ---------------------------------------------------------------------
df_all["Mes"] = df_all["Fecha"].dt.strftime("%B %Y")
df_all = df_all.sort_values(["Fecha", "Usuario"]).reset_index(drop=True)
df_all.to_csv(HIST_PATH, index=False, encoding="utf-8")

print(f"Filas finales grabadas: {len(df_all)}")
print("Histórico actualizado (dedupe por worklog + colapso diario).")











