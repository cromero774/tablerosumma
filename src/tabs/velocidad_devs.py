"""
Pestaña Velocidad de devs - Tablero SUMMA
Implementa la lógica completa de métricas de productividad de desarrolladores
"""

import streamlit as st
import pandas as pd
import json
import os
import time
import pickle
import altair as alt
from datetime import datetime, timedelta
from src.jira_conexion import get_jira
from src.utils.configuracion import cache_path, cargar_epicas_relevantes
from src.utils.database_helper import DatabaseHelper

def mostrar_velocidad_devs(df, issues_jira):
    """Mostrar la pestaña de Velocidad de devs"""
    
    st.header("🔥 Velocidad de devs")
    st.caption("📊 **Métricas de productividad de desarrolladores**")
    
    # Mostrar fecha de última actualización
    db_helper = DatabaseHelper()
    db_helper.conectar()
    fecha_actualizacion = db_helper.obtener_fecha_ultima_actualizacion()
    db_helper.cerrar()
    st.caption(f"🕒 **Última actualización:** {fecha_actualizacion}")

    # ==========================
    #   FUNCIONES MODULARES
    # ==========================
    
    def _norm(s):
        return str(s or "").strip()

    def _mes_start(dt):
        if pd.isna(dt):
            return pd.NaT
        return pd.Timestamp(year=dt.year, month=dt.month, day=1)

    def _mes_label(dt):
        if pd.isna(dt):
            return ""
        return dt.strftime("%B %Y")

    def _proy_ok(project_key: str, sel: str) -> bool:
        v = _norm(project_key)
        if sel == "ATI":
            return v == "ATI"
        if sel == "Postventas":
            return v in ("REP", "TAL")
        return True

    STATUS_TESTING = {
        "en testing", "testing", "qa", "en test", "pruebas", "ready for qa", "ready for testing"
    }

    def _get_points_from_fields(fields: dict) -> float:
        for key in ["customfield_10026", "customfield_10016", "storyPoints"]:
            val = fields.get(key)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue
        return 0.0

    # ==========================
    #   CARGA DE DATOS BASE
    # ==========================
    
    # Cargar mapeo de usuarios primero
    with open("data/accountid_to_name.json", "r", encoding="utf-8") as f:
        accountid_to_name = json.load(f)
    
    # Crear diccionario inverso name_to_acc
    name_to_acc = {v: k for k, v in accountid_to_name.items()}

    allowed_names = set(accountid_to_name.values()) | set(name_to_acc.keys())
    
    # Usar el DataFrame que se pasa como parámetro
    df_horas = df.copy()
    
    # Aplicar mapeo de usuarios
    df_horas["Usuario_nombre"] = df_horas["Usuario"].map(accountid_to_name).fillna(df_horas["Usuario"]).apply(_norm)
    
    # Filtrar solo usuarios que están en el mapeo (desarrolladores válidos)
    df_horas = df_horas[df_horas["Usuario_nombre"].isin(accountid_to_name.values())]
    
    df_horas["Fecha"] = pd.to_datetime(df_horas["Fecha"], errors="coerce")
    df_horas["Mes_dt"] = df_horas["Fecha"].apply(lambda d: _mes_start(d) if pd.notna(d) else pd.NaT)
    
    # Agrupar por usuario y mes (sin filtro de proyecto por ahora)
    df_horas_sum = df_horas.groupby(["Usuario_nombre", "Mes_dt"], as_index=False)["Horas"].sum()

    # ==========================
    #   UI: SELECTOR DE FECHAS
    # ==========================
    
    
    # Inicializar session_state para filtros (últimos 3 meses incluyendo el mes actual)
    if "vel_fecha_inicio" not in st.session_state:
        # Calcular dinámicamente: hace 2 meses desde el mes actual (para tener 3 meses en total)
        hoy = datetime.now()
        hace_dos_meses = hoy - pd.DateOffset(months=2)
        st.session_state["vel_fecha_inicio"] = hace_dos_meses.replace(day=1).date()
    if "vel_fecha_fin" not in st.session_state:
        # Último día del mes actual
        hoy = datetime.now()
        ultimo_dia_mes_actual = (hoy.replace(day=1) + pd.offsets.MonthEnd(0)).date()
        st.session_state["vel_fecha_fin"] = ultimo_dia_mes_actual
    if "vel_proyecto_sel" not in st.session_state:
        st.session_state["vel_proyecto_sel"] = "Todos"
    
    col_fecha1, col_fecha2, col_proj, col_btn = st.columns([1, 1, 1, 1])
    
    # === OPTIMIZACIÓN: Callbacks para evitar recargas innecesarias ===
    def on_fecha_inicio_change():
        st.session_state["vel_fecha_inicio"] = st.session_state["vel_fecha_inicio_input"]
        # NO forzar refresh, solo rerun para aplicar filtros
        
    def on_fecha_fin_change():
        st.session_state["vel_fecha_fin"] = st.session_state["vel_fecha_fin_input"]
        # NO forzar refresh, solo rerun para aplicar filtros
        
    def on_proyecto_change():
        st.session_state["vel_proyecto_sel"] = st.session_state["vel_proyecto_input"]
        # NO forzar refresh al cambiar proyecto, filtrar en memoria
    
    with col_fecha1:
        fecha_inicio = st.date_input(
            "Fecha inicio",
            value=st.session_state["vel_fecha_inicio"],
            help="Fecha de inicio del período a evaluar",
            key="vel_fecha_inicio_input",
            on_change=on_fecha_inicio_change
        )
    with col_fecha2:
        fecha_fin = st.date_input(
            "Fecha fin",
            value=st.session_state["vel_fecha_fin"],
            help="Fecha de fin del período a evaluar",
            key="vel_fecha_fin_input",
            on_change=on_fecha_fin_change
        )
    with col_proj:
        proyecto_sel = st.selectbox(
            "Proyecto", 
            ["Todos", "ATI", "Postventas"], 
            index=["Todos", "ATI", "Postventas"].index(st.session_state["vel_proyecto_sel"]),
            key="vel_proyecto_input",
            on_change=on_proyecto_change
        )
    with col_btn:
        if st.button("🔄 Actualizar datos", help="Fuerza la recarga de datos desde Jira", key="velocidad_actualizar"):
            st.session_state["force_refresh"] = True
            # Limpiar TODOS los caches de velocidad
            keys_to_clear = [k for k in st.session_state.keys() if k.startswith(("velocidad_cache", "calculos_velocidad", "usuarios_validos"))]
            for key in keys_to_clear:
                del st.session_state[key]
            st.success("✅ Actualizando datos...")
            st.rerun()
    
    # === PROTECCIÓN: Cache inteligente con invalidación ===
    cache_key_velocidad = f"velocidad_{proyecto_sel}_{fecha_inicio}_{fecha_fin}"
    
    # Botón adicional para limpiar cache específico
    if st.button("🗑️ Limpiar Cache Velocidad", help="Limpia completamente el cache de velocidad", key="velocidad_limpiar_cache"):
        # Limpiar todos los caches relacionados con velocidad
        import glob
        
        # Buscar archivos de cache de velocidad
        cache_files = glob.glob("data/cache_velocidad_*")
        for cache_file in cache_files:
            try:
                os.remove(cache_file)
            except Exception:
                pass
        
        # Limpiar session state
        keys_to_clear = [k for k in st.session_state.keys() if k.startswith("velocidad_cache")]
        for key in keys_to_clear:
            del st.session_state[key]
        
        st.success("✅ Cache de velocidad limpiado completamente. Recargando...")
        st.rerun()

    # ==========================
    #   FUNCIÓN: CARGAR DATOS DE JIRA
    # ==========================
    
    def cargar_datos_velocidad(_jira, _fecha_inicio, _fecha_fin, _proyecto_sel, _force_refresh):
        """
        Cargar datos de velocidad desde la base de datos SQLite
        Mantiene el mismo formato de salida que la versión anterior para compatibilidad
        """
        try:
            tiempo_inicio_carga = time.time()
            # Inicializar helper de base de datos
            db = DatabaseHelper()
            db.conectar()
            tiempo_conexion = time.time()
            print(f"⏱️ [VELOCIDAD-CARGA] Conexión BD: {tiempo_conexion - tiempo_inicio_carga:.2f}s")
            
            # Cargar datos desde la base (sin filtros de fechas - se filtra por fecha de testing)
            # Incluir historias desde 2023 y permitir historias sin puntos (spikes)
            tiempo_antes_historias = time.time()
            historias = db.obtener_historias_con_transiciones(["REP", "TAL", "ATI"], fecha_desde='2023-01-01', incluir_sin_puntos=True)
            tiempo_despues_historias = time.time()
            print(f"⏱️ [VELOCIDAD-CARGA] Obtener historias: {tiempo_despues_historias - tiempo_antes_historias:.2f}s ({len(historias)} historias)")
            
            # Obtener primera fecha de testing para todas las historias de una vez (OPTIMIZACIÓN)
            tiempo_antes_fechas_testing = time.time()
            issue_keys = [iss.get("key") for iss in historias]
            fechas_testing = db.obtener_primera_fecha_testing(issue_keys)
            tiempo_despues_fechas_testing = time.time()
            print(f"⏱️ [VELOCIDAD-CARGA] Obtener fechas testing: {tiempo_despues_fechas_testing - tiempo_antes_fechas_testing:.2f}s ({len(fechas_testing)} fechas)")
            
            tiempo_antes_bugs = time.time()
            bugs = db.obtener_bugs_con_cierre(["REP", "TAL", "ATI"])
            tiempo_despues_bugs = time.time()
            print(f"⏱️ [VELOCIDAD-CARGA] Obtener bugs: {tiempo_despues_bugs - tiempo_antes_bugs:.2f}s ({len(bugs)} bugs)")
            
            # Cerrar conexión
            db.cerrar()
            
            tiempo_fin_carga = time.time()
            print(f"⏱️ [VELOCIDAD-CARGA] Total carga BD: {tiempo_fin_carga - tiempo_inicio_carga:.2f}s")
            
            # Agregar fechas de testing directamente a las historias (OPTIMIZACIÓN)
            for iss in historias:
                key = iss.get("key")
                if key in fechas_testing:
                    # Agregar fecha de testing directamente al issue
                    iss["_primera_fecha_testing"] = fechas_testing[key]
            
            return historias, bugs
            
        except Exception as e:
            st.error(f"❌ Error cargando datos desde la base de datos: {e}")
            return [], []

    # ==========================
    #   FUNCIÓN: PROCESAR HISTORIAS
    # ==========================
    
    def procesar_historias(historias, accountid_to_name, name_to_acc):
        tiempo_inicio_proceso = time.time()
        rows_issues = []
        contador_historias = 0
        contador_spikes = 0
        contador_filtradas_proyecto = 0
        contador_sin_testing = 0
        contador_sin_puntos = 0
        contador_sin_owner = 0
        
        for iss in historias:
            f = iss.get("fields", {}) or {}
            itype = _norm((f.get("issuetype", {}) or {}).get("name")).lower()
            # Incluir historias y spikes para contar velocidad y puntos
            if itype not in ("historia", "spike"):
                continue
            
            if itype == "historia":
                contador_historias += 1
            else:
                contador_spikes += 1
            
            proj_key = _norm((f.get("project") or {}).get("key"))
            if not _proy_ok(proj_key, proyecto_sel):
                contador_filtradas_proyecto += 1
                continue
            
            key = iss.get("key", "")
            pts = _get_points_from_fields(f)
            
            # Buscar owner al momento de testing
            owner_name, owner_id, first_dt = _owner_al_momento_testing(iss, accountid_to_name, name_to_acc)
            
            if pd.isna(first_dt):
                contador_sin_testing += 1
            elif pts <= 0:
                contador_sin_puntos += 1
            elif not owner_name or not owner_id:
                contador_sin_owner += 1
            else:
                rows_issues.append({
                    "Issue": key,
                    "Puntos": pts,
                    "Usuario_nombre": owner_name,
                    "Mes": _mes_label(_mes_start(first_dt)),
                    "Proyecto": proj_key,
                })
        
        tiempo_fin_proceso = time.time()
        tiempo_procesamiento = tiempo_fin_proceso - tiempo_inicio_proceso
        print(f"⏱️ [VELOCIDAD-PROCESAR] Procesamiento de historias:")
        print(f"    - Tiempo total: {tiempo_procesamiento:.2f}s")
        print(f"    - Historias procesadas: {contador_historias}")
        print(f"    - Spikes procesados: {contador_spikes}")
        print(f"    - Filtradas por proyecto: {contador_filtradas_proyecto}")
        print(f"    - Sin testing: {contador_sin_testing}")
        print(f"    - Sin puntos: {contador_sin_puntos}")
        print(f"    - Sin owner: {contador_sin_owner}")
        print(f"    - Resultado final: {len(rows_issues)} filas")
        
        return pd.DataFrame(rows_issues, columns=["Issue", "Puntos", "Usuario_nombre", "Mes", "Proyecto"])

    def _owner_al_momento_testing(iss, accountid_to_name, name_to_acc):
        f = iss.get("fields", {}) or {}
        
        # Usar el assignee actual (quien tiene la historia ahora)
        current_id = (f.get("assignee") or {}).get("accountId")
        current_name = _norm(accountid_to_name.get(current_id) or (f.get("assignee") or {}).get("displayName"))
        
        # OPTIMIZACIÓN: Si ya tenemos la fecha de testing pre-calculada, usarla directamente
        if "_primera_fecha_testing" in iss:
            fecha_testing = iss["_primera_fecha_testing"]
            if fecha_testing:
                fecha_dt = pd.to_datetime(fecha_testing, errors="coerce")
                if pd.notna(fecha_dt):
                    return current_name, current_id, fecha_dt
            return None, None, None
        
        # Fallback: procesar changelog (solo si no tenemos fecha pre-calculada)
        histories = (iss.get("changelog", {}) or {}).get("histories", []) or []
        histories = sorted(histories, key=lambda h: pd.to_datetime(h.get("created"), errors="coerce"))
        
        # Solo buscar la fecha de testing, no cambiar el assignee
        for hist in histories:
            h_created = pd.to_datetime(hist.get("created"), errors="coerce")
            
            # Primera vez que pasa a testing
            for it in hist.get("items", []) or []:
                if _norm(it.get("field")).lower() == "status" and _norm(it.get("toString")).lower() in STATUS_TESTING:
                    if pd.notna(h_created):
                        # Retornar el assignee actual con la fecha de testing
                        return current_name, current_id, h_created
        
        return None, None, None

    # ==========================
    #   FUNCIÓN: PROCESAR BUGS
    # ==========================
    
    def procesar_bugs(bugs, historias_por_dev):
        bug_rows = []
        bugs_extra_rows = []

        bugs_filtrados_por_tipo = 0
        bugs_filtrados_por_proyecto = 0
        bugs_filtrados_por_estado = 0
        bugs_filtrados_por_fecha = 0
        bugs_filtrados_por_asignado = 0
        
        for iss in bugs:
            f = iss.get("fields", {}) or {}
            itype = _norm((f.get("issuetype", {}) or {}).get("name")).lower()
            if itype != "error":
                bugs_filtrados_por_tipo += 1
                continue

            bug_key = iss.get("key", "")
            bug_proj = _norm((f.get("project") or {}).get("key"))

            if not _proy_ok(bug_proj, proyecto_sel):
                bugs_filtrados_por_proyecto += 1
                continue

            estado_bug = _norm((f.get("status", {}) or {}).get("name")).lower()
            
            # Estados válidos más amplios para bugs (incluyendo estados en español)
            estados_validos = ("resolved", "closed", "done", "cerrado", "resuelto", "hecho", "completado", "finalizado", "terminado", "aprobado", "hecha")
            if estado_bug not in estados_validos:
                bugs_filtrados_por_estado += 1
                continue
            
            fecha_cierre = pd.to_datetime(f.get("statuscategorychangedate", ""), errors="coerce")
            if pd.isna(fecha_cierre):
                bugs_filtrados_por_fecha += 1
                continue

            bug_mes_cierre = _mes_label(_mes_start(fecha_cierre))
            assg = f.get("assignee") or {}
            bug_assignee_id = assg.get("accountId")
            bug_assignee_nm = _norm(accountid_to_name.get(bug_assignee_id) or assg.get("displayName"))

            if not bug_assignee_nm:
                bugs_filtrados_por_asignado += 1
                continue
            
            # Buscar si es bug extra (vinculado a HU del dev)
            candidate_hus = set()
            parent_key = (f.get("parent") or {}).get("key", "")
            if parent_key:
                candidate_hus.add(parent_key)
            for link in (f.get("issuelinks") or []):
                for side in ("inwardIssue", "outwardIssue"):
                    lk = link.get(side) or {}
                    k = lk.get("key")
                    if k:
                        candidate_hus.add(k)

            # Determinar si es bug extra o bug normal
            # Bug extra: NO vinculado a ninguna historia del MISMO desarrollador
            # Bug normal: SÍ vinculado a alguna historia del MISMO desarrollador
            historias_del_dev = historias_por_dev.get(bug_assignee_nm, set())
            
            # Verificar si está vinculado a historias del dev
            is_bug_extra = not bool(candidate_hus & historias_del_dev)
            
            if is_bug_extra:
                # Bug extra: vinculado a historia del mismo dev
                bugs_extra_rows.append({
                    "Issue": bug_key,
                    "Usuario_nombre": bug_assignee_nm,
                    "Mes": bug_mes_cierre,
                    "Proyecto": bug_proj,
                })
            else:
                # Bug normal: no vinculado a historia del dev
                bug_rows.append({
                    "Issue": bug_key,
                    "Usuario_nombre": bug_assignee_nm,
                    "Mes": bug_mes_cierre,
                    "Proyecto": bug_proj,
                })
        
        return bug_rows, bugs_extra_rows

    # ==========================
    #   FUNCIÓN: AGREGAR POR USUARIO/MES
    # ==========================
    
    def agregar_por_usuario_mes(df_issues, bug_rows, bugs_extra_rows, df_horas_sum):
        # Puntos por usuario/mes
        if not df_issues.empty:
            df_puntos = df_issues.groupby(["Usuario_nombre", "Mes"], as_index=False).agg(
                Puntos=("Puntos", "sum"),
                Claves=("Issue", lambda x: ", ".join(sorted(set(k for k in x if k)))),
            )
        else:
            df_puntos = pd.DataFrame(columns=["Usuario_nombre", "Mes", "Puntos", "Claves"])

        # Bugs por usuario/mes
        if bug_rows:
            df_bugs = pd.DataFrame(bug_rows)
            df_bugs = df_bugs.groupby(["Usuario_nombre", "Mes"], as_index=False).agg(
                Bugs=("Issue", "count"),
                Bugs_claves=("Issue", lambda x: ", ".join(sorted(set(k for k in x if k)))),
            )
        else:
            df_bugs = pd.DataFrame(columns=["Usuario_nombre", "Mes", "Bugs", "Bugs_claves"])
        
        # Bugs extra por usuario/mes
        if bugs_extra_rows:
            df_bugs_extra = pd.DataFrame(bugs_extra_rows)
            df_bugs_extra = df_bugs_extra.groupby(["Usuario_nombre", "Mes"], as_index=False).agg(
                Bugs_resueltos_extra=("Issue", "count"),
                Bugs_extra_claves=("Issue", lambda x: ", ".join(sorted(set(k for k in x if k)))),
            )
        else:
            df_bugs_extra = pd.DataFrame(columns=["Usuario_nombre", "Mes", "Bugs_resueltos_extra", "Bugs_extra_claves"])
        
        # Crear base unificada
        df_puntos["_Mes_dt_aux"] = pd.to_datetime(df_puntos["Mes"], format="%B %Y", errors="coerce")
        
        # Convertir accountids a nombres legibles en df_horas_sum para el merge
        df_horas_sum_legible = df_horas_sum.copy()
        df_horas_sum_legible["Usuario_nombre"] = df_horas_sum_legible["Usuario_nombre"].map(
            lambda x: accountid_to_name.get(x, x) if x in accountid_to_name else x
        )
        
        base_horas = df_horas_sum_legible[["Usuario_nombre", "Mes_dt"]].drop_duplicates() if "Mes_dt" in df_horas_sum_legible.columns else pd.DataFrame(columns=["Usuario_nombre","Mes_dt"])
        base_puntos = df_puntos[["Usuario_nombre", "_Mes_dt_aux"]].rename(columns={"_Mes_dt_aux":"Mes_dt"}).drop_duplicates()
        df_base = pd.concat([base_horas, base_puntos], ignore_index=True).dropna(subset=["Mes_dt"]).drop_duplicates()
        df_base["Mes"] = df_base["Mes_dt"].dt.strftime("%B %Y")

        # Merge todos los datos
        df_merge = df_base.merge(df_horas_sum_legible[["Usuario_nombre","Mes_dt","Horas"]], on=["Usuario_nombre","Mes_dt"], how="left")
        
        # Merge con puntos
        df_merge = df_merge.merge(df_puntos[["Usuario_nombre","Mes","Puntos","Claves"]], on=["Usuario_nombre","Mes"], how="left")

        # Merge con bugs
        df_merge = df_merge.merge(df_bugs, on=["Usuario_nombre", "Mes"], how="left")
        df_merge = df_merge.merge(df_bugs_extra, on=["Usuario_nombre", "Mes"], how="left")

        # Llenar valores faltantes
        for col, fill in [("Horas", 0.0), ("Puntos", 0.0), ("Bugs", 0), ("Bugs_resueltos_extra", 0)]:
            if col in df_merge.columns:
                df_merge[col] = df_merge[col].fillna(fill)
        for col in ["Claves", "Bugs_claves", "Bugs_extra_claves"]:
            if col in df_merge.columns:
                df_merge[col] = df_merge[col].fillna("").astype(str)

        # Calcular velocidad (usando 80% de las horas)
        df_merge["Velocidad"] = df_merge.apply(
            lambda r: round((r["Horas"] * 0.8) / r["Puntos"], 4) if r["Puntos"] > 0 else 0, axis=1
        )
        
        return df_merge

    # ==========================
    #   FUNCIÓN: APLICAR FILTROS
    # ==========================
    
    def aplicar_filtros(df_completo, fecha_inicio, fecha_fin, proyecto_sel):
        # Filtrar por fechas
        df_completo["Mes_dt"] = pd.to_datetime(df_completo["Mes_dt"], errors="coerce")
        fecha_limite_inicio = pd.Timestamp(fecha_inicio)
        fecha_limite_fin = pd.Timestamp(fecha_fin)
        
        df_filtrado = df_completo[
            (df_completo["Mes_dt"] >= fecha_limite_inicio) & 
            (df_completo["Mes_dt"] <= fecha_limite_fin)
        ].copy()
        
        return df_filtrado

    # ==========================
    #   FUNCIÓN: CALCULAR MÉTRICAS FINALES
    # ==========================
    
    def calcular_metricas_finales(df_filtrado):
        def calcular_nota_final(r):
            p = float(r.get("Puntos", 0.0))
            h = float(r.get("Horas", 0.0))
            b = int(r.get("Bugs", 0))
            v = float(r.get("Velocidad", 0.0))
            bex = int(r.get("Bugs_resueltos_extra", 0))

            if p <= 0: 
                return 0.0

            # Calcular puntuación de puntos
            if p < 8: sp = 0.70
            elif 8 <= p < 10: sp = 0.80
            elif 10 <= p < 13: sp = 0.85
            elif 13 <= p < 16: sp = 0.90
            elif 16 <= p <= 19: sp = 1.05
            elif p >= 20: sp = 1.10
            else: sp = 1.00  # p == 16

            # Calcular puntuación de horas
            if h >= 128: 
                sh = 1.00
            elif 100 <= h <= 127: 
                sh = 0.95
            else: 
                sh = 0.70

            # Calcular puntuación de bugs
            if b == 0: 
                sb = 1.00
            elif 1 <= b <= 3: 
                sb = 0.95
            elif 4 <= b <= 5: 
                sb = 0.90
            else: 
                sb = 0.80

            # Calcular puntuación de velocidad
            if v <= 5: sv = 1.10
            elif 6 <= v <= 7: sv = 1.05
            elif abs(v - 8.0) < 1e-9: sv = 1.00
            elif 8 < v <= 10: sv = 0.95
            elif 10 < v <= 12: sv = 0.90
            else: sv = 0.80

            # Calcular puntuación base
            base = (sp * 0.40) + (sh * 0.25) + (sv * 0.25) + (sb * 0.10)

            # Calcular bonus por bugs extra
            if 1 <= bex <= 5: bonus = 0.02
            elif 6 <= bex <= 10: bonus = 0.03
            elif bex > 10: bonus = 0.05
            else: bonus = 0.0

            return round((base + bonus) * 100, 2)

        if not df_filtrado.empty:
            df_filtrado["Nota_final"] = df_filtrado.apply(calcular_nota_final, axis=1)
            # Agregar columna Mes_label para el gráfico
            df_filtrado["Mes_label"] = df_filtrado["Mes_dt"].apply(_mes_label)
        else:
            df_filtrado["Nota_final"] = pd.Series(dtype=float)
            df_filtrado["Mes_label"] = pd.Series(dtype=str)

        return df_filtrado

    # ==========================
    #   FUNCIONES AUXILIARES PARA RANKING
    # ==========================
    
    def _calcular_usuarios_validos(df_final, allowed_names):
        """Calcula los usuarios válidos que tienen puntos"""
        df_final = df_final.copy()
        df_final["Usuario_nombre"] = df_final["Usuario_nombre"].apply(_norm)
        users_with_points = set(
            df_final.loc[df_final["Puntos"] > 0, "Usuario_nombre"].dropna().astype(str)
        )
        return sorted(list(allowed_names & users_with_points))
    
    def _mostrar_selector_usuario(usuarios_validos):
        """Muestra el selector de usuario y maneja la selección"""
        # === OPTIMIZACIÓN: Cache de usuarios para evitar recargas ===
        cache_key_usuarios = f"usuarios_validos_{len(usuarios_validos)}"
        
        # Mantener la selección de usuario si está disponible
        usuario_actual = st.session_state.get("vel_usuario_actual", "Todos")
        
        # Verificar si la lista de usuarios cambió
        usuarios_cache = st.session_state.get(cache_key_usuarios, [])
        if usuarios_cache != usuarios_validos:
            # Lista de usuarios cambió, PERO mantener el usuario seleccionado si sigue siendo válido
            usuario_anterior = st.session_state.get("vel_usuario_actual", "Todos")
            if usuario_anterior in ["Todos"] + usuarios_validos:
                # El usuario anterior sigue siendo válido, mantenerlo
                usuario_actual = usuario_anterior
            else:
                # El usuario anterior ya no es válido, resetear a "Todos"
                usuario_actual = "Todos"
            st.session_state[cache_key_usuarios] = usuarios_validos.copy()
        
        if usuario_actual not in ["Todos"] + usuarios_validos:
            usuario_actual = "Todos"
        
        # Calcular el índice correcto
        if usuario_actual in usuarios_validos:
            index_usuario = usuarios_validos.index(usuario_actual) + 1  # +1 porque "Todos" está en posición 0
        else:
            index_usuario = 0  # "Todos"
            
        # === OPTIMIZACIÓN: Usar on_change para evitar recargas ===
        def on_usuario_change():
            st.session_state["vel_usuario_actual"] = st.session_state["vel_usuario"]
            
        usuario_sel = st.selectbox(
            "Seleccioná usuario", ["Todos"] + usuarios_validos, 
            index=index_usuario,
            key="vel_usuario",
            on_change=on_usuario_change
        )
        
        # Guardar la selección actual
        st.session_state["vel_usuario_actual"] = usuario_sel
        return usuario_sel
    
    def _mostrar_cards_objetivos():
        """Muestra las cards con objetivos y ponderaciones"""
        st.subheader("🎯 Objetivos y Ponderaciones")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            with st.expander("📊 **Puntos** (40%)", expanded=False):
                st.markdown("""
                **Objetivo:** 16 puntos/mes = 100%
                
                **Escala:**
                - ≥20 puntos: 110%
                - 16-19 puntos: 105%
                - 13-15 puntos: 90%
                - 10-12 puntos: 85%
                - 8-9 puntos: 80%
                - <8 puntos: 70%
                """)
        
        with col2:
            with st.expander("⏰ **Horas** (25%)", expanded=False):
                st.markdown("""
                **Objetivo:** ≥128 horas/mes = 100%
                
                **Escala:**
                - ≥128 horas: 100%
                - 100-127 horas: 95%
                - <100 horas: 70%
                """)
        
        with col3:
            with st.expander("🚀 **Velocidad** (25%)", expanded=False):
                st.markdown("""
                **Objetivo:** ≤8 horas/punto = 100%
                
                **Escala:**
                - ≤5 h/punto: 110%
                - 6-7 h/punto: 105%
                - 8 h/punto: 100%
                - 9-10 h/punto: 95%
                - 11-12 h/punto: 90%
                - >12 h/punto: 80%
                """)
        
        with col4:
            with st.expander("🐛 **Bugs** (10%)", expanded=False):
                st.markdown("""
                **Objetivo:** 0 bugs/mes = 100%
                
                **Escala:**
                - 0 bugs: 100%
                - 1-3 bugs: 95%
                - 4-5 bugs: 90%
                - >5 bugs: 80%
                
                **Bonus Bugs Extra:**
                - 1-5 extra: +2%
                - 6-10 extra: +3%
                - >10 extra: +5%
                """)
    
    def _calcular_ranking(df_final, usuarios_validos):
        """Calcula el ranking de desarrolladores"""
        df_rank_src = df_final[df_final["Usuario_nombre"].isin(usuarios_validos)].copy()
        
        if df_rank_src.empty:
            return pd.DataFrame(columns=[
                "Usuario_nombre", "Promedio_puntos", "Promedio_horas", "Promedio_velocidad", 
                "Promedio_bugs", "Promedio_bugs_extra", "Nota_final", "Meses_con_nota_0", "Total_meses"
            ])
        
        # Calcular promedios excluyendo meses con nota final 0
        df_ranking = (
            df_rank_src.groupby("Usuario_nombre", as_index=False)
            .agg(
                Promedio_puntos=("Puntos", "mean"),
                Promedio_horas=("Horas", "mean"),
                Promedio_velocidad=("Velocidad", "mean"),
                Promedio_bugs=("Bugs", "mean"),
                Promedio_bugs_extra=("Bugs_resueltos_extra", "mean"),
                Nota_final=("Nota_final", "mean"),
                # Contar meses con nota 0 para alertas
                Meses_con_nota_0=("Nota_final", lambda x: (x == 0).sum()),
                Total_meses=("Nota_final", "count"),
            )
            .sort_values("Nota_final", ascending=False)
            .reset_index(drop=True)
        )

        # Recalcular promedio de nota final excluyendo meses con nota 0
        df_ranking["Promedio_nota_final"] = df_ranking.apply(
            lambda row: df_rank_src[
                (df_rank_src["Usuario_nombre"] == row["Usuario_nombre"]) & 
                (df_rank_src["Nota_final"] > 0)
            ]["Nota_final"].mean() if row["Meses_con_nota_0"] < row["Total_meses"] else 0, 
            axis=1
        )
        
        return df_ranking
    
    def _mostrar_tabla_ranking(df_ranking, usuario_sel):
        """Muestra la tabla de ranking con formato"""
        if df_ranking.empty:
            return
            
        # Mostrar solo las columnas necesarias (ocultar las de control)
        columnas_mostrar = [
            "Usuario_nombre", "Promedio_puntos", "Promedio_horas", "Promedio_velocidad", 
            "Promedio_bugs", "Promedio_bugs_extra", "Promedio_nota_final"
        ]
        
        # Función para pintar filas con meses en nota 0
        def highlight_zero_months(row):
            # Obtener los valores del DataFrame original
            original_row = df_ranking.loc[row.name]
            if original_row['Meses_con_nota_0'] > 0:
                return ['color: #ffc107'] * len(row)  # Texto amarillo
            else:
                return [''] * len(row)  # Sin color
        
        # Formatear números antes de mostrar
        df_formatted = df_ranking[columnas_mostrar].copy()
        
        # Formatear columnas numéricas con 1 decimal
        df_formatted['Promedio_puntos'] = df_formatted['Promedio_puntos'].apply(lambda x: f"{x:.1f}")
        df_formatted['Promedio_horas'] = df_formatted['Promedio_horas'].apply(lambda x: f"{x:.1f}")
        df_formatted['Promedio_velocidad'] = df_formatted['Promedio_velocidad'].apply(lambda x: f"{x:.1f}")
        df_formatted['Promedio_bugs'] = df_formatted['Promedio_bugs'].apply(lambda x: f"{x:.1f}")
        df_formatted['Promedio_bugs_extra'] = df_formatted['Promedio_bugs_extra'].apply(lambda x: f"{x:.1f}")
        df_formatted['Promedio_nota_final'] = df_formatted['Promedio_nota_final'].apply(lambda x: f"{x:.1f}")
        
        # Mostrar tabla con resaltado y formato
        st.dataframe(
            df_formatted.style.apply(highlight_zero_months, axis=1),
            use_container_width=True, 
            hide_index=True
        )
        
        # Leyenda simple
        st.markdown("**Nota:** El texto en amarillo corresponde a desarrolladores que tienen meses con nota final 0.")
    
    def _mostrar_grafico_ranking(df_ranking, usuario_sel):
        """Muestra el gráfico de ranking general"""
        if usuario_sel != "Todos" or df_ranking.empty:
            return
            
        st.subheader("📊 Velocidad por Desarrollador")
        
        # Preparar datos para el gráfico
        df_grafico_ranking = df_ranking[['Usuario_nombre', 'Promedio_velocidad']].copy()
        df_grafico_ranking = df_grafico_ranking.sort_values('Promedio_velocidad', ascending=False)
        
        # Crear gráfico de barras con Altair
        import altair as alt
        
        # Crear DataFrame con datos y línea de objetivo
        chart_df_ranking = df_grafico_ranking.copy()
        chart_df_ranking['Objetivo'] = 8
        
        # Crear gráfico base
        base_ranking = alt.Chart(chart_df_ranking).add_selection(
            alt.selection_interval(bind='scales')
        )
        
        # Barras de datos
        bars = base_ranking.mark_bar(
            color='#1f77b4',
            opacity=0.7
        ).encode(
            x=alt.X('Usuario_nombre:N', sort=None, title='Desarrolladores'),
            y=alt.Y('Promedio_velocidad:Q', title='Velocidad (horas/punto)')
        )
        
        # Línea de objetivo
        objective_ranking = base_ranking.mark_rule(
            stroke='red',
            strokeDash=[5, 5],
            strokeWidth=2
        ).encode(
            y=alt.datum(8)
        )
        
        # Combinar gráficos
        chart_ranking = (bars + objective_ranking).resolve_scale(
            color='independent'
        ).properties(
            width=600,
            height=400,
            title='Velocidad Promedio por Desarrollador'
        )
        
        # Mostrar gráfico
        st.altair_chart(chart_ranking, use_container_width=True)
        
        # Agregar nota sobre el objetivo
        st.markdown("**Objetivo:** ≤8 horas/punto (línea roja punteada)")
    
    def _mostrar_historial_usuario(df_final, usuario_sel):
        """Muestra el historial del usuario seleccionado"""
        if usuario_sel == "Todos":
            return
            
        st.subheader(f"Historial de {usuario_sel}")
        df_hist = df_final[df_final["Usuario_nombre"] == usuario_sel].copy()
        if not df_hist.empty:
            df_hist = df_hist.sort_values("Mes_dt")
        st.dataframe(
            df_hist[[
                "Usuario_nombre", "Mes", "Horas", "Puntos", "Claves",
                "Velocidad", "Bugs", "Bugs_claves", "Bugs_resueltos_extra", 
                "Bugs_extra_claves", "Nota_final"
            ]],
            use_container_width=True,
            hide_index=True,
        )
        return df_hist
    
    def _mostrar_grafico_velocidad_mensual(df_hist, usuario_sel):
        """Muestra el gráfico de velocidad mensual del usuario"""
        if len(df_hist) <= 1:  # Solo mostrar gráfico si hay más de un mes
            st.info("Se necesita más de un mes de datos para mostrar el gráfico de velocidad mensual.")
            return
            
        st.subheader(f"📈 Velocidad Mensual - {usuario_sel}")
        
        # Preparar datos para el gráfico mensual
        df_grafico_mensual = df_hist[['Mes_label', 'Velocidad']].copy()
        
        # Crear gráfico de líneas con Altair (mantiene tema oscuro)
        import altair as alt
        
        # Crear DataFrame con datos y línea de objetivo
        chart_df = df_grafico_mensual.copy()
        chart_df['Objetivo'] = 8
        
        # Crear gráfico base
        base = alt.Chart(chart_df).add_selection(
            alt.selection_interval(bind='scales')
        )
        
        # Línea de datos
        line = base.mark_line(
            point=True,
            strokeWidth=3,
            color='#1f77b4'
        ).encode(
            x=alt.X('Mes_label:N', sort=None, title='Mes'),
            y=alt.Y('Velocidad:Q', title='Velocidad (horas/punto)')
        )
        
        # Línea de objetivo
        objective = base.mark_rule(
            stroke='red',
            strokeDash=[5, 5],
            strokeWidth=2
        ).encode(
            y=alt.datum(8)
        )
        
        # Combinar gráficos
        chart = (line + objective).resolve_scale(
            color='independent'
        ).properties(
            width=600,
            height=300,
            title=f'Velocidad Mensual - {usuario_sel}'
        )
        
        # Mostrar gráfico
        st.altair_chart(chart, use_container_width=True)
        
        # Agregar nota sobre el objetivo
        st.markdown("**Objetivo:** ≤8 horas/punto (línea roja punteada)")

    # ==========================
    #   FUNCIÓN: MOSTRAR RANKING Y HISTÓRICO
    # ==========================
    
    def mostrar_ranking_y_historico(df_final, usuario_sel, allowed_names):
        """Función principal refactorizada para mostrar ranking y histórico"""
        
        # === OPTIMIZACIÓN: Cache de cálculos pesados ===
        cache_key_calculos = f"calculos_velocidad_{len(df_final)}_{hash(str(allowed_names))}"
        
        # Verificar si ya tenemos los cálculos en cache
        if cache_key_calculos in st.session_state:
            usuarios_validos = st.session_state[cache_key_calculos]["usuarios_validos"]
            df_ranking_completo = st.session_state[cache_key_calculos]["df_ranking"]
        else:
            # 1. Calcular usuarios válidos
            usuarios_validos = _calcular_usuarios_validos(df_final, allowed_names)
            
            # 4. Calcular ranking completo (una sola vez)
            st.subheader("Ranking de devs")
            df_ranking_completo = _calcular_ranking(df_final, usuarios_validos)
            
            # Guardar en cache
            st.session_state[cache_key_calculos] = {
                "usuarios_validos": usuarios_validos,
                "df_ranking": df_ranking_completo
            }
        
        # 2. Mostrar selector de usuario (rápido, solo filtro)
        usuario_sel = _mostrar_selector_usuario(usuarios_validos)
        
        # 3. Mostrar cards de objetivos
        _mostrar_cards_objetivos()
        
        if df_ranking_completo.empty:
            st.info("No hay usuarios con puntos en la ventana seleccionada.")
        else:
            # 5. Filtrar por usuario si no es "Todos" (rápido, solo filtro)
            if usuario_sel != "Todos":
                df_ranking = df_ranking_completo[df_ranking_completo["Usuario_nombre"] == usuario_sel]
                
                # Mostrar alerta si el usuario tiene meses con nota 0
                if not df_ranking.empty and df_ranking.iloc[0]["Meses_con_nota_0"] > 0:
                    meses_con_0 = df_ranking.iloc[0]["Meses_con_nota_0"]
                    total_meses = df_ranking.iloc[0]["Total_meses"]
                    st.warning(f"⚠️ **Atención:** {usuario_sel} tiene {meses_con_0} de {total_meses} meses con nota final 0. Verificar datos.")
            else:
                df_ranking = df_ranking_completo
            
            # 6. Mostrar tabla de ranking
            _mostrar_tabla_ranking(df_ranking, usuario_sel)
            
            # 7. Mostrar gráfico de ranking general
            _mostrar_grafico_ranking(df_ranking, usuario_sel)
        
        # 8. Mostrar historial del usuario
        df_hist = _mostrar_historial_usuario(df_final, usuario_sel)
        
        # 9. Mostrar gráfico de velocidad mensual
        if df_hist is not None:
            _mostrar_grafico_velocidad_mensual(df_hist, usuario_sel)

    # ==========================
    #   EJECUCIÓN PRINCIPAL
    # ==========================
    
    tiempo_inicio = time.time()
    print(f"⏱️ [VELOCIDAD] Inicio de carga de pestaña")
    
    # Cargar datos (usar cache si está disponible y es válido)
    force_refresh = st.session_state.get("force_refresh", False)
    
    tiempo_antes_carga = time.time()
    print(f"⏱️ [VELOCIDAD] Antes de cargar datos: {tiempo_antes_carga - tiempo_inicio:.2f}s")
    
    # Verificar si hay cache válido
    if (not force_refresh and 
        cache_key_velocidad in st.session_state and 
        len(st.session_state[cache_key_velocidad].get("historias", [])) >= 5):
        cache_data = st.session_state[cache_key_velocidad]
        historias = cache_data.get("historias", [])
        bugs = cache_data.get("bugs", [])
        tiempo_despues_carga = time.time()
        print(f"⏱️ [VELOCIDAD] Datos desde cache: {tiempo_despues_carga - tiempo_antes_carga:.2f}s ({len(historias)} historias, {len(bugs)} bugs)")
    else:
        historias, bugs = cargar_datos_velocidad(
            get_jira(), fecha_inicio.strftime("%Y-%m-%d"), fecha_fin.strftime("%Y-%m-%d"), 
            proyecto_sel, force_refresh
        )
        tiempo_despues_carga = time.time()
        print(f"⏱️ [VELOCIDAD] Datos desde BD: {tiempo_despues_carga - tiempo_antes_carga:.2f}s ({len(historias)} historias, {len(bugs)} bugs)")
    
    if not historias and not bugs:
        st.error("❌ No se pudieron cargar datos de Jira")
        st.stop()
    
    # === PROTECCIÓN: Alertas visuales de calidad de datos ===
    col_alert1, col_alert2 = st.columns(2)
    
    tiempo_antes_procesar_historias = time.time()
    print(f"⏱️ [VELOCIDAD] Antes de procesar historias: {tiempo_antes_procesar_historias - tiempo_inicio:.2f}s")
    
    # Procesar datos
    df_issues = procesar_historias(historias, accountid_to_name, name_to_acc)
    
    tiempo_despues_procesar_historias = time.time()
    print(f"⏱️ [VELOCIDAD] Procesar historias: {tiempo_despues_procesar_historias - tiempo_antes_procesar_historias:.2f}s ({len(df_issues)} filas)")
    
    # Crear mapeo de historias por desarrollador para bugs extra
    tiempo_antes_mapeo = time.time()
    historias_por_dev = {}
    for _, row in df_issues.iterrows():
        dev = row["Usuario_nombre"]
        historia = row["Issue"]
        if dev not in historias_por_dev:
            historias_por_dev[dev] = set()
        historias_por_dev[dev].add(historia)
    
    tiempo_despues_mapeo = time.time()
    print(f"⏱️ [VELOCIDAD] Crear mapeo historias por dev: {tiempo_despues_mapeo - tiempo_antes_mapeo:.2f}s")
    
    tiempo_antes_procesar_bugs = time.time()
    bug_rows, bugs_extra_rows = procesar_bugs(bugs, historias_por_dev)
    
    tiempo_despues_procesar_bugs = time.time()
    print(f"⏱️ [VELOCIDAD] Procesar bugs: {tiempo_despues_procesar_bugs - tiempo_antes_procesar_bugs:.2f}s ({len(bug_rows)} bugs normales, {len(bugs_extra_rows)} bugs extra)")
    
    # Aplicar filtro de proyecto a las horas
    tiempo_antes_filtro_horas = time.time()
    if proyecto_sel == "ATI":
        proyectos_validos = ["AFUs ATI", "TECH LAB - INTERNO"]
    elif proyecto_sel == "Postventas":
        proyectos_validos = ["TALLER - MAIPÚ -", "REPUESTOS MAIPU", "AFUS", "TECH LAB - INTERNO"]
    else:  # Todos
        proyectos_validos = ["TALLER - MAIPÚ -", "REPUESTOS MAIPU", "AFUS", "AFUs ATI", "TECH LAB - INTERNO"]
    
    # Filtrar horas por proyecto
    df_horas_filtrado = df_horas[df_horas["Proyecto_logico"].isin(proyectos_validos)]
    df_horas_sum_filtrado = df_horas_filtrado.groupby(["Usuario_nombre", "Mes_dt"], as_index=False)["Horas"].sum()
    
    tiempo_despues_filtro_horas = time.time()
    print(f"⏱️ [VELOCIDAD] Filtrar y agrupar horas: {tiempo_despues_filtro_horas - tiempo_antes_filtro_horas:.2f}s")
    
    tiempo_antes_agregar = time.time()
    # Agregar por usuario/mes
    df_completo = agregar_por_usuario_mes(df_issues, bug_rows, bugs_extra_rows, df_horas_sum_filtrado)
    
    tiempo_despues_agregar = time.time()
    print(f"⏱️ [VELOCIDAD] Agregar por usuario/mes: {tiempo_despues_agregar - tiempo_antes_agregar:.2f}s")
    
    tiempo_antes_aplicar_filtros = time.time()
    # Aplicar filtros
    df_filtrado = aplicar_filtros(df_completo, fecha_inicio, fecha_fin, proyecto_sel)
    
    tiempo_despues_aplicar_filtros = time.time()
    print(f"⏱️ [VELOCIDAD] Aplicar filtros: {tiempo_despues_aplicar_filtros - tiempo_antes_aplicar_filtros:.2f}s")
    
    tiempo_antes_metricas = time.time()
    # Calcular métricas finales
    df_final = calcular_metricas_finales(df_filtrado)
    
    tiempo_despues_metricas = time.time()
    print(f"⏱️ [VELOCIDAD] Calcular métricas finales: {tiempo_despues_metricas - tiempo_antes_metricas:.2f}s")
    
    tiempo_antes_mostrar = time.time()
    # Mostrar resultados
    mostrar_ranking_y_historico(df_final, "Todos", allowed_names)
    
    tiempo_final = time.time()
    tiempo_total = tiempo_final - tiempo_inicio
    print(f"⏱️ [VELOCIDAD] ⏱️⏱️⏱️ TIEMPO TOTAL: {tiempo_total:.2f} segundos ⏱️⏱️⏱️")
    print(f"⏱️ [VELOCIDAD] Mostrar resultados: {tiempo_final - tiempo_antes_mostrar:.2f}s")