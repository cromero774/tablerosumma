"""
Pestaña de Horas Postventas
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from utils.configuracion import MAPEO_TEM, PROYECTOS_POSTVENTA

def mostrar_horas_postventas(df):
    """Mostrar la pestaña de Horas Postventas"""
    
    # Constantes de proyectos
    INTERNAL = "TECH LAB - INTERNO"
    POSTVENTA_NON_INTERNAL = ["TALLER - MAIPÚ -", "REPUESTOS MAIPU", "AFUS"]
    ATI_NON_INTERNAL = ["AFUs ATI"]
    
    MESES_ES = {
        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
    }
    
    if not df.empty:
        cols = st.columns(3)
        
        with cols[0]:
            years = sorted(df["Fecha"].apply(lambda x: str(x)[:4]).unique())
            year = st.selectbox("Año", options=years, index=len(years) - 1, key="horas_postventas_anio")
        
        with cols[1]:
            meses_numeros = list(MESES_ES.keys())
            meses_nombres = [MESES_ES[m] for m in meses_numeros]
            mes_nom = st.selectbox("Mes", options=meses_nombres, index=datetime.now().month - 1, key="horas_postventas_mes")
            mes_real = meses_numeros[meses_nombres.index(mes_nom)]
        
        with cols[2]:
            # Filtrar solo usuarios que están en el mapeo (son nombres válidos, no IDs)
            usuarios_validos = [u for u in df["Usuario"].dropna().unique() if str(u).strip() != ""]
            usuarios_lista = ["Todos"] + sorted(usuarios_validos)
            usuario_seleccionado = st.selectbox("Usuario", usuarios_lista, index=0, key="horas_postventas_usuario")
        
        # Función auxiliar para armar el texto "Usuario (TEM-1, TEM-2); Otro (TEM-5)"
        def _usuarios_y_tems_string(df_alert):
            pares = []
            for usuario, g in df_alert.groupby("Usuario"):
                tems = sorted(g["Issue"].astype(str).unique(), key=lambda x: (len(x), x))
                if str(usuario).strip():
                    pares.append(f"{usuario} ({', '.join(tems)})")
            return "; ".join(pares)
        
        # ============ VISTA "TODOS" ============
        if usuario_seleccionado == "Todos":
            # 1) Filtro por año/mes (sin filtrar proyecto aún)
            df_mes = df[df["Fecha"].str.startswith(str(year))]
            df_mes = df_mes[df_mes["Fecha"].str[5:7] == mes_real]
            
            
            # 2) Usuarios que cargaron no-internal por área (en ese mes)
            users_post = set(df_mes[df_mes["Proyecto_logico"].isin(POSTVENTA_NON_INTERNAL)]["Usuario"])
            users_ati = set(df_mes[df_mes["Proyecto_logico"].isin(ATI_NON_INTERNAL)]["Usuario"])
            users_both = users_post & users_ati
            
            # 3) Armar vista para Postventas
            # POSTVENTAS:
            # - Usuarios BOTH: TODAS sus filas (ATI + POST + INTERNO)
            # - Usuarios solo POST: filas POST + INTERNO
            df_vista = df_mes[
                (df_mes["Usuario"].isin(users_both)) |
                (
                    df_mes["Usuario"].isin(users_post) &
                    (df_mes["Proyecto_logico"].isin(POSTVENTA_NON_INTERNAL + [INTERNAL]))
                )
            ]
            
            # === ALERTA: TEM NO MAPEADAS ===
            if not df_vista.empty:
                # Trabajar únicamente con usuarios mapeados a nombre (JSON aplicado previamente)
                df_mes_alerta = df_mes[df_mes["Usuario"].notna()].copy()
                
                # TEM no mapeada = Issue arranca "TEM-" y NO está en MAPEO_TEM
                mask_tem_no_mapeada = (
                    df_mes_alerta["Issue"].astype(str).str.startswith("TEM-", na=False) &
                    (~df_mes_alerta["Issue"].isin(list(MAPEO_TEM.keys())))
                )
                
                # Limitar a usuarios que realmente aparecen en la vista (y están mapeados)
                usuarios_vista = set(df_vista["Usuario"].dropna().unique())
                df_tem_no_mapeada = df_mes_alerta[mask_tem_no_mapeada & df_mes_alerta["Usuario"].isin(usuarios_vista)].copy()
                
                if not df_tem_no_mapeada.empty:
                    usuarios_y_tems = _usuarios_y_tems_string(df_tem_no_mapeada)
                    st.error(f"⚠️ **TEM no mapeadas** en {MESES_ES[mes_real]} {year}. {usuarios_y_tems}")
                    cols_alerta = ["Usuario", "Fecha", "Issue", "Proyecto", "Horas"]
                    for c in cols_alerta:
                        if c not in df_tem_no_mapeada.columns:
                            df_tem_no_mapeada[c] = ""
                    st.dataframe(
                        df_tem_no_mapeada[cols_alerta].sort_values(["Usuario", "Fecha"]),
                        use_container_width=True, hide_index=True
                    )
            
            if df_vista.empty:
                st.warning("No hay horas cargadas para el mes, año y usuario seleccionados.")
            else:
                # 4) Pivot por usuario x proyecto
                proyectos_mostrar = POSTVENTA_NON_INTERNAL + [INTERNAL]
                tabla_pivot = pd.pivot_table(
                    df_vista,
                    values='Horas',
                    index='Usuario',
                    columns='Proyecto_logico',
                    aggfunc='sum',
                    fill_value=0
                )
                # asegurar columnas en el orden esperado
                for col in proyectos_mostrar:
                    if col not in tabla_pivot.columns:
                        tabla_pivot[col] = 0
                tabla_pivot = tabla_pivot[proyectos_mostrar]
                
                tabla_pivot["Total"] = tabla_pivot.sum(axis=1)
                totales = tabla_pivot.sum(axis=0)
                tabla_final = pd.concat([tabla_pivot, pd.DataFrame([totales], index=["Total general"])])
                
                mostrar_detalle = st.checkbox("Mostrar detalle por proyecto", value=False, key="horas_postventas_detalle")
                tabla_mostrar = tabla_final if mostrar_detalle else tabla_final[["Total"]]
                
                st.dataframe(
                    tabla_mostrar.reset_index().style.format({
                        c: "{:,.2f}".format for c in tabla_mostrar.columns if c != "Usuario"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
        
        # ============ VISTA POR USUARIO ============
        else:
            # Universo del usuario (para gráficos/tabla) — igual que antes
            fecha_ref = datetime(int(year), int(mes_real), 1)
            fecha_inicio = (fecha_ref - pd.DateOffset(months=5)).replace(day=1)
            
            df_user = df[df["Usuario"] == usuario_seleccionado].copy()
            df_user["Fecha_dt"] = pd.to_datetime(df_user["Fecha"], errors="coerce")
            df_user = df_user[
                (df_user["Fecha_dt"] >= fecha_inicio) &
                (df_user["Fecha_dt"] <= fecha_ref + pd.offsets.MonthEnd(0))
            ]
            df_user["anio_mes"] = df_user["Fecha_dt"].dt.strftime("%Y-%m")
            
            # Para la vista, incluir INTERNAL solo si trabajó en el área ese mes
            meses_ultimos = pd.date_range(start=fecha_inicio, end=fecha_ref, freq="MS").strftime("%Y-%m").tolist()
            bolsas = []
            for ym in meses_ultimos:
                df_m = df_user[df_user["anio_mes"] == ym]
                if df_m.empty:
                    continue
                
                has_post = df_m["Proyecto_logico"].isin(POSTVENTA_NON_INTERNAL).any()
                has_ati = df_m["Proyecto_logico"].isin(ATI_NON_INTERNAL).any()
                
                if has_post and has_ati:
                    bolsas.append(df_m)  # si trabajó en ambas, mostrar todo
                elif has_post:
                    bolsas.append(df_m[df_m["Proyecto_logico"].isin(POSTVENTA_NON_INTERNAL + [INTERNAL])])
            
            df_user_vista = pd.concat(bolsas, ignore_index=True) if bolsas else pd.DataFrame(columns=df_user.columns)
            
            # === ALERTA: TEM NO MAPEADAS (solo mes/año seleccionados, usuario mapeado) ===
            df_user_mes = df[
                (df["Fecha"].str.startswith(str(year))) &
                (df["Fecha"].str[5:7] == mes_real) &
                (df["Usuario"] == usuario_seleccionado)
            ].copy()
            
            if not df_user_mes.empty and pd.notna(usuario_seleccionado):
                mask_tem_no_mapeada_user = (
                    df_user_mes["Issue"].astype(str).str.startswith("TEM-", na=False) &
                    (~df_user_mes["Issue"].isin(list(MAPEO_TEM.keys())))
                )
                df_tem_no_mapeada_user = df_user_mes[mask_tem_no_mapeada_user].copy()
                if not df_tem_no_mapeada_user.empty:
                    usuarios_y_tems = _usuarios_y_tems_string(df_tem_no_mapeada_user)
                    st.error(f"⚠️ **TEM no mapeadas** en {MESES_ES[mes_real]} {year}. {usuarios_y_tems}")
                    cols_alerta = ["Usuario", "Fecha", "Issue", "Proyecto", "Horas"]
                    for c in cols_alerta:
                        if c not in df_tem_no_mapeada_user.columns:
                            df_tem_no_mapeada_user[c] = ""
                    st.dataframe(
                        df_tem_no_mapeada_user[cols_alerta].sort_values(["Fecha"]),
                        use_container_width=True, hide_index=True
                    )
            
            # Resumen por mes (últimos 6)
            if df_user_vista.empty:
                st.subheader(f"Horas cargadas por {usuario_seleccionado} (últimos 6 meses)")
                st.info("Sin datos para mostrar con los criterios actuales.")
            else:
                resumen_meses = df_user_vista.groupby("anio_mes")["Horas"].sum().reset_index()
                resumen_meses = resumen_meses.set_index("anio_mes").reindex(meses_ultimos, fill_value=0).reset_index()
                resumen_meses["Mes"] = resumen_meses["anio_mes"].apply(lambda x: MESES_ES[x[5:]] + " " + x[:4])
                
                st.subheader(f"Horas cargadas por {usuario_seleccionado} (últimos 6 meses)")
                st.dataframe(resumen_meses[["Mes", "Horas"]], hide_index=True, use_container_width=True)
                st.bar_chart(resumen_meses.set_index("anio_mes")["Horas"], use_container_width=True)
    else:
        st.warning("No hay datos para el período seleccionado.")
