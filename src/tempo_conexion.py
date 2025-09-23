import os
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

TEMPO_TOKEN = os.getenv("TEMPO_TOKEN")
TEMPO_BASE_URL = "https://api.tempo.io/4"

HEADERS = {
    "Authorization": f"Bearer {TEMPO_TOKEN}",
    "Accept": "application/json"
}

def tempo_get(endpoint: str, params: Dict[str, Any] = None) -> Any:
    """Consulta genérica GET a la API de Tempo."""
    url = f"{TEMPO_BASE_URL}/{endpoint}"
    resp = requests.get(url, headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json()


def traer_worklogs(from_date: str, to_date: str, limit: int = 1000) -> List[Dict[str, Any]]:
    """Trae worklogs de Tempo en el rango de fechas dado."""
    worklogs = []
    url = f"{TEMPO_BASE_URL}/worklogs?from={from_date}&to={to_date}&limit={limit}"
    while url:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            print("Error en la API Tempo:", resp.text)
            break
        data = resp.json()
        worklogs.extend(data.get("results", []))
        url = data.get("metadata", {}).get("next", None)
    return worklogs

# Puedes agregar más funciones según necesidades (por ejemplo, para traer cuentas, proyectos, etc.)
