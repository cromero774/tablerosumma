# Guía para Desplegar en Render (Free Tier)

## ⚠️ Consideraciones Importantes para Render Free

### 1. **Sistema de Archivos Efímero**
- Los archivos se **borran** cuando el servicio se reinicia
- La base de datos `data/tablero_completo.db` se perderá en cada reinicio
- **Solución**: La BD se inicializa automáticamente si no existe (estructura básica)

### 2. **Tiempo de Sincronización**
- La sincronización completa puede tomar **40-60 minutos**
- Render free tiene límites de tiempo para build/start
- **Problema**: No puedes sincronizar durante el build porque requiere credenciales de Jira
- **Solución**: Sincronización manual después del deploy O script de background

### 3. **Memoria Limitada**
- Render free tiene ~512MB RAM
- La base de datos puede ser grande (~100MB+)
- **Solución**: Optimizaciones ya implementadas (vectorización)

### 4. **Variables de Entorno Necesarias en Render**
Configurar en Render Dashboard → Environment:
- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`
- `TEMPO_TOKEN`

## 📋 Pasos para Deploy

### Paso 1: Merge a Master
```bash
git checkout master
git merge feature/base-datos
git push origin master
```

### Paso 2: Configurar Render

1. **Build Command:**
   ```
   pip install -r requirements.txt
   ```

2. **Start Command:**
   ```
   streamlit run tablero.py --server.port=$PORT --server.address=0.0.0.0
   ```

3. **Variables de Entorno:**
   - Agregar todas las variables de Jira/Tempo

### Paso 3: Sincronizar Base de Datos

**Opción A: Manual (Recomendada para empezar)**
1. Después del deploy, ejecuta en tu máquina local:
   ```bash
   python src/database_completa.py
   ```
2. Sube la BD generada a Render (necesitarías un volumen persistente o script)

**Opción B: Script de Background en Render**
- Crear un endpoint o script que sincronice en background
- Ejecutarlo manualmente después del deploy

**Opción C: Sincronización Automática al Inicio**
- Modificar `tablero.py` para sincronizar si la BD está vacía
- ⚠️ **Problema**: Puede tomar 40-60 minutos y Render puede timeout

## 🔄 Estrategia Recomendada

**Mejor opción para Render Free:**
1. Sincronizar la BD localmente
2. Subir la BD a un servicio de almacenamiento (S3, Google Drive, etc.)
3. Descargar la BD al inicio en Render
4. O usar un volumen persistente (requiere plan pago)

## ⚙️ Modificaciones Necesarias

1. ✅ La BD se inicializa automáticamente si no existe (estructura básica)
2. ⚠️ La sincronización completa debe hacerse manualmente o en background
3. ⚠️ Render free NO tiene almacenamiento persistente

## 🚨 Limitaciones de Render Free

- **Sin almacenamiento persistente**: La BD se pierde en cada reinicio
- **Sin cron jobs**: No puedes programar sincronizaciones automáticas
- **Límite de tiempo**: Build/start limitados a ~10-15 minutos

## 💡 Alternativas

1. **Render Paid**: Tiene volúmenes persistentes
2. **Base de datos externa**: Usar PostgreSQL/SQLite en otro servicio
3. **S3 + Script**: Guardar BD en S3 y descargarla al inicio
