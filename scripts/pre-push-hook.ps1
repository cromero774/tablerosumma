#!/usr/bin/env pwsh
"""
Git hook para ejecutar antes de push
Colocar en .git/hooks/pre-push (o crear symlink)
"""
$ErrorActionPreference = "Stop"

# Ejecutar script de verificación
& "$PSScriptRoot\verificar_antes_de_push.ps1"

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n❌ Push cancelado. Corrige los problemas antes de continuar." -ForegroundColor Red
    exit 1
}

exit 0

