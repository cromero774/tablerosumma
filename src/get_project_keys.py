from jira_conexion import jira

def get_project_key(project_id):
    try:
        project = jira._get_json(f'project/{project_id}')
        return project.get('key'), project.get('name')
    except Exception as e:
        print(f"Error obteniendo key para ID {project_id}: {e}")
        return None, None

ids = [10170, 10171]
for pid in ids:
    key, name = get_project_key(pid)
    print(f"ID: {pid}  -->  KEY: {key}  |  Nombre: {name}")
