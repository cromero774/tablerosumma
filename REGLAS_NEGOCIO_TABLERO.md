# REGLAS DE NEGOCIO DEL TABLERO SUMMA

## 📊 **CONFIGURACIÓN GENERAL**

### **Mapeos de Proyectos:**
```python
MAPEO_TEM = {
    "TEM-1":  ("CORE-TECH", "TECH LAB - INTERNO"),
    "TEM-2":  ("CORE-TECH", "TECH LAB - INTERNO"),
    "TEM-5":  ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - ESCRITURA RF POSVENTA"),
    "TEM-7":  ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO MODULO REPUESTOS"),
    "TEM-8":  ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO ATI"),
    "TEM-9":  ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO MODULO TALLER"),
    "TEM-28": ("CORE-TECH", "TECH LAB - INTERNO"),
    "TEM-30": ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - ESCRITURA RF ATI"),
}

RESUMEN_A_PROYECTO = {
    "MAIPU - SUMMA - ESCRITURA RF POSVENTA": "AFUS",
    "MAIPU - SUMMA - DESARROLLO MODULO REPUESTOS": "REPUESTOS MAIPU",
    "MAIPU - SUMMA - DESARROLLO MODULO TALLER": "TALLER - MAIPÚ -",
    "MAIPU - SUMMA - DESARROLLO ATI": "AFUs ATI",
    "MAIPU - SUMMA - ESCRITURA RF ATI": "AFUs ATI",
    "": "TECH LAB - INTERNO"
}

PROYECTOS_POSTVENTA = [
    "TALLER - MAIPÚ -",
    "REPUESTOS MAIPU", 
    "AFUS",
    "TECH LAB - INTERNO"
]

PROYECTOS_ATI = [
    "AFUs ATI",
    "TECH LAB - INTERNO"
]
```

### **Reglas de Proyecto Lógico:**
- **Antes de junio 2025**: Ignorar filas "TEMPO WORKLOAD", usar proyecto normalizado
- **Desde junio 2025**: Si es TEM-, usar MAPEO_TEM
- **Normalización**: CORETECH/Core Tech/TECHLAB → "TECH LAB - INTERNO"

---

## 🏢 **PESTAÑAS POSTVENTAS**

### 1. **📊 Horas Postventas**
**Proyectos incluidos:** `PROYECTOS_POSTVENTA`
**Reglas:**
- Análisis de horas por usuario y proyecto
- Filtros por mes/año
- Alertas para TEM no mapeadas
- Vista pivotada usuario x proyecto

### 2. **💻 Desarrollo Postventas** 
**Proyectos incluidos:** `PROYECTOS_POSTVENTA`
**Reglas:**
- **Limitación**: Solo últimos 6 meses (mayo-octubre 2025)
- Carga issues de Jira con cache
- Análisis por sprint y versión
- Filtros por proyecto y período

### 3. **📦 Entregables Postventas**
**Proyectos incluidos:** `PROYECTOS_POSTVENTAS`
**Reglas:**
- Gestión de épicas por mes de entrega
- Cálculo de % avance por épica
- Priorización por mes y % avance
- Alertas para épicas incompletas

### 4. **📈 Histórico Postventa**
**Proyectos incluidos:** `PROYECTOS_POSTVENTAS`
**Reglas:**
- Análisis histórico de rendimiento
- Métricas de evolución temporal

---

## 🏢 **PESTAÑAS ATI**

### 5. **📊 Horas ATI**
**Proyectos incluidos:** `PROYECTOS_ATI`
**Reglas:**
- Análisis específico para ATI
- Misma lógica que Horas Postventas pero con proyectos ATI

### 6. **💻 Desarrollo ATI**
**Proyectos incluidos:** `PROYECTOS_ATI`
**Reglas:**
- Seguimiento de desarrollo específico ATI
- Misma lógica que Desarrollo Postventas

### 7. **📦 Entregables ATI**
**Proyectos incluidos:** `PROYECTOS_ATI`
**Reglas:**
- Gestión de entregables específicos ATI
- Misma lógica que Entregables Postventas

### 8. **📈 Histórico ATI**
**Proyectos incluidos:** `PROYECTOS_ATI`
**Reglas:**
- Análisis histórico específico ATI
- Misma lógica que Histórico Postventas

---

## 🐛 **BUGS**

### 9. **🐛 BUGS**
**Reglas:**
- Gestión y seguimiento de bugs
- Análisis de tiempo de resolución
- Métricas de bugs por Historia de Usuario
- Estados: To Do, In Progress, Done

---

## ⚡ **VELOCIDAD**

### 10. **⚡ Velocidad de devs**
**Reglas:**
- **CRÍTICO**: NUNCA reducir cantidad de datos (max_issues y max_bugs = 10000)
- Análisis de velocidad de desarrollo
- Métricas de story points completados
- Filtros por período y equipo

---

## 📊 **GANTT**

### 11. **📊 Gantt**
**Reglas:**
- Vista de cronograma
- Planificación temporal
- Dependencias entre tareas

---

## 🔧 **REGLAS TÉCNICAS**

### **Cache:**
- Cache de 24 horas para issues de Jira
- Cache específico por pestaña
- Fallback a cache viejo si existe

### **Usuarios:**
- Mapeo de account IDs a nombres desde `accountid_to_name.json`
- Usuarios BOTH: ven todas sus filas (ATI + POST + INTERNO)
- Usuarios solo ATI: ven filas ATI + INTERNO
- Usuarios solo POSTVENTA: ven filas POSTVENTA + INTERNO

### **Fechas:**
- Feriados argentinos 2025 incluidos en cálculos
- Días laborables excluyen fines de semana
- Formato de fechas: DD/MM/YYYY

### **Validaciones:**
- Alertas para TEM no mapeadas
- Validación de datos faltantes
- Manejo de errores con mensajes informativos
