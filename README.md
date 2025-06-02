# Tablero Automático con Jira y Tempo

## Requisitos

- Python 3.8+
- Acceso a Jira y Tempo con API tokens

## Instalación

```bash
pip install -r requirements.txt
```

## Configuración

Crear un archivo `.env` con:

```
JIRA_SERVER_URL=https://tujira.atlassian.net
JIRA_USERNAME=tu_usuario@dominio.com
JIRA_API_TOKEN=abc123
API_TOKEN=tu_token_de_tempo
```

## Ejecución

```bash
bash run.sh
```
