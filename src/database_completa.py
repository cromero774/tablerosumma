#!/usr/bin/env python3
"""
Script único para gestión completa de base de datos SQLite del Tablero SUMMA
Incluye: creación de tablas, sincronización con Jira/Tempo, cálculos de métricas
"""

import sqlite3
import json
import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class TableroDatabase:
    def __init__(self, db_path: str = "data/tablero_completo.db"):
        self.db_path = db_path
        self.conn = None
        
        # Cargar variables de entorno
        load_dotenv()
        
        self.jira_base_url = os.getenv("JIRA_BASE_URL")
        self.jira_email = os.getenv("JIRA_EMAIL")
        self.jira_token = os.getenv("JIRA_API_TOKEN")
        self.tempo_token = os.getenv("TEMPO_TOKEN")
        
        # Validar variables críticas
        if not self.jira_base_url:
            print("⚠️ JIRA_BASE_URL no encontrado en .env")
        if not self.jira_email:
            print("⚠️ JIRA_EMAIL no encontrado en .env")
        if not self.jira_token:
            print("⚠️ JIRA_API_TOKEN no encontrado en .env")
        if not self.tempo_token:
            print("⚠️ TEMPO_TOKEN no encontrado en .env")
        
    def conectar(self):
        """Conectar a la base de datos SQLite"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Para acceso por nombre de columna
        
        # Verificar y actualizar esquema si es necesario
        self._actualizar_esquema()
        
        return self.conn
    
    def _actualizar_esquema(self):
        """Actualizar esquema de la base de datos si es necesario"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(issues)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Columnas nuevas que necesitamos agregar
            nuevas_columnas = [
                ('issue_links', 'TEXT'),
                ('subtasks', 'TEXT'),
                ('sprint', 'TEXT'),
                ('version', 'TEXT'),
                ('tempo_project', 'TEXT'),
                ('proyecto_logico', 'TEXT')
            ]
            
            # Agregar columnas faltantes
            for col_name, col_type in nuevas_columnas:
                if col_name not in columns:
                    print(f"🔄 Agregando columna {col_name} a tabla issues...")
                    cursor.execute(f"ALTER TABLE issues ADD COLUMN {col_name} {col_type}")
            
            # Verificar si existe tabla mapeo_proyectos
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mapeo_proyectos'")
            if not cursor.fetchone():
                print("🔄 Creando tabla mapeo_proyectos...")
                cursor.execute("""
                    CREATE TABLE mapeo_proyectos (
                        tem_key TEXT PRIMARY KEY,
                        proyecto_tempo TEXT NOT NULL,
                        proyecto_normalizado TEXT NOT NULL,
                        area TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            
            # Verificar si existe tabla calculos_temporales
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='calculos_temporales'")
            if not cursor.fetchone():
                print("🔄 Creando tabla calculos_temporales...")
                cursor.execute("""
                    CREATE TABLE calculos_temporales (
                        issue_key TEXT PRIMARY KEY,
                        tiempo_resolucion_horas REAL,
                        tiempo_en_progreso_horas REAL,
                        bugs_asociados INTEGER DEFAULT 0,
                        es_bloqueante BOOLEAN DEFAULT 0,
                        tipo_bug TEXT,
                        fecha_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (issue_key) REFERENCES issues(key)
                    )
                """)
            
            # Verificar si existe tabla issue_transitions
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='issue_transitions'")
            if not cursor.fetchone():
                print("🔄 Creando tabla issue_transitions...")
                cursor.execute("""
                    CREATE TABLE issue_transitions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        issue_key TEXT NOT NULL,
                        from_status TEXT,
                        to_status TEXT,
                        transition_date TIMESTAMP NOT NULL,
                        is_testing BOOLEAN DEFAULT 0,
                        is_progress BOOLEAN DEFAULT 0,
                        is_done BOOLEAN DEFAULT 0,
                        changed_by TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (issue_key) REFERENCES issues(key),
                        UNIQUE(issue_key, transition_date)
                    )
                """)
            
            self.conn.commit()
            print("✅ Esquema actualizado correctamente")
            
        except Exception as e:
            print(f"⚠️ Error actualizando esquema: {e}")
            self.conn.rollback()
    
    def cerrar(self):
        """Cerrar conexión a la base de datos"""
        if self.conn:
            self.conn.close()
    
    def crear_tablas(self):
        """Crear todas las tablas de la base de datos"""
        cursor = self.conn.cursor()
        
        # 1. TABLA USUARIOS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                account_id TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                email TEXT,
                display_name TEXT,
                activo BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. TABLA ÉPICAS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS epicas (
                rn TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                mes_entrega TEXT,
                proyecto TEXT,
                estado TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 3. TABLA ISSUES
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                key TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                status TEXT NOT NULL,
                project TEXT NOT NULL,
                issuetype TEXT NOT NULL,
                assignee_id TEXT,
                parent_key TEXT,
                epic_link TEXT,
                story_points INTEGER,
                priority TEXT,
                duedate DATE,
                created_date TIMESTAMP,
                updated_date TIMESTAMP,
                resolution_date TIMESTAMP,
                status_category_changed_date TIMESTAMP,
                labels TEXT, -- JSON array
                fix_versions TEXT, -- JSON array
                custom_fields TEXT, -- JSON object
                issue_links TEXT, -- JSON array para vinculaciones
                subtasks TEXT, -- JSON array de subtareas
                sprint TEXT, -- Sprint actual
                version TEXT, -- Versión asignada
                tempo_project TEXT, -- Proyecto Tempo mapeado
                proyecto_logico TEXT, -- Proyecto normalizado según reglas
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assignee_id) REFERENCES usuarios(account_id),
                FOREIGN KEY (parent_key) REFERENCES issues(key),
                FOREIGN KEY (epic_link) REFERENCES epicas(rn)
            )
        """)
        
        # 4. TABLA MAPEO_PROYECTOS (para reglas de negocio)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mapeo_proyectos (
                tem_key TEXT PRIMARY KEY,
                proyecto_tempo TEXT NOT NULL,
                proyecto_normalizado TEXT NOT NULL,
                area TEXT NOT NULL, -- ATI, POSTVENTA, INTERNO
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 5. TABLA CALCULOS_TEMPORALES (para métricas calculadas)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calculos_temporales (
                issue_key TEXT PRIMARY KEY,
                tiempo_resolucion_horas REAL,
                tiempo_en_progreso_horas REAL,
                bugs_asociados INTEGER DEFAULT 0,
                es_bloqueante BOOLEAN DEFAULT 0,
                tipo_bug TEXT, -- KINETIC, MEJORA, etc.
                fecha_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (issue_key) REFERENCES issues(key)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS worklogs (
                tempo_worklog_id TEXT PRIMARY KEY,
                issue_key TEXT NOT NULL,
                author_id TEXT NOT NULL,
                time_spent_seconds INTEGER NOT NULL,
                time_spent_hours REAL NOT NULL,
                start_date DATE NOT NULL,
                description TEXT,
                tempo_account TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (issue_key) REFERENCES issues(key),
                FOREIGN KEY (author_id) REFERENCES usuarios(account_id)
            )
        """)
        
        # 6. TABLA TRANSICIONES DE ESTADO
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issue_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_key TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT,
                transition_date TIMESTAMP NOT NULL,
                is_testing BOOLEAN DEFAULT 0,
                is_progress BOOLEAN DEFAULT 0,
                is_done BOOLEAN DEFAULT 0,
                changed_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (issue_key) REFERENCES issues(key),
                UNIQUE(issue_key, transition_date)
            )
        """)
        
        # 7. TABLA MÉTRICAS POR RN (PRE-CALCULADAS)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metricas_por_rn (
                rn TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                mes_entrega TEXT,
                total_historias INTEGER DEFAULT 0,
                historias_completadas INTEGER DEFAULT 0,
                total_puntos INTEGER DEFAULT 0,
                puntos_completados INTEGER DEFAULT 0,
                total_bugs INTEGER DEFAULT 0,
                bugs_resueltos INTEGER DEFAULT 0,
                bugs_uat INTEGER DEFAULT 0,
                bugs_dcr INTEGER DEFAULT 0,
                horas_totales REAL DEFAULT 0.0,
                velocidad_promedio REAL DEFAULT 0.0,
                avance_porcentaje REAL DEFAULT 0.0,
                tiempo_promedio_resolucion REAL DEFAULT 0.0,
                bugs_por_historia REAL DEFAULT 0.0,
                fecha_ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rn) REFERENCES epicas(rn)
            )
        """)
        
        # 7. TABLA MÉTRICAS POR USUARIO (PRE-CALCULADAS)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metricas_por_usuario (
                account_id TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                total_horas REAL DEFAULT 0.0,
                total_issues INTEGER DEFAULT 0,
                issues_completados INTEGER DEFAULT 0,
                bugs_resueltos INTEGER DEFAULT 0,
                velocidad_promedio REAL DEFAULT 0.0,
                proyectos_trabajados TEXT, -- JSON array
                fecha_ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES usuarios(account_id)
            )
        """)
        
        # 8. TABLA MÉTRICAS POR PROYECTO (PRE-CALCULADAS)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metricas_por_proyecto (
                proyecto TEXT PRIMARY KEY,
                total_issues INTEGER DEFAULT 0,
                issues_completados INTEGER DEFAULT 0,
                total_horas REAL DEFAULT 0.0,
                bugs_abiertos INTEGER DEFAULT 0,
                bugs_cerrados INTEGER DEFAULT 0,
                velocidad_promedio REAL DEFAULT 0.0,
                fecha_ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 9. TABLA MÉTRICAS POR MES (PRE-CALCULADAS)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metricas_por_mes (
                mes TEXT NOT NULL, -- "2025-01"
                proyecto TEXT NOT NULL,
                total_horas REAL DEFAULT 0.0,
                total_issues INTEGER DEFAULT 0,
                bugs_resueltos INTEGER DEFAULT 0,
                velocidad_promedio REAL DEFAULT 0.0,
                fecha_ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (mes, proyecto)
            )
        """)
        
        # CREAR ÍNDICES PARA RENDIMIENTO
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_project ON issues(project)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_assignee ON issues(assignee_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_epic ON issues(epic_link)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transitions_issue ON issue_transitions(issue_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_worklogs_issue ON worklogs(issue_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_worklogs_author ON worklogs(author_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_worklogs_date ON worklogs(start_date)")
        
        self.conn.commit()
        print("✅ Tablas creadas exitosamente")
    
    def cargar_usuarios_desde_json(self, json_path: str = "data/accountid_to_name.json"):
        """Cargar usuarios desde archivo JSON"""
        if not os.path.exists(json_path):
            print(f"⚠️ Archivo {json_path} no encontrado")
            return
        
        with open(json_path, 'r', encoding='utf-8') as f:
            usuarios_data = json.load(f)
        
        cursor = self.conn.cursor()
        for account_id, nombre in usuarios_data.items():
            cursor.execute("""
                INSERT OR REPLACE INTO usuarios (account_id, nombre, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (account_id, nombre))
        
        self.conn.commit()
        print(f"✅ {len(usuarios_data)} usuarios cargados")
    
    def cargar_epicas_desde_json(self, json_path: str = "data/epicas_relevantes.json"):
        """Cargar épicas desde archivo JSON"""
        if not os.path.exists(json_path):
            print(f"⚠️ Archivo {json_path} no encontrado")
            return
        
        with open(json_path, 'r', encoding='utf-8') as f:
            epicas_data = json.load(f)
        
        cursor = self.conn.cursor()
        for epica in epicas_data:
            cursor.execute("""
                INSERT OR REPLACE INTO epicas (rn, nombre, mes_entrega, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (epica['rn'], epica['nombre'], epica.get('mes_entrega', '')))
        
        self.conn.commit()
        print(f"✅ {len(epicas_data)} épicas cargadas")
    
    def cargar_mapeo_proyectos(self):
        """Cargar mapeo de proyectos según reglas de negocio"""
        print("🔄 Cargando mapeo de proyectos...")
        
        cursor = self.conn.cursor()
        
        # MAPEO_TEM según reglas de negocio
        mapeo_tem = {
            "TEM-1": ("CORE-TECH", "TECH LAB - INTERNO", "INTERNO"),
            "TEM-2": ("CORE-TECH", "TECH LAB - INTERNO", "INTERNO"),
            "TEM-5": ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - ESCRITURA RF POSVENTA", "POSTVENTA"),
            "TEM-7": ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO MODULO REPUESTOS", "POSTVENTA"),
            "TEM-8": ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO ATI", "ATI"),
            "TEM-9": ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO MODULO TALLER", "POSTVENTA"),
            "TEM-28": ("CORE-TECH", "TECH LAB - INTERNO", "INTERNO"),
            "TEM-30": ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - ESCRITURA RF ATI", "ATI"),
        }
        
        # RESUMEN_A_PROYECTO según reglas de negocio
        resumen_a_proyecto = {
            "MAIPU - SUMMA - ESCRITURA RF POSVENTA": ("AFUS", "POSTVENTA"),
            "MAIPU - SUMMA - DESARROLLO MODULO REPUESTOS": ("REPUESTOS MAIPU", "POSTVENTA"),
            "MAIPU - SUMMA - DESARROLLO MODULO TALLER": ("TALLER - MAIPÚ -", "POSTVENTA"),
            "MAIPU - SUMMA - DESARROLLO ATI": ("AFUs ATI", "ATI"),
            "MAIPU - SUMMA - ESCRITURA RF ATI": ("AFUs ATI", "ATI"),
            "TECH LAB - INTERNO": ("TECH LAB - INTERNO", "INTERNO"),
        }
        
        # Insertar mapeo TEM
        for tem_key, (proyecto_tempo, proyecto_normalizado, area) in mapeo_tem.items():
            cursor.execute("""
                INSERT OR REPLACE INTO mapeo_proyectos (
                    tem_key, proyecto_tempo, proyecto_normalizado, area
                ) VALUES (?, ?, ?, ?)
            """, (tem_key, proyecto_tempo, proyecto_normalizado, area))
        
        # Insertar resumen a proyecto
        for proyecto_tempo, (proyecto_normalizado, area) in resumen_a_proyecto.items():
            cursor.execute("""
                INSERT OR REPLACE INTO mapeo_proyectos (
                    tem_key, proyecto_tempo, proyecto_normalizado, area
                ) VALUES (?, ?, ?, ?)
            """, (f"RESUMEN_{proyecto_tempo}", proyecto_tempo, proyecto_normalizado, area))
        
        self.conn.commit()
        print(f"✅ Mapeo de proyectos cargado")
    
    def sincronizar_issues_jira(self, proyectos: List[str] = ["REP", "TAL", "ATI", "BUG"]):
        """Sincronizar issues desde Jira usando la conexión existente del tablero"""
        print("🔄 Sincronizando issues desde Jira...")
        
        try:
            # Usar la conexión existente del tablero
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from src.jira_conexion import get_jira
            jira = get_jira()
            
            total_proyectos = len(proyectos)
            for i, proyecto in enumerate(proyectos):
                print(f"  📋 Procesando proyecto {proyecto} ({i+1}/{total_proyectos})...")
                
                # Usar JQL específico según el proyecto (como en el tablero real)
                if proyecto == "BUG":
                    # Bugs UAT - SIN CHANGELOG (se carga después)
                    jql = 'project = BUG ORDER BY created DESC'
                    fields = "key,issuetype,created,project,summary,status,priority,labels,issuelinks,assignee,parent,updated,customfield_10016"
                    issues = self._traer_todas_las_issues(jira, jql, fields, max_results=5000)
                else:
                    # Proyectos normales - historias Y errors SIN CHANGELOG (se carga después)
                    # INCLUYENDO subtasks para cálculo de porcentaje de avance
                    jql = f'project = {proyecto} AND (issuetype = Historia OR issuetype = Error) ORDER BY created DESC'
                    fields = "key,summary,status,project,issuetype,assignee,parent,customfield_10016,customfield_10026,duedate,statuscategorychangedate,updated,created,resolutiondate,priority,labels,fixVersions,issuelinks,customfield_10021,subtasks"
                    issues = self._traer_todas_las_issues(jira, jql, fields, max_results=5000)
                
                if not issues:
                    print(f"    ⚠️ No se encontraron issues para {proyecto}")
                    continue
                
                cursor = self.conn.cursor()
                print(f"    📥 Insertando {len(issues)} issues de {proyecto} en la base de datos...")
                for issue in issues:
                    fields_data = issue.get('fields', {})
                
                    # Extraer datos del issue
                    assignee = fields_data.get('assignee', {})
                    assignee_id = assignee.get('accountId') if assignee else None
                    
                    parent = fields_data.get('parent', {})
                    parent_key = parent.get('key') if parent else None
                    
                    epic_link = fields_data.get('customfield_10016')
                    story_points = fields_data.get('customfield_10026')
                    
                    labels = json.dumps(fields_data.get('labels', []))
                    fix_versions = json.dumps([v.get('name', '') for v in fields_data.get('fixVersions', [])])
                    
                    custom_fields = {
                        'customfield_10016': epic_link,
                        'customfield_10026': story_points
                    }
                    
                    # Extraer campos adicionales
                    issue_links = json.dumps(fields_data.get('issuelinks', []))
                    subtasks = json.dumps(fields_data.get('subtasks', []))
                    sprint = self._extraer_sprint(fields_data)
                    version = self._extraer_version(fields_data)
                    tempo_project = self._mapear_proyecto_tempo(fields_data)
                    proyecto_logico = self._normalizar_proyecto(fields_data)
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO issues (
                            key, summary, status, project, issuetype, assignee_id, parent_key,
                            epic_link, story_points, priority, duedate, created_date, updated_date,
                            resolution_date, status_category_changed_date, labels, fix_versions,
                            custom_fields, issue_links, subtasks, sprint, version, tempo_project, proyecto_logico,
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        issue['key'],
                        fields_data.get('summary', ''),
                        fields_data.get('status', {}).get('name', ''),
                        fields_data.get('project', {}).get('key', ''),
                        fields_data.get('issuetype', {}).get('name', ''),
                        assignee_id,
                        parent_key,
                        epic_link,
                        story_points,
                        fields_data.get('priority', {}).get('name', ''),
                        fields_data.get('duedate'),
                        fields_data.get('created'),
                        fields_data.get('updated'),
                        fields_data.get('resolutiondate'),
                        fields_data.get('statuscategorychangedate'),
                        labels,
                        fix_versions,
                        json.dumps(custom_fields),
                        issue_links,
                        subtasks,
                        sprint,
                        version,
                        tempo_project,
                        proyecto_logico
                    ))
                
                # Commit de las issues ANTES de procesar changelog
                self.conn.commit()
                print(f"    ✅ {len(issues)} issues de {proyecto} insertadas en la base de datos")
                
                # Procesar changelog para calcular métricas temporales (POR LOTES)
                print(f"    🔄 Procesando changelog para métricas temporales (POR LOTES) del proyecto {proyecto}...")
                print(f"    ⚠️  Esto puede tomar varios minutos - procesando {len(issues)} issues del proyecto {proyecto}...")
                self._procesar_changelog_por_lotes(jira, issues, len(issues), proyecto)
                
                # Procesar transiciones de estado
                print(f"    🔄 Procesando transiciones de estado del proyecto {proyecto}...")
                self._procesar_transiciones(issues, len(issues))
                
                # Commit final de transiciones
                self.conn.commit()
                print(f"    ✅ {len(issues)} issues de {proyecto} sincronizados con changelog y transiciones")
        
        except Exception as e:
            print(f"❌ Error sincronizando issues: {e}")
    
    def _traer_todas_las_issues(self, jira, jql, fields, max_results=5000):
        """Traer todas las issues usando la misma lógica del tablero"""
        print(f"    🔄 Cargando issues básicas (sin changelog)...")
        issues = []
        batch_size = 100  # Jira tiene límite máximo de 100 por request
        
        # Convertir fields de string a lista si es necesario
        if isinstance(fields, str):
            fields_list = [f.strip() for f in fields.split(",") if f.strip()]
        else:
            fields_list = fields
        
        batch_num = 0
        token = None
        
        while len(issues) < max_results:
            batch_num += 1
            
            # Llamar a search_jql directamente
            data = jira.search_jql(jql=jql, fields=fields_list, max_results=batch_size, next_page_token=token)
            
            batch = data.get("issues", [])
            
            if not batch:  # No hay más issues
                print(f"    📊 No hay más issues disponibles (total encontradas: {len(issues)})")
                break
                
            issues.extend(batch)
            
            # Obtener el token para la siguiente página
            token = data.get("nextPageToken")
            
            progress_pct = min(100, (len(issues) / max_results) * 100)
            print(f"    📊 Cargadas {len(issues)} issues... ({progress_pct:.1f}% - Lote {batch_num})")
            
            # Si no hay más páginas
            if not token:
                print(f"    📊 Último lote recibido (total issues: {len(issues)})")
                break
            
        print(f"    ✅ Total issues básicas cargadas: {len(issues)}")
        return issues
    
    def _traer_todas_las_issues_con_changelog(self, jira, jql, fields, max_results=5000):
        """Traer todas las issues CON CHANGELOG usando la misma lógica del tablero"""
        print(f"    🔄 Cargando issues con changelog (esto puede tomar varios minutos)...")
        issues, start_at = [], 0
        batch_size = 100  # Jira tiene límite máximo de 100 por request
        
        # Calcular progreso estimado
        total_batches = (max_results + batch_size - 1) // batch_size
        
        while len(issues) < max_results:
            batch_num = (start_at // batch_size) + 1
            progress_pct = min(100, (batch_num / total_batches) * 100)
            
            # Note: changelog se descarga lote por lote, no en esta función
            # Esta función NO se usa actualmente, se usa _traer_todas_las_issues + procesar changelog por lotes
            endpoint = f'search?jql={jql}&fields={fields}&startAt={start_at}&maxResults={batch_size}&expand=changelog'
            data = jira._get_json(endpoint)
            batch = data.get("issues", [])
            
            if not batch:  # No hay más issues
                break
                
            issues.extend(batch)
            
            # Si el lote es menor que batch_size, no hay más páginas
            if len(batch) < batch_size:
                break
                
            start_at += batch_size
            print(f"    📊 Cargadas {len(issues)} issues... ({progress_pct:.1f}% - Lote {batch_num}/{total_batches})")
            
        print(f"    ✅ Total issues con changelog cargadas: {len(issues)}")
        return issues
    
    def obtener_changelog_issue(self, jira, issue_key):
        """Obtener changelog de una issue específica cuando se necesite"""
        try:
            endpoint = f'issue/{issue_key}?expand=changelog'
            return jira._get(endpoint)
        except Exception as e:
            print(f"❌ Error obteniendo changelog para {issue_key}: {e}")
            return None
    
    def calcular_tiempos_estado(self, jira, issue_key):
        """Calcular tiempos de estado desde changelog"""
        issue_data = self.obtener_changelog_issue(jira, issue_key)
        if not issue_data:
            return None, None
            
        changelog = issue_data.get('changelog', {})
        histories = changelog.get('histories', [])
        
        # Patrones de estados según el tablero
        TODO_PATTERNS = ("to do", "por hacer", "pendiente", "backlog", "asignados a backlog")
        PROGRESS_PATTERNS = ("in progress", "haciendo", "desarroll", "en curso", "working", "asignado a desarrollo")
        DONE_PATTERNS = ("cerrad", "done", "resuelt", "hech", "closed")
        
        start_dt, end_dt = None, None
        
        for hist in histories:
            h_created = pd.to_datetime(hist.get('created'), errors='coerce')
            for item in hist.get('items', []):
                if item.get('field') != 'status':
                    continue
                    
                to_str = (item.get('toString') or '').lower()
                from_str = (item.get('fromString') or '').lower()
                
                if start_dt is None:
                    sale_de_todo = any(p in from_str for p in TODO_PATTERNS) and not any(p in to_str for p in TODO_PATTERNS)
                    entra_en_prog = any(p in to_str for p in PROGRESS_PATTERNS)
                    if sale_de_todo or entra_en_prog:
                        start_dt = h_created
                
                if end_dt is None and any(p in to_str for p in DONE_PATTERNS):
                    end_dt = h_created
        
        # Calcular horas
        tiempo_resolucion = None
        tiempo_en_progreso = None
        
        if start_dt and end_dt:
            tiempo_resolucion = (end_dt - start_dt).total_seconds() / 3600
        elif start_dt:
            tiempo_en_progreso = (datetime.now() - start_dt).total_seconds() / 3600
            
        return tiempo_resolucion, tiempo_en_progreso
    
    def _procesar_transiciones(self, issues, total_issues):
        """Procesar todas las transiciones de estado desde el changelog"""
        cursor = self.conn.cursor()
        
        # Estados de testing según velocidad_devs.py
        STATUS_TESTING = {"en testing", "testing", "qa", "en test", "pruebas", "ready for qa", "ready for testing"}
        STATUS_PROGRESS = {"in progress", "haciendo", "desarroll", "en curso", "working", "asignado a desarrollo"}
        STATUS_DONE = {"cerrad", "done", "resuelt", "hech", "closed"}
        
        for i, issue in enumerate(issues):
            if (i + 1) % 500 == 0 or (i + 1) == total_issues:
                print(f"      📊 Transiciones: {i+1}/{total_issues} ({((i+1)/total_issues)*100:.1f}%)")
            
            issue_key = issue['key']
            changelog = issue.get('changelog', {})
            histories = changelog.get('histories', [])
            
            if not histories:
                continue
            
            for hist in histories:
                transition_date = pd.to_datetime(hist.get('created', ''), errors='coerce')
                if pd.isna(transition_date):
                    continue
                
                # Convertir Timestamp a string para SQLite
                transition_date_str = transition_date.strftime('%Y-%m-%d %H:%M:%S')
                
                author = hist.get('author', {})
                changed_by = author.get('displayName', '') if author else ''
                
                for item in hist.get('items', []):
                    if item.get('field') == 'status':
                        from_status = item.get('fromString', '')
                        to_status = item.get('toString', '')
                        
                        # Detectar tipos de transición
                        is_testing = to_status.lower() in STATUS_TESTING
                        is_progress = to_status.lower() in STATUS_PROGRESS
                        is_done = to_status.lower() in STATUS_DONE
                        
                        # Insertar transición
                        try:
                            cursor.execute("""
                                INSERT OR IGNORE INTO issue_transitions (
                                    issue_key, from_status, to_status, transition_date,
                                    is_testing, is_progress, is_done, changed_by
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (issue_key, from_status, to_status, transition_date_str,
                                  is_testing, is_progress, is_done, changed_by))
                        except Exception as e:
                            print(f"        ⚠️ Error insertando transición para {issue_key}: {e}")
    
    def _procesar_changelog_por_lotes(self, jira, issues, total_issues, proyecto=None):
        """Procesar changelog por lotes pequeños para evitar timeouts"""
        cursor = self.conn.cursor()
        lote_size = 50  # Procesar de a 50 issues por vez
        total_lotes = (total_issues + lote_size - 1) // lote_size
        
        proyecto_prefix = f"{proyecto} - " if proyecto else ""
        
        for lote_num in range(total_lotes):
            inicio = lote_num * lote_size
            fin = min(inicio + lote_size, total_issues)
            lote_issues = issues[inicio:fin]
            
            print(f"      📊 {proyecto_prefix}Procesando lote {lote_num + 1}/{total_lotes} (issues {inicio + 1}-{fin})...")
            
            for i, issue in enumerate(lote_issues):
                issue_key = issue['key']
                fields_data = issue.get('fields', {})
                
                try:
                    # Obtener changelog individual para esta issue
                    changelog_data = self.obtener_changelog_issue(jira, issue_key)
                    if changelog_data:
                        # AGREGAR EL CHANGELOG A LA ISSUE para que _procesar_transiciones pueda usarlo
                        issue['changelog'] = changelog_data.get('changelog', {})
                        
                        # Calcular tiempos de estado desde changelog
                        tiempo_resolucion, tiempo_en_progreso = self._calcular_tiempos_desde_changelog_completo(changelog_data)
                        
                        # Detectar tipo de bug y si es bloqueante
                        tipo_bug = None
                        es_bloqueante = False
                        if fields_data.get('issuetype', {}).get('name') == 'Bug':
                            tipo_bug = self._detectar_tipo_bug(fields_data)
                            es_bloqueante = self._es_bug_bloqueante(fields_data)
                        
                        # Contar bugs asociados (para historias)
                        bugs_asociados = 0
                        if fields_data.get('issuetype', {}).get('name') == 'Historia':
                            bugs_asociados = self._contar_bugs_asociados(issue_key)
                        
                        # Insertar/actualizar cálculos temporales
                        cursor.execute("""
                            INSERT OR REPLACE INTO calculos_temporales (
                                issue_key, tiempo_resolucion_horas, tiempo_en_progreso_horas,
                                bugs_asociados, es_bloqueante, tipo_bug, fecha_calculo
                            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (issue_key, tiempo_resolucion, tiempo_en_progreso, bugs_asociados, es_bloqueante, tipo_bug))
                    
                except Exception as e:
                    print(f"        ⚠️ Error procesando {issue_key}: {e}")
                    continue
            
            # Commit después de cada lote
            self.conn.commit()
            print(f"      ✅ {proyecto_prefix}Lote {lote_num + 1}/{total_lotes} completado")
    
    def _calcular_tiempos_desde_changelog_completo(self, changelog_data):
        """Calcular tiempos de estado desde changelog completo con manejo de timezone"""
        changelog = changelog_data.get('changelog', {})
        histories = changelog.get('histories', [])
        
        if not histories:
            return None, None
        
        # Patrones de estados según el tablero
        TODO_PATTERNS = ("to do", "por hacer", "pendiente", "backlog", "asignados a backlog")
        PROGRESS_PATTERNS = ("in progress", "haciendo", "desarroll", "en curso", "working", "asignado a desarrollo")
        DONE_PATTERNS = ("cerrad", "done", "resuelt", "hech", "closed")
        
        start_dt, end_dt = None, None
        
        for hist in histories:
            # Manejar timezone correctamente
            h_created_str = hist.get('created', '')
            try:
                h_created = pd.to_datetime(h_created_str, errors='coerce')
                # Convertir a naive datetime si es necesario
                if h_created.tzinfo is not None:
                    h_created = h_created.replace(tzinfo=None)
            except:
                continue
                
            for item in hist.get('items', []):
                if item.get('field') != 'status':
                    continue
                    
                to_str = (item.get('toString') or '').lower()
                from_str = (item.get('fromString') or '').lower()
                
                if start_dt is None:
                    sale_de_todo = any(p in from_str for p in TODO_PATTERNS) and not any(p in to_str for p in TODO_PATTERNS)
                    entra_en_prog = any(p in to_str for p in PROGRESS_PATTERNS)
                    if sale_de_todo or entra_en_prog:
                        start_dt = h_created
                
                if end_dt is None and any(p in to_str for p in DONE_PATTERNS):
                    end_dt = h_created
        
        # Calcular horas
        tiempo_resolucion = None
        tiempo_en_progreso = None
        
        if start_dt and end_dt:
            tiempo_resolucion = (end_dt - start_dt).total_seconds() / 3600
        elif start_dt:
            tiempo_en_progreso = (datetime.now() - start_dt).total_seconds() / 3600
            
        return tiempo_resolucion, tiempo_en_progreso
    
    def _procesar_changelog_para_metricas(self, issues, total_issues):
        """Procesar changelog de issues para calcular métricas temporales"""
        cursor = self.conn.cursor()
        
        for i, issue in enumerate(issues):
            issue_key = issue['key']
            fields_data = issue.get('fields', {})
            
            # Mostrar progreso cada 100 issues
            if (i + 1) % 100 == 0 or (i + 1) == total_issues:
                progress_pct = ((i + 1) / total_issues) * 100
                print(f"      📊 Procesando changelog: {i+1}/{total_issues} ({progress_pct:.1f}%)")
            
            # Calcular tiempos de estado desde changelog
            tiempo_resolucion, tiempo_en_progreso = self._calcular_tiempos_desde_changelog(issue)
            
            # Detectar tipo de bug y si es bloqueante
            tipo_bug = None
            es_bloqueante = False
            if fields_data.get('issuetype', {}).get('name') == 'Bug':
                tipo_bug = self._detectar_tipo_bug(fields_data)
                es_bloqueante = self._es_bug_bloqueante(fields_data)
            
            # Contar bugs asociados (para historias)
            bugs_asociados = 0
            if fields_data.get('issuetype', {}).get('name') == 'Historia':
                bugs_asociados = self._contar_bugs_asociados(issue_key)
            
            # Insertar/actualizar cálculos temporales
            cursor.execute("""
                INSERT OR REPLACE INTO calculos_temporales (
                    issue_key, tiempo_resolucion_horas, tiempo_en_progreso_horas,
                    bugs_asociados, es_bloqueante, tipo_bug, fecha_calculo
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (issue_key, tiempo_resolucion, tiempo_en_progreso, bugs_asociados, es_bloqueante, tipo_bug))
    
    def _calcular_tiempos_desde_changelog(self, issue):
        """Calcular tiempos de estado desde changelog de la issue"""
        changelog = issue.get('changelog', {})
        histories = changelog.get('histories', [])
        
        if not histories:
            return None, None
        
        # Patrones de estados según el tablero
        TODO_PATTERNS = ("to do", "por hacer", "pendiente", "backlog", "asignados a backlog")
        PROGRESS_PATTERNS = ("in progress", "haciendo", "desarroll", "en curso", "working", "asignado a desarrollo")
        DONE_PATTERNS = ("cerrad", "done", "resuelt", "hech", "closed")
        
        start_dt, end_dt = None, None
        
        for hist in histories:
            h_created = pd.to_datetime(hist.get('created'), errors='coerce')
            for item in hist.get('items', []):
                if item.get('field') != 'status':
                    continue
                    
                to_str = (item.get('toString') or '').lower()
                from_str = (item.get('fromString') or '').lower()
                
                if start_dt is None:
                    sale_de_todo = any(p in from_str for p in TODO_PATTERNS) and not any(p in to_str for p in TODO_PATTERNS)
                    entra_en_prog = any(p in to_str for p in PROGRESS_PATTERNS)
                    if sale_de_todo or entra_en_prog:
                        start_dt = h_created
                
                if end_dt is None and any(p in to_str for p in DONE_PATTERNS):
                    end_dt = h_created
        
        # Calcular horas
        tiempo_resolucion = None
        tiempo_en_progreso = None
        
        if start_dt and end_dt:
            tiempo_resolucion = (end_dt - start_dt).total_seconds() / 3600
        elif start_dt:
            tiempo_en_progreso = (datetime.now() - start_dt).total_seconds() / 3600
            
        return tiempo_resolucion, tiempo_en_progreso
    
    def _detectar_tipo_bug(self, fields_data):
        """Detectar tipo de bug (KINETIC, MEJORA, etc.)"""
        labels = fields_data.get('labels', [])
        if not labels:
            return None
            
        labels_str = " ".join(labels).upper()
        if "KINETIC" in labels_str:
            return "KINETIC"
        elif "MEJORA" in labels_str:
            return "MEJORA"
        return None
    
    def _es_bug_bloqueante(self, fields_data):
        """Detectar si un bug es bloqueante por prioridad"""
        priority = fields_data.get('priority', {}).get('name', '')
        priority_str = priority.upper()
        return "MUY ALTA" in priority_str or "HIGHEST" in priority_str or "CRITICAL" in priority_str
    
    def _contar_bugs_asociados(self, issue_key):
        """Contar bugs asociados a una historia"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM issues 
            WHERE parent_key = ? AND issuetype = 'Error'
        """, (issue_key,))
        return cursor.fetchone()[0] or 0
    
    def _extraer_sprint(self, fields_data):
        """Extraer sprint de los campos de la issue"""
        # Buscar en customfield_10021 (Sprint)
        sprint_field = fields_data.get('customfield_10021')
        if sprint_field and isinstance(sprint_field, list) and len(sprint_field) > 0:
            return sprint_field[0].get('name', '')
        return None
    
    def _extraer_version(self, fields_data):
        """Extraer versión de los campos de la issue"""
        fix_versions = fields_data.get('fixVersions', [])
        if fix_versions and len(fix_versions) > 0:
            return fix_versions[0].get('name', '')
        return None
    
    def _mapear_proyecto_tempo(self, fields_data):
        """Mapear proyecto Tempo según reglas de negocio"""
        # Esta función se implementaría basándose en los worklogs
        # Por ahora retorna None, se puede implementar después
        return None
    
    def _normalizar_proyecto(self, fields_data):
        """Normalizar proyecto según reglas de negocio"""
        project_key = fields_data.get('project', {}).get('key', '')
        
        # Normalización según reglas
        if project_key in ['REP', 'TAL']:
            return 'POSTVENTA'
        elif project_key == 'ATI':
            return 'ATI'
        elif project_key == 'BUG':
            return 'UAT'
        else:
            return 'INTERNO'
    
    def sincronizar_worklogs_tempo(self, dias_atras: int = 90):
        """Sincronizar worklogs desde Tempo API + CSV histórico"""
        print("🔄 Sincronizando worklogs desde Tempo API + CSV histórico...")
        
        cursor = self.conn.cursor()
        total_worklogs = 0
        
        # 1. Cargar datos de Tempo API (últimos 3 meses)
        print("  📊 Cargando datos recientes desde Tempo API...")
        fecha_fin = datetime.now().date()
        fecha_inicio = fecha_fin - timedelta(days=dias_atras)
        
        worklogs_tempo = self._consultar_tempo_api(fecha_inicio, fecha_fin)
        
        if worklogs_tempo:
            for worklog in worklogs_tempo:
                author = worklog.get('author', {})
                author_id = author.get('accountId')
                
                issue = worklog.get('issue', {})
                issue_key = issue.get('key')
                
                time_spent_seconds = worklog.get('timeSpentSeconds', 0)
                time_spent_hours = time_spent_seconds / 3600.0 if time_spent_seconds else 0.0
                
                start_date = worklog.get('startDate')
                if 'T' in start_date:
                    start_date = start_date.split('T')[0]
                
                tempo_account = self._extraer_tempo_account(worklog)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO worklogs (
                        tempo_worklog_id, issue_key, author_id, time_spent_seconds,
                        time_spent_hours, start_date, description, tempo_account, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    worklog.get('tempoWorklogId', ''),
                    issue_key,
                    author_id,
                    time_spent_seconds,
                    time_spent_hours,
                    start_date,
                    worklog.get('description', ''),
                    tempo_account
                ))
            
            total_worklogs += len(worklogs_tempo)
            print(f"    ✅ {len(worklogs_tempo)} worklogs de Tempo API cargados")
        else:
            print("    ⚠️ No se encontraron worklogs en Tempo API")
        
        # 2. Cargar datos históricos y actuales desde CSV (igual que cargar_datos_principales)
        print("  📊 Cargando datos históricos y actuales desde CSV...")
        hist_path = "data/horas_historicas.csv"
        actual_path = "data/horas_con_proyecto.csv"
        
        # Cargar y combinar CSVs igual que cargar_datos_principales
        if os.path.exists(hist_path) and os.path.exists(actual_path):
            try:
                df_hist = pd.read_csv(hist_path)
                df_actual = pd.read_csv(actual_path)
                min_fecha_actual = pd.to_datetime(df_actual["Fecha"], errors="coerce").min()
                df_hist["Fecha_dt"] = pd.to_datetime(df_hist["Fecha"], errors="coerce")
                df_hist = df_hist[df_hist["Fecha_dt"] < min_fecha_actual]
                df_hist = df_hist.drop(columns="Fecha_dt")
                df_historico = pd.concat([df_hist, df_actual], ignore_index=True)
                
                # Deduplicar: si hay registros idénticos (issue+fecha+usuario+horas) con diferentes TempoWorklogId,
                # mantener solo el primero (para evitar duplicados en la BD)
                df_historico['_grupo_contenido'] = (
                    df_historico['Issue'].astype(str) + '_' + 
                    df_historico['Fecha'].astype(str) + '_' + 
                    df_historico['Usuario'].astype(str) + '_' + 
                    df_historico['Horas'].astype(str)
                )
                df_historico = df_historico.drop_duplicates(subset=['_grupo_contenido'], keep='first')
                df_historico = df_historico.drop(columns='_grupo_contenido')
            except Exception as e:
                print(f"    ⚠️ Error combinando CSVs: {e}")
                if os.path.exists(actual_path):
                    df_historico = pd.read_csv(actual_path)
                else:
                    df_historico = pd.DataFrame()
        elif os.path.exists(actual_path):
            df_historico = pd.read_csv(actual_path)
        elif os.path.exists(hist_path):
            df_historico = pd.read_csv(hist_path)
        else:
            df_historico = pd.DataFrame()
        
        if not df_historico.empty:
            try:
                filas_procesadas = 0
                filas_omitidas = 0
                
                # Generar IDs únicos para registros sin TempoWorklogId
                # Agrupar por issue+fecha+usuario y agregar contador para hacer único cada worklog
                def generar_id_unico(row, contador):
                    tempo_wid = str(row.get('TempoWorklogId', '')).strip()
                    if not tempo_wid or tempo_wid == 'nan':
                        issue_key = str(row.get('Issue', '')).strip()
                        fecha = str(row.get('Fecha', '')).strip()
                        usuario = str(row.get('Usuario', '')).strip()
                        return f"csv_noid_{issue_key}_{fecha}_{usuario}_{contador}"
                    else:
                        return f"csv_{tempo_wid}"
                
                # Contar cuántos hay de cada combinación para asignar contadores
                df_historico['grupo'] = df_historico.apply(
                    lambda row: f"{row.get('Issue', '')}_{row.get('Fecha', '')}_{row.get('Usuario', '')}", 
                    axis=1
                )
                contadores = {}
                
                for _, row in df_historico.iterrows():
                    # Validar datos requeridos
                    issue_key = str(row.get('Issue', '')).strip()
                    usuario = str(row.get('Usuario', '')).strip()
                    fecha = str(row.get('Fecha', '')).strip()
                    
                    # Saltar filas con datos faltantes críticos
                    if not issue_key or not usuario or not fecha or issue_key == 'nan' or usuario == 'nan' or fecha == 'nan':
                        filas_omitidas += 1
                        continue
                    
                    # Convertir datos del CSV al formato de la base
                    tempo_wid = str(row.get('TempoWorklogId', '')).strip()
                    if not tempo_wid or tempo_wid == 'nan':
                        # Sin TempoWorklogId, usar contador secuencial para hacer único
                        grupo = f"{issue_key}_{fecha}_{usuario}"
                        if grupo not in contadores:
                            contadores[grupo] = 0
                        contadores[grupo] += 1
                        tempo_worklog_id = f"csv_noid_{issue_key}_{fecha}_{usuario}_{contadores[grupo]}"
                    else:
                        tempo_worklog_id = f"csv_{tempo_wid}"
                    
                    try:
                        horas = float(row.get('Horas', 0))
                        cursor.execute("""
                            INSERT OR REPLACE INTO worklogs (
                                tempo_worklog_id, issue_key, author_id, time_spent_seconds,
                                time_spent_hours, start_date, description, tempo_account, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (
                            tempo_worklog_id,
                            issue_key,
                            usuario,
                            int(horas * 3600),  # Convertir horas a segundos
                            horas,
                            fecha,
                            f"CSV histórico - {row.get('Proyecto', '')}",
                            row.get('Cuenta', '')
                        ))
                        filas_procesadas += 1
                    except (ValueError, TypeError) as e:
                        print(f"    ⚠️ Error procesando fila CSV: {e}")
                        filas_omitidas += 1
                        continue
                
                total_worklogs += filas_procesadas
                print(f"    ✅ {filas_procesadas} worklogs históricos del CSV cargados")
                if filas_omitidas > 0:
                    print(f"    ⚠️ {filas_omitidas} filas omitidas por datos faltantes")
                
            except Exception as e:
                print(f"    ❌ Error cargando CSV: {e}")
        else:
            print("    ⚠️ No se encontraron archivos CSV de horas")
        
        self.conn.commit()
        print(f"✅ Total: {total_worklogs} worklogs sincronizados (Tempo API + CSV histórico)")
    
    def sincronizar_worklogs_csv_solo(self):
        """Sincronizar solo worklogs desde CSV histórico y actual"""
        print("🔄 Sincronizando worklogs desde CSV histórico y actual...")
        
        cursor = self.conn.cursor()
        
        # Limpiar worklogs existentes de CSV antes de recargar (para evitar duplicados de sincronizaciones anteriores)
        print("  🗑️  Limpiando worklogs existentes de CSV...")
        cursor.execute("DELETE FROM worklogs WHERE tempo_worklog_id LIKE 'csv_%'")
        registros_eliminados = cursor.rowcount
        print(f"    ✅ {registros_eliminados} registros CSV antiguos eliminados")
        self.conn.commit()
        hist_path = "data/horas_historicas.csv"
        actual_path = "data/horas_con_proyecto.csv"
        
        # Cargar y combinar CSVs igual que cargar_datos_principales
        if os.path.exists(hist_path) and os.path.exists(actual_path):
            try:
                df_hist = pd.read_csv(hist_path)
                df_actual = pd.read_csv(actual_path)
                min_fecha_actual = pd.to_datetime(df_actual["Fecha"], errors="coerce").min()
                df_hist["Fecha_dt"] = pd.to_datetime(df_hist["Fecha"], errors="coerce")
                df_hist = df_hist[df_hist["Fecha_dt"] < min_fecha_actual]
                df_hist = df_hist.drop(columns="Fecha_dt")
                df_csv = pd.concat([df_hist, df_actual], ignore_index=True)
                
                # Deduplicar: si hay registros idénticos (issue+fecha+usuario+horas) con diferentes TempoWorklogId,
                # mantener solo el primero (para evitar duplicados en la BD)
                df_csv['_grupo_contenido'] = (
                    df_csv['Issue'].astype(str) + '_' + 
                    df_csv['Fecha'].astype(str) + '_' + 
                    df_csv['Usuario'].astype(str) + '_' + 
                    df_csv['Horas'].astype(str)
                )
                df_csv = df_csv.drop_duplicates(subset=['_grupo_contenido'], keep='first')
                df_csv = df_csv.drop(columns='_grupo_contenido')
            except Exception as e:
                print(f"    ⚠️ Error combinando CSVs: {e}")
                if os.path.exists(actual_path):
                    df_csv = pd.read_csv(actual_path)
                else:
                    df_csv = pd.DataFrame()
        elif os.path.exists(actual_path):
            df_csv = pd.read_csv(actual_path)
        elif os.path.exists(hist_path):
            df_csv = pd.read_csv(hist_path)
        else:
            df_csv = pd.DataFrame()
        
        if not df_csv.empty:
            try:
                filas_procesadas = 0
                filas_omitidas = 0
                
                # Generar IDs únicos para registros sin TempoWorklogId usando contador
                contadores = {}
                
                for _, row in df_csv.iterrows():
                    # Validar datos requeridos
                    issue_key = str(row.get('Issue', '')).strip()
                    usuario = str(row.get('Usuario', '')).strip()
                    fecha = str(row.get('Fecha', '')).strip()
                    
                    # Saltar filas con datos faltantes críticos
                    if not issue_key or not usuario or not fecha or issue_key == 'nan' or usuario == 'nan' or fecha == 'nan':
                        filas_omitidas += 1
                        continue
                    
                    # Convertir datos del CSV al formato de la base
                    tempo_wid = str(row.get('TempoWorklogId', '')).strip()
                    if not tempo_wid or tempo_wid == 'nan':
                        # Sin TempoWorklogId, usar contador secuencial para hacer único
                        grupo = f"{issue_key}_{fecha}_{usuario}"
                        if grupo not in contadores:
                            contadores[grupo] = 0
                        contadores[grupo] += 1
                        tempo_worklog_id = f"csv_noid_{issue_key}_{fecha}_{usuario}_{contadores[grupo]}"
                    else:
                        tempo_worklog_id = f"csv_{tempo_wid}"
                    
                    try:
                        horas = float(row.get('Horas', 0))
                        cursor.execute("""
                            INSERT OR REPLACE INTO worklogs (
                                tempo_worklog_id, issue_key, author_id, time_spent_seconds,
                                time_spent_hours, start_date, description, tempo_account, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (
                            tempo_worklog_id,
                            issue_key,
                            usuario,
                            int(horas * 3600),  # Convertir horas a segundos
                            horas,
                            fecha,
                            f"CSV histórico - {row.get('Proyecto', '')}",
                            row.get('Cuenta', '')
                        ))
                        filas_procesadas += 1
                    except (ValueError, TypeError) as e:
                        print(f"    ⚠️ Error procesando fila CSV: {e}")
                        filas_omitidas += 1
                        continue
                
                self.conn.commit()
                print(f"    ✅ {filas_procesadas} worklogs históricos del CSV cargados")
                if filas_omitidas > 0:
                    print(f"    ⚠️ {filas_omitidas} filas omitidas por datos faltantes")
                
            except Exception as e:
                print(f"    ❌ Error cargando CSV: {e}")
        else:
            print("    ⚠️ No se encontraron archivos CSV de horas")
    
    def calcular_metricas_por_rn(self):
        """Calcular métricas pre-calculadas por RN"""
        print("🔄 Calculando métricas por RN...")
        
        cursor = self.conn.cursor()
        
        # Obtener todas las épicas
        cursor.execute("SELECT rn, nombre, mes_entrega FROM epicas")
        epicas = cursor.fetchall()
        
        for epica in epicas:
            rn = epica['rn']
            nombre = epica['nombre']
            mes_entrega = epica['mes_entrega']
            
            # Contar historias
            cursor.execute("""
                SELECT COUNT(*) as total, 
                       SUM(CASE WHEN status IN ('Done', 'Closed', 'Resolved') THEN 1 ELSE 0 END) as completadas,
                       SUM(COALESCE(story_points, 0)) as total_puntos,
                       SUM(CASE WHEN status IN ('Done', 'Closed', 'Resolved') THEN COALESCE(story_points, 0) ELSE 0 END) as puntos_completados
                FROM issues 
                WHERE epic_link = ? AND issuetype = 'Historia'
            """, (rn,))
            
            hist_result = cursor.fetchone()
            
            # Contar bugs
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status IN ('Done', 'Closed', 'Resolved') THEN 1 ELSE 0 END) as resueltos
                FROM issues 
                WHERE epic_link = ? AND issuetype = 'Error'
            """, (rn,))
            
            bug_result = cursor.fetchone()
            
            # Contar horas
            cursor.execute("""
                SELECT SUM(time_spent_hours) as total_horas
                FROM worklogs w
                JOIN issues i ON w.issue_key = i.key
                WHERE i.epic_link = ?
            """, (rn,))
            
            horas_result = cursor.fetchone()
            
            # Calcular métricas
            total_historias = hist_result['total'] or 0
            historias_completadas = hist_result['completadas'] or 0
            total_puntos = hist_result['total_puntos'] or 0
            puntos_completados = hist_result['puntos_completados'] or 0
            total_bugs = bug_result['total'] or 0
            bugs_resueltos = bug_result['resueltos'] or 0
            horas_totales = horas_result['total_horas'] or 0.0
            
            avance_porcentaje = (historias_completadas / total_historias * 100) if total_historias > 0 else 0
            velocidad_promedio = (puntos_completados / horas_totales) if horas_totales > 0 else 0
            bugs_por_historia = (total_bugs / total_historias) if total_historias > 0 else 0
            
            # Insertar/actualizar métricas
            cursor.execute("""
                INSERT OR REPLACE INTO metricas_por_rn (
                    rn, nombre, mes_entrega, total_historias, historias_completadas,
                    total_puntos, puntos_completados, total_bugs, bugs_resueltos,
                    horas_totales, avance_porcentaje, velocidad_promedio, bugs_por_historia,
                    fecha_ultima_actualizacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                rn, nombre, mes_entrega, total_historias, historias_completadas,
                total_puntos, puntos_completados, total_bugs, bugs_resueltos,
                horas_totales, avance_porcentaje, velocidad_promedio, bugs_por_historia
            ))
        
        self.conn.commit()
        print(f"✅ Métricas calculadas para {len(epicas)} RNs")
    
    def calcular_metricas_por_usuario(self):
        """Calcular métricas pre-calculadas por usuario"""
        print("🔄 Calculando métricas por usuario...")
        
        cursor = self.conn.cursor()
        
        # Obtener todos los usuarios
        cursor.execute("SELECT account_id, nombre FROM usuarios")
        usuarios = cursor.fetchall()
        
        for usuario in usuarios:
            account_id = usuario['account_id']
            nombre = usuario['nombre']
            
            # Métricas de horas
            cursor.execute("""
                SELECT SUM(time_spent_hours) as total_horas
                FROM worklogs 
                WHERE author_id = ?
            """, (account_id,))
            
            horas_result = cursor.fetchone()
            
            # Métricas de issues
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status IN ('Done', 'Closed', 'Resolved') THEN 1 ELSE 0 END) as completados,
                       SUM(CASE WHEN issuetype = 'Error' AND status IN ('Done', 'Closed', 'Resolved') THEN 1 ELSE 0 END) as bugs_resueltos
                FROM issues 
                WHERE assignee_id = ?
            """, (account_id,))
            
            issues_result = cursor.fetchone()
            
            # Proyectos trabajados
            cursor.execute("""
                SELECT DISTINCT project 
                FROM issues 
                WHERE assignee_id = ?
            """, (account_id,))
            
            proyectos = [row['project'] for row in cursor.fetchall()]
            
            # Calcular métricas
            total_horas = horas_result['total_horas'] or 0.0
            total_issues = issues_result['total'] or 0
            issues_completados = issues_result['completados'] or 0
            bugs_resueltos = issues_result['bugs_resueltos'] or 0
            velocidad_promedio = (issues_completados / total_horas) if total_horas > 0 else 0
            
            # Insertar/actualizar métricas
            cursor.execute("""
                INSERT OR REPLACE INTO metricas_por_usuario (
                    account_id, nombre, total_horas, total_issues, issues_completados,
                    bugs_resueltos, velocidad_promedio, proyectos_trabajados,
                    fecha_ultima_actualizacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                account_id, nombre, total_horas, total_issues, issues_completados,
                bugs_resueltos, velocidad_promedio, json.dumps(proyectos)
            ))
        
        self.conn.commit()
        print(f"✅ Métricas calculadas para {len(usuarios)} usuarios")
    
    def calcular_metricas_por_proyecto(self):
        """Calcular métricas pre-calculadas por proyecto"""
        print("🔄 Calculando métricas por proyecto...")
        
        cursor = self.conn.cursor()
        
        # Obtener todos los proyectos
        cursor.execute("SELECT DISTINCT project FROM issues")
        proyectos = cursor.fetchall()
        
        for proyecto_row in proyectos:
            proyecto = proyecto_row['project']
            
            # Métricas de issues
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status IN ('Done', 'Closed', 'Resolved') THEN 1 ELSE 0 END) as completados,
                       SUM(CASE WHEN issuetype = 'Error' THEN 1 ELSE 0 END) as total_bugs,
                       SUM(CASE WHEN issuetype = 'Error' AND status IN ('Done', 'Closed', 'Resolved') THEN 1 ELSE 0 END) as bugs_cerrados
                FROM issues 
                WHERE project = ?
            """, (proyecto,))
            
            issues_result = cursor.fetchone()
            
            # Métricas de horas
            cursor.execute("""
                SELECT SUM(time_spent_hours) as total_horas
                FROM worklogs w
                JOIN issues i ON w.issue_key = i.key
                WHERE i.project = ?
            """, (proyecto,))
            
            horas_result = cursor.fetchone()
            
            # Calcular métricas
            total_issues = issues_result['total'] or 0
            issues_completados = issues_result['completados'] or 0
            bugs_abiertos = issues_result['total_bugs'] or 0
            bugs_cerrados = issues_result['bugs_cerrados'] or 0
            total_horas = horas_result['total_horas'] or 0.0
            velocidad_promedio = (issues_completados / total_horas) if total_horas > 0 else 0
            
            # Insertar/actualizar métricas
            cursor.execute("""
                INSERT OR REPLACE INTO metricas_por_proyecto (
                    proyecto, total_issues, issues_completados, total_horas,
                    bugs_abiertos, bugs_cerrados, velocidad_promedio,
                    fecha_ultima_actualizacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                proyecto, total_issues, issues_completados, total_horas,
                bugs_abiertos, bugs_cerrados, velocidad_promedio
            ))
        
        self.conn.commit()
        print(f"✅ Métricas calculadas para {len(proyectos)} proyectos")
    
    def sincronizacion_completa(self):
        """Ejecutar sincronización completa"""
        print("🚀 Iniciando sincronización completa...")
        
        pasos_totales = 7
        paso_actual = 0
        
        try:
            # 1. Crear tablas
            paso_actual += 1
            print(f"📋 Paso {paso_actual}/{pasos_totales}: Creando tablas...")
            self.crear_tablas()
            
            # 2. Cargar datos estáticos
            paso_actual += 1
            print(f"📋 Paso {paso_actual}/{pasos_totales}: Cargando datos estáticos...")
            self.cargar_usuarios_desde_json()
            self.cargar_epicas_desde_json()
            self.cargar_mapeo_proyectos()
            
            # 3. Sincronizar issues desde Jira (CON CHANGELOG)
            paso_actual += 1
            print(f"📋 Paso {paso_actual}/{pasos_totales}: Sincronizando issues desde Jira...")
            print("⚠️  Cargando issues básicos (rápido) + changelog por lotes (lento)...")
            self.sincronizar_issues_jira()
            
            # 4. Sincronizar worklogs
            paso_actual += 1
            print(f"📋 Paso {paso_actual}/{pasos_totales}: Sincronizando worklogs...")
            self.sincronizar_worklogs_csv_solo()
            
            # 5. Calcular métricas por RN
            paso_actual += 1
            print(f"📋 Paso {paso_actual}/{pasos_totales}: Calculando métricas por RN...")
            self.calcular_metricas_por_rn()
            
            # 6. Calcular métricas por usuario
            paso_actual += 1
            print(f"📋 Paso {paso_actual}/{pasos_totales}: Calculando métricas por usuario...")
            self.calcular_metricas_por_usuario()
            
            # 7. Calcular métricas por proyecto
            paso_actual += 1
            print(f"📋 Paso {paso_actual}/{pasos_totales}: Calculando métricas por proyecto...")
            self.calcular_metricas_por_proyecto()
            
            print("🎉 ¡SINCRONIZACIÓN COMPLETA FINALIZADA!")
            print("✅ Base de datos lista con todos los datos y métricas calculadas")
            
        except Exception as e:
            print(f"❌ Error en sincronización: {e}")
            raise
    
    def _consultar_jira_api(self, jql: str, fields: str, expand: str = None, max_results: int = 1000):
        """Consultar API de Jira"""
        headers = {
            "Authorization": f"Basic {self._get_jira_auth()}",
            "Accept": "application/json"
        }
        
        params = {
            "jql": jql,
            "fields": fields,
            "maxResults": max_results
        }
        
        if expand:
            params["expand"] = expand
        
        url = f"{self.jira_base_url}/rest/api/2/search"
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("issues", [])
        except Exception as e:
            print(f"❌ Error consultando Jira: {e}")
            return []
    
    def _consultar_tempo_api(self, fecha_inicio, fecha_fin):
        """Consultar API de Tempo"""
        headers = {
            "Authorization": f"Bearer {self.tempo_token}",
            "Accept": "application/json"
        }
        
        params = {
            "from": fecha_inicio.isoformat(),
            "to": fecha_fin.isoformat(),
            "limit": 1000
        }
        
        url = "https://api.tempo.io/4/worklogs"
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as e:
            print(f"❌ Error consultando Tempo: {e}")
            return []
    
    def _get_jira_auth(self):
        """Obtener autenticación básica para Jira"""
        import base64
        auth_string = f"{self.jira_email}:{self.jira_token}"
        return base64.b64encode(auth_string.encode()).decode()
    
    def _extraer_tempo_account(self, worklog):
        """Extraer cuenta de Tempo desde worklog"""
        attributes = worklog.get("attributes", [])
        for attr in attributes:
            if isinstance(attr, dict):
                key = attr.get("key", "").lower()
                if "tempo:account" in key or "account" in key:
                    value = attr.get("value", {})
                    if isinstance(value, dict):
                        return value.get("key", "")
                    return str(value)
        return ""


def main():
    """Función principal"""
    print("🎯 Tablero SUMMA - Gestión de Base de Datos SQLite")
    print("=" * 50)
    
    # Crear instancia de la base de datos
    db = TableroDatabase()
    
    try:
        # Conectar a la base de datos
        db.conectar()
        
        # Ejecutar sincronización completa
        db.sincronizacion_completa()
        
        print("\n🎉 ¡Proceso completado exitosamente!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    finally:
        # Cerrar conexión
        db.cerrar()
    
    return 0


if __name__ == "__main__":
    exit(main())
