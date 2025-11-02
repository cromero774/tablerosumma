"""
Módulo de conexión a la base de datos SQLite del tablero
Proporciona funciones para leer datos en formato compatible con el tablero
"""
import sqlite3
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path


class DatabaseHelper:
    """Helper para leer datos de la base de datos SQLite"""
    
    def __init__(self, db_path: str = "data/tablero_completo.db"):
        self.db_path = db_path
        self.conn = None
        
    def conectar(self):
        """Conectar a la base de datos"""
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def cerrar(self):
        """Cerrar conexión"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
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
        
        # Construir query SQL
        proyectos_str = "', '".join(proyectos)
        query = f"""
            SELECT 
                i.key,
                i.summary,
                i.status,
                i.project,
                i.issuetype,
                i.assignee_id,
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
            WHERE i.project IN ('{proyectos_str}') 
                AND i.issuetype = 'Historia'
                AND ({'1=1' if incluir_sin_puntos else '(i.story_points IS NOT NULL AND i.story_points > 0 OR i.epic_link IS NOT NULL OR i.parent_key IS NOT NULL)'})
                AND i.created_date >= '{fecha_desde}'
            ORDER BY i.updated_date DESC
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Convertir a formato compatible con API de Jira
        issues = []
        for row in rows:
            # Construir estructura de fields
            # Obtener el nombre del usuario desde la tabla de usuarios
            assignee_name = None
            if row["assignee_id"]:
                cursor.execute("SELECT nombre FROM usuarios WHERE account_id = ?", (row["assignee_id"],))
                user_result = cursor.fetchone()
                assignee_name = user_result["nombre"] if user_result else None
            
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
                    "labels": json.loads(row["labels"]) if row["labels"] else [],
                    "fixVersions": json.loads(row["fix_versions"]) if row["fix_versions"] else [],
                    "issuelinks": json.loads(row["issue_links"]) if row["issue_links"] else [],
                    "subtasks": json.loads(row["subtasks"]) if row["subtasks"] else [],
                },
                "changelog": {
                    "histories": []
                }
            }
            
            # Obtener transiciones de esta issue
            transitions_query = """
                SELECT from_status, to_status, transition_date, changed_by, is_testing, is_progress, is_done
                FROM issue_transitions
                WHERE issue_key = ?
                ORDER BY transition_date ASC
            """
            cursor.execute(transitions_query, (row["key"],))
            transitions = cursor.fetchall()
            
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
        query = f"""
            SELECT 
                i.key,
                i.summary,
                i.status,
                i.project,
                i.issuetype,
                i.assignee_id,
                i.parent_key,
                i.priority,
                i.status_category_changed_date,
                i.issue_links,
                i.created_date,
                i.updated_date
            FROM issues i
            WHERE i.project IN ('{proyectos_str}') 
                AND i.issuetype = 'Error'
                AND i.status_category_changed_date IS NOT NULL
                AND i.created_date >= '2025-01-01'
                AND i.created_date < '2026-01-01'
            ORDER BY i.status_category_changed_date DESC
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Convertir a formato compatible con API de Jira
        issues = []
        for row in rows:
            # Obtener el nombre del usuario desde la tabla de usuarios
            assignee_name = None
            if row["assignee_id"]:
                cursor.execute("SELECT nombre FROM usuarios WHERE account_id = ?", (row["assignee_id"],))
                user_result = cursor.fetchone()
                assignee_name = user_result["nombre"] if user_result else None
            
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
                    "issuelinks": json.loads(row["issue_links"]) if row["issue_links"] else [],
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
        
        query = f"""
            SELECT 
                i.key,
                i.summary,
                i.status,
                i.project,
                i.issuetype,
                i.assignee_id,
                i.parent_key,
                i.priority,
                i.labels,
                i.epic_link,
                i.created_date,
                i.updated_date
            FROM issues i
            WHERE i.project = 'BUG' 
                AND i.issuetype = 'Error'
            ORDER BY i.created_date DESC
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Convertir a formato compatible con API de Jira
        issues = []
        for row in rows:
            # Obtener el nombre del usuario desde la tabla de usuarios
            assignee_name = None
            if row["assignee_id"]:
                cursor.execute("SELECT nombre FROM usuarios WHERE account_id = ?", (row["assignee_id"],))
                user_result = cursor.fetchone()
                assignee_name = user_result["nombre"] if user_result else None
            
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
            
            # Obtener transiciones de esta issue para el changelog
            cursor.execute("""
                SELECT from_status, to_status, transition_date, changed_by
                FROM issue_transitions
                WHERE issue_key = ?
                ORDER BY transition_date ASC
            """, (row["key"],))
            transitions = cursor.fetchall()
            
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
        """Obtener worklogs en formato compatible con el tablero"""
        if not self.conn:
            self.conectar()
        
        query = """
            SELECT 
                w.issue_key AS Issue,
                w.author_id AS Usuario,
                w.time_spent_hours AS Horas,
                w.start_date AS Fecha
            FROM worklogs w
            ORDER BY w.start_date DESC
        """
        
        return pd.read_sql_query(query, self.conn)

