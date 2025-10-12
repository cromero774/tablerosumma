# REGLAS DE NEGOCIO - PESTAÑA BUGS

## 1. FUNCIONALIDADES PRINCIPALES

### **TABLA TRANSPUESTA MENSUAL**
- **Métricas mostradas por mes:**
  - Pendientes
  - Cerrados  
  - % Cumplimiento
  - Mejoras
  - Bugs Otras Funcionalidades
  - Bugs de Entregables
  - Bugs Bloqueantes
  - **SLA Validación QA** (días de To Do → EN VALIDACIÓN QA)
  - **SLA Aprobado por QA** (días de To Do → APROBADO POR QA)

### **DESPLEGABLES POR MES**
Cada mes tiene desplegables con:
- **Mejoras**: Lista de mejoras cerradas
- **Bugs Otras Funcionalidades**: Bugs no relacionados con entregables
- **Bugs de Entregables**: Bugs relacionados con épicas de entregables
- **Bugs Bloqueantes**: Bugs con tiempos de resolución

### **BUGS INTERNOS POR MES** (NUEVA TABLA)
- **Proyectos**: TAL, REP, ATI
- **Criterio**: Fecha de creación
- **Exclusión**: Bugs vinculados a proyecto "BUG-XXX" (externos)
- **Formato**: Pivot table con meses como columnas, proyectos como filas

### **BUGS INTERNOS POR USUARIO** (NUEVA TABLA)
- **Criterio**: Bugs vinculados a historias
- **Asignación**: Usuario asignado a la historia vinculada (NO al bug)
- **Fallback**: Si historia no tiene asignado, usar asignado del bug
- **Formato**: Pivot table con meses como columnas, usuarios como filas
- **Meses**: Enero 2025 a Diciembre 2025 (incluso con 0 bugs)

## 2. CLASIFICACIÓN DE BUGS

### Tipos de Bugs:
- **KINETIC**: Bugs con etiqueta "KINETIC" en el campo `labels`
- **MEJORA**: Bugs con etiqueta "MEJORA" en el campo `labels`
- **Bugs EVOLTIS**: Q Mensual - KINETIC - MEJORA
- **Bugs Bloqueantes**: Bugs con prioridad "Muy alta" (excluyendo KINETIC y MEJORA)

### Fórmulas:
```
Q Bugs EVOLTIS = Q Mensual - Q KINETIC - Q MEJORA
% Bugs Bloqueantes = (Q Bloqueantes / Q Bugs EVOLTIS) * 100
```

## 3. CÁLCULOS SLA

### **SLA Validación QA**
- **Medición**: Días laborables desde salida de "To Do" hasta entrada a "EN VALIDACIÓN QA"
- **Exclusión**: Fines de semana y feriados argentinos 2025

### **SLA Aprobado por QA**  
- **Medición**: Días laborables desde salida de "To Do" hasta entrada a "APROBADO POR QA"
- **Exclusión**: Fines de semana y feriados argentinos 2025

### **Feriados Argentina 2025:**
- 1/1, 20/2, 21/2, 24/3, 2/4, 1/5, 25/5, 17/6, 20/6, 9/7, 8/12, 25/12

## 4. DETALLE POR MES (Expandable)

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

## 5. FUENTE DE DATOS

### Conexión JIRA Principal (Bugs):
- **Proyecto**: `BUG` (project = BUG)
- **Período**: `created >= "2024-01-01"`
- **JQL**: `project = BUG AND created >= "2024-01-01"`

### Conexión JIRA Bugs Internos:
- **Proyectos**: `TAL`, `REP`, `ATI`
- **JQL Bugs**: `project in (TAL, REP, ATI) AND issuetype in (Error, Bug) AND created >= "2025-01-01" ORDER BY created ASC`
- **JQL Historias**: `project in (TAL, REP, ATI) AND issuetype in ("Historia", "Story", "User Story") AND created >= "2025-01-01"`

### Campos requeridos:
```
key,created,priority,issuetype,summary,status,labels,parent,customfield_10016,customfield_10014,customfield_10015,customfield_10017,customfield_10018,customfield_10019,customfield_10020,customfield_10021,customfield_10022,customfield_10023,customfield_10024,customfield_10025,fixVersions,components,resolution,assignee,reporter,updated,issuelinks
```

### Campos específicos:
- **KINETIC/MEJORA**: Campo `labels`
- **Prioridad**: Campo `priority` (para bugs bloqueantes)
- **Épica**: Campo `parent` → `customfield_10016`
- **Tipo**: Campo `issuetype` (debe ser "Error")
- **Vínculos**: Campo `issuelinks` (expandido para detectar bugs externos)

### Changelog para tiempos:
- **Expand**: `changelog` en la consulta
- **Estados**: Historial de cambios en `changelog.histories`
- **Transiciones**: "To Do" o "Por Hacer" → "EN VALIDACIÓN QA" → "APROBADO POR QA"

## 6. ARCHIVOS DE CONFIGURACIÓN

### Archivos necesarios:
- **`epicas_relevantes.json`**: Lista de épicas relevantes con nombres
- **`accountid_to_name.json`**: Mapeo de usuarios

### Caches utilizados:
- **Bugs por Mes**: `bugs_tal_internos.pkl`, `bugs_rep_internos.pkl`, `bugs_ati_internos.pkl`
- **Bugs por Usuario**: `bugs_historias_tal_rep.pkl`, `bugs_todos_tal_rep_ati_completo.pkl`
- **SLA**: `bugs_sla_tiempos.pkl`

## 7. FUNCIONES PRINCIPALES

### Funciones de clasificación:
```python
def detectar_etiqueta_kinetic_mejora(labels):
    # Detecta si es KINETIC o MEJORA

def es_epica_del_json(epic_key):
    # Verifica si la épica está en epicas_relevantes.json

def es_bloqueante_por_prioridad(priority):
    # Verifica si es prioridad "Muy alta"

def tiene_vinculo_bug(issue):
    # Detecta si bug está vinculado a proyecto "BUG-XXX" (externo)
```

### Función de tiempos:
```python
def _calcular_tiempos_estado(bug_issue):
    # Calcula días laborables entre estados
    # Excluye sábados, domingos y feriados argentinos 2025
    # Estados: "To Do" o "Por Hacer" → "EN VALIDACIÓN QA" → "APROBADO POR QA"

def calcular_dias_laborables(fecha_inicio, fecha_fin):
    # Excluye fines de semana y feriados argentinos 2025
```

### Función de nombres:
```python
def _obtener_nombre_epica(epic_key):
    # Obtiene nombre legible de la épica desde epicas_relevantes.json
```

### Funciones globales:
```python
def traer_todas_las_issues_global(jira, jql, fields, max_results=5000):
    # Carga issues con paginación mensual para evitar límites API

def traer_todas_las_issues(jira, jql, fields, max_results=5000):
    # Carga issues simple para compatibilidad
```

## 8. LAYOUT DE LA INTERFAZ

### Estructura principal:
1. **Tabla transpuesta mensual** con métricas principales (incluyendo SLA)
2. **Expandable por mes** con detalles
3. **Dos columnas** en el detalle: "Bugs Otras Funcionalidades" (izq) y "Bugs de Entregables" (der)
4. **Tabla de Bugs Bloqueantes** debajo con tiempos
5. **🐛 Bugs Internos por Mes** (nueva tabla)
6. **👥 Bugs Internos por Usuario** (nueva tabla)

### Colores y formato:
- **% Bloqueantes**: Verde si <20%, Rojo si ≥20%
- **Iconos**: 🐛 para bugs, 📊 para métricas, 🚨 para bloqueantes
- **Columnas Total**: Agregadas a las tablas de bugs internos

## 9. FUNCIONALIDADES ELIMINADAS

### **Cards por Estado** (ELIMINADO)
- ❌ Cards de estados (POR HACER, EN VALIDACIÓN QA, etc.)
- ❌ KPIs de cards (Pendientes, Cerrados, % Cumplimiento)
- ❌ Card de excluidos
- ❌ Funciones helper de cards

### **Filtros Antiguos** (ELIMINADO)
- ❌ Selectbox de "Proyecto"
- ❌ Selectbox de "Mes (detalle opcional)"
- ❌ Botón "Actualizar" con progreso
- ❌ Barra de progreso
- ❌ Mensajes de estado

### **Mensajes Informativos** (ELIMINADO)
- ❌ "Se excluyeron X issues..."

## 10. NOTAS IMPORTANTES

- **NO incluir** KINETIC y MEJORA en bugs bloqueantes
- **Calcular % Bloqueantes** sobre Q Bugs EVOLTIS, no sobre Q Mensual
- **Mostrar nombres de épicas**, no claves
- **Excluir fines de semana y feriados** en cálculo de días SLA
- **Paginación mensual** para evitar límites de API Jira (100 issues por llamada)
- **Bugs externos**: Excluir bugs vinculados a proyecto "BUG-XXX"
- **Asignación usuario**: Priorizar asignado de historia sobre asignado de bug
- **Meses completos**: Mostrar todos los meses 2025, incluso con 0 bugs
- **Sin asignar**: Excluir fila "Sin asignar" de la tabla de usuarios

