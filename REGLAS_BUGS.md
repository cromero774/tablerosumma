# REGLAS DE NEGOCIO - PESTAÑA BUGS

## 1. CLASIFICACIÓN DE BUGS

### Tipos de Bugs:
- **KINETIC**: Bugs con etiqueta "KINETIC" en el campo `labels`
- **MEJORA**: Bugs con etiqueta "MEJORA" en el campo `labels`
- **Bugs EVOLTIS**: Q Mensual - KINETIC - MEJORA
- **Bugs Bloqueantes**: Bugs con prioridad "Muy alta" (excluyendo KINETIC y MEJORA)

## 2. MÉTRICAS POR MES

### Métricas principales:
- **Q Bugs Mensuales**: Total de bugs del mes
- **Q Mejoras**: Cantidad de bugs MEJORA
- **Q KINETIC**: Cantidad de bugs KINETIC
- **Q Bugs Bloqueantes**: Cantidad de bugs bloqueantes (sin KINETIC/MEJORA)
- **Q Bugs EVOLTIS**: Q Mensual - KINETIC - MEJORA
- **% Bugs Bloqueantes**: (Q Bloqueantes / Q Bugs EVOLTIS) * 100

### Fórmulas:
```
Q Bugs EVOLTIS = Q Mensual - Q KINETIC - Q MEJORA
% Bugs Bloqueantes = (Q Bloqueantes / Q Bugs EVOLTIS) * 100
```

## 3. DETALLE POR MES (Expandable)

### Secciones del detalle:
1. **Mejoras**: 
   - Lista de claves de bugs MEJORA
   - Cantidad entre paréntesis: "BUG-123, BUG-456 (2)"

2. **Bugs Otras Funcionalidades** (lado izquierdo):
   - **Con épica del JSON**: Tabla con nombre de épica, cantidad por prioridad, total
   - **Sin épica**: Lista de claves de bugs sin épica bajo "Sin épica"

3. **Bugs de Entregables** (lado derecho):
   - Tabla con bugs que tienen épicas del JSON
   - Contados por prioridad y total

4. **Bugs Bloqueantes**:
   - Tabla con clave y tiempos en días
   - Columnas: "Clave", "Días To Do → Validación QA", "Días Validación QA → Aprobado QA"
   - Excluir fines de semana del cálculo

## 4. FUENTE DE DATOS

### Conexión JIRA:
- **Proyecto**: `BUG` (project = BUG)
- **Período**: `created >= "2024-01-01"`
- **JQL**: `project = BUG AND created >= "2024-01-01"`

### Campos requeridos:
```
key,created,priority,issuetype,summary,status,labels,parent,customfield_10016,customfield_10014,customfield_10015,customfield_10017,customfield_10018,customfield_10019,customfield_10020,customfield_10021,customfield_10022,customfield_10023,customfield_10024,customfield_10025,fixVersions,components,resolution,assignee,reporter,updated,issuelinks
```

### Campos específicos:
- **KINETIC/MEJORA**: Campo `labels`
- **Prioridad**: Campo `priority` (para bugs bloqueantes)
- **Épica**: Campo `parent` → `customfield_10016`
- **Tipo**: Campo `issuetype` (debe ser "Error")

### Changelog para tiempos:
- **Expand**: `changelog` en la consulta
- **Estados**: Historial de cambios en `changelog.histories`
- **Transiciones**: "To Do" → "EN VALIDACIÓN QA" → "APROBADO POR QA"

## 5. ARCHIVOS DE CONFIGURACIÓN

### Archivos necesarios:
- **`epicas_relevantes.json`**: Lista de épicas relevantes con nombres
- **`accountid_to_name.json`**: Mapeo de usuarios

### Cache:
- **Función**: `cargar_issues_jira_cache()`
- **Archivo**: `data/cache_bugs_issues.pkl`
- **Duración**: 24 horas

## 6. FUNCIONES PRINCIPALES

### Funciones de clasificación:
```python
def detectar_etiqueta_kinetic_mejora(labels):
    # Detecta si es KINETIC o MEJORA

def es_epica_del_json(epic_key):
    # Verifica si la épica está en epicas_relevantes.json

def es_bloqueante_por_prioridad(priority):
    # Verifica si es prioridad "Muy alta"
```

### Función de tiempos:
```python
def _calcular_tiempos_estado(bug_issue):
    # Calcula días laborables entre estados
    # Excluye sábados y domingos
    # Estados: "To Do" → "EN VALIDACIÓN QA" → "APROBADO POR QA"
```

### Función de nombres:
```python
def _obtener_nombre_epica(epic_key):
    # Obtiene nombre legible de la épica desde epicas_relevantes.json
```

## 7. LAYOUT DE LA INTERFAZ

### Estructura principal:
1. **Tabla mensual** con métricas principales
2. **Expandable por mes** con detalles
3. **Dos columnas** en el detalle: "Bugs Otras Funcionalidades" (izq) y "Bugs de Entregables" (der)
4. **Tabla de Bugs Bloqueantes** debajo con tiempos

### Colores y formato:
- **% Bloqueantes**: Verde si <20%, Rojo si ≥20%
- **Iconos**: 🐛 para bugs, 📊 para métricas, 🚨 para bloqueantes

## 8. NOTAS IMPORTANTES

- **NO incluir** KINETIC y MEJORA en bugs bloqueantes
- **Calcular % Bloqueantes** sobre Q Bugs EVOLTIS, no sobre Q Mensual
- **Mostrar nombres de épicas**, no claves
- **Excluir fines de semana** en cálculo de días
- **Mantener compatibilidad** con filtros existentes

