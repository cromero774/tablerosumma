# 📥 Guía: Usar Google Drive para la Base de Datos en Render

## Paso 1: Subir la Base de Datos a Google Drive

### 1.1 Preparar el archivo
La base de datos está en: `data/tablero_completo.db` (~51 MB)

### 1.2 Subir a Google Drive

**Método 1: Desde el navegador**
1. Ve a [Google Drive](https://drive.google.com)
2. Crea una carpeta llamada "Tablero SUMMA" (o cualquier nombre)
3. Arrastra `data/tablero_completo.db` a esa carpeta
4. Espera a que termine la subida

**Método 2: Desde la app de escritorio**
1. Instala Google Drive para Windows
2. Copia `data/tablero_completo.db` a la carpeta de Google Drive
3. Espera a que se sincronice

### 1.3 Obtener el ID del archivo

**Opción A: Desde el link compartido (Recomendada)**
1. Click derecho en `tablero_completo.db` en Google Drive
2. Selecciona "Obtener enlace" o "Compartir"
3. Marca "Cualquier persona con el enlace"
4. Copia el enlace. Debería verse así:
   ```
   https://drive.google.com/file/d/1ABC123xyz456DEF789/view?usp=sharing
   ```
5. El **ID del archivo** es la parte entre `/d/` y `/view`:
   ```
   1ABC123xyz456DEF789
   ```

**Opción B: Desde la URL del navegador**
1. Abre el archivo en Google Drive
2. Mira la URL en el navegador:
   ```
   https://drive.google.com/file/d/1ABC123xyz456DEF789/view
   ```
3. El ID es: `1ABC123xyz456DEF789`

### 1.4 Verificar que el archivo sea público
- El archivo debe ser accesible sin autenticación
- Marca "Cualquier persona con el enlace puede ver"

---

## Paso 2: Configurar en Render

### 2.1 Agregar Variable de Entorno

En Render Dashboard:
1. Ve a tu servicio → **Environment**
2. Agrega nueva variable:
   - **Key**: `GOOGLE_DRIVE_FILE_ID`
   - **Value**: El ID que obtuviste (ej: `1ABC123xyz456DEF789`)
3. Guarda los cambios

### 2.2 Verificar Variables Existentes

Asegúrate de tener estas variables configuradas:
- ✅ `JIRA_BASE_URL`
- ✅ `JIRA_EMAIL`
- ✅ `JIRA_API_TOKEN`
- ✅ `TEMPO_TOKEN`
- ✅ `GOOGLE_DRIVE_FILE_ID` (nueva)

---

## Paso 3: Probar el Deploy

### 3.1 Hacer Deploy
1. Push a master
2. Render hará el deploy automáticamente
3. La BD se descargará automáticamente al inicio

### 3.2 Verificar en los Logs

En Render Dashboard → **Logs**, deberías ver:
```
📥 Descargando base de datos desde Google Drive...
✅ Base de datos descargada (51.23 MB)
```

---

## 🔄 Actualizar la Base de Datos

Cuando necesites actualizar la BD:

1. **Sincronizar localmente:**
   ```bash
   python src/database_completa.py
   ```

2. **Subir a Google Drive:**
   - Reemplaza el archivo `tablero_completo.db` en Google Drive
   - O sube uno nuevo y actualiza el `GOOGLE_DRIVE_FILE_ID` en Render

3. **Reiniciar el servicio en Render:**
   - Render Dashboard → Manual Deploy → Clear build cache & deploy
   - O simplemente espera al próximo reinicio (se descargará automáticamente)

---

## ⚠️ Limitaciones de Google Drive

- **Tamaño máximo**: 15 GB gratis (tu BD es ~51 MB, no hay problema)
- **Límite de descarga**: Google puede limitar descargas muy frecuentes
- **Velocidad**: Puede ser más lenta que S3 o un servicio dedicado

---

## 🚀 Próximos Pasos: Migrar a PostgreSQL (AWS)

Cuando quieras migrar a PostgreSQL en AWS:

1. Ver archivo `GUIA_POSTGRESQL_AWS.md` (por crear)
2. Cambiar `DatabaseHelper` para usar PostgreSQL
3. Migrar datos de SQLite a PostgreSQL
4. Actualizar variables de entorno en Render

---

## 📝 Checklist

- [ ] BD subida a Google Drive
- [ ] ID del archivo obtenido
- [ ] Archivo marcado como público (cualquiera con el link)
- [ ] Variable `GOOGLE_DRIVE_FILE_ID` configurada en Render
- [ ] Deploy realizado
- [ ] BD descargada correctamente (verificar en logs)

