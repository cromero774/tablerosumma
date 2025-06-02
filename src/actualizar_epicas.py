import os
import json

def actualizar_epicas():
    epicas = [
        {"rn": "REP-4220", "nombre": "AJUSTES DE STOCK", "mes_entrega": "Junio"},
        {"rn": "REP-4217", "nombre": "GENERAR PRESUPUESTO", "mes_entrega": "Junio"},
        {"rn": "REP-4221", "nombre": "MOVIMIENTO ENTRE UBICACIONES", "mes_entrega": "Marzo"},
        {"rn": "REP-4218", "nombre": "NOTA DE TRASLADO", "mes_entrega": "Abril"},
        {"rn": "REP-4248", "nombre": "TRANSFERENCIAS INTERNAS Y EXTERNAS", "mes_entrega": "Agosto"},
        {"rn": "REP-4269", "nombre": "[GESTIÓN DE RECLAMOS]", "mes_entrega": "Junio"},
        {"rn": "REP-4268", "nombre": "NOTA DE NO CONFORMIDAD V1", "mes_entrega": "Julio"},
        {"rn": "REP-4270", "nombre": "NOTA DE NO CONFORMIDAD V2", "mes_entrega": "Agosto"},
        {"rn": "REP-4219", "nombre": "GESTIÓN DE ALMACÉN", "mes_entrega": "Agosto"},
        {"rn": "REP-4574", "nombre": "LOTEO DE PIEZAS", "mes_entrega": "Octubre"},
        {"rn": "REP-4806", "nombre": "CONFIGURACION DE TOPES DE DESCUENTO/INCREMENTO", "mes_entrega": "Agosto"},
        {"rn": "REP-4541", "nombre": "Gestión de Reservas (Control de reservas)", "mes_entrega": "Septiembre"},
        {"rn": "TAL-3544", "nombre": "[CIERRE DE SERVICIOS - TRABAJOS]", "mes_entrega": "Agosto"},
        {"rn": "TAL-3509", "nombre": "TOPES DE DESCUENTO/INCREMENTO", "mes_entrega": "Julio"},
        {"rn": "TAL-3462", "nombre": "CONFIGURACIÓN DE OT", "mes_entrega": "Julio"},
        {"rn": "TAL-3461", "nombre": "AUTORIZACIÓN DE ANULACIONES", "mes_entrega": "Julio"}
    ]

    ruta_actual = os.path.dirname(os.path.abspath(__file__))
    ruta_guardado = os.path.join(ruta_actual, "../data/epicas_relevantes.json")


    with open(ruta_guardado, "w", encoding="utf-8") as f:
        json.dump(epicas, f, indent=4, ensure_ascii=False)

    print(f"Archivo epicas_relevantes.json actualizado en {ruta_guardado}")

if __name__ == "__main__":
    actualizar_epicas()





