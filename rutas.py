"""Rutas HTTP: leen la petición, llaman a la lógica y a la BD y responden JSON."""

import os
from functools import wraps

from flask import Blueprint, jsonify, render_template, request, session

import db
from logica import (Conflicto, DatosInvalidos, NoEncontrada, TasasNoDisponibles,
                    calcular_resumen, convertir, obtener_tasas, rango_mes,
                    tasa_cambio, validar_descripcion, validar_fecha,
                    validar_mes, validar_moneda, validar_monto)

bp = Blueprint("rutas", __name__)


# ------------------------
# UTILIDADES
# ------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("auth"):
            return jsonify({"error": "No autorizado"}), 401
        return f(*args, **kwargs)
    return decorated_function


def leer_json():
    """Cuerpo JSON de la petición como dict. Si no es JSON válido, error 400."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise DatosInvalidos("Cuerpo JSON inválido")
    return data


def objetivo_de(conn, persona):
    """Objetivo de la persona; si no existe, error 400."""
    if not persona:
        raise DatosInvalidos("Falta la persona")
    objetivo = db.obtener_objetivo(conn, persona)
    if objetivo is None:
        raise DatosInvalidos("Persona desconocida")
    return objetivo


def preparar_conversion(moneda):
    """Devuelve (moneda que se usará, tasas, aviso).

    Si la API de tasas no responde, se muestra en EUR y se avisa, en lugar
    de enseñar euros con el símbolo de otra moneda como pasaba antes.
    """
    if moneda == "EUR":
        return "EUR", None, None
    try:
        return moneda, obtener_tasas(), None
    except TasasNoDisponibles:
        return "EUR", None, "Tipo de cambio no disponible: importes en EUR"


def importe(valor):
    # Los importes viajan como texto con 2 decimales ("1070.00") para no
    # perder precisión en el JSON; el navegador los convierte para mostrarlos.
    return f"{valor:.2f}"


# ------------------------
# PÁGINA Y SESIÓN
# ------------------------

@bp.route("/")
def home():
    return render_template("index.html")


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    pin = str(data.get("pin", ""))

    if pin == os.environ.get("APP_PIN", "1234"):
        session["auth"] = True
        return jsonify({"ok": True})

    return jsonify({"ok": False, "error": "PIN incorrecto"}), 401


@bp.route("/check-auth", methods=["GET"])
def check_auth():
    if session.get("auth"):
        return jsonify({"auth": True})
    return jsonify({"auth": False}), 401


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


# ------------------------
# TRANSFERENCIAS
# ------------------------

@bp.route("/transferencias", methods=["GET"])
@login_required
def obtener_transferencias():
    persona = request.args.get("persona")
    moneda = validar_moneda(request.args.get("moneda"))
    mes = validar_mes(request.args.get("mes"))
    desde, hasta = rango_mes(mes)

    with db.conexion() as conn:
        objetivo_de(conn, persona)
        transferencias = db.listar_transferencias(conn, persona, desde, hasta)

    moneda, tasas, aviso = preparar_conversion(moneda)

    for t in transferencias:
        t["monto_eur"] = importe(t["monto"])
        t["monto"] = importe(convertir(t["monto"], "EUR", moneda, tasas))

    return jsonify({
        "mes": mes,
        "moneda": moneda,
        "aviso": aviso,
        "transferencias": transferencias,
    })


@bp.route("/transferencias", methods=["POST"])
@login_required
def crear_transferencia():
    data = leer_json()
    monto = validar_monto(data.get("monto"))
    fecha = validar_fecha(data.get("fecha"))
    descripcion = validar_descripcion(data.get("descripcion"))
    persona = data.get("persona")

    with db.conexion() as conn:
        objetivo_de(conn, persona)
        nuevo_id = db.insertar_transferencia(conn, monto, fecha, descripcion, persona)

    return jsonify({"mensaje": "Transferencia creada", "id": nuevo_id}), 201


@bp.route("/transferencias/<int:id>", methods=["PUT"])
@login_required
def editar_transferencia(id):
    data = leer_json()
    monto = validar_monto(data.get("monto"))
    fecha = validar_fecha(data.get("fecha"))
    descripcion = validar_descripcion(data.get("descripcion"))

    with db.conexion() as conn:
        transferencia = db.obtener_transferencia(conn, id)
        if transferencia is None:
            raise NoEncontrada("No existe")
        if transferencia["confirmada"]:
            raise Conflicto("No se puede editar una transferencia confirmada")
        db.actualizar_transferencia(conn, id, monto, fecha, descripcion)

    return jsonify({"ok": True})


@bp.route("/transferencias/<int:id>/confirmar", methods=["PATCH"])
@login_required
def confirmar_transferencia(id):
    with db.conexion() as conn:
        confirmada = db.alternar_confirmacion(conn, id)

    if confirmada is None:
        raise NoEncontrada("No encontrada")
    return jsonify({"confirmada": confirmada})


@bp.route("/transferencias/<int:id>", methods=["DELETE"])
@login_required
def eliminar_transferencia(id):
    with db.conexion() as conn:
        transferencia = db.obtener_transferencia(conn, id)
        if transferencia is None:
            raise NoEncontrada("No existe")
        if transferencia["confirmada"]:
            raise Conflicto("No se puede eliminar una transferencia confirmada")
        db.eliminar_transferencia(conn, id)

    return jsonify({"mensaje": "ok"})


# ------------------------
# RESUMEN Y OBJETIVO
# ------------------------

@bp.route("/resumen", methods=["GET"])
@login_required
def obtener_resumen():
    persona = request.args.get("persona")
    moneda = validar_moneda(request.args.get("moneda"))
    mes = validar_mes(request.args.get("mes"))
    desde, hasta = rango_mes(mes)

    with db.conexion() as conn:
        objetivo = objetivo_de(conn, persona)
        confirmado, pendiente = db.sumar_por_estado(conn, persona, desde, hasta)

    resumen = calcular_resumen(confirmado, pendiente, objetivo)
    moneda, tasas, aviso = preparar_conversion(moneda)

    respuesta = {
        clave: importe(convertir(resumen[clave], "EUR", moneda, tasas))
        for clave in ("total_confirmado", "pendiente", "objetivo", "restante")
    }
    respuesta.update({
        "porcentaje": float(resumen["porcentaje"]),
        "porcentaje_pendiente": float(resumen["porcentaje_pendiente"]),
        "objetivo_eur": importe(objetivo),
        "mes": mes,
        "moneda": moneda,
        "aviso": aviso,
    })
    return jsonify(respuesta)


@bp.route("/objetivo", methods=["POST"])
@login_required
def guardar_objetivo():
    data = leer_json()
    objetivo = validar_monto(data.get("objetivo"), campo="Objetivo")

    with db.conexion() as conn:
        objetivo_de(conn, data.get("persona"))
        db.guardar_objetivo(conn, data.get("persona"), objetivo)

    return jsonify({"mensaje": "ok", "objetivo": importe(objetivo)})


# ------------------------
# CONVERSOR
# ------------------------

@bp.route("/convertir", methods=["GET"])
@login_required
def convertir_cantidad():
    cantidad = validar_monto(request.args.get("cantidad"), campo="Cantidad")
    de = validar_moneda(request.args.get("de"))
    a = validar_moneda(request.args.get("a"))

    tasas = obtener_tasas() if de != a else None
    tasa = tasa_cambio(de, a, tasas) if tasas else 1

    return jsonify({
        "cantidad": importe(cantidad),
        "de": de,
        "a": a,
        "resultado": importe(convertir(cantidad, de, a, tasas)),
        "tasa": f"{tasa:.4f}",
    })
