# REGLAS DE NEGOCIO - PESTAÑA ENTREGABLES POSTVENTAS

## 1. FUENTE DE DATOS

### Archivo de configuración:
- **Archivo**: `epicas_relevantes.json`
- **Estructura**: Lista de épicas con nombres y fechas de entrega

### JIRA Query:
- **JQL**: `project in (REP, TAL) AND issuetype = Historia`
- **Campos**: key,summary,status,project,issuetype,assignee,parent,customfield_10016,customfield_10026,duedate,statuscategorychangedate,updated

## 2. CLASIFICACIÓN

### Por épica:
- **Épicas del JSON**: Historias vinculadas a épicas en `epicas_relevantes.json`
- **Sin épica**: Historias sin parent o con parent no reconocido

### Por estado:
- **Lista para implementar**: Historias completadas
- **En desarrollo**: Historias en progreso
- **Otros**: Resto de estados

## 3. MÉTRICAS

### Por épica:
- **Total de historias**: Cantidad total
- **Completadas**: Historias "lista para implementar"
- **% Avance**: (Completadas / Total) * 100
- **Puntos totales**: Suma de puntos de todas las historias

### Por mes de entrega:
- Agrupación por fecha de entrega planificada
- Progreso acumulado

## 4. FUNCIONES AUXILIARES

### Normalización:
```python
def normalize(s):
    # Normaliza texto ignorando acentos y mayúsculas

def _status_norm(s):
    # Normaliza estados
```

### Mapeo de épicas:
- Buscar coincidencia por nombre normalizado
- Usar `parent.summary` como fuente principal

## 5. VISUALIZACIÓN

### Estructura:
- Lista de épicas ordenada por mes de entrega
- Expandable con detalles de historias
- Indicadores de progreso visual
- Información de puntos y fechas

### Colores:
- Verde: Épicas completadas (100%)
- Amarillo: Épicas en progreso
- Rojo: Épicas atrasadas
