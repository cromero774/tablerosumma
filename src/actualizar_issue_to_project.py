import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import time
import json
import pandas as pd
import base64

# --- Configuración
load_dotenv()
TEMPO_TOKEN = os.getenv("TEMPO_TOKEN")
JIRA_API_URL = os.getenv("JIRA_API_URL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "../data")
ISSUE_TO_PROJECT_FILE = os.path.join(DATA_DIR, "issue_to_project.json")
HORAS_CON_PROYECTO_FILE = os.path.join(DATA_DIR, "horas_con_proyecto.csv")
ACCOUNT_MAP_FILE = os.path.join(DATA_DIR, "accountid_to_name.json")

# ===== Helpers =====
def get_jira_auth_headers():
    auth_string = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}"
    return {
        "Authorization": f"Basic {base64.b64encode(auth_string.encode()).decode()}",
        "Accept": "application/json",
    }

def get_project_from_issue(issue_id):
    """Devuelve (project_key, project_name) para un issueId."""
    url = f"{JIRA_API_URL}/issue/{issue_id}"
    resp = requests.get(url, headers=get_jira_auth_headers(), timeout=60)
    if resp.status_code == 200:
        data = resp.json()
        proj = data.get("fields", {}).get("project", {}) or {}
        return (proj.get("key") or ""), (proj.get("name") or "")
    else:
        print(f"❌ Error buscando issue {issue_id}: {resp.status_code} - {resp.text}")
        return ("", "")

def get_jira_issue_key(issue_id, key_cache):
    """Devuelve issue key para un issueId (con caché en memoria)."""
    if issue_id in key_cache:
        return key_cache[issue_id]
    url = f"{JIRA_API_URL}/issue/{issue_id}"
    resp = requests.get(url, headers=get_jira_auth_headers(), timeout=60)
    if resp.status_code == 200:
        data = resp.json()
        key = data.get("key", "")
        key_cache[issue_id] = key
        return key
    else:
        print(f"❌ Error buscando KEY para issue {issue_id}: {resp.status_code} - {resp.text}")
        key_cache[issue_id] = ""
        return ""

def get_tempo_worklogs(date_from, date_to, limit=1000):
    """GET /4/worklogs paginado por metadata.next (sin 'worker' para evitar problemas de permisos)."""
    url = f"https://api.tempo.io/4/worklogs?from={date_from}&to={date_to}&limit={limit}"
    worklogs = []
    headers = {"Authorization": f"Bearer {TEMPO_TOKEN}", "Accept": "application/json"}
    while url:
        resp = requests.get(url, headers=headers, timeout=60)
        if resp.status_code != 200:
            print("Error en la API Tempo:", resp.text)
            break
        data = resp.json() or {}
        results = data.get("results", [])
        if isinstance(results, dict):
            results = [results]
        if not isinstance(results, list):
            results = []
        worklogs.extend(results)
        url = (data.get("metadata") or {}).get("next")
    return worklogs

def load_issue_to_project():
    if os.path.exists(ISSUE_TO_PROJECT_FILE):
        with open(ISSUE_TO_PROJECT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_issue_to_project(mapping):
    with open(ISSUE_TO_PROJECT_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

def extract_tempo_account(w):
    """Extrae el Tempo Account (id o key) desde attributes."""
    attrs = w.get("attributes")
    if isinstance(attrs, dict):
        for k, v in attrs.items():
            k_l = str(k).lower()
            if "account" in k_l:
                if isinstance(v, dict):
                    return str(v.get("id") or v.get("key") or "")
                return str(v)
    elif isinstance(attrs, list):
        for item in attrs:
            if not isinstance(item, dict):
                continue
            k = str(item.get("key") or "").lower()
            if "account" in k or "tempo:account" in k:
                val = item.get("value")
                if isinstance(val, dict):
                    return str(val.get("id") or val.get("key") or "")
                return str(val or "")
    return ""

def load_account_map():
    if os.path.exists(ACCOUNT_MAP_FILE):
        with open(ACCOUNT_MAP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# ===== MAIN =====
def main():
    # Ventana: desde 2025-06-01 (como tenías) hasta hoy
    fecha_inicio = "2025-06-01"
    fecha_fin = datetime.now().date().strftime("%Y-%m-%d")

    # Usuarios válidos (solo los que están en tu JSON)
    account_map = load_account_map()
    allowed_users = set(account_map.keys())

    print(f"Descargando worklogs de Tempo {fecha_inicio} → {fecha_fin}…")
    worklogs = get_tempo_worklogs(fecha_inicio, fecha_fin)
    print(f"Total worklogs (visibles): {len(worklogs)}")

    # Filtrar localmente por usuarios del JSON
    wlogs = [w for w in worklogs if (w.get("author") or {}).get("accountId") in allowed_users]
    print(f"Worklogs tras filtrar por usuarios del JSON: {len(wlogs)}")

    # 1) Recolectar issueIds
    issue_ids = set()
    for w in wlogs:
        issue = w.get("issue", {}) or {}
        issue_id = str(issue.get("id") or "")
        if issue_id:
            issue_ids.add(issue_id)
    print(f"Issues únicos detectados: {len(issue_ids)}")

    # 2) Cargar mapping local y consultar Jira solo por faltantes
    issue_to_project = load_issue_to_project()
    faltantes = [iid for iid in issue_ids if iid not in issue_to_project]
    print(f"Hay {len(faltantes)} issues nuevos a consultar en Jira...")

    for idx, issue_id in enumerate(faltantes, 1):
        proj_key, proj_name = get_project_from_issue(issue_id)
        issue_to_project[issue_id] = proj_key or proj_name or "Desconocido"
        print(f"[{idx}/{len(faltantes)}] IssueId {issue_id} => Proyecto: {issue_to_project[issue_id]}")
        time.sleep(0.2)  # evita rate limit

    save_issue_to_project(issue_to_project)
    print(f"Mapping actualizado en '{ISSUE_TO_PROJECT_FILE}'.")

    # 3) Armar CSV de salida
    key_cache = {}
    rows = []
    for w in wlogs:
        author = w.get("author") or {}
        usuario = author.get("accountId", "SinUsuario")
        horas = (w.get("timeSpentSeconds") or 0) / 3600.0
        issue = w.get("issue") or {}
        issue_id = str(issue.get("id") or "")
        issue_key = issue.get("key") or ""
        if not issue_key and issue_id:
            issue_key = get_jira_issue_key(issue_id, key_cache)
        fecha = w.get("startDate") or (w.get("dateStarted") or "")[:10]
        proyecto = issue_to_project.get(issue_id, "Desconocido")
        cuenta = extract_tempo_account(w)
        tempo_wid = str(w.get("id") or "")

        rows.append({
            "Usuario": usuario,
            "Proyecto": proyecto,           # KEY (REP/TAL/ATI)
            "Cuenta": cuenta,               # Tempo Account (para alertas de TEM no mapeada)
            "Fecha": fecha,
            "Horas": round(horas, 4),
            "Issue": issue_key,
            "IssueId": issue_id,
            "TempoWorklogId": tempo_wid
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.strftime("%Y-%m-%d")
        df["Horas"] = pd.to_numeric(df["Horas"], errors="coerce").fillna(0.0).round(4)

    print("Preview:")
    print(df.head())
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_csv(HORAS_CON_PROYECTO_FILE, index=False, encoding="utf-8")
    print(f"Resumen guardado en '{HORAS_CON_PROYECTO_FILE}'.")

if __name__ == "__main__":
    main()








