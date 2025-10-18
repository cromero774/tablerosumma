#!/usr/bin/env python3
"""
Script para ejecutar todos los tests del tablero SUMMA
"""

import subprocess
import sys
import os

def run_tests():
    """Ejecutar todos los tests"""
    
    print("🧪 Ejecutando tests del Tablero SUMMA...")
    print("=" * 50)
    
    # Verificar que pytest está instalado
    try:
        import pytest
        print(f"✅ pytest {pytest.__version__} encontrado")
    except ImportError:
        print("❌ pytest no está instalado. Instalando...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-test.txt"])
    
    # Ejecutar tests con diferentes niveles de verbosidad
    test_commands = [
        {
            "name": "Tests básicos",
            "command": [sys.executable, "-m", "pytest", "tests/test_basicos.py", "-v"]
        },
        {
            "name": "Tests de imports",
            "command": [sys.executable, "-m", "pytest", "tests/test_imports.py", "-v"]
        },
        {
            "name": "Tests con mocks",
            "command": [sys.executable, "-m", "pytest", "tests/test_mocks.py", "-v"]
        },
        {
            "name": "Tests funcionales existentes",
            "command": [sys.executable, "-m", "pytest", "tests/test_simple.py", "tests/test_bugs_duplication.py", "tests/test_bugs_fix.py", "-v"]
        },
        {
            "name": "Todos los tests funcionales",
            "command": [sys.executable, "-m", "pytest", "tests/test_basicos.py", "tests/test_imports.py", "tests/test_mocks.py", "tests/test_simple.py", "tests/test_bugs_duplication.py", "tests/test_bugs_fix.py", "-v"]
        }
    ]
    
    results = []
    
    for test in test_commands:
        print(f"\n🔍 Ejecutando: {test['name']}")
        print("-" * 30)
        
        try:
            result = subprocess.run(test["command"], capture_output=True, text=True)
            results.append({
                "name": test["name"],
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            })
            
            if result.returncode == 0:
                print(f"✅ {test['name']} - PASSED")
            else:
                print(f"❌ {test['name']} - FAILED")
                if result.stderr:
                    print(f"Error: {result.stderr}")
                    
        except Exception as e:
            print(f"❌ Error ejecutando {test['name']}: {e}")
            results.append({
                "name": test["name"],
                "success": False,
                "output": "",
                "error": str(e)
            })
    
    # Resumen final
    print("\n" + "=" * 50)
    print("📊 RESUMEN DE TESTS")
    print("=" * 50)
    
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    
    for result in results:
        status = "✅ PASSED" if result["success"] else "❌ FAILED"
        print(f"{status} - {result['name']}")
    
    print(f"\n🎯 Resultado final: {passed}/{total} tests pasaron")
    
    if passed == total:
        print("🎉 ¡Todos los tests pasaron exitosamente!")
        return True
    else:
        print("⚠️  Algunos tests fallaron. Revisa los errores arriba.")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)