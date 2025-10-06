# REGLAS DE NEGOCIO - PESTAÑA HISTÓRICO POSTVENTA

## 1. FUENTE DE DATOS

### Archivo de configuración:
- **Archivo**: `epicas_relevantes.json`
- **Filtro**: Solo épicas que empiecen con "REP-" o "TAL-"

### JIRA Queries:
- **Historias**: `project in (REP, TAL) AND issuetype = Historia`
- **Bugs REP**: `project = REP AND issuetype = Error`
- **Bugs TAL**: `project = TAL AND issuetype = Error`
- **Bugs UAT**: `project = BUG AND created >= "2025-01-01"`

## 2. MÉTRICAS PRINCIPALES

### Por épica (RN):
- **% Avance**: (Historias completadas / Total historias) * 100
- **Puntos totales**: Suma de puntos de todas las historias
- **Bugs asociados**: Bugs vinculados a historias del RN
- **Bugs UAT**: Bugs del proyecto BUG vinculados por Epic Link
- **DCR**: (Bugs asociados / (Bugs asociados + Bugs UAT)) * 100

### Cálculo de DCR:
```
DCR = (Bugs REP/TAL / (Bugs REP/TAL + Bugs UAT)) * 100
```

## 3. CLASIFICACIÓN DE BUGS

### Bugs asociados (REP/TAL):
- Bugs vinculados a historias del mismo desarrollador
- Cálculo de promedio de horas de resolución
- Agrupación por claves de historias

### Bugs UAT:
- Bugs del proyecto BUG
- Vinculados por Epic Link a épicas del RN
- Solo bugs creados desde 2025-01-01

## 4. FUNCIONES AUXILIARES

### Cálculo de horas:
```python
def _bug_resolution_hours(bug_issue):
    # Calcula horas desde inicio hasta resolución
    # Usa changelog para estados
```

### Mapeo de bugs:
```python
def _bugs_por_hu(bugs_issues):
    # Agrupa bugs por historia de usuario
    # Retorna: {HU_KEY: {"bugs": [...], "hrs": [...]}}
```

### Detección de campo épica:
```python
def detectar_campo_epic_link():
    # Detecta el campo correcto para Epic Link
```

## 5. CACHE

### Archivos de cache:
- **Historias TAL**: `data/cache_desarrollo_tal_issues.pkl`
- **Historias REP**: `data/cache_desarrollo_rep_issues.pkl`
- **Bugs REP**: `data/cache_desarrollo_bugs_rep.pkl`
- **Bugs TAL**: `data/cache_desarrollo_bugs_tal.pkl`
- **Bugs UAT**: `data/cache_desarrollo_bugs_uat.pkl`
- **Tabla procesada**: `data/cache_historico_tabla_procesada.pkl`

### Duración: 24 horas

## 6. VISUALIZACIÓN

### Estructura:
- Lista de RNs ordenada por mes de entrega
- Expandable con detalles de historias
- Indicadores de DCR con colores
- Información de bugs y tiempos

### Colores DCR:
- Verde: DCR ≥ 90% (Excelente)
- Rojo: DCR < 90% (Necesita mejora)

### Filtros:
- Búsqueda por nombre de RN
- Botón de actualización para limpiar cache
