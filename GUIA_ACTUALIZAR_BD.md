# 🔄 Guía: Actualizar la Base de Datos para Render

## 📊 Tamaño Actual

La base de datos actualmente pesa aproximadamente **~51 MB** (`data/tablero_completo.db`).

Este tamaño puede variar según:
- Cantidad de issues sincronizadas
- Cantidad de worklogs
- Historial de transiciones
- Datos de changelog

---

## 🔄 Proceso de Actualización

### Opción 1: Actualización Completa (Recomendada)

**Cuándo usar:**
- Primera vez que subes la BD
- Después de mucho tiempo sin actualizar
- Cuando necesitas todos los datos históricos

**Pasos:**

1. **Sincronizar la base de datos localmente:**
   ```bash
   python src/database_completa.py
   ```
   
   O usar el script de actualización:
   ```bash
   python scripts/actualizar_bd_para_render.py
   ```

2. **Verificar el tamaño:**
   ```bash
   # Windows PowerShell
   powershell -Command "(Get-Item 'data\tablero_completo.db').Length / 1MB"
   ```

3. **Subir a Google Drive:**
   - Abre Google Drive
   - Reemplaza el archivo `tablero_completo.db` existente
   - O sube uno nuevo y actualiza el ID en Render

4. **Actualizar en Render:**
   - Si subiste un archivo nuevo, actualiza `GOOGLE_DRIVE_FILE_ID` en Render
   - Reinicia el servicio en Render (o espera al próximo reinicio)

**Tiempo estimado:** 40-60 minutos (sincronización completa)

---

### Opción 2: Actualización Incremental (Solo Nuevas Horas)

**Cuándo usar:**
- Actualizaciones periódicas (semanal, diaria)
- Solo necesitas agregar nuevas horas de trabajo
- Ya tienes todos los issues sincronizados

**Pasos:**

1. **Sincronizar solo nuevas horas:**
   ```python
   from src.database_completa import TableroDatabase
   
   db = TableroDatabase("data/tablero_completo.db")
   db.conectar()
   
   # Esto solo sincroniza worklogs nuevos desde la última vez
   db.sincronizar_worklogs_tempo(fecha_desde=None)
   
   db.cerrar()
   ```

2. **Subir a Google Drive** (igual que Opción 1)

**Tiempo estimado:** 5-15 minutos (solo nuevas horas)

---

## 📥 Subir a Google Drive

### Método 1: Reemplazar Archivo Existente

1. Ve a Google Drive
2. Busca `tablero_completo.db`
3. Click derecho → "Gestionar versiones" → "Subir nueva versión"
4. Selecciona el nuevo archivo
5. Espera a que termine la subida

**Ventaja:** El ID del archivo no cambia, no necesitas actualizar Render

### Método 2: Subir Archivo Nuevo

1. Ve a Google Drive
2. Sube el nuevo `tablero_completo.db`
3. Obtén el nuevo ID del archivo
4. Actualiza `GOOGLE_DRIVE_FILE_ID` en Render con el nuevo ID

---

## ⚙️ Automatización (Opcional)

### Script de Actualización Automática

Puedes crear un script que:
1. Sincronice la BD
2. La suba automáticamente a Google Drive (usando API)
3. Notifique cuando termine

**Ejemplo básico (requiere Google Drive API):**
```python
# scripts/actualizar_y_subir.py
from src.database_completa import TableroDatabase
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ... código de sincronización ...
# ... código de subida a Google Drive ...
```

---

## 🔍 Verificación

### Verificar que la BD se actualizó correctamente:

1. **Tamaño del archivo:**
   - Debe ser similar o mayor al anterior
   - Si es mucho menor, puede haber un problema

2. **Fecha de modificación:**
   - Debe ser reciente (hoy)

3. **Probar localmente:**
   ```bash
   # Abrir el tablero local
   streamlit run tablero.py
   # Verificar que los datos más recientes aparezcan
   ```

4. **Verificar en Render:**
   - Revisar logs para ver si se descargó correctamente
   - Verificar que el tamaño sea correcto
   - Probar que los datos más recientes aparezcan

---

## 📅 Frecuencia de Actualización Recomendada

### Para Desarrollo/Testing:
- **Semanal** o cuando necesites datos actualizados

### Para Producción:
- **Diaria** (automática si es posible)
- **O manual** cuando se necesite

### Actualización Automática:
- Puedes usar un cron job local (si tienes servidor siempre encendido)
- O un servicio como GitHub Actions (si tienes el repo en GitHub)
- O AWS Lambda + EventBridge (si ya usas AWS)

---

## ⚠️ Consideraciones

1. **Tamaño del archivo:**
   - Google Drive gratis: 15 GB
   - Tu BD: ~51 MB
   - Puedes tener muchas versiones sin problema

2. **Límites de descarga:**
   - Google Drive puede limitar descargas muy frecuentes
   - Si Render descarga muchas veces, puede haber problemas

3. **Velocidad:**
   - La descarga puede tomar 1-2 minutos en Render
   - La primera vez que se carga el tablero puede ser más lento

4. **Backup:**
   - Mantén una copia local de la BD
   - O guarda versiones en Google Drive

---

## 🚨 Troubleshooting

### Problema: La BD no se descarga en Render
- Verificar que `GOOGLE_DRIVE_FILE_ID` esté configurado correctamente
- Verificar que el archivo sea público (cualquiera con el link)
- Revisar logs de Render para ver el error

### Problema: La BD está vacía después de descargar
- Verificar que el archivo se descargó completamente (tamaño correcto)
- Verificar que la BD local tiene datos antes de subir

### Problema: La BD es muy grande (>100 MB)
- Considerar comprimir (aunque SQLite ya está optimizado)
- O migrar a PostgreSQL que maneja mejor archivos grandes

---

## 📝 Checklist de Actualización

- [ ] Sincronizar BD localmente
- [ ] Verificar tamaño del archivo
- [ ] Probar BD localmente (verificar datos)
- [ ] Subir a Google Drive
- [ ] Verificar que el archivo sea público
- [ ] Actualizar `GOOGLE_DRIVE_FILE_ID` en Render (si es archivo nuevo)
- [ ] Reiniciar servicio en Render
- [ ] Verificar logs de Render
- [ ] Probar tablero en Render (verificar datos)

