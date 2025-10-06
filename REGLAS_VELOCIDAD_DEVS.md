# REGLAS DE NEGOCIO - PESTAÑA VELOCIDAD DE DEVS

## 1. FUENTE DE DATOS

### JIRA Queries:
- **Historias**: `project in (REP, TAL, ATI) AND issuetype = Historia AND (cf[10026] is not EMPTY OR cf[10016] is not EMPTY OR 'Story Points' is not EMPTY)`
- **Bugs**: `project in (REP, TAL, ATI) AND issuetype = Error`

### Campos requeridos:
```
key,summary,status,project,issuetype,assignee,customfield_10026,customfield_10016,storyPoints,statuscategorychangedate,parent,issuelinks,created,updated
```

### Archivos de configuración:
- **`data/accountid_to_name.json`**: Mapeo de usuarios
- **`data/horas.csv`**: Datos de horas trabajadas

## 2. MÉTRICAS PRINCIPALES

### Por desarrollador:
- **Puntos**: Story points completados
- **Horas**: Horas trabajadas (80% para cálculo de velocidad)
- **Velocidad**: (Horas * 0.8) / Puntos
- **Bugs**: Bugs resueltos vinculados a sus historias
- **Bugs extra**: Bugs resueltos NO vinculados a sus historias

### Cálculo de velocidad:
```
Velocidad = (Horas * 0.8) / Puntos
Objetivo: ≤8 horas/punto
```

## 3. CLASIFICACIÓN DE BUGS

### Bugs normales:
- Bugs vinculados a historias del MISMO desarrollador
- Se restan puntos de la nota final

### Bugs extra:
- Bugs NO vinculados a historias del desarrollador
- Dan bonus a la nota final

## 4. SISTEMA DE PUNTUACIÓN

### Nota final (0-100):
- **Puntos (40%)**: 16 puntos/mes = 100%
- **Horas (25%)**: ≥128 horas/mes = 100%
- **Velocidad (25%)**: ≤8 h/punto = 100%
- **Bugs (10%)**: 0 bugs/mes = 100%

### Escalas de puntos:
- ≥20 puntos: 110%
- 16-19 puntos: 105%
- 13-15 puntos: 90%
- 10-12 puntos: 85%
- 8-9 puntos: 80%
- <8 puntos: 70%

### Escalas de horas:
- ≥128 horas: 100%
- 100-127 horas: 95%
- <100 horas: 70%

### Escalas de velocidad:
- ≤5 h/punto: 110%
- 6-7 h/punto: 105%
- 8 h/punto: 100%
- 9-10 h/punto: 95%
- 11-12 h/punto: 90%
- >12 h/punto: 80%

### Escalas de bugs:
- 0 bugs: 100%
- 1-3 bugs: 95%
- 4-5 bugs: 90%
- >5 bugs: 80%

### Bonus bugs extra:
- 1-5 extra: +2%
- 6-10 extra: +3%
- >10 extra: +5%

## 5. FILTROS

### Filtros disponibles:
- **Rango de fechas**: Desde/Hasta
- **Proyecto**: Todos/ATI/Postventas
- **Usuario**: Selector de usuarios

### Filtros de proyecto:
- **ATI**: Solo proyectos ATI
- **Postventas**: Solo proyectos REP y TAL
- **Todos**: Todos los proyectos

## 6. FUNCIONES PRINCIPALES

### Procesamiento de historias:
```python
def procesar_historias(historias, accountid_to_name, name_to_acc):
    # Procesa historias y calcula puntos por desarrollador

def _owner_al_momento_testing(iss, accountid_to_name, name_to_acc):
    # Determina el owner al momento de testing
```

### Procesamiento de bugs:
```python
def procesar_bugs(bugs, historias_por_dev):
    # Clasifica bugs en normales y extra
```

### Cálculo de métricas:
```python
def calcular_metricas_finales(df_filtrado):
    # Calcula nota final y métricas
```

## 7. VISUALIZACIÓN

### Estructura:
- Selector de fechas y proyecto
- Cards de objetivos y ponderaciones
- Tabla de ranking de desarrolladores
- Gráfico de velocidad por desarrollador
- Historial detallado por usuario
- Gráfico de velocidad mensual

### Cache:
- **Archivo**: `data/cache_velocidad_data_{proyecto}_{fecha_inicio}_{fecha_fin}.pkl`
- **Duración**: 24 horas
- **Session state**: Cache temporal para cálculos pesados
