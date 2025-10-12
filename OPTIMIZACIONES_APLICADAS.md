# OPTIMIZACIONES APLICADAS AL TABLERO

## RESUMEN DE CAMBIOS:

### 1. Cache base de 6h → 24h
**Línea 196:**
```python
def cargar_issues_jira_cache(jql: str, fields: str, nombre_cache: str, max_horas: int = 24):
```

### 2. Cache de enlaces BUGS de 12h → 48h
**Línea 2396:**
```python
if (datetime.now() - mtime) < timedelta(hours=48):  # Cache de 48h para enlaces
```

### 3. Cache Velocidad de 24h → 48h
**Línea 3788:**
```python
if (datetime.now() - mtime) < timedelta(hours=48):
```

### 4. Paralelización en Velocidad (líneas 3822-3849)
**Cambio de carga secuencial a paralela con ThreadPoolExecutor:**

```python
# Primero cargar todas las issues sin changelog
issues_sin_changelog = []
start_at = 0
max_issues = 10000

while True:
    params = {"jql": jql_hist, "fields": FIELDS, "startAt": start_at, "maxResults": 100}
    data = _jira._get_json("search", params=params)
    batch = data.get("issues", [])
    issues_sin_changelog.extend(batch)
    
    if len(batch) < 100 or len(issues_sin_changelog) >= max_issues:
        break
    start_at += 100

# Ahora enriquecer con changelog en paralelo
def enriquecer_con_changelog(issue):
    try:
        endpoint = f"issue/{quote_plus(issue['key'])}?expand=changelog&fields={quote_plus(FIELDS)}"
        return _jira._get_json(endpoint)
    except Exception:
        return issue

historias = []
with ThreadPoolExecutor(max_workers=10) as executor:
    historias = list(executor.map(enriquecer_con_changelog, issues_sin_changelog))
```

### 5. Filtrado en memoria - Velocidad (NO recargar al cambiar proyecto)

**Líneas 3701-3711 - Eliminar force_refresh de callbacks:**
```python
def on_fecha_inicio_change():
    st.session_state["vel_fecha_inicio"] = st.session_state["vel_fecha_inicio_input"]
    # NO forzar refresh, solo rerun para aplicar filtros
    
def on_fecha_fin_change():
    st.session_state["vel_fecha_fin"] = st.session_state["vel_fecha_fin_input"]
    # NO forzar refresh, solo rerun para aplicar filtros
    
def on_proyecto_change():
    st.session_state["vel_proyecto_sel"] = st.session_state["vel_proyecto_input"]
    # NO forzar refresh al cambiar proyecto, filtrar en memoria
```

**Líneas 3780-3807 - Cache global (Todos):**
```python
# === CACHE PERSISTENTE EN ARCHIVO (SIN filtro de proyecto, cachea TODO) ===
# Usar cache global que incluye todos los proyectos
cache_key = f"velocidad_data_Todos_{_fecha_inicio}_{_fecha_fin}"
cache_file = cache_path(cache_key, 'pkl')

# ... resto del código ...

# SIEMPRE cargar TODOS los proyectos (se filtrará después en memoria)
proy_jql = "project in (REP, TAL, ATI)"
```

### 6. Todos los caches de 24h → 48h
**Reemplazar GLOBALMENTE:**
```python
# BUSCAR: if (datetime.now() - mtime) < timedelta(hours=24):
# REEMPLAZAR POR: if (datetime.now() - mtime) < timedelta(hours=48):
```

---

## PROBLEMA PENDIENTE: BUGS - Saltar procesamiento cuando hay cache

**Líneas 2412-2542:**
El bloque de procesamiento de bugs debe estar completamente dentro del `else` para que NO se ejecute cuando hay cache.

La estructura correcta es:
```python
if procesamiento_enlaces_cacheado:
    # rows, excluidos, y los caches ya están cargados del archivo
    pass
else:
    # TODO el procesamiento va aquí dentro del else
    # (líneas 2418-2541 deben estar indentadas dentro del else)
```

