"""
Módulo de conexión a la base de datos SQLite del tablero
Proporciona funciones para leer datos en formato compatible con el tablero
"""
import sqlite3
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path


class LazyJSONField:
    """Wrapper para parsear JSON solo cuando se accede al campo - funciona como lista o dict según el contenido"""
    def __init__(self, raw_value: str):
        self.raw_value = raw_value
        self._parsed = None
    
    def _ensure_parsed(self):
        """Forzar parseo"""
        if self._parsed is None:
            try:
                if self.raw_value and self.raw_value.strip() and self.raw_value != "[]":
                    self._parsed = json.loads(self.raw_value)
                else:
                    self._parsed = []
            except:
                self._parsed = []
        return self._parsed
    
    def __getitem__(self, key):
        self._ensure_parsed()
        return self._parsed[key]
    
    def __iter__(self):
        self._ensure_parsed()
        return iter(self._parsed)
    
    def __len__(self):
        self._ensure_parsed()
        return len(self._parsed)
    
    def __bool__(self):
        self._ensure_parsed()
        return bool(self._parsed)
    
    def __repr__(self):
        self._ensure_parsed()
        return repr(self._parsed)
    
    def get(self, key, default=None):
        """Método get para compatibilidad con dicts"""
        self._ensure_parsed()
        if isinstance(self._parsed, dict):
            return self._parsed.get(key, default)
        # Si es lista, retornar default (no tiene get)
        return default
    
    def __contains__(self, item):
        self._ensure_parsed()
        return item in self._parsed
    
    def __eq__(self, other):
        """Comparación para compatibilidad"""
        self._ensure_parsed()
        if isinstance(other, LazyJSONField):
            other._ensure_parsed()
            return self._parsed == other._parsed
        return self._parsed == other
    
    def __ne__(self, other):
        return not self.__eq__(other)


class DatabaseHelper:
    """Helper para leer datos de la base de datos SQLite"""
    
    def __init__(self, db_path: str = "data/tablero_completo.db"):
        """
        Args:
            db_path: Ruta a la base de datos
        """
        self.db_path = db_path
        self.conn = None
        
    def conectar(self):
        """Conectar a la base de datos (cada instancia crea su propia conexión por thread safety)"""
        if not self.conn:
            # Usar check_same_thread=False para permitir uso en diferentes threads de Streamlit
            # pero cada instancia tiene su propia conexión
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def cerrar(self):
        """Cerrar conexión"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        """Context manager: entrar"""
        self.conectar()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: salir"""
        self.cerrar()
    
    @classmethod
    def cerrar_conexion_compartida(cls):
        """Método legacy para compatibilidad (ya no se usa)"""
        pass
    
    def obtener_primera_fecha_testing(self, issue_keys: List[str]) -> Dict[str, str]:
        """
        Obtener la primera fecha en testing para múltiples issues usando SQL agregado
        Retorna un diccionario {issue_key: fecha_testing} o None si no tiene testing
        """
        if not issue_keys:
            return {}
        
        if not self.conn:
            self.conectar()
        
        placeholders = ','.join(['?' for _ in issue_keys])
        query = f"""
            SELECT issue_key, MIN(transition_date) as primera_fecha_testing
            FROM issue_transitions
            WHERE issue_key IN ({placeholders}) AND is_testing = 1
            GROUP BY issue_key
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query, issue_keys)
        rows = cursor.fetchall()
        
        return {row["issue_key"]: row["primera_fecha_testing"] for row in rows}
    
    def obtener_historias_con_transiciones(self, proyectos: List[str] = ["REP", "TAL", "ATI"], fecha_desde: str = '2024-01-01', incluir_sin_puntos: bool = False) -> List[Dict[str, Any]]:
        """
        Obtener historias de los proyectos especificados con sus transiciones de estado
        Devuelve en formato compatible con la API de Jira (para mantener compatibilidad con el código existente)
        
        Args:
            proyectos: Lista de proyectos a consultar
            fecha_desde: Fecha mínima de creación (formato 'YYYY-MM-DD'). Por defecto '2024-01-01'
        """
        if not self.conn:
            self.conectar()
        
        # Construir query SQL con JOIN para evitar N+1 queries
        proyectos_str = "', '".join(proyectos)
        query = f"""
            SELECT 
                i.key,
                i.summary,
                i.status,
                i.project,
                i.issuetype,
                i.assignee_id,
                u.nombre AS assignee_name,
                i.parent_key,
                i.epic_link,
                i.story_points,
                i.priority,
                i.duedate,
                i.created_date,
                i.updated_date,
                i.resolution_date,
                i.status_category_changed_date,
                i.labels,
                i.fix_versions,
                i.custom_fields,
                i.issue_links,
                i.subtasks,
                i.sprint,
                i.version,
                i.tempo_project,
                i.proyecto_logico
            FROM issues i
            LEFT JOIN usuarios u ON i.assignee_id = u.account_id
            WHERE i.project IN ('{proyectos_str}') 
                AND (i.issuetype = 'Historia' OR i.issuetype = 'Spike')
                AND ({'1=1' if incluir_sin_puntos else '(i.story_points IS NOT NULL AND i.story_points > 0 OR i.epic_link IS NOT NULL OR i.parent_key IS NOT NULL)'})
                AND i.created_date >= '{fecha_desde}'
            ORDER BY i.updated_date DESC
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Cargar TODAS las transiciones en batch (una sola query en lugar de N queries)
        issue_keys = [row["key"] for row in rows]
        transiciones_por_issue = {}
        if issue_keys:
            # Usar parámetros con IN para cargar todas las transiciones de una vez
            placeholders = ','.join(['?' for _ in issue_keys])
            transitions_query = f"""
                SELECT issue_key, from_status, to_status, transition_date, changed_by, is_testing, is_progress, is_done
                FROM issue_transitions
                WHERE issue_key IN ({placeholders})
                ORDER BY issue_key, transition_date ASC
            """
            cursor.execute(transitions_query, issue_keys)
            transitions = cursor.fetchall()
            
            # Agrupar transiciones por issue_key
            for trans in transitions:
                issue_key = trans["issue_key"]
                if issue_key not in transiciones_por_issue:
                    transiciones_por_issue[issue_key] = []
                transiciones_por_issue[issue_key].append(trans)
        
        # Convertir a formato compatible con API de Jira
        issues = []
        for row in rows:
            # Construir estructura de fields
            # El nombre del usuario ya viene en el JOIN
            assignee_name = row["assignee_name"]
            
            assignee = {
                "accountId": row["assignee_id"],
                "displayName": assignee_name
            } if row["assignee_id"] else None
            parent = {"key": row["parent_key"]} if row["parent_key"] else None

            # Reconstruir issue como JSON compatible con API de Jira
            issue = {
                "key": row["key"],
                "fields": {
                    "summary": row["summary"],
                    "status": {"name": row["status"]},
                    "project": {"key": row["project"]},
                    "issuetype": {"name": row["issuetype"]},
                    "assignee": assignee,
                    "parent": parent,
                    "customfield_10016": row["epic_link"],
                    "customfield_10026": row["story_points"],
                    "priority": {"name": row["priority"]} if row["priority"] else None,
                    "duedate": row["duedate"],
                    "created": row["created_date"],
                    "updated": row["updated_date"],
                    "resolutiondate": row["resolution_date"],
                    "statuscategorychangedate": row["status_category_changed_date"],
                    "labels": LazyJSONField(row["labels"] or "[]"),
                    "fixVersions": LazyJSONField(row["fix_versions"] or "[]"),
                    "issuelinks": LazyJSONField(row["issue_links"] or "[]"),
                    "subtasks": LazyJSONField(row["subtasks"] or "[]"),
                    "sprint": row["sprint"],  # Sprint almacenado directamente
                    "version": row["version"],  # Versión almacenada directamente
                },
                "changelog": {
                    "histories": []
                }
            }
            
            # Obtener transiciones de esta issue desde el diccionario pre-cargado
            transitions = transiciones_por_issue.get(row["key"], [])
            
            # Convertir transiciones a formato de histories
            for trans in transitions:
                history = {
                    "created": trans["transition_date"],
                    "author": {"displayName": trans["changed_by"]} if trans["changed_by"] else None,
                    "items": [{
                        "field": "status",
                        "fromString": trans["from_status"],
                        "toString": trans["to_status"]
                    }]
                }
                issue["changelog"]["histories"].append(history)
            
            issues.append(issue)
        
        return issues
    
    def obtener_bugs_con_cierre(self, proyectos: List[str] = ["REP", "TAL", "ATI"]) -> List[Dict[str, Any]]:
        """
        Obtener bugs cerrados de los proyectos especificados
        Devuelve en formato compatible con la API de Jira
        """
        if not self.conn:
            self.conectar()
        
        proyectos_str = "', '".join(proyectos)
        # Usar JOIN para obtener nombres de usuarios en una sola query
        query = f"""
            SELECT 
                i.key,
                i.summary,
                i.status,
                i.project,
                i.issuetype,
                i.assignee_id,
                u.nombre AS assignee_name,
                i.parent_key,
                i.priority,
                i.status_category_changed_date,
                i.issue_links,
                i.created_date,
                i.updated_date
            FROM issues i
            LEFT JOIN usuarios u ON i.assignee_id = u.account_id
            WHERE i.project IN ('{proyectos_str}') 
                AND i.issuetype = 'Error'
                AND i.status_category_changed_date IS NOT NULL
                AND i.created_date >= '2023-01-01'
            ORDER BY i.status_category_changed_date DESC
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Convertir a formato compatible con API de Jira
        issues = []
        for row in rows:
            # El nombre del usuario ya viene en el JOIN
            assignee_name = row["assignee_name"]
            
            assignee = {
                "accountId": row["assignee_id"],
                "displayName": assignee_name
            } if row["assignee_id"] else None
            parent = {"key": row["parent_key"]} if row["parent_key"] else None
            
            issue = {
                "key": row["key"],
                "fields": {
                    "summary": row["summary"],
                    "status": {"name": row["status"]},
                    "project": {"key": row["project"]},
                    "issuetype": {"name": row["issuetype"]},
                    "assignee": assignee,
                    "parent": parent,
                    "priority": {"name": row["priority"]} if row["priority"] else None,
                    "statuscategorychangedate": row["status_category_changed_date"],
                    "issuelinks": LazyJSONField(row["issue_links"] or "[]"),
                    "created": row["created_date"],
                    "updated": row["updated_date"],
                }
            }
            issues.append(issue)
        
        return issues
    
    def obtener_bugs_proyecto_bug(self) -> List[Dict[str, Any]]:
        """
        Obtener bugs del proyecto BUG con changelog
        Devuelve en formato compatible con la API de Jira
        """
        if not self.conn:
            self.conectar()
        
        # Usar JOIN para obtener nombres de usuarios en una sola query
        query = f"""
            SELECT 
                i.key,
                i.summary,
                i.status,
                i.project,
                i.issuetype,
                i.assignee_id,
                u.nombre AS assignee_name,
                i.parent_key,
                i.priority,
                i.labels,
                i.epic_link,
                i.created_date,
                i.updated_date
            FROM issues i
            LEFT JOIN usuarios u ON i.assignee_id = u.account_id
            WHERE i.project = 'BUG' 
                AND i.issuetype = 'Error'
            ORDER BY i.created_date DESC
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Cargar TODAS las transiciones en batch (una sola query)
        issue_keys = [row["key"] for row in rows]
        transiciones_por_issue = {}
        if issue_keys:
            placeholders = ','.join(['?' for _ in issue_keys])
            transitions_query = f"""
                SELECT issue_key, from_status, to_status, transition_date, changed_by
                FROM issue_transitions
                WHERE issue_key IN ({placeholders})
                ORDER BY issue_key, transition_date ASC
            """
            cursor.execute(transitions_query, issue_keys)
            transitions = cursor.fetchall()
            
            # Agrupar transiciones por issue_key
            for trans in transitions:
                issue_key = trans["issue_key"]
                if issue_key not in transiciones_por_issue:
                    transiciones_por_issue[issue_key] = []
                transiciones_por_issue[issue_key].append(trans)
        
        # Convertir a formato compatible con API de Jira
        issues = []
        for row in rows:
            # El nombre del usuario ya viene en el JOIN
            assignee_name = row["assignee_name"]
            
            assignee = {
                "accountId": row["assignee_id"],
                "displayName": assignee_name
            } if row["assignee_id"] else None
            parent = {"key": row["parent_key"]} if row["parent_key"] else None
            
            issue = {
                "key": row["key"],
                "fields": {
                    "summary": row["summary"],
                    "status": {"name": row["status"]},
                    "project": {"key": row["project"]},
                    "issuetype": {"name": row["issuetype"]},
                    "assignee": assignee,
                    "parent": parent,
                    "priority": {"name": row["priority"]} if row["priority"] else None,
                    "labels": json.loads(row["labels"]) if row["labels"] else [],
                    "customfield_10016": row["epic_link"],
                    "created": row["created_date"],
                    "updated": row["updated_date"],
                },
                "changelog": {
                    "histories": []
                }
            }
            
            # Obtener transiciones de esta issue desde el diccionario pre-cargado
            transitions = transiciones_por_issue.get(row["key"], [])
            
            # Convertir transiciones a formato de histories
            for trans in transitions:
                history = {
                    "created": trans["transition_date"],
                    "author": {"displayName": trans["changed_by"]} if trans["changed_by"] else None,
                    "items": [{
                        "field": "status",
                        "fromString": trans["from_status"],
                        "toString": trans["to_status"]
                    }]
                }
                issue["changelog"]["histories"].append(history)
            
            issues.append(issue)
        
        return issues
    
    def obtener_mapeo_usuarios(self) -> Dict[str, str]:
        """
        Obtener mapeo de account_id a nombre de usuario
        Compatible con accountid_to_name.json
        """
        if not self.conn:
            self.conectar()
        
        query = "SELECT account_id, nombre FROM usuarios WHERE activo = 1"
        cursor = self.conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
        return {row["account_id"]: row["nombre"] for row in rows}
    
    def obtener_worklogs(self) -> pd.DataFrame:
        """
        Obtener worklogs en formato compatible con el tablero
        Incluye: Issue, Usuario (nombre), Horas, Fecha, Proyecto, Cuenta (tempo_account)
        
        Maneja el caso donde issue_key puede ser un ID numérico o una clave de Jira.
        Si es numérico, intenta buscar en issues usando el ID, o inferir el proyecto desde prefijos.
        """
        if not self.conn:
            self.conectar()
        
        # Primero intentar obtener directamente con JOIN
        query = """
            SELECT 
                w.issue_key AS Issue,
                COALESCE(u.nombre, w.author_id) AS Usuario,
                w.time_spent_hours AS Horas,
                w.start_date AS Fecha,
                i.project AS Proyecto,
                COALESCE(w.tempo_account, '') AS Cuenta
            FROM worklogs w
            LEFT JOIN issues i ON w.issue_key = i.key
            LEFT JOIN usuarios u ON w.author_id = u.account_id
            ORDER BY w.start_date DESC
        """
        
        df = pd.read_sql_query(query, self.conn)
        
        # Para los que no tienen proyecto (probablemente IDs numéricos), intentar inferir desde issue_key
        # o buscar en issues por algún otro campo
        if 'Proyecto' in df.columns:
            mask_sin_proyecto = df['Proyecto'].isna() | (df['Proyecto'] == '')
            
            # Intentar inferir desde prefijos en Issue
            df.loc[mask_sin_proyecto & df['Issue'].str.match(r'^REP-', na=False), 'Proyecto'] = 'REP'
            df.loc[mask_sin_proyecto & df['Issue'].str.match(r'^TAL-', na=False), 'Proyecto'] = 'TAL'
            df.loc[mask_sin_proyecto & df['Issue'].str.match(r'^ATI-', na=False), 'Proyecto'] = 'ATI'
            df.loc[mask_sin_proyecto & df['Issue'].str.match(r'^AFUS-', na=False), 'Proyecto'] = 'AFUS'
            df.loc[mask_sin_proyecto & df['Issue'].str.match(r'^BUG-', na=False), 'Proyecto'] = 'BUG'
            
            # Si aún no tiene proyecto y es un ID numérico, intentar buscar en issues
            # Nota: Esto es una aproximación - idealmente necesitaríamos hacer una llamada a Jira API
            # Por ahora, dejamos None para que obtener_proyecto_logico intente inferirlo desde el Issue
            
        return df
    
    def obtener_fecha_ultima_actualizacion(self) -> str:
        """
        Obtener la fecha de última actualización de la base de datos
        Retorna la fecha más reciente entre issues y worklogs
        """
        if not self.conn:
            self.conectar()
        
        cursor = self.conn.cursor()
        
        # Obtener la fecha más reciente de issues
        cursor.execute("SELECT MAX(updated_at) as fecha FROM issues")
        resultado_issues = cursor.fetchone()
        fecha_issues = resultado_issues['fecha'] if resultado_issues and resultado_issues['fecha'] else None
        
        # Obtener la fecha más reciente de worklogs
        cursor.execute("SELECT MAX(updated_at) as fecha FROM worklogs")
        resultado_worklogs = cursor.fetchone()
        fecha_worklogs = resultado_worklogs['fecha'] if resultado_worklogs and resultado_worklogs['fecha'] else None
        
        # Usar la más reciente
        fechas = [f for f in [fecha_issues, fecha_worklogs] if f is not None]
        if not fechas:
            return "No disponible"
        
        fecha_max = max(fechas)
        
        # Formatear fecha para mostrar
        try:
            from datetime import datetime
            if isinstance(fecha_max, str):
                fecha_dt = datetime.strptime(fecha_max.split('.')[0], "%Y-%m-%d %H:%M:%S")
            else:
                fecha_dt = fecha_max
            return fecha_dt.strftime("%d/%m/%Y %H:%M")
        except:
            return fecha_max
    
    def obtener_estados_subtareas(self, subtask_keys: List[str]) -> Dict[str, str]:
        """
        Obtener los estados de múltiples subtareas desde la base de datos
        Devuelve un diccionario {subtask_key: status}
        """
        if not subtask_keys:
            return {}
        
        if not self.conn:
            self.conectar()
        
        # Crear placeholders para la consulta IN
        placeholders = ','.join('?' * len(subtask_keys))
        query = f"""
            SELECT key, status
            FROM issues
            WHERE key IN ({placeholders})
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query, subtask_keys)
        rows = cursor.fetchall()
        
        return {row["key"]: row["status"] for row in rows}

    # ============================
    # MÓDULO DE VACACIONES
    # ============================

    def _ensure_connection(self):
        if not self.conn:
            self.conectar()

    def contar_vacaciones_totales(self) -> int:
        self._ensure_connection()
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) AS cantidad FROM vacaciones")
        row = cursor.fetchone()
        return row["cantidad"] if row else 0

    def obtener_vacaciones_agrupadas(self) -> List[Dict[str, Any]]:
        """Obtener vacaciones agrupadas por usuario con el formato utilizado por la pestaña."""
        self._ensure_connection()
        cursor = self.conn.cursor()
        query = """
            SELECT 
                v.usuario,
                v.opcion,
                v.fecha_desde,
                v.fecha_hasta,
                v.fecha_creacion,
                COALESCE(o.observaciones, '') AS observaciones
            FROM vacaciones v
            LEFT JOIN vacaciones_observaciones o ON o.usuario = v.usuario
            ORDER BY v.usuario, v.opcion
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        agrupado: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            usuario = row["usuario"]
            if usuario not in agrupado:
                agrupado[usuario] = {
                    "usuario": usuario,
                    "opciones": [],
                    "observaciones": row["observaciones"],
                    "fecha_registro": row["fecha_creacion"]
                }
            agrupado[usuario]["opciones"].append({
                "desde": row["fecha_desde"],
                "hasta": row["fecha_hasta"]
            })

        # Asegurarse de que cada usuario tenga lista de opciones
        for entry in agrupado.values():
            entry["opciones"] = entry.get("opciones", [])[:3]

        return list(agrupado.values())

    def obtener_vacaciones_usuario(self, usuario: str) -> List[Dict[str, Any]]:
        self._ensure_connection()
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT opcion, fecha_desde, fecha_hasta
            FROM vacaciones
            WHERE usuario = ?
            ORDER BY opcion
            """,
            (usuario,)
        )
        rows = cursor.fetchall()
        return [{"opcion": row["opcion"], "desde": row["fecha_desde"], "hasta": row["fecha_hasta"]} for row in rows]

    def agregar_vacaciones(self, usuario: str, opciones: List[Dict[str, str]], observaciones: Optional[str] = None):
        """Agregar nuevas opciones de vacaciones para un usuario."""
        if not opciones:
            return
        self._ensure_connection()
        cursor = self.conn.cursor()

        cursor.execute("SELECT opcion FROM vacaciones WHERE usuario = ? ORDER BY opcion", (usuario,))
        existentes = [row["opcion"] for row in cursor.fetchall()]
        if len(existentes) >= 3:
            raise ValueError("El usuario ya tiene el máximo de 3 opciones registradas")

        siguiente_opcion = len(existentes) + 1
        for opcion in opciones:
            if siguiente_opcion > 3:
                break
            cursor.execute(
                """
                INSERT INTO vacaciones (usuario, opcion, fecha_desde, fecha_hasta)
                VALUES (?, ?, ?, ?)
                """,
                (usuario, siguiente_opcion, opcion["desde"], opcion["hasta"])
            )
            siguiente_opcion += 1

        if observaciones is not None:
            self.guardar_observaciones_vacaciones(usuario, observaciones, commit=False)

        self.conn.commit()

    def guardar_observaciones_vacaciones(self, usuario: str, observaciones: str, commit: bool = True):
        self._ensure_connection()
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO vacaciones_observaciones (usuario, observaciones, ultima_actualizacion)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(usuario) DO UPDATE SET observaciones = excluded.observaciones, ultima_actualizacion = CURRENT_TIMESTAMP
            """,
            (usuario, observaciones)
        )
        if commit:
            self.conn.commit()

    def actualizar_vacacion(self, usuario: str, opcion: int, fecha_desde: str, fecha_hasta: str):
        self._ensure_connection()
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE vacaciones
            SET fecha_desde = ?, fecha_hasta = ?, ultima_actualizacion = CURRENT_TIMESTAMP
            WHERE usuario = ? AND opcion = ?
            """,
            (fecha_desde, fecha_hasta, usuario, opcion)
        )
        self.conn.commit()

    def eliminar_vacacion(self, usuario: str, opcion: int):
        self._ensure_connection()
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM vacaciones WHERE usuario = ? AND opcion = ?", (usuario, opcion))
        self._reindexar_vacaciones_usuario(usuario, cursor)
        self.conn.commit()

    def eliminar_todas_vacaciones(self, usuario: str):
        self._ensure_connection()
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM vacaciones WHERE usuario = ?", (usuario,))
        cursor.execute("DELETE FROM vacaciones_observaciones WHERE usuario = ?", (usuario,))
        self.conn.commit()

    def _reindexar_vacaciones_usuario(self, usuario: str, cursor: Optional[sqlite3.Cursor] = None):
        interno = cursor is None
        if interno:
            self._ensure_connection()
            cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM vacaciones WHERE usuario = ? ORDER BY opcion", (usuario,))
        rows = cursor.fetchall()
        for idx, row in enumerate(rows, start=1):
            cursor.execute(
                "UPDATE vacaciones SET opcion = ?, ultima_actualizacion = CURRENT_TIMESTAMP WHERE id = ?",
                (idx, row["id"])
            )
        if interno:
            self.conn.commit()

    # ============================
    # USUARIOS PARA VACACIONES
    # ============================

    def obtener_usuarios_vacaciones(self) -> List[Dict[str, Any]]:
        self._ensure_connection()
        cursor = self.conn.cursor()
        cursor.execute("SELECT nombre, lider, dias_vacaciones FROM usuarios_vacaciones ORDER BY nombre")
        rows = cursor.fetchall()
        return [
            {
                "nombre": row["nombre"],
                "lider": row["lider"],
                "dias_vacaciones": row["dias_vacaciones"]
            }
            for row in rows
        ]

    def contar_usuarios_vacaciones(self) -> int:
        self._ensure_connection()
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) AS cantidad FROM usuarios_vacaciones")
        row = cursor.fetchone()
        return row["cantidad"] if row else 0

    def insertar_usuarios_vacaciones_bulk(self, usuarios: List[Dict[str, Any]]):
        if not usuarios:
            return
        self._ensure_connection()
        cursor = self.conn.cursor()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO usuarios_vacaciones (nombre, lider, dias_vacaciones)
            VALUES (?, ?, ?)
            """,
            [(u["nombre"], u.get("lider"), u.get("dias_vacaciones")) for u in usuarios]
        )
        self.conn.commit()


