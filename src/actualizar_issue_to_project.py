# -*- coding: utf-8 -*-
# src/actualizar_issue_to_project.py

import os
import base64
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
import pandas as pd
from dotenv import load_dotenv

# =============================
#  Carga de configuración (.env)
# =============================
ROOT = Path(__file__).resolve().parents[1]  # proyecto/
# Cargamos .env del root aunque se ejecute desde /src
load_dotenv(ROOT / ".env")
load_dotenv()  # por si ya estaba en el CWD

TEMPO_TOKEN    = os.getenv("TEMPO_TOKEN")
JIRA_EMAIL     = os.getenv("JIRA_EMAIL") or os.getenv("JIRA_USER")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN") or os.getenv("JIRA_TOKEN")

# Si no hay JIRA_API_URL, lo derivamos de JIRA_BASE_URL / JIRA_URL
_api = os.getenv("JIRA_API_URL")
if not _api:
    _base = os.getenv("JIRA_BASE_URL") or os.getenv("JIRA_URL") or ""
    if _base:
        _api = _base.rstrip("/") + "/rest/api/3"

# Normalización y validación
if _api and not _api.startswith("http"):
    _api = "https://" + _api.lstrip("/")
JIRA_API_URL = _api.rstrip("/") if _api else None

_missing = [k for k, v in {
    "TEMPO_TOKEN": TEMPO_TOKEN,
    "JIRA_EMAIL": JIRA_EMAIL,
    "JIRA_API_TOKEN": JIRA_API_TOKEN,
    "JIRA_API_URL": JIRA_API_URL,
}.items() if not v]
if _missing:
    raise SystemExit(
        "Variables faltantes para actualizar_issue_to_project:\n  - "
        + "\n  - ".join(_missing) +
        "\nTip: no toques tu .env; el script ya deriva JIRA_API_URL de JIRA_BASE_URL si hace falta."
    )

# ==============
#  Archivos I/O
# ==============
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ACCOUNT_MAP_FILE = DATA_DIR / "accountid_to_name.json"
ISSUE_TO_PROJECT = DATA_DIR / "issue_to_project.json"
HORAS_CON_PROYECTO_FILE = DATA_DIR / "horas_con_proyecto.csv"

# ===================
#  Helpers de Auth
# ===================
def jira_headers():
    basic = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
    return {"Authorization": f"Basic {basic}", "Accept": "application/json"}

def tempo_headers():
    return {"Authorization": f"Bearer {TEMPO_TOKEN}", "Accept": "application/json"}

# ==========================
#  Utilitarios JSON
# ==========================
def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default

def save_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

# ==========================
#  Tempo & Jira helpers
# ==========================
def fetch_tempo_worklogs(date_from: str, date_to: str, page_limit: int = 1000):
    """
    Descarga worklogs de Tempo (API v4) paginando hasta traer todo el rango.
    Retorna lista de dicts.
    """
    url = "https://api.tempo.io/4/worklogs"
    params = {"from": date_from, "to": date_to, "limit": page_limit, "offset": 0}
    out = []
    while True:
        resp = requests.get(url, headers=tempo_headers(), params=params, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"Tempo error {resp.status_code}: {resp.text}")
        data = resp.json()
        results = data.get("results", [])
        out.extend(results)
        if len(results) < page_limit:
            break
        params["offset"] += page_limit
        time.sleep(0.2)  # respiro
    return out

def jira_issue_project(issue_id_or_key: str):
    """
    Devuelve (proj_key, proj_name) para un issue (tolera id o key).
    """
    url = f"{JIRA_API_URL}/issue/{issue_id_or_key}"
    params = {"fields": "project"}
    resp = requests.get(url, headers=jira_headers(), params=params, timeout=60)
    if resp.status_code != 200:
        print(f"❌ Jira issue {issue_id_or_key}: {resp.status_code} - {resp.text[:200]}")
        return None, None
    data = resp.json()
    f = data.get("fields", {}) or {}
    proj = f.get("project") or {}
    return proj.get("key"), proj.get("name")

def get_jira_issue_key(issue_id_or_key: str, cache: dict) -> str:
    """
    Obtiene la KEY (REP-123, etc.) para un issue, con caché simple.
    """
    if not issue_id_or_key:
        return ""
    if issue_id_or_key in cache:
        return cache[issue_id_or_key]

    url = f"{JIRA_API_URL}/issue/{issue_id_or_key}"
    params = {"fields": "key"}  # respuesta liviana
    try:
        resp = requests.get(url, headers=jira_headers(), params=params, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            key = data.get("key") or ""
            cache[issue_id_or_key] = key
            return key
    except Exception:
        pass
    cache[issue_id_or_key] = ""
    return ""

def extract_tempo_account(worklog: dict) -> str:
    """
    Extrae la 'Cuenta' desde atributos de Tempo si viene cargada.
    Tolera formatos:
      - lista de dicts: [{"key":"tempo:account","value":{"key":"ATI"}}]
      - dict con 'values'/'attributes'/'attributeValues': {"values":[...]}
      - lista de strings: ["tempo:account=ATI", "account: Postventas", ...]
    Si no puede determinarla, devuelve "" (y luego se deriva por proyecto).
    """
    raw = worklog.get("attributes") or worklog.get("attributeValues") or []

    # Normalizamos a lista
    if isinstance(raw, dict):
        items = []
        for k in ("values", "attributes", "attributeValues"):
            v = raw.get(k)
            if isinstance(v, list):
                items.extend(v)
        attrs_list = items
    elif isinstance(raw, list):
        attrs_list = raw
    else:
        attrs_list = []

    # Caso 1: objetos {key, value}
    for a in attrs_list:
        if isinstance(a, dict):
            k = str(a.get("key") or a.get("name") or "").lower()
            if k in ("tempo:account", "account", "tempo_account", "tempoaccount", "tempo account", "tempo-account"):
                v = a.get("value")
                if isinstance(v, dict):
                    return v.get("key") or v.get("name") or ""
                if isinstance(v, str):
                    return v.strip()

    # Caso 2: strings "tempo:account=ATI" / "account: Postventas" / etc.
    for a in attrs_list:
        if isinstance(a, str):
            s = a.strip()
            low = s.lower()
            if "tempo:account" in low or low.startswith("account"):
                if "ati" in low:
                    return "ATI"
                if "postventa" in low or "postventas" in low:
                    return "Postventas"
                # Intento genérico: última palabra en mayúscula si parece clave
                parts = [p for p in s.replace("=", " ").replace(":", " ").split() if p]
                if parts:
                    cand = parts[-1].upper()
                    if cand in ("ATI", "REP", "TAL"):
                        return cand

    return ""

# ==========================
#  Normalización del mapping
# ==========================
def normalize_issue_to_project(mapping_raw):
    """
    Tolera formatos:
    - viejo: { "12345": "REP", "67890": "ATI", ... }
    - nuevo: { "12345": {"project_key":"REP","project_name":"Postventas"}, ... }
    Devuelve dict: {issue_id: "PROY"}
    """
    out = {}
    changed = False
    if not isinstance(mapping_raw, dict):
        return out, changed
    for k, v in mapping_raw.items():
        if isinstance(v, dict):
            proj_key = v.get("project_key") or v.get("key") or v.get("project")
            out[k] = proj_key
        elif isinstance(v, str) or v is None:
            out[k] = v if isinstance(v, str) else None
        else:
            out[k] = None
            changed = True
    return out, changed

# ==========================
#  Proceso principal
# ==========================
def main():
    # 1) Rango por defecto: ~108 días (como venías usando)
    hoy = datetime.today().date()
    df = hoy - timedelta(days=108)
    date_from = os.getenv("TEMPO_FROM") or df.isoformat()
    date_to   = os.getenv("TEMPO_TO") or hoy.isoformat()
    print(f"Descargando worklogs de Tempo {date_from} → {date_to}…")

    wlogs = fetch_tempo_worklogs(date_from, date_to)
    print(f"Total worklogs (visibles): {len(wlogs)}")

    # 2) Filtrado por usuarios permitidos (si existe el JSON)
    acc_map = load_json(ACCOUNT_MAP_FILE, {})
    allowed_ids = set(acc_map.keys())
    if allowed_ids:
        wlogs = [w for w in wlogs if str((w.get("author") or {}).get("accountId")) in allowed_ids]
    print(f"Worklogs tras filtrar por usuarios del JSON: {len(wlogs)}")

    # 2.1) Chequeo de duplicados por Tempo ID
    def _tempo_id(w):
        return str(w.get("tempoWorklogId") or w.get("id") or w.get("self") or "")
    tempo_ids = [_tempo_id(w) for w in wlogs]
    uniq_ids = {i for i in tempo_ids if i}
    dups_tempo = len([i for i in tempo_ids if i]) - len(uniq_ids)
    if dups_tempo > 0:
        print(f"⚠️ Duplicados por Tempo ID: {dups_tempo} (se mantienen como registros separados).")
    else:
        print("✅ No se detectaron duplicados por Tempo ID.")

    # 3) Juntar issues únicos
    issue_ids = []
    for w in wlogs:
        issue = w.get("issue") or {}
        iid = str(issue.get("id") or "") or str(issue.get("key") or "")
        if iid:
            issue_ids.append(iid)
    issue_ids = sorted(set(issue_ids))
    print(f"Issues únicos detectados: {len(issue_ids)}")

    # 4) Cargar mapping y normalizar
    mapping_raw = load_json(ISSUE_TO_PROJECT, {})
    issue_to_project, changed = normalize_issue_to_project(mapping_raw)
    if changed:
        print("ℹ️ Se detectó formato viejo/mixto en issue_to_project.json. Normalizando…")
        save_json(ISSUE_TO_PROJECT, issue_to_project)

    # 5) Completar proyectos faltantes consultando a Jira (por id o key)
    faltantes = [iid for iid in issue_ids if not issue_to_project.get(iid)]
    print(f"Hay {len(faltantes)} issues nuevos a consultar en Jira...")
    for iid in faltantes:
        proj_key, _proj_name = jira_issue_project(iid)
        if proj_key:
            issue_to_project[iid] = proj_key
        else:
            issue_to_project[iid] = None
        time.sleep(0.1)  # backoff

    # Guardamos mapping actualizado
    save_json(ISSUE_TO_PROJECT, issue_to_project)

    # 6) Armar CSV de salida (todas las columnas que usa tu histórico)
    key_cache = {}
    rows = []
    for w in wlogs:
        author = w.get("author") or {}
        usuario = author.get("accountId", "SinUsuario")

        secs = w.get("timeSpentSeconds")
        try:
            horas = float(secs) / 3600.0 if secs is not None else 0.0
        except Exception:
            horas = 0.0

        issue = w.get("issue") or {}
        issue_id = str(issue.get("id") or "")
        issue_key = issue.get("key") or ""
        if not issue_key and issue_id:
            issue_key = get_jira_issue_key(issue_id, key_cache)

        # Fecha (YYYY-MM-DD)
        fecha = w.get("startDate") or w.get("dateStarted") or ""
        if "T" in fecha:
            fecha = fecha.split("T", 1)[0]

        # Proyecto
        proyecto = issue_to_project.get(issue_id)
        if not proyecto and issue_key:
            proyecto = issue_to_project.get(issue_key)
        if not proyecto:
            proyecto = "Desconocido"

        # Cuenta (Tempo) o derivación por proyecto
        cuenta = extract_tempo_account(w) or (
            "ATI" if proyecto == "ATI"
            else "Postventas" if proyecto in ("REP", "TAL")
            else ""
        )

        tempo_wid = str(w.get("id") or w.get("tempoWorklogId") or "")

        rows.append({
            "Usuario": usuario,
            "Fecha": fecha,
            "Horas": round(horas, 4),
            "Proyecto": proyecto,
            "Issue": issue_key,
            "IssueId": issue_id,
            "TempoWorklogId": tempo_wid,
            "Cuenta": cuenta
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.strftime("%Y-%m-%d")
        df["Horas"] = pd.to_numeric(df["Horas"], errors="coerce").fillna(0.0).round(4)

    # 6.1) Chequeo de posibles duplicados (informativo)
    if not df.empty:
        dup_mask = df.duplicated(subset=["Usuario", "Fecha", "Proyecto", "IssueId", "TempoWorklogId"], keep=False)
        dup_count = int(dup_mask.sum())
        if dup_count > 0:
            print(f"⚠️ Posibles duplicados en filas a exportar (Usuario/Fecha/Proyecto/IssueId/TempoWorklogId): {dup_count}")
        else:
            print("✅ No se detectaron posibles duplicados en filas a exportar.")

    # 7) Guardar CSV final en el orden exacto que consume el histórico
    os.makedirs(DATA_DIR, exist_ok=True)
    cols = ["Usuario", "Fecha", "Horas", "Proyecto", "Issue", "IssueId", "TempoWorklogId", "Cuenta"]
    df = df.reindex(columns=cols)
    df.to_csv(HORAS_CON_PROYECTO_FILE, index=False, encoding="utf-8")
    print(f"Resumen guardado en '{HORAS_CON_PROYECTO_FILE}'.")
    print("Preview:")
    print(df.head())

if __name__ == "__main__":
    main()














