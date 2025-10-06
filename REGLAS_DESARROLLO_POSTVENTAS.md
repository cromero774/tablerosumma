# REGLAS DE NEGOCIO - PESTAÑA DESARROLLO POSTVENTAS

## 1. PROYECTOS

### Proyectos incluidos:
- REP (Repuestos)
- TAL (Taller)

## 2. FUENTE DE DATOS

### JIRA Query:
- **JQL**: `project in (REP, TAL) AND issuetype = Historia`
- **Campos**: key,summary,status,project,issuetype,assignee,parent,customfield_10016,customfield_10026,duedate,statuscategorychangedate,updated

### Cache:
- **Archivo**: `data/cache_desarrollo_issues.pkl`
- **Duración**: 24 horas

## 3. CLASIFICACIÓN

### Por estado:
- **Lista para implementar**: Historias listas
- **En desarrollo**: Historias en progreso
- **Otros estados**: Resto de estados

### Por épica:
- **Con épica**: Historias con parent.summary
- **Sin épica**: Historias sin parent

## 4. MÉTRICAS

### Por desarrollador:
- Total de historias asignadas
- Puntos totales
- Estado de cada historia

### Por épica:
- Historias agrupadas por épica
- Progreso por épica
- Puntos por épica

## 5. FUNCIONES AUXILIARES

### Normalización:
```python
def _status_norm(s):
    # Normaliza estados a minúsculas

def normalize(s):
    # Normaliza texto ignorando acentos
```

### Mapeo de épicas:
- Usar `parent.summary` como nombre de épica
- Fallback a `customfield_10016` si no hay parent

## 6. VISUALIZACIÓN

### Estructura:
- Lista de historias por desarrollador
- Agrupación por épica
- Estado visual con colores
- Información de puntos y fechas
