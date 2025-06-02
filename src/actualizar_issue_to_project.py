import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
import json
import pandas as pd

# --- Configuración
load_dotenv()
TEMPO_TOKEN = os.getenv("TEMPO_TOKEN")
JIRA_API_URL = os.getenv("JIRA_API_URL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ISSUE_TO_PROJECT_FILE = os.path.join(BASE_DIR, "../data/issue_to_project.json")
HORAS_CON_PROYECTO_FILE = os.path.join(BASE_DIR, "../data/horas_con_proyecto.csv")


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
        project_name = project.get("name")
        return project_name
    else:
        print(f"❌ Error buscando issue {issue_id}: {resp.status_code} - {resp.text}")
        return None

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

def load_issue_to_project():
    if os.path.exists(ISSUE_TO_PROJECT_FILE):
        with open(ISSUE_TO_PROJECT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

def save_issue_to_project(mapping):
    with open(ISSUE_TO_PROJECT_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

def main():
    # --- Traer worklogs de los ÚLTIMOS 3 MESES ---
    hoy = datetime.now().date()
    tres_meses_atras = hoy - timedelta(days=90)
    fecha_inicio = tres_meses_atras.strftime("%Y-%m-%d")
    fecha_fin = hoy.strftime("%Y-%m-%d")
    print(f"Descargando worklogs de Tempo desde {fecha_inicio} hasta {fecha_fin}...")
    worklogs = get_tempo_worklogs(fecha_inicio, fecha_fin)
    print(f"Cantidad total de registros: {len(worklogs)}")
    issue_ids = set()
    for w in worklogs:
        issue = w.get("issue", {})
        issue_id = str(issue.get("id"))
        if issue_id:
            issue_ids.add(issue_id)
    print(f"Issues únicos detectados: {len(issue_ids)}")

    # --- Paso 2: Cargar el mapping local
    issue_to_project = load_issue_to_project()
    faltantes = [iid for iid in issue_ids if iid not in issue_to_project]
    print(f"Hay {len(faltantes)} issues nuevos a consultar en Jira...")

    # --- Paso 3: Consultar Jira solo por los faltantes
    for idx, issue_id in enumerate(faltantes):
        project_name = get_project_from_issue(issue_id)
        if project_name:
            issue_to_project[issue_id] = project_name
        else:
            issue_to_project[issue_id] = "Desconocido"
        print(f"[{idx+1}/{len(faltantes)}] Issue {issue_id} => Proyecto: {issue_to_project[issue_id]}")
        time.sleep(0.2)  # Evita rate limit

    # --- Paso 4: Guardar mapping actualizado
    save_issue_to_project(issue_to_project)
    print(f"\nMapping actualizado en '{ISSUE_TO_PROJECT_FILE}'.")

    # --- Generar un DataFrame de horas con nombre de proyecto
    print("\nGenerando DataFrame de resumen...")
    data = []
    for w in worklogs:
        usuario = w.get("author", {}).get("accountId", "SinUsuario")
        horas = w.get("timeSpentSeconds", 0) / 3600
        issue_id = str(w.get("issue", {}).get("id"))
        fecha = w.get("startDate")
        proyecto = issue_to_project.get(issue_id, "Desconocido")
        data.append({
            "Usuario": usuario,
            "Proyecto": proyecto,
            "Fecha": fecha,
            "Horas": horas,
        })
    df = pd.DataFrame(data)
    print("Primeras filas del resumen:")
    print(df.head())
    df.to_csv(HORAS_CON_PROYECTO_FILE, index=False, encoding="utf-8")
    print(f"Resumen guardado en '{HORAS_CON_PROYECTO_FILE}'.")

if __name__ == "__main__":
    main()




