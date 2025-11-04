#!/usr/bin/env pwsh
"""
Script para limpiar archivos temporales antes de cambiar de rama
Ejecutar antes de git checkout
"""
$ErrorActionPreference = "Continue"

Write-Host "🧹 Limpiando archivos temporales..." -ForegroundColor Cyan

# Limpiar __pycache__
$cache_dirs = @(
    "src/__pycache__",
    "src/tabs/__pycache__",
    "src/utils/__pycache__",
    "__pycache__"
)

foreach ($dir in $cache_dirs) {
    if (Test-Path $dir) {
        Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  ✅ Removido: $dir" -ForegroundColor Green
    }
}

# Limpiar archivos .pyc sueltos
Get-ChildItem -Path . -Filter "*.pyc" -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# Limpiar archivos temporales de base de datos (si existen)
$temp_db_files = @(
    "data/tablero_completo.db.tmp",
    "data/jira_database.db.tmp"
)

foreach ($file in $temp_db_files) {
    if (Test-Path $file) {
        Remove-Item -Path $file -Force -ErrorAction SilentlyContinue
        Write-Host "  ✅ Removido: $file" -ForegroundColor Green
    }
}

Write-Host "`n✅ Limpieza completada. Puedes cambiar de rama sin problemas." -ForegroundColor Green

