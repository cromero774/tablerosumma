# REGLAS PESTAÑA BUGS - VERSIÓN ACTUALIZADA

## 🎯 FUNCIONALIDADES PRINCIPALES

### 1. **TABLA TRANSPUESTA MENSUAL**
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

### 2. **DESPLEGABLES POR MES**
Cada mes tiene desplegables con:
- **Mejoras**: Lista de mejoras cerradas
- **Bugs Otras Funcionalidades**: Bugs no relacionados con entregables
- **Bugs de Entregables**: Bugs relacionados con épicas de entregables
- **Bugs Bloqueantes**: Bugs con tiempos de resolución

### 3. **BUGS INTERNOS POR MES** (NUEVA TABLA)
- **Proyectos**: TAL, REP, ATI
- **Criterio**: Fecha de creación
- **Exclusión**: Bugs vinculados a proyecto "BUG-XXX" (externos)
- **Formato**: Pivot table con meses como columnas, proyectos como filas

### 4. **BUGS INTERNOS POR USUARIO** (NUEVA TABLA)
- **Criterio**: Bugs vinculados a historias
- **Asignación**: Usuario asignado a la historia vinculada (NO al bug)
- **Fallback**: Si historia no tiene asignado, usar asignado del bug
- **Formato**: Pivot table con meses como columnas, usuarios como filas
- **Meses**: Enero 2025 a Diciembre 2025 (incluso con 0 bugs)

## 🔧 FUNCIONES TÉCNICAS

### **`_calcular_tiempos_estado`**
```python
def _calcular_tiempos_estado(issue):
    # Encuentra primera salida de "To Do" o "Por Hacer"
    # Calcula días laborables hasta "EN VALIDACIÓN QA" y "APROBADO POR QA"
    # Excluye sábados, domingos y feriados argentinos 2025
```

### **`calcular_dias_laborables`**
```python
def calcular_dias_laborables(fecha_inicio, fecha_fin):
    # Excluye fines de semana y feriados argentinos
    # Feriados 2025: 1/1, 20/2, 21/2, 24/3, 2/4, 1/5, 25/5, 17/6, 20/6, 9/7, 8/12, 25/12
```

### **`tiene_vinculo_bug`**
```python
def tiene_vinculo_bug(issue):
    # Detecta si bug está vinculado a proyecto "BUG-XXX"
    # Retorna True si es externo (debe excluirse)
```

## 📊 CÁLCULOS SLA

### **SLA Validación QA**
- **Medición**: Días laborables desde salida de "To Do" hasta entrada a "EN VALIDACIÓN QA"
- **Exclusión**: Fines de semana y feriados argentinos 2025

### **SLA Aprobado por QA**  
- **Medición**: Días laborables desde salida de "To Do" hasta entrada a "APROBADO POR QA"
- **Exclusión**: Fines de semana y feriados argentinos 2025

## 🚫 FUNCIONALIDADES ELIMINADAS

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

## 🔄 CARGAS DE DATOS

### **Bugs Internos por Mes**
```python
# JQL para cada proyecto
jql_tal = 'project = TAL AND issuetype in (Error, Bug) AND created >= "2025-01-01" ORDER BY created ASC'
jql_rep = 'project = REP AND issuetype in (Error, Bug) AND created >= "2025-01-01" ORDER BY created ASC'  
jql_ati = 'project = ATI AND issuetype in (Error, Bug) AND created >= "2025-01-01" ORDER BY created ASC'

# Paginación por mes para evitar límites API
# Carga mensual: Enero 2025 a Diciembre 2025
```

### **Bugs Internos por Usuario**
```python
# Carga historias de TAL, REP, ATI
jql_historias = 'project in (TAL, REP, ATI) AND issuetype in ("Historia", "Story", "User Story") AND created >= "2025-01-01"'

# Carga bugs de TAL, REP, ATI  
jql_bugs = 'project in (TAL, REP, ATI) AND issuetype in (Error, Bug) AND created >= "2025-01-01" ORDER BY created ASC'

# Vinculación: bug.issuelinks → historia.assignee
```

## 📋 CACHES UTILIZADOS

### **Bugs por Mes**
- `bugs_tal_internos.pkl`
- `bugs_rep_internos.pkl` 
- `bugs_ati_internos.pkl`

### **Bugs por Usuario**
- `bugs_historias_tal_rep.pkl`
- `bugs_todos_tal_rep_ati_completo.pkl`

### **SLA**
- `bugs_sla_tiempos.pkl`

## ⚠️ CONSIDERACIONES IMPORTANTES

1. **Límites API**: Usar paginación mensual para evitar límites de 100 issues por llamada
2. **Exclusión Externa**: Bugs vinculados a "BUG-XXX" son externos, no contar
3. **Asignación Usuario**: Priorizar asignado de historia sobre asignado de bug
4. **Meses Completos**: Mostrar todos los meses 2025, incluso con 0 bugs
5. **Días Laborables**: Excluir fines de semana y feriados argentinos en SLA
6. **Estados SLA**: Buscar "To Do" y "Por Hacer" como estado inicial
7. **Estados Destino**: "EN VALIDACIÓN QA" y "APROBADO POR QA"

## 🔧 FUNCIONES GLOBALES UTILIZADAS

- `traer_todas_las_issues_global()`: Para carga con paginación mensual
- `traer_todas_las_issues()`: Para carga simple
- `_safe_issue_key()`: Para claves seguras
- `normalize()`: Para normalización de nombres
- `detectar_campo_epic_link()`: Para detección de vínculos épicos
