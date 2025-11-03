# 🐘 Guía: Migrar a PostgreSQL en AWS (RDS)

## 📋 Prerequisitos

- Cuenta de AWS activa
- Acceso a AWS RDS (Relational Database Service)
- Conocimiento básico de AWS Console

---

## Paso 1: Crear Base de Datos PostgreSQL en AWS RDS

### 1.1 Acceder a RDS

1. Ve a [AWS Console](https://console.aws.amazon.com)
2. Busca "RDS" en el buscador
3. Click en "RDS" → "Databases"

### 1.2 Crear Base de Datos

1. Click en **"Create database"**
2. Selecciona:
   - **Engine type**: PostgreSQL
   - **Version**: PostgreSQL 15.x o superior (recomendado)
   - **Templates**: **Free tier** (si estás probando) o **Production**
   
3. **Settings**:
   - **DB instance identifier**: `tablero-summa-db`
   - **Master username**: `tablero_admin` (o el que prefieras)
   - **Master password**: Genera una contraseña segura (guárdala)

4. **Instance configuration**:
   - **Free tier**: `db.t3.micro` (1 vCPU, 1 GB RAM)
   - **Production**: `db.t3.small` o superior

5. **Storage**:
   - **Storage type**: General Purpose SSD (gp3)
   - **Allocated storage**: 20 GB (mínimo)

6. **Connectivity**:
   - **Public access**: ✅ **Yes** (para que Render pueda conectarse)
   - **VPC**: Default VPC
   - **Security group**: Crear nuevo (o usar existente)
   
   ⚠️ **IMPORTANTE**: Necesitarás configurar el Security Group para permitir conexiones desde Render

7. **Database authentication**: Password authentication

8. Click **"Create database"**

### 1.3 Esperar a que se cree

- Toma ~5-10 minutos
- Espera a que el estado sea **"Available"**

### 1.4 Obtener el Endpoint

1. En la lista de bases de datos, click en tu instancia
2. Copia el **Endpoint** (ej: `tablero-summa-db.xxxxx.us-east-1.rds.amazonaws.com`)
3. Copia el **Port** (por defecto: `5432`)

---

## Paso 2: Configurar Security Group

### 2.1 Acceder al Security Group

1. En la página de tu base de datos RDS
2. Ve a la pestaña **"Connectivity & security"**
3. Click en el **Security Group** (ej: `sg-xxxxx`)

### 2.2 Agregar Regla de Inbound

1. Click en **"Edit inbound rules"**
2. Click **"Add rule"**
3. Configura:
   - **Type**: PostgreSQL
   - **Protocol**: TCP
   - **Port**: 5432
   - **Source**: `0.0.0.0/0` (cualquier IP) ⚠️ **Solo para testing**
   
   Para producción, usa la IP de Render o un rango específico.

4. Click **"Save rules"**

---

## Paso 3: Crear Base de Datos y Tablas

### 3.1 Conectarse a PostgreSQL

**Desde tu máquina local:**
```bash
# Instalar cliente PostgreSQL (si no lo tienes)
# Windows: Descargar desde https://www.postgresql.org/download/windows/

# Conectarse
psql -h tablero-summa-db.xxxxx.us-east-1.rds.amazonaws.com -U tablero_admin -d postgres
```

O usar un cliente gráfico como:
- **pgAdmin** (recomendado)
- **DBeaver**
- **TablePlus**

### 3.2 Crear Base de Datos

```sql
CREATE DATABASE tablero_summa;
\c tablero_summa
```

### 3.3 Crear Tablas

Necesitarás adaptar el script `database_completa.py` para PostgreSQL, o exportar desde SQLite.

**Opción A: Usar script de migración** (por crear)
**Opción B: Exportar desde SQLite y importar a PostgreSQL**

---

## Paso 4: Modificar el Código para Usar PostgreSQL

### 4.1 Instalar psycopg2

Agregar a `requirements.txt`:
```
psycopg2-binary
```

### 4.2 Modificar DatabaseHelper

Crear `src/utils/database_helper_postgresql.py` que use:
```python
import psycopg2
from psycopg2.extras import RealDictCursor

class DatabaseHelper:
    def __init__(self):
        self.conn = None
        
    def conectar(self):
        self.conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD")
        )
        return self.conn
```

### 4.3 Adaptar Queries SQL

- SQLite usa `?` para parámetros, PostgreSQL usa `%s`
- Algunos tipos de datos pueden diferir
- Funciones SQL pueden ser diferentes

---

## Paso 5: Configurar Variables en Render

Agregar estas variables de entorno:

```
POSTGRES_HOST=tablero-summa-db.xxxxx.us-east-1.rds.amazonaws.com
POSTGRES_PORT=5432
POSTGRES_DB=tablero_summa
POSTGRES_USER=tablero_admin
POSTGRES_PASSWORD=tu_contraseña_segura
```

---

## Paso 6: Migrar Datos de SQLite a PostgreSQL

### Opción A: Script de Migración

Crear script que:
1. Lee desde SQLite (`data/tablero_completo.db`)
2. Escribe en PostgreSQL
3. Mantiene la estructura de tablas

### Opción B: Exportar/Importar

```bash
# Exportar desde SQLite
sqlite3 data/tablero_completo.db .dump > export.sql

# Adaptar SQL para PostgreSQL (puede requerir cambios)
# Importar a PostgreSQL
psql -h HOST -U USER -d DB < export.sql
```

---

## 💰 Costos Estimados

### Free Tier (Primeros 12 meses)
- **db.t3.micro**: Gratis (750 horas/mes)
- **20 GB storage**: Gratis
- **Total**: $0/mes

### Después del Free Tier
- **db.t3.micro**: ~$15/mes
- **20 GB storage**: ~$2.30/mes
- **Backups**: ~$2/mes
- **Total**: ~$20/mes

### Producción (db.t3.small)
- **db.t3.small**: ~$30/mes
- **Storage**: Variable según uso
- **Total**: ~$35-50/mes

---

## ✅ Ventajas de PostgreSQL

- ✅ **Persistencia garantizada**: No se pierde en reinicios
- ✅ **Mejor rendimiento**: Para consultas complejas
- ✅ **Escalabilidad**: Fácil de escalar
- ✅ **Backups automáticos**: Configurables en RDS
- ✅ **Monitoreo**: CloudWatch incluido
- ✅ **Seguridad**: Encriptación, VPC, etc.

---

## 📝 Checklist

- [ ] Base de datos PostgreSQL creada en RDS
- [ ] Security Group configurado
- [ ] Base de datos y tablas creadas
- [ ] Código modificado para usar PostgreSQL
- [ ] Variables de entorno configuradas en Render
- [ ] Datos migrados desde SQLite
- [ ] Pruebas realizadas
- [ ] Backup configurado

---

## 🔄 Próximos Pasos

1. Probar con Google Drive primero
2. Si funciona bien, migrar a PostgreSQL
3. Configurar backups automáticos en RDS
4. Configurar monitoreo en CloudWatch

