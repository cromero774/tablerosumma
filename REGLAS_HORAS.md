# REGLAS DE NEGOCIO - PESTAÑA HORAS

## 1. PROYECTOS

### Postventas:
- TALLER - MAIPÚ -
- REPUESTOS MAIPU
- AFUS
- TECH LAB - INTERNO

### ATI:
- AFUs ATI
- TECH LAB - INTERNO

## 2. FUENTE DE DATOS

### Archivo principal:
- **Archivo**: `data/horas.csv`
- **Campos**: Fecha, Usuario, Horas, Proyecto_logico

### Mapeo de usuarios:
- **Archivo**: `data/accountid_to_name.json`
- **Función**: Convertir account IDs a nombres legibles

## 3. MÉTRICAS

### Por usuario:
- Total de horas trabajadas
- Promedio de horas por mes
- Distribución por proyecto

### Por proyecto:
- Total de horas por proyecto
- Usuarios que trabajaron en cada proyecto
- Tendencias temporales

## 4. FILTROS

### Filtros disponibles:
- **Rango de fechas**: Desde/Hasta
- **Usuario**: Selector de usuarios
- **Proyecto**: Postventas/ATI/Todos

## 5. VISUALIZACIONES

### Gráficos:
- Gráfico de barras por usuario
- Gráfico de líneas temporal
- Gráfico de torta por proyecto

### Tablas:
- Resumen por usuario
- Detalle por fecha
- Comparación entre proyectos

