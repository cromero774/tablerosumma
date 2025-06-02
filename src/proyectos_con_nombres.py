import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
import json

# --- Configuración
load_dotenv()
TEMPO_TOKEN = os.getenv("TEMPO_TOKEN")
JIRA_API_URL = os.getenv("JIRA_API_URL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")

# --- Funciones auxiliares
def get_jira_auth_headers():
    import base64
    auth_string = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}"
    return {
        "Authorization": f"Basic {base64.b64encode(auth_string.encode()).decode()}",
        "Accept": "application/json"
    }

def get_project_from_issue(issue_id):
    url = f"{JIRA_API_URL}/issue/{issue_id}"
    resp = requests.get(url, headers=get_jira_auth_headers())
    if resp.status_code == 200:
        data = resp.json()
        project = data.get("fields", {}).get("project", {})
        project_id = project.get("id")
        project_key = project.get("key")
        project_name = project.get("name")
        return project_id, project_key, project_name
    else:
        print(f"❌ Error buscando issue {issue_id}: {resp.status_code} - {resp.text}")
        return None, None, None

# --- Obtener todos los issues de Tempo en el rango de fechas
def get_tempo_worklogs(from_date, to_date, limit=1000):
    url = f"https://api.tempo.io/4/worklogs?from={from_date}&to={to_date}&limit={limit}"
    worklogs = []
    while url:
        response = requests.get(url, headers={"Authorization": f"Bearer {TEMPO_TOKEN}", "Accept": "application/json"})
        if response.status_code != 200:
            print("Error en la API Tempo:", response.text)
            break
        data = response.json()
        worklogs.extend(data.get("results", []))
        url = data.get("metadata", {}).get("next", None)
    return worklogs

if __name__ == "__main__":
    # Elegí el período a analizar
    hoy = datetime.now().date()
    tres_meses_atras = hoy - timedelta(days=90)
    fecha_inicio = tres_meses_atras.strftime("%Y-%m-%d")
    fecha_fin = hoy.strftime("%Y-%m-%d")

    # Paso 1: Traer todos los worklogs
    print("Consultando Tempo...")
    worklogs = get_tempo_worklogs(fecha_inicio, fecha_fin)
    print(f"Cantidad total de registros: {len(worklogs)}")

    # Paso 2: Obtener todos los issue IDs únicos
    issue_ids = set()
    for w in worklogs:
        issue = w.get("issue", {})
        issue_id = issue.get("id")
        if issue_id:
            issue_ids.add(issue_id)
    print(f"Issues únicos detectados: {len(issue_ids)}")

    # Paso 3: Consultar Jira por cada issue, guardar info del proyecto (evita repes)
    proyectos = dict()  # project_id : (project_key, project_name)
    issues_x_proyecto = dict()  # project_id: [issues]

    for idx, issue_id in enumerate(issue_ids):
        pid, pkey, pname = get_project_from_issue(issue_id)
        if pid and pid not in proyectos:
            proyectos[pid] = (pkey, pname)
            issues_x_proyecto[pid] = []
        if pid:
            issues_x_proyecto[pid].append(issue_id)
        print(f"[{idx+1}/{len(issue_ids)}] Issue {issue_id} => Proyecto: {pkey} - {pname} (ID: {pid})")
        time.sleep(0.2)  # para evitar rate limit

    # Paso 4: Mostrar todos los proyectos encontrados
    print("\n=== Proyectos únicos encontrados ===")
    for pid, (pkey, pname) in proyectos.items():
        print(f"Project Key: {pkey}\tNombre: {pname}\tID: {pid}\tIssues: {len(issues_x_proyecto[pid])}")

    # (Opcional) Guardar a archivo json/csv
    with open("proyectos_detectados.json", "w", encoding="utf-8") as f:
        json.dump({pid: {"key": k, "name": n, "issues": issues_x_proyecto[pid]} for pid, (k, n) in proyectos.items()}, f, ensure_ascii=False, indent=2)




