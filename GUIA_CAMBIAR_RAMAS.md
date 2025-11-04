# 🔀 Guía para Cambiar entre Ramas

## ✅ Problemas Solucionados

1. **Archivos `__pycache__` causando conflictos** - Limpieza automática
2. **Diferencias entre `main` y `feature/base-datos`** - Sincronizadas
3. **Error de credenciales al abrir tablero** - Solucionado

## 🚀 Proceso para Cambiar de Rama

### Opción 1: Automática (Recomendada)

El hook de git se ejecuta automáticamente después de cada `git checkout`:

```powershell
git checkout main
# o
git checkout feature/base-datos
```

El hook limpia automáticamente los archivos `__pycache__` y temporales.

### Opción 2: Manual

Si prefieres hacerlo manualmente antes de cambiar:

```powershell
# Limpiar archivos temporales
.\scripts\limpiar_al_cambiar_rama.ps1

# Cambiar de rama
git checkout main
# o
git checkout feature/base-datos
```

## 📋 Checklist antes de cambiar de rama

1. **Verificar que no hay cambios sin commit:**
   ```powershell
   git status
   ```
   Si hay cambios, hacer commit o stash:
   ```powershell
   git stash
   # o
   git commit -m "Mensaje del commit"
   ```

2. **Limpiar archivos temporales (automático o manual):**
   ```powershell
   .\scripts\limpiar_al_cambiar_rama.ps1
   ```

3. **Cambiar de rama:**
   ```powershell
   git checkout <rama>
   ```

## 🐛 Si hay errores al cambiar de rama

### Error: "Your local changes would be overwritten"

**Solución:**
```powershell
# Opción 1: Guardar cambios
git stash

# Opción 2: Descartar cambios (¡CUIDADO!)
git checkout -- <archivo>

# Opción 3: Commit los cambios
git commit -m "Mensaje"
```

### Error: Archivos `__pycache__` causando conflictos

**Solución:**
```powershell
# Limpiar manualmente
Remove-Item -Path src/__pycache__,src/tabs/__pycache__,src/utils/__pycache__ -Recurse -Force

# Luego cambiar de rama
git checkout <rama>
```

## 📝 Notas Importantes

- **`main`** y **`feature/base-datos`** ahora tienen el mismo `configuracion.py` (descarga en background)
- Los archivos `__pycache__` se limpian automáticamente al cambiar de rama
- El archivo `.env` debe estar presente en ambas ramas (local, no en git)
- Los archivos de base de datos (`data/tablero_completo.db`) se ignoran en git

## 🔧 Verificar que las ramas están sincronizadas

```powershell
# Ver diferencias en archivos .py
git diff main feature/base-datos --name-only -- "*.py"

# Si no hay salida, están sincronizadas ✅
```

## 🚨 Si necesitas forzar la sincronización

```powershell
# Desde feature/base-datos, traer cambios a main
git checkout main
git checkout feature/base-datos -- src/utils/configuracion.py
git commit -m "Sincronizar con feature/base-datos"
git push origin main
```

