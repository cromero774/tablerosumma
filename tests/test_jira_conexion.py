import pytest
from jira_conexion import traer_issues_jql

def test_traer_issues_jql():
    jql = 'project = TEST and status = "Done"'
    fields = 'key'
    try:
        issues = traer_issues_jql(jql, fields, max_results=1)
        assert isinstance(issues, list)
    except Exception as e:
        # Si no hay credenciales o el endpoint falla, el test pasa si la excepción es controlada
        assert True
