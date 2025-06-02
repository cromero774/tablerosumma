import requests
import base64
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

class JiraAPI:
    def __init__(self):
        self.base_url = "https://evoltis.atlassian.net/rest/api/3/"
        auth = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode("utf-8")).decode("utf-8")
        self.headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json"
        }

    def _get_json(self, endpoint):
        url = self.base_url + endpoint if not endpoint.startswith("http") else endpoint
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"Error al consultar Jira: {response.status_code} - {response.text}")
        return response.json()

    def buscar_issues(self, jql, fields=None, max_results=50):
        params = {
            "jql": jql,
            "maxResults": max_results
        }
        if fields:
            params["fields"] = ",".join(fields)
        endpoint = "search"
        url = self.base_url + endpoint
        response = requests.get(url, headers=self.headers, params=params)
        if response.status_code != 200:
            raise Exception(f"Error al consultar Jira: {response.status_code} - {response.text}")
        return response.json()["issues"]

# Instancia global para importar directamente
jira = JiraAPI()



