"""Lógica de negocio: validaciones, cálculos y divisas.

Este módulo no sabe nada de Flask ni de la base de datos: recibe valores y
devuelve valores. Por eso se puede probar con tests sencillos.

Todos los importes se manejan como Decimal (nunca float) para no perder
céntimos: en float, 0.1 + 0.2 da 0.30000000000000004.
"""

import logging
import time
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import requests

log = logging.getLogger(__name__)

MONEDAS = ("EUR", "USD", "GBP")
CENTIMOS = Decimal("0.01")
MONTO_MAXIMO = Decimal("1000000")
MAX_DESCRIPCION = 200


# ------------------------
# ERRORES DE NEGOCIO
# ------------------------
# Las rutas lanzan estos errores y app.py los convierte en una respuesta
# JSON con su código HTTP. Así no hay que repetir jsonify(...) en cada ruta.

class ErrorNegocio(Exception):
    codigo = 400


class DatosInvalidos(ErrorNegocio):
    codigo = 400


class NoEncontrada(ErrorNegocio):
    codigo = 404


class Conflicto(ErrorNegocio):
    codigo = 409


class TasasNoDisponibles(ErrorNegocio):
    codigo = 503


# ------------------------
# VALIDACIONES
# ------------------------

def a_decimal(valor):
    """Convierte un número leído de la BD (float, int o Decimal) a Decimal con 2 decimales."""
    # str() primero: Decimal(0.1) daría 0.1000000000000000055511151231257827...
    return Decimal(str(valor)).quantize(CENTIMOS, rounding=ROUND_HALF_UP)


def validar_monto(valor, campo="Monto"):
    """Devuelve el importe como Decimal positivo con como mucho 2 decimales."""
    if valor is None or isinstance(valor, bool):
        raise DatosInvalidos(f"{campo} obligatorio")

    try:
        monto = Decimal(str(valor).strip().replace(",", "."))
    except InvalidOperation:
        raise DatosInvalidos(f"{campo} inválido")

    if not monto.is_finite() or monto <= 0:
        raise DatosInvalidos(f"{campo} debe ser mayor que 0")
    if monto > MONTO_MAXIMO:
        raise DatosInvalidos(f"{campo} demasiado grande")
    if monto != monto.quantize(CENTIMOS):
        raise DatosInvalidos(f"{campo}: como máximo 2 decimales")

    return monto.quantize(CENTIMOS)


def validar_fecha(valor):
    """Devuelve la fecha como texto 'YYYY-MM-DD' si es válida."""
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        raise DatosInvalidos("Fecha inválida (formato AAAA-MM-DD)")


def validar_mes(valor=None):
    """Devuelve el mes 'YYYY-MM'. Si no se indica, el mes actual."""
    if not valor:
        return datetime.now().strftime("%Y-%m")
    try:
        return datetime.strptime(str(valor), "%Y-%m").strftime("%Y-%m")
    except ValueError:
        raise DatosInvalidos("Mes inválido (formato AAAA-MM)")


def rango_mes(mes):
    """Devuelve (primer día del mes, primer día del mes siguiente) como texto.

    Filtrar con 'fecha >= inicio AND fecha < fin' funciona igual en SQLite
    (fechas como texto) y en PostgreSQL (tipo DATE), sin funciones propias
    de cada motor.
    """
    año, numero = (int(parte) for parte in mes.split("-"))
    siguiente = (año + 1, 1) if numero == 12 else (año, numero + 1)
    return f"{año:04d}-{numero:02d}-01", f"{siguiente[0]:04d}-{siguiente[1]:02d}-01"


def validar_descripcion(valor):
    if valor is None:
        return ""
    if not isinstance(valor, str):
        raise DatosInvalidos("Descripción inválida")
    valor = valor.strip()
    if len(valor) > MAX_DESCRIPCION:
        raise DatosInvalidos(
            f"Descripción demasiado larga (máximo {MAX_DESCRIPCION} caracteres)")
    return valor


def validar_moneda(valor):
    moneda = (valor or "EUR").upper()
    if moneda not in MONEDAS:
        raise DatosInvalidos("Moneda no soportada")
    return moneda


# ------------------------
# CÁLCULOS
# ------------------------

def calcular_resumen(confirmado, pendiente, objetivo):
    """Calcula el resumen del mes. Todos los importes en Decimal.

    - restante: lo que falta por recibir (negativo si se superó el objetivo).
    - porcentaje: progreso confirmado respecto al objetivo (puede pasar de 100).
    - porcentaje_pendiente: lo que aportaría lo pendiente si se confirma.
    """
    restante = objetivo - confirmado

    if objetivo > 0:
        porcentaje = confirmado / objetivo * 100
        porcentaje_pendiente = pendiente / objetivo * 100
    else:
        porcentaje = porcentaje_pendiente = Decimal(0)

    una_cifra = Decimal("0.1")
    return {
        "total_confirmado": confirmado,
        "pendiente": pendiente,
        "objetivo": objetivo,
        "restante": restante,
        "porcentaje": porcentaje.quantize(una_cifra, rounding=ROUND_HALF_UP),
        "porcentaje_pendiente": porcentaje_pendiente.quantize(una_cifra, rounding=ROUND_HALF_UP),
    }


# ------------------------
# DIVISAS
# ------------------------
# Las tasas se piden una sola vez (con base EUR) y se guardan en memoria
# durante una hora. Antes se hacía una petición HTTP por cada importe.

URL_TASAS = "https://api.exchangerate-api.com/v4/latest/EUR"
DURACION_CACHE = 3600  # segundos

_cache_tasas = {"tasas": None, "hora": 0.0}


def descargar_tasas():
    """Pide las tasas a ExchangeRate-API. Devuelve {moneda: Decimal} con base EUR."""
    respuesta = requests.get(URL_TASAS, timeout=3)
    respuesta.raise_for_status()
    rates = respuesta.json()["rates"]
    return {moneda: Decimal(str(rates[moneda])) for moneda in MONEDAS}


def obtener_tasas():
    """Devuelve las tasas usando la caché. Lanza TasasNoDisponibles si no hay ninguna."""
    ahora = time.monotonic()
    tasas = _cache_tasas["tasas"]

    if tasas and ahora - _cache_tasas["hora"] < DURACION_CACHE:
        return tasas

    try:
        tasas = descargar_tasas()
    except (requests.RequestException, ValueError, KeyError, TypeError,
            InvalidOperation) as error:
        log.warning("No se pudieron descargar las tasas: %s", error)
        if _cache_tasas["tasas"]:
            # Mejor una tasa de hace un rato que ninguna.
            return _cache_tasas["tasas"]
        raise TasasNoDisponibles("No se pudo obtener el tipo de cambio")

    _cache_tasas["tasas"] = tasas
    _cache_tasas["hora"] = ahora
    return tasas


def vaciar_cache_tasas():
    _cache_tasas["tasas"] = None
    _cache_tasas["hora"] = 0.0


def tasa_cambio(de, a, tasas):
    """Tasa para pasar de una moneda a otra a partir de tasas con base EUR."""
    return tasas[a] / tasas[de]


def convertir(monto, de, a, tasas):
    if de == a:
        return monto
    return (monto * tasa_cambio(de, a, tasas)).quantize(CENTIMOS, rounding=ROUND_HALF_UP)
