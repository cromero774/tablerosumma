# 🧪 Guía de Tests del Tablero

## ¿Qué son los tests?

Los tests son **verificaciones automáticas** que comprueban que tu código funciona correctamente. Es como tener un asistente que:
- ✅ Ejecuta tu código automáticamente
- ✅ Verifica que los resultados sean los esperados  
- ✅ Te avisa si algo se rompe cuando haces cambios

## ¿Qué tests tienes configurados?

### **1. Tests de Archivos de Datos** 📁
- Verifican que todos los archivos CSV y JSON existen
- Comprueban que se pueden leer correctamente
- Validan la estructura de los datos

### **2. Tests de Filtrado de Proyectos** 🔍
- Verifican que el filtrado REP/TAL funciona
- Comprueban que el filtrado ATI funciona
- Validan que los filtros excluyen datos incorrectos

### **3. Tests de Cálculos** 🧮
- Verifican que se pueden crear DataFrames
- Comprueban que el filtrado de datos funciona
- Validan la lógica de cálculos básicos

## ¿Cómo ejecutar los tests?

### **Opción 1: Usar el script automático** (Recomendado)
```bash
python run_tests.py
```

### **Opción 2: Usar pytest directamente**
```bash
pytest tests/ -v
```

### **Opción 3: Ejecutar un test específico**
```bash
python run_tests.py test_simple.py
```

## ¿Qué significa el resultado?

### **✅ Todos los tests pasaron**
```
============================= 10 passed in 0.52s ==============================
✅ ¡Todos los tests pasaron correctamente!
```
**Significa:** Todo está funcionando perfectamente. Puedes continuar con confianza.

### **❌ Algunos tests fallaron**
```
=========================== short test summary info ===========================
FAILED tests/test_simple.py::TestCalculations::test_calculation_logic
============================= 1 failed, 9 passed in 0.75s ==============================
```
**Significa:** Hay un problema que necesita ser corregido. El test te dice exactamente qué falló.

## ¿Cuándo ejecutar los tests?

### **Antes de hacer cambios importantes:**
- Ejecuta los tests para asegurarte de que todo funciona
- Haz tus cambios
- Ejecuta los tests nuevamente para verificar que no rompiste nada

### **Después de hacer cambios:**
- Siempre ejecuta los tests para verificar que todo sigue funcionando
- Si algún test falla, sabrás inmediatamente qué se rompió

### **Cuando algo no funciona:**
- Ejecuta los tests para ver si el problema está en los datos o en el código
- Los tests te ayudarán a identificar dónde está el problema

## ¿Cómo agregar nuevos tests?

Si quieres agregar un nuevo test, edita el archivo `tests/test_simple.py` y agrega una nueva función que empiece con `test_`:

```python
def test_mi_nueva_funcionalidad(self):
    """Test: Verificar que mi nueva funcionalidad funciona"""
    # Tu código de prueba aquí
    assert resultado == esperado
    print(f"✅ Mi funcionalidad funciona: {resultado}")
```

## ¿Qué hacer si un test falla?

1. **Lee el mensaje de error** - Te dice exactamente qué falló
2. **Revisa el código** - Busca el problema en la línea indicada
3. **Corrige el problema** - Haz los cambios necesarios
4. **Ejecuta los tests nuevamente** - Verifica que se corrigió

## Resumen

- **Los tests son tu red de seguridad** 🛡️
- **Ejecútalos antes y después de cambios** 🔄
- **Te avisan inmediatamente si algo se rompe** ⚠️
- **Son fáciles de ejecutar** - Solo un comando: `python run_tests.py`

¡Ahora tienes tests configurados y funcionando! 🎉

