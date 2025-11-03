# 📊 Estado Actual de la Base de Datos

## Ubicación Actual
- **Local**: `data/tablero_completo.db` (~53 MB)
- **En git**: ❌ NO (está en `.gitignore`)
- **En la nube**: ❌ NO

## El Problema
Render Free **NO puede acceder a archivos de tu máquina local**. Cada instancia de Render es un servidor independiente que:
- Se crea desde cero en cada deploy
- Solo tiene acceso a lo que está en el repositorio git
- Borra todos los archivos en cada reinicio (sin almacenamiento persistente)

## ✅ Opciones para Usar la BD en Render

### Opción 1: Subir la BD a Git (Temporal)
**Pros:**
- ✅ Simple: solo commitear la BD
- ✅ Render la tendrá automáticamente

**Contras:**
- ⚠️ La BD es grande (~53MB) - git puede ser lento
- ⚠️ Cada cambio en la BD requiere commit
- ⚠️ No es una buena práctica para BDs grandes

**Cómo hacerlo:**
```bash
# 1. Quitar la BD del .gitignore temporalmente
# Editar .gitignore y comentar: # data/tablero_completo.db

# 2. Agregar la BD a git
git add data/tablero_completo.db

# 3. Commit
git commit -m "Agregar base de datos inicial para Render"

# 4. Push
git push origin master
```

**⚠️ IMPORTANTE**: Después del primer deploy, volver a agregar al `.gitignore` para no subir actualizaciones.

---

### Opción 2: Almacenamiento en la Nube + Descarga al Inicio
**Pros:**
- ✅ La BD queda persistente en la nube
- ✅ No llena el repositorio git
- ✅ Puedes actualizar la BD sin hacer commit

**Contras:**
- ⚠️ Requiere script para descargar
- ⚠️ Render Free puede ser lento descargando

**Cómo hacerlo:**
1. Subir `data/tablero_completo.db` a:
   - Google Drive (público)
   - Dropbox (link público)
   - S3 (AWS)
   - GitHub Releases (máx 100MB)

2. Crear script en Render que descargue la BD al inicio:
```python
# En tablero.py o script separado
import os
import urllib.request

if not os.path.exists("data/tablero_completo.db"):
    print("Descargando base de datos...")
    url = "https://tu-link-publico.com/tablero_completo.db"
    urllib.request.urlretrieve(url, "data/tablero_completo.db")
```

---

### Opción 3: Base de Datos Externa (Recomendada para Producción)
**Pros:**
- ✅ Persistencia garantizada
- ✅ Compartida entre local y Render
- ✅ No se pierde en reinicios
- ✅ Puedes actualizar desde cualquier lugar

**Contras:**
- ⚠️ Requiere servicio externo (Railway, Supabase, etc.)
- ⚠️ Cambios en código para usar PostgreSQL o SQLite remoto

**Servicios gratuitos:**
- **Railway**: PostgreSQL gratis (500 horas/mes)
- **Supabase**: PostgreSQL gratis (500MB)
- **Neon**: PostgreSQL gratis (3GB)

---

### Opción 4: Sincronización Manual (Actual)
**Cómo funciona:**
1. Sincronizas la BD localmente con `python src/database_completa.py`
2. Subes la BD actualizada a Render (opción 1 o 2)
3. Render usa esa BD hasta el próximo reinicio

**Problema:**
- ⚠️ En Render Free, la BD se pierde en cada reinicio
- ⚠️ Necesitas re-subirla manualmente

---

## 🎯 Recomendación Según Uso

### Si solo necesitas probar/desarrollo:
**Opción 1** (subir a git temporalmente) es la más simple

### Si necesitas producción estable:
**Opción 3** (BD externa) es la mejor

### Si quieres mantener la BD actual sincronizada:
**Opción 2** (nube + descarga) es un buen balance

