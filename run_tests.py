#!/usr/bin/env python3
"""
Script para ejecutar todos los tests del tablero
"""
import subprocess
import sys
from pathlib import Path

def run_tests():
    """Ejecutar todos los tests"""
    print("🧪 Ejecutando tests del tablero...")
    print("=" * 50)
    
    try:
        # Ejecutar pytest con verbose
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/", 
            "-v", 
            "--tb=short",
            "--color=yes"
        ], capture_output=True, text=True)
        
        # Mostrar output
        print(result.stdout)
        if result.stderr:
            print("Errores:")
            print(result.stderr)
        
        # Mostrar resultado final
        if result.returncode == 0:
            print("\n✅ ¡Todos los tests pasaron correctamente!")
        else:
            print(f"\n❌ {result.returncode} tests fallaron")
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Error ejecutando tests: {e}")
        return False

def run_specific_test(test_file):
    """Ejecutar un test específico"""
    print(f"🧪 Ejecutando test específico: {test_file}")
    print("=" * 50)
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            f"tests/{test_file}", 
            "-v", 
            "--tb=short",
            "--color=yes"
        ], capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("Errores:")
            print(result.stderr)
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Error ejecutando test: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Ejecutar test específico
        test_file = sys.argv[1]
        success = run_specific_test(test_file)
    else:
        # Ejecutar todos los tests
        success = run_tests()
    
    sys.exit(0 if success else 1)

