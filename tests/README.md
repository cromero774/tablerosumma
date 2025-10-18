# Tests del Tablero SUMMA

Este directorio contiene todos los tests para el tablero SUMMA modularizado.

## Estructura de Tests

### 📁 Archivos de Test

- **`test_imports.py`** - Tests para verificar que todos los imports funcionan correctamente
- **`test_configuracion.py`** - Tests unitarios para configuración y utilidades
- **`test_tabs_individual.py`** - Tests unitarios para cada pestaña individual
- **`test_integracion.py`** - Tests de integración para el tablero completo
- **`test_mocks.py`** - Tests con mocks para Jira y APIs externas

### 📁 Archivos de Configuración

- **`conftest.py`** - Configuración global para pytest con fixtures comunes
- **`__init__.py`** - Archivo para hacer del directorio un paquete Python

## 🚀 Ejecutar Tests

### Opción 1: Script automatizado
```bash
python run_tests.py
```

### Opción 2: pytest directamente
```bash
# Todos los tests
pytest tests/ -v

# Tests específicos
pytest tests/test_imports.py -v
pytest tests/test_configuracion.py -v
pytest tests/test_tabs_individual.py -v
pytest tests/test_integracion.py -v
pytest tests/test_mocks.py -v

# Con coverage
pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
```

### Opción 3: Tests por categoría
```bash
# Solo tests unitarios
pytest tests/ -m unit

# Solo tests de integración
pytest tests/ -m integration

# Solo tests con mocks
pytest tests/ -m mock
```

## 📋 Tipos de Tests

### 1. Tests de Imports (`test_imports.py`)
- ✅ Verifican que todos los módulos se importan correctamente
- ✅ Validan la estructura modular
- ✅ Confirman que las funciones están disponibles

### 2. Tests de Configuración (`test_configuracion.py`)
- ✅ Validan constantes y configuraciones
- ✅ Prueban funciones de carga de datos
- ✅ Verifican utilidades compartidas

### 3. Tests de Pestañas Individuales (`test_tabs_individual.py`)
- ✅ Cada pestaña se prueba de forma aislada
- ✅ Verifican que las funciones principales funcionan
- ✅ Usan mocks para dependencias externas

### 4. Tests de Integración (`test_integracion.py`)
- ✅ Prueban la integración entre componentes
- ✅ Validan el flujo completo de datos
- ✅ Verifican consistencia entre pestañas

### 5. Tests con Mocks (`test_mocks.py`)
- ✅ Simulan conexiones a Jira
- ✅ Mockean APIs de Tempo
- ✅ Prueban el sistema de cache
- ✅ Simulan Streamlit para testing

## 🔧 Fixtures Disponibles

### Fixtures de Datos
- `sample_dataframe` - DataFrame de ejemplo
- `sample_epicas_relevantes` - Datos de épicas de ejemplo
- `sample_issues_jira` - Issues de Jira de ejemplo

### Fixtures de Mocks
- `mock_jira` - Mock de conexión a Jira
- `mock_streamlit` - Mock de Streamlit
- `mock_tempo` - Mock de Tempo

## 📊 Coverage

Los tests incluyen cobertura de código para:
- ✅ Todas las pestañas (`src/tabs/`)
- ✅ Utilidades (`src/utils/`)
- ✅ Módulos principales (`src/`)
- ✅ Funciones de configuración

## 🐛 Debugging

### Ver output detallado
```bash
pytest tests/ -v -s
```

### Ver solo errores
```bash
pytest tests/ --tb=short
```

### Ejecutar un test específico
```bash
pytest tests/test_imports.py::TestImportsPrincipales::test_import_tablero_principal -v
```

## 📝 Agregar Nuevos Tests

### 1. Tests Unitarios
```python
def test_nueva_funcion():
    """Test para nueva función"""
    # Arrange
    input_data = "test"
    
    # Act
    result = nueva_funcion(input_data)
    
    # Assert
    assert result == "expected"
```

### 2. Tests con Mocks
```python
@patch('src.mi_modulo.funcion_externa')
def test_con_mock(mock_funcion):
    """Test con mock"""
    mock_funcion.return_value = "mocked"
    
    result = mi_funcion()
    
    assert result == "expected"
    mock_funcion.assert_called_once()
```

## 🎯 Objetivos de Testing

- **Cobertura**: >90% del código
- **Funcionalidad**: Todas las pestañas funcionan
- **Integración**: Flujo completo sin errores
- **Robustez**: Manejo de errores y casos edge
- **Mantenibilidad**: Tests claros y documentados

## 🔍 Troubleshooting

### Error: ModuleNotFoundError
```bash
# Asegurar que el path está correcto
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Error: ImportError
```bash
# Verificar que todos los módulos existen
python -c "import src.tabs.bugs; print('OK')"
```

### Error: Streamlit en tests
- Los tests usan mocks de Streamlit
- No se ejecuta la interfaz real
- Solo se prueban las funciones de lógica
