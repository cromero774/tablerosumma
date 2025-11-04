# 🚀 Guía de Deployment a Render

## ✅ Checklist antes de hacer push a main

### 1. Verificar archivos grandes o no deseados

**NUNCA hacer commit de:**
- `data/tablero_completo.db` (base de datos - se descarga desde Google Drive)
- `data/jira_database.db`
- `data/cache/*.pkl` (archivos de cache)
- `*.pkl` (archivos pickle)
- `__pycache__/` (archivos compilados de Python)
- `*.pyc`
- `.env.backup` o cualquier backup de `.env`

### 2. Usar el script de verificación

```powershell
# Ejecutar antes de hacer push
.\scripts\verificar_antes_de_push.ps1
```

### 3. Verificar .gitignore

Asegurarse de que `.gitignore` incluye:
```
data/tablero_completo.db
data/jira_database.db
data/cache/*.pkl
*.pkl
__pycache__/
*.pyc
.env
.env.backup
```

### 4. Proceso de merge a main

**SIEMPRE seguir estos pasos:**

1. **Verificar cambios en feature/base-datos:**
   ```powershell
   git checkout feature/base-datos
   git status
   ```

2. **Verificar que no hay archivos grandes en staging:**
   ```powershell
   git diff --cached --name-only | Select-String -Pattern "\.(db|pkl|pyc)$"
   ```
   Si hay resultados, removerlos:
   ```powershell
   git reset HEAD <archivo>
   ```

3. **Cambiar a main:**
   ```powershell
   git checkout main
   git pull origin main
   ```

4. **Hacer merge SOLO de archivos .py:**
   ```powershell
   git merge feature/base-datos --no-commit --no-ff
   git reset HEAD data/ src/*/__pycache__/ .env.backup 2>$null
   git commit -m "Merge feature/base-datos (solo código fuente)"
   ```

5. **Verificar antes de push:**
   ```powershell
   .\scripts\verificar_antes_de_push.ps1
   ```

6. **Hacer push:**
   ```powershell
   git push origin main
   ```

## 🔧 Si ya se agregaron archivos grandes por error

### Opción 1: Remover del último commit (si no se hizo push)

```powershell
git reset --soft HEAD~1
git reset HEAD data/tablero_completo.db data/cache/*.pkl
git commit -m "Mensaje corregido"
```

### Opción 2: Remover del historial (si ya se hizo push)

**⚠️ ADVERTENCIA: Esto reescribe el historial. Solo hacer si es necesario.**

```powershell
# Limpiar historial de feature/base-datos
git checkout feature/base-datos
git filter-branch --force --index-filter "git rm --cached --ignore-unmatch data/tablero_completo.db data/cache/*.pkl .env.backup src/*/__pycache__/*.pyc -r" --prune-empty --tag-name-filter cat -- --all
git push origin feature/base-datos --force
```

## 📋 Verificación en Render

Después del push, verificar en Render:

1. **Logs de deployment:**
   - Buscar "✅ Base de datos descargada exitosamente desde Google Drive"
   - NO debe aparecer "Timed Out"

2. **Health check:**
   - La app debe responder en menos de 30 segundos
   - No debe mostrar errores de timeout

3. **Funcionalidad:**
   - Verificar que las pestañas cargan correctamente
   - Verificar que la fecha de actualización se muestra

## 🐛 Problemas comunes

### "Large files detected" al hacer push

**Causa:** Archivos grandes en el historial de commits

**Solución:**
1. Verificar qué archivos están causando el problema
2. Removerlos del staging con `git reset HEAD <archivo>`
3. Asegurarse de que están en `.gitignore`
4. Rehacer el commit

### Timeout en Render

**Causa:** Descarga síncrona de la BD bloqueando el inicio

**Solución:** Verificar que `configuracion.py` usa descarga en background (threading)

### BD no se descarga en Render

**Causa:** Variable de entorno `GOOGLE_DRIVE_FILE_ID` no configurada

**Solución:** Configurar en Render Dashboard → Environment → Add Environment Variable

## 📝 Notas importantes

- **NUNCA** hacer commit de archivos de base de datos o cache
- La BD se descarga automáticamente desde Google Drive en Render
- Si necesitas actualizar la BD en Google Drive, subirla manualmente y actualizar el ID si cambió
- Los archivos `.pkl` de cache son generados automáticamente y no deben estar en git

