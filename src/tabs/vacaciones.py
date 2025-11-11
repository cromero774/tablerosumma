"""
Pestaña de Vacaciones
Gestión de vacaciones de usuarios
"""

import streamlit as st
import json
import os
from datetime import datetime, date, timedelta
import pandas as pd
import io

from src.utils.database_helper import DatabaseHelper

def cargar_datos_usuarios():
    """Cargar datos de usuarios desde la base de datos."""
    with DatabaseHelper() as db:
        _migrar_usuarios_desde_json(db)
        return db.obtener_usuarios_vacaciones()

def cargar_vacaciones_registradas():
    """Cargar vacaciones registradas desde la base de datos."""
    with DatabaseHelper() as db:
        _migrar_vacaciones_desde_json(db)
        return db.obtener_vacaciones_agrupadas()


def _migrar_vacaciones_desde_json(db: DatabaseHelper):
    """Migrar datos del JSON legacy a la base de datos si aún no se migraron."""
    vacaciones_path = "data/vacaciones_registradas.json"
    if not os.path.exists(vacaciones_path):
        return

    try:
        if db.contar_vacaciones_totales() > 0:
            return

        with open(vacaciones_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for vac in data:
            usuario = vac.get("usuario")
            if not usuario:
                continue

            opciones = []
            if "opciones" in vac:
                opciones = vac.get("opciones", [])
            elif "opcion_principal" in vac and vac["opcion_principal"]:
                opcion = vac["opcion_principal"]
                if "cambiable" in opcion:
                    opcion = {k: v for k, v in opcion.items() if k != "cambiable"}
                opciones = [opcion]

            observaciones = vac.get("observaciones", "")
            if opciones:
                db.agregar_vacaciones(usuario, opciones, observaciones)
            elif observaciones:
                db.guardar_observaciones_vacaciones(usuario, observaciones)

        # Renombrar archivo para no volver a migrar
        backup_path = vacaciones_path + ".bak"
        os.replace(vacaciones_path, backup_path)
        st.success("✅ Vacaciones migradas a la base de datos y archivo legado renombrado a vacaciones_registradas.json.bak")
    except Exception as e:
        st.warning(f"⚠️ No se pudo migrar el archivo de vacaciones legado: {e}")


def _migrar_usuarios_desde_json(db: DatabaseHelper):
    """Migrar usuarios desde el archivo JSON legacy a la tabla correspondiente."""
    usuarios_path = "data/usuarios_vacaciones.json"
    if not os.path.exists(usuarios_path):
        return

    try:
        if db.contar_usuarios_vacaciones() > 0:
            return

        with open(usuarios_path, 'r', encoding='utf-8') as f:
            usuarios = json.load(f)

        db.insertar_usuarios_vacaciones_bulk(usuarios)
        backup_path = usuarios_path + ".bak"
        os.replace(usuarios_path, backup_path)
        st.success("✅ Usuarios de vacaciones migrados a la base de datos. Archivo legado renombrado a usuarios_vacaciones.json.bak")
    except Exception as e:
        st.warning(f"⚠️ No se pudo migrar el archivo de usuarios de vacaciones: {e}")

def obtener_usuario_por_nombre(nombre, usuarios):
    """Obtener datos de usuario por nombre"""
    for usuario in usuarios:
        if usuario["nombre"] == nombre:
            return usuario
    return None

def calcular_dias_periodo(desde, hasta):
    """Calcular cantidad de días entre dos fechas (inclusive)"""
    desde_date = datetime.strptime(desde, "%Y-%m-%d").date()
    hasta_date = datetime.strptime(hasta, "%Y-%m-%d").date()
    return (hasta_date - desde_date).days + 1

def hay_solapamiento_fechas(fecha1_desde, fecha1_hasta, fecha2_desde, fecha2_hasta):
    """Verificar si dos períodos de fechas se solapan"""
    # Convertir a objetos date para comparación
    d1_inicio = datetime.strptime(fecha1_desde, "%Y-%m-%d").date()
    d1_fin = datetime.strptime(fecha1_hasta, "%Y-%m-%d").date()
    d2_inicio = datetime.strptime(fecha2_desde, "%Y-%m-%d").date()
    d2_fin = datetime.strptime(fecha2_hasta, "%Y-%m-%d").date()
    
    # Dos períodos se solapan si: inicio1 <= fin2 AND inicio2 <= fin1
    return d1_inicio <= d2_fin and d2_inicio <= d1_fin

def obtener_opcion_principal_por_usuario(vacaciones_registradas, usuarios):
    """Obtener todas las opciones de cada usuario para visualización (hasta 3 opciones)"""
    datos_opciones = []
    nombres_usuarios = {u["nombre"]: u for u in usuarios}
    
    # Primero, recopilar todas las opciones con sus fechas para detectar conflictos
    opciones_con_fechas = []
    for vac in vacaciones_registradas:
        usuario = vac.get("usuario")
        opciones = vac.get("opciones", [])
        for opcion in opciones:
            opciones_con_fechas.append({
                "usuario": usuario,
                "desde": opcion["desde"],
                "hasta": opcion["hasta"],
                "vac_data": vac
            })
    
    # Procesar cada usuario y sus opciones
    for vac in vacaciones_registradas:
        usuario = vac.get("usuario")
        opciones = vac.get("opciones", [])
        usuario_data = nombres_usuarios.get(usuario, {})
        
        # Si no tiene opciones, mostrar una fila vacía
        if not opciones:
            datos_opciones.append({
                "Usuario": usuario,
                "Líder": usuario_data.get("lider", ""),
                "Opción": "-",
                "Desde": "-",
                "Hasta": "-",
                "Días": "-",
                "⚠️ Conflicto": "",
                "Observaciones": vac.get("observaciones", "")
            })
        else:
            # Mostrar cada opción en una fila separada
            for idx, opcion in enumerate(opciones, 1):
                # Verificar si hay solapamiento con otros usuarios
                usuarios_con_conflicto = []
                for otra_opcion in opciones_con_fechas:
                    if otra_opcion["usuario"] != usuario:  # No comparar con el mismo usuario
                        if hay_solapamiento_fechas(
                            opcion["desde"], opcion["hasta"],
                            otra_opcion["desde"], otra_opcion["hasta"]
                        ):
                            usuarios_con_conflicto.append(otra_opcion["usuario"])
                
                # Crear indicador de conflicto
                if usuarios_con_conflicto:
                    conflicto_texto = f"⚠️ Conflicto con: {', '.join(sorted(set(usuarios_con_conflicto)))}"
                else:
                    conflicto_texto = ""
                
                datos_opciones.append({
                    "Usuario": usuario if idx == 1 else "",  # Solo mostrar nombre en la primera opción
                    "Líder": usuario_data.get("lider", "") if idx == 1 else "",
                    "Opción": f"Opción {idx}",
                    "Desde": datetime.strptime(opcion["desde"], "%Y-%m-%d").strftime("%d/%m/%Y"),
                    "Hasta": datetime.strptime(opcion["hasta"], "%Y-%m-%d").strftime("%d/%m/%Y"),
                    "Días": calcular_dias_periodo(opcion["desde"], opcion["hasta"]),
                    "⚠️ Conflicto": conflicto_texto,
                    "Observaciones": vac.get("observaciones", "") if idx == 1 else ""  # Solo mostrar observaciones en la primera opción
                })
    
    return pd.DataFrame(datos_opciones)

def obtener_todas_las_opciones_por_usuario(vacaciones_registradas, usuarios):
    """Obtener todas las opciones de cada usuario para descarga (hasta 3 opciones)"""
    datos_completos = []
    nombres_usuarios = {u["nombre"]: u for u in usuarios}
    
    for vac in vacaciones_registradas:
        usuario = vac.get("usuario")
        opciones = vac.get("opciones", [])
        usuario_data = nombres_usuarios.get(usuario, {})
        
        # Si no tiene opciones, agregar una fila vacía
        if not opciones:
            datos_completos.append({
                "Usuario": usuario,
                "Líder": usuario_data.get("lider", ""),
                "Opción": "-",
                "Desde": "-",
                "Hasta": "-",
                "Días": "-",
                "Observaciones": vac.get("observaciones", "")
            })
        else:
            # Agregar cada opción
            for idx, opcion in enumerate(opciones, 1):
                datos_completos.append({
                    "Usuario": usuario,
                    "Líder": usuario_data.get("lider", ""),
                    "Opción": f"Opción {idx}",
                    "Desde": datetime.strptime(opcion["desde"], "%Y-%m-%d").strftime("%d/%m/%Y"),
                    "Hasta": datetime.strptime(opcion["hasta"], "%Y-%m-%d").strftime("%d/%m/%Y"),
                    "Días": calcular_dias_periodo(opcion["desde"], opcion["hasta"]),
                    "Observaciones": vac.get("observaciones", "")
                })
    
    return pd.DataFrame(datos_completos)

def mostrar_vacaciones():
    """Mostrar la pestaña de Vacaciones"""
    
    # Inicializar session state para edición (DEBE estar al inicio)
    if 'usuario_editando' not in st.session_state:
        st.session_state.usuario_editando = None
    
    st.header("🏖️ Vacaciones")
    st.caption("📅 Gestión de vacaciones del equipo")
    
    # Cargar datos
    usuarios = cargar_datos_usuarios()
    vacaciones_registradas = cargar_vacaciones_registradas()
    
    if not usuarios:
        st.warning("⚠️ No se encontraron datos de usuarios en la base de datos. Ejecuta la migración o carga la tabla `usuarios_vacaciones`.")
        return
    
    # ========== SECCIÓN 1: AGREGAR VACACIONES ==========
    st.subheader("➕ Agregar Vacaciones")
    
    # Inicializar flag de reset si no existe
    if 'reset_form_agregar' not in st.session_state:
        st.session_state.reset_form_agregar = 0
    
    nombres_usuarios = sorted([u["nombre"] for u in usuarios])
    
    # Usar el flag de reset para cambiar la key del selectbox y forzar reset
    reset_key = f"select_usuario_agregar_{st.session_state.reset_form_agregar}"
    usuario_para_agregar = st.selectbox(
        "Usuario:",
        options=[""] + nombres_usuarios,
        key=reset_key,
        index=0
    )
    
    if usuario_para_agregar:
        usuario_data_agregar = obtener_usuario_por_nombre(usuario_para_agregar, usuarios)
        
        if usuario_data_agregar:
            # Verificar si el usuario ya tiene vacaciones registradas
            vacaciones_usuario_existentes = [v for v in vacaciones_registradas if v.get("usuario") == usuario_para_agregar]
            opciones_existentes = []
            if vacaciones_usuario_existentes:
                opciones_existentes = vacaciones_usuario_existentes[0].get("opciones", [])
            
            # Mostrar información del usuario
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.info(f"**Líder:** {usuario_data_agregar.get('lider', 'N/A')}")
            with col_info2:
                dias_disponibles = usuario_data_agregar.get("dias_vacaciones")
                if dias_disponibles is not None:
                    st.info(f"**Días de vacaciones:** {dias_disponibles}")
            
            # Verificar cuántas opciones puede agregar
            opciones_disponibles = 3 - len(opciones_existentes)
            if opciones_disponibles <= 0:
                st.warning(f"⚠️ {usuario_para_agregar} ya tiene 3 opciones de vacaciones registradas. Edita o elimina una opción existente para agregar nuevas.")
            else:
                st.info(f"💡 Puedes agregar hasta {opciones_disponibles} opción(es) de vacaciones (máximo 3 opciones por usuario).")
                
                # Formulario para agregar opciones (hasta 3)
                opciones_fechas = []  # Almacenar todas las fechas ingresadas
                opciones_a_guardar = []
                errores_validacion = []
                
                for i in range(opciones_disponibles):
                    st.markdown(f"#### Opción {len(opciones_existentes) + i + 1}")
                    
                    col_op1, col_op2 = st.columns(2)
                    
                    with col_op1:
                        fecha_desde = st.date_input(
                            f"Fecha desde (Opción {len(opciones_existentes) + i + 1}):",
                            value=None,
                            key=f"fecha_desde_opcion_{i}_{st.session_state.reset_form_agregar}"
                        )
                    
                    with col_op2:
                        # Si hay fecha desde seleccionada, usar esa como mínimo para fecha hasta
                        min_value_hasta = fecha_desde if fecha_desde else None
                        fecha_hasta = st.date_input(
                            f"Fecha hasta (Opción {len(opciones_existentes) + i + 1}):",
                            value=None,
                            min_value=min_value_hasta,
                            key=f"fecha_hasta_opcion_{i}_{st.session_state.reset_form_agregar}"
                        )
                    
                    # Validar que si hay fecha desde, también debe haber fecha hasta
                    if fecha_desde and not fecha_hasta:
                        errores_validacion.append(f"⚠️ Opción {len(opciones_existentes) + i + 1}: Si completaste 'Fecha desde', también debes completar 'Fecha hasta'")
                    elif not fecha_desde and fecha_hasta:
                        errores_validacion.append(f"⚠️ Opción {len(opciones_existentes) + i + 1}: Si completaste 'Fecha hasta', también debes completar 'Fecha desde'")
                    elif fecha_desde and fecha_hasta:
                        if fecha_hasta < fecha_desde:
                            errores_validacion.append(f"⚠️ Opción {len(opciones_existentes) + i + 1}: La fecha 'hasta' debe ser mayor o igual a la fecha 'desde'")
                        else:
                            dias = calcular_dias_periodo(
                                fecha_desde.strftime("%Y-%m-%d"),
                                fecha_hasta.strftime("%Y-%m-%d")
                            )
                            st.caption(f"📅 {dias} día(s) - Opción {len(opciones_existentes) + i + 1}")
                            opciones_a_guardar.append({
                                "desde": fecha_desde.strftime("%Y-%m-%d"),
                                "hasta": fecha_hasta.strftime("%Y-%m-%d")
                            })
                    
                    # Guardar estado de las fechas para validación
                    opciones_fechas.append({
                        "desde": fecha_desde,
                        "hasta": fecha_hasta
                    })
                
                # Mostrar errores de validación si los hay
                if errores_validacion:
                    for error in errores_validacion:
                        st.warning(error)
                
                # Campo de observaciones
                observaciones_nueva = st.text_area(
                    "Observaciones:",
                    value="",
                    key=f"observaciones_nueva_{st.session_state.reset_form_agregar}",
                    height=100
                )
                
                # Validar que al menos una opción esté completa antes de permitir guardar
                puede_guardar = len(opciones_a_guardar) > 0 and len(errores_validacion) == 0
                
                if puede_guardar:
                    if st.button("💾 Guardar Vacaciones", key="btn_guardar_vacaciones", type="primary"):
                        try:
                            observaciones_guardar = None
                            if observaciones_nueva is not None and observaciones_nueva.strip():
                                observaciones_guardar = observaciones_nueva
                            with DatabaseHelper() as db:
                                db.agregar_vacaciones(usuario_para_agregar, opciones_a_guardar, observaciones_guardar)
                            if 'reset_form_agregar' not in st.session_state:
                                st.session_state.reset_form_agregar = 0
                            st.session_state.reset_form_agregar += 1
                            total_dias = sum(calcular_dias_periodo(op["desde"], op["hasta"]) for op in opciones_a_guardar)
                            st.success(f"✅ {len(opciones_a_guardar)} opción(es) guardada(s) para {usuario_para_agregar} (total: {total_dias} días)")
                            st.rerun()
                        except ValueError as e:
                            st.error(f"❌ {e}")
                        except Exception as e:
                            st.error(f"❌ Error guardando vacaciones: {e}")
                elif len(opciones_a_guardar) == 0 and any(op["desde"] or op["hasta"] for op in opciones_fechas):
                    st.error("❌ Debes completar al menos una opción de vacaciones (fecha desde y fecha hasta) para poder guardar.")
                elif len(opciones_a_guardar) == 0:
                    st.caption("💡 Completa al menos una opción de vacaciones (fecha desde y fecha hasta) para guardar.")
    
    st.markdown("---")
    
    # ========== SECCIÓN 2: TABLA RESUMEN ==========
    st.subheader("📊 Resumen de Vacaciones")
    
    if vacaciones_registradas:
        df_resumen = obtener_opcion_principal_por_usuario(vacaciones_registradas, usuarios)
        
        if not df_resumen.empty:
            # Verificar si hay conflictos de fechas
            hay_conflictos = False
            if "⚠️ Conflicto" in df_resumen.columns:
                hay_conflictos = df_resumen["⚠️ Conflicto"].str.contains("⚠️", na=False).any()
            
            if hay_conflictos:
                st.warning("⚠️ **ADVERTENCIA:** Hay usuarios con períodos de vacaciones que se solapan en las mismas fechas. Revisa la columna '⚠️ Conflicto' en la tabla.")
            
            st.dataframe(df_resumen, use_container_width=True, hide_index=True)
        else:
            st.info("No hay vacaciones registradas.")
    else:
        st.info("No hay vacaciones registradas.")
    
    st.markdown("---")
    
    # ========== SECCIÓN 3: EDITAR/ELIMINAR ==========
    st.subheader("✏️ Editar o Eliminar Registro")
    
    # Si hay un usuario en edición desde la tabla, mostrar formulario de edición
    if st.session_state.usuario_editando:
        usuario_seleccionado = st.session_state.usuario_editando
        usuario_data = obtener_usuario_por_nombre(usuario_seleccionado, usuarios)
        
        st.info(f"✏️ **Editando:** {usuario_seleccionado}")
        if st.button("❌ Cancelar edición", key="btn_cancelar_edicion"):
            st.session_state.usuario_editando = None
            st.rerun()
        
        if usuario_data:
            # Obtener días disponibles del usuario (disponible para todo el contexto)
            dias_disponibles_usuario = usuario_data.get("dias_vacaciones")
            
            # Mostrar información del usuario
            col1, col2 = st.columns(2)
            
            with col1:
                st.info(f"**Líder:** {usuario_data['lider']}")
            
            with col2:
                # Solo mostrar días de vacaciones si tiene
                if dias_disponibles_usuario is not None:
                    st.info(f"**Días de vacaciones:** {dias_disponibles_usuario}")
            
            st.markdown("---")
            
            # Obtener vacaciones existentes del usuario (ahora es un solo registro con array de opciones)
            vac_data = None
            for vac in vacaciones_registradas:
                if vac.get("usuario") == usuario_seleccionado:
                    vac_data = vac
                    break
            
            if vac_data:
                opciones = vac_data.get("opciones", [])
                observaciones = vac_data.get("observaciones", "")
                
                if opciones:
                    # Inicializar selector de opción si no existe
                    if 'opcion_editando' not in st.session_state:
                        st.session_state.opcion_editando = 0
                    
                    # Si hay múltiples opciones, mostrar selector
                    if len(opciones) > 1:
                        opciones_para_seleccionar = []
                        for i, op in enumerate(opciones):
                            desde_str = datetime.strptime(op["desde"], "%Y-%m-%d").strftime("%d/%m/%Y")
                            hasta_str = datetime.strptime(op["hasta"], "%Y-%m-%d").strftime("%d/%m/%Y")
                            dias = calcular_dias_periodo(op["desde"], op["hasta"])
                            opciones_para_seleccionar.append(f"Opción {i+1}: {desde_str} - {hasta_str} ({dias} días)")
                        
                        opcion_seleccionada = st.selectbox(
                            "Seleccionar opción de vacaciones a editar:",
                            options=opciones_para_seleccionar,
                            key="select_opcion_editar",
                            index=st.session_state.opcion_editando
                        )
                        indice_opcion = opciones_para_seleccionar.index(opcion_seleccionada)
                        st.session_state.opcion_editando = indice_opcion
                    else:
                        st.session_state.opcion_editando = 0
                    
                    opcion_actual = opciones[st.session_state.opcion_editando]
                    desde = datetime.strptime(opcion_actual["desde"], "%Y-%m-%d").date()
                    hasta = datetime.strptime(opcion_actual["hasta"], "%Y-%m-%d").date()
                    dias = calcular_dias_periodo(opcion_actual["desde"], opcion_actual["hasta"])
                    
                    # Mostrar información de la opción actual
                    st.markdown(f"#### Opción {st.session_state.opcion_editando + 1}")
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.metric("Desde", desde.strftime("%d/%m/%Y"))
                    with col_info2:
                        st.metric("Hasta", hasta.strftime("%d/%m/%Y"))
                    with col_info3:
                        st.metric("Días", dias)
                    
                    # Mostrar observaciones actuales
                    if observaciones:
                        st.info(f"**Observaciones actuales:** {observaciones}")
                    
                    # Sección de edición
                    st.markdown("#### ✏️ Editar Vacaciones")
                    
                    col_edit1, col_edit2 = st.columns(2)
                    
                    with col_edit1:
                        nueva_fecha_desde = st.date_input(
                            "Nueva fecha desde:",
                            value=desde,
                            key="nueva_fecha_desde_opcion"
                        )
                    
                    with col_edit2:
                        # Usar la fecha desde como mínimo para fecha hasta
                        nueva_fecha_hasta = st.date_input(
                            "Nueva fecha hasta:",
                            value=hasta,
                            min_value=nueva_fecha_desde,
                            key="nueva_fecha_hasta_opcion"
                        )
                    
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        if st.button("✏️ Actualizar Opción", key="btn_actualizar_opcion", use_container_width=True):
                            if nueva_fecha_hasta < nueva_fecha_desde:
                                st.error("❌ La fecha 'hasta' debe ser mayor o igual a la fecha 'desde'")
                            else:
                                try:
                                    indice_actual = st.session_state.opcion_editando
                                    with DatabaseHelper() as db:
                                        db.actualizar_vacacion(
                                            usuario_seleccionado,
                                            indice_actual + 1,
                                            nueva_fecha_desde.strftime("%Y-%m-%d"),
                                            nueva_fecha_hasta.strftime("%Y-%m-%d")
                                        )
                                    st.session_state.usuario_editando = None
                                    st.session_state.opcion_editando = 0
                                except Exception as e:
                                    st.error(f"❌ Error actualizando la opción: {e}")
                                else:
                                    st.success("✅ Opción de vacaciones actualizada")
                                    st.rerun()
                    
                    with col_btn2:
                        if st.button("🗑️ Eliminar Opción", key="btn_eliminar_opcion", type="secondary", use_container_width=True):
                            try:
                                indice_actual = st.session_state.opcion_editando
                                with DatabaseHelper() as db:
                                    db.eliminar_vacacion(usuario_seleccionado, indice_actual + 1)
                                st.session_state.usuario_editando = None
                                st.session_state.opcion_editando = 0
                            except Exception as e:
                                st.error(f"❌ Error eliminando la opción: {e}")
                            else:
                                st.success("✅ Opción de vacaciones eliminada")
                                st.rerun()
                    
                    # Editar observaciones
                    st.markdown("#### 📝 Editar Observaciones")
                    nuevas_observaciones = st.text_area(
                        "Observaciones:",
                        value=observaciones,
                        key="editar_observaciones_vacaciones",
                        height=100
                    )
                    
                    if st.button("💾 Actualizar Observaciones", key="btn_actualizar_observaciones"):
                        try:
                            with DatabaseHelper() as db:
                                db.guardar_observaciones_vacaciones(usuario_seleccionado, nuevas_observaciones or "")
                            st.session_state.usuario_editando = None
                            st.session_state.opcion_editando = 0
                        except Exception as e:
                            st.error(f"❌ Error guardando observaciones: {e}")
                        else:
                            st.success("✅ Observaciones actualizadas")
                            st.rerun()
                else:
                    st.warning("⚠️ Este usuario no tiene opciones de vacaciones registradas.")
            else:
                st.warning("⚠️ Este usuario no tiene vacaciones registradas.")
    else:
        # Si no hay usuario en edición, mostrar selector para editar o eliminar
        if vacaciones_registradas:
            df_resumen = obtener_opcion_principal_por_usuario(vacaciones_registradas, usuarios)
            
            if not df_resumen.empty:
                # Obtener usuarios únicos (filtrar valores vacíos)
                usuarios_con_vacaciones = sorted([u for u in df_resumen['Usuario'].tolist() if u and u != ""])
                usuario_a_editar = st.selectbox(
                    "Seleccionar usuario para editar o eliminar:",
                    options=[""] + usuarios_con_vacaciones,
                    key="select_usuario_editar"
                )
                
                if usuario_a_editar:
                    col_edit_btn, col_delete_btn = st.columns(2)
                    
                    with col_edit_btn:
                        if st.button("✏️ Editar", key="btn_editar_desde_tabla", type="primary", use_container_width=True):
                            st.session_state.usuario_editando = usuario_a_editar
                            st.rerun()
                    
                    with col_delete_btn:
                        # Verificar si hay confirmación pendiente para este usuario
                        usuario_pendiente_eliminar = st.session_state.get('usuario_pendiente_eliminar', None)
                        
                        if usuario_pendiente_eliminar == usuario_a_editar:
                            st.warning(f"⚠️ ¿Estás seguro de eliminar todas las vacaciones de {usuario_a_editar}?")
                            col_conf1, col_conf2 = st.columns(2)
                            with col_conf1:
                                if st.button("✅ Confirmar", key="btn_confirmar_eliminar", type="primary", use_container_width=True):
                                    try:
                                        with DatabaseHelper() as db:
                                            db.eliminar_todas_vacaciones(usuario_a_editar)
                                        st.session_state.usuario_pendiente_eliminar = None
                                        st.session_state.usuario_editando = None
                                    except Exception as e:
                                        st.error(f"❌ Error eliminando vacaciones: {e}")
                                    else:
                                        st.success(f"✅ Vacaciones de {usuario_a_editar} eliminadas correctamente")
                                        st.rerun()
                            with col_conf2:
                                if st.button("❌ Cancelar", key="btn_cancelar_eliminar", use_container_width=True):
                                    st.session_state.usuario_pendiente_eliminar = None
                                    st.rerun()
                        else:
                            if st.button("🗑️ Eliminar", key="btn_eliminar_desde_tabla", type="secondary", use_container_width=True):
                                st.session_state.usuario_pendiente_eliminar = usuario_a_editar
                                st.rerun()
    
    st.markdown("---")
    
    # ========== SECCIÓN 4: DESCARGAR DATOS ==========
    if vacaciones_registradas:
        st.subheader("📥 Descargar Datos Completos")
        df_completo = obtener_todas_las_opciones_por_usuario(vacaciones_registradas, usuarios)
        
        if not df_completo.empty:
            # Convertir DataFrame a CSV con codificación UTF-8 con BOM para Excel
            # El BOM (Byte Order Mark) hace que Excel reconozca automáticamente UTF-8
            output = io.BytesIO()
            # Agregar BOM UTF-8 manualmente
            output.write('\ufeff'.encode('utf-8'))
            # Escribir el DataFrame como CSV
            df_completo.to_csv(output, index=False, encoding='utf-8', lineterminator='\n')
            csv_bytes = output.getvalue()
            
            st.download_button(
                label="⬇️ Descargar todas las opciones (CSV)",
                data=csv_bytes,
                file_name=f"vacaciones_completas_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                key="btn_descargar_vacaciones"
            )
            st.caption("💡 El archivo descargado incluye todas las opciones de vacaciones (hasta 3 por usuario) de todos los usuarios")
