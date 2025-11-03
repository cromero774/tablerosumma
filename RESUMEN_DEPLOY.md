# 📋 Resumen: Pasos para Deploy en Render

## ✅ Cambios Realizados

1. **Inicialización automática de BD**: Si la BD no existe, se crea la estructura básica automáticamente
2. **Procfile actualizado**: Configurado para Render con puerto dinámico
3. **Guía de deployment**: Creado `GUIA_RENDER.md` con instrucciones detalladas

## 🚨 PROBLEMA CRÍTICO: Render Free Tier

### El Problema Principal:
- **Render Free NO tiene almacenamiento persistente**
- La base de datos se **BORRA** en cada reinicio del servicio
- La sincronización completa toma **40-60 minutos**

### Soluciones Posibles:

#### Opción 1: Base de Datos Externa (Recomendada)
- Usar PostgreSQL/SQLite en otro servicio (Railway, Supabase, etc.)
- Render se conecta a la BD externa
- ✅ Persistencia garantizada
- ✅ No se pierde en reinicios

#### Opción 2: Sincronización Manual Periódica
- Sincronizar la BD localmente
- Subir la BD a un servicio de almacenamiento (S3, Google Drive)
- Descargar la BD al inicio en Render
- ⚠️ Requiere script adicional

#### Opción 3: Render Paid (Volumen Persistente)
- Upgrade a plan pago de Render
- Tiene volúmenes persistentes
- ✅ Más simple pero tiene costo

## 📝 Pasos para Merge a Master

```bash
# 1. Asegurarte de estar en feature/base-datos
git checkout feature/base-datos

# 2. Cambiar a master
git checkout master

# 3. Hacer merge
git merge feature/base-datos

# 4. Resolver conflictos si los hay (probablemente no)

# 5. Push a master
git push origin master
```

## ⚙️ Configuración en Render

### Variables de Entorno (CRÍTICAS):
```
JIRA_BASE_URL=https://tu-jira.atlassian.net
JIRA_EMAIL=tu-email@evoltis.com
JIRA_API_TOKEN=tu-token
TEMPO_TOKEN=tu-tempo-token
```

### Build Command:
```
pip install -r requirements.txt
```

### Start Command (ya está en Procfile):
```
streamlit run tablero.py --server.port=$PORT --server.address=0.0.0.0
```

## 🔄 Sincronización de Base de Datos

### Primera vez (después del deploy):
1. La BD se creará automáticamente (estructura vacía)
2. Necesitas sincronizar los datos:
   - Opción A: Ejecutar `python src/database_completa.py` localmente y subir la BD
   - Opción B: Crear un endpoint en Render para sincronizar (puede tomar mucho tiempo)

### Sincronizaciones periódicas:
- Render Free NO tiene cron jobs
- Debes sincronizar manualmente cuando sea necesario
- O usar un servicio externo para cron jobs

## ⚠️ Limitaciones de Render Free

1. **Sin almacenamiento persistente**: BD se pierde en reinicios
2. **Sin cron jobs**: No puedes automatizar sincronizaciones
3. **Límite de tiempo**: Build/start limitados (~10-15 min)
4. **Límite de memoria**: ~512MB RAM

## 💡 Recomendación Final

**Para producción, recomiendo:**
1. Usar una base de datos externa (PostgreSQL en Railway/Supabase)
2. Modificar `database_helper.py` para conectarse a PostgreSQL
3. Render solo lee de la BD externa
4. Sincronización manual o con cron job externo

**Para testing rápido:**
1. Deploy en Render con SQLite
2. Sincronizar manualmente cuando sea necesario
3. Aceptar que la BD se pierde en reinicios

