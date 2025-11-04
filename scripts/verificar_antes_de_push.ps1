#!/usr/bin/env pwsh
"""
Script para verificar que no haya archivos grandes o no deseados antes de hacer push
"""
$ErrorActionPreference = "Stop"

Write-Host "🔍 Verificando archivos antes de push..." -ForegroundColor Cyan

# Verificar archivos grandes en staging
$staged_files = git diff --cached --name-only
if ($staged_files) {
    Write-Host "`n📦 Archivos en staging:" -ForegroundColor Yellow
    $staged_files | ForEach-Object { Write-Host "  - $_" }
    
    # Verificar archivos grandes o no deseados
    $problemas = @()
    foreach ($file in $staged_files) {
        # Verificar tamaño (más de 1MB)
        $size = (Get-Item $file -ErrorAction SilentlyContinue).Length
        if ($size -and $size -gt 1MB) {
            $size_mb = [math]::Round($size / 1MB, 2)
            $problemas += "❌ $file es muy grande ($size_mb MB)"
        }
        
        # Verificar extensiones no deseadas
        if ($file -match '\.(db|pkl|pyc)$|__pycache__|\.env\.backup') {
            $problemas += "❌ $file no debería estar en git"
        }
    }
    
    if ($problemas.Count -gt 0) {
        Write-Host "`n⚠️ PROBLEMAS ENCONTRADOS:" -ForegroundColor Red
        $problemas | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        Write-Host "`n💡 SOLUCIÓN:" -ForegroundColor Yellow
        Write-Host "  1. Remover del staging: git reset HEAD <archivo>" -ForegroundColor Yellow
        Write-Host "  2. Verificar .gitignore incluye estos archivos" -ForegroundColor Yellow
        Write-Host "  3. Volver a hacer commit solo con archivos .py" -ForegroundColor Yellow
        exit 1
    }
}

# Verificar que .gitignore esté actualizado
$gitignore_content = Get-Content .gitignore -Raw -ErrorAction SilentlyContinue
$required_patterns = @(
    "data/tablero_completo.db",
    "data/jira_database.db",
    "data/cache/",
    "*.pkl",
    "__pycache__/",
    "*.pyc",
    ".env"
)

$faltantes = @()
foreach ($pattern in $required_patterns) {
    if ($gitignore_content -notmatch [regex]::Escape($pattern)) {
        $faltantes += $pattern
    }
}

if ($faltantes.Count -gt 0) {
    Write-Host "`n⚠️ .gitignore no incluye:" -ForegroundColor Red
    $faltantes | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host "`n💡 Agregar estos patrones a .gitignore" -ForegroundColor Yellow
    exit 1
}

Write-Host "`n✅ Todo está correcto. Puedes hacer push." -ForegroundColor Green
exit 0

