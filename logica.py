"""Lógica de negocio: validaciones y cálculos.

Este módulo no sabe nada de Flask ni de la base de datos: recibe valores y
devuelve valores. Por eso se puede probar con tests sencillos.

Todos los importes se manejan como Decimal (nunca float) para no perder
céntimos: en float, 0.1 + 0.2 da 0.30000000000000004.
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTIMOS = Decimal("0.01")
MONTO_MAXIMO = Decimal("1000000")
MAX_DESCRIPCION = 200
MAX_NOMBRE = 40


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


def validar_mes_cuenta(valor, fecha):
    """Mes para el que cuenta una transferencia, o None si es el de su fecha.

    Solo puede ser el mes de la fecha o el siguiente (un adelanto): no tiene
    sentido que cuente para un mes que ya ha pasado. Solo se guarda cuando
    es el siguiente; lo normal es que quede vacío y cuente por su fecha.
    """
    if not valor:
        return None
    try:
        mes = datetime.strptime(str(valor), "%Y-%m").strftime("%Y-%m")
    except ValueError:
        raise DatosInvalidos("Mes de cuenta inválido (formato AAAA-MM)")

    mes_fecha = fecha[:7]
    if mes == mes_fecha:
        return None
    if mes != rango_mes(mes_fecha)[1][:7]:   # primer día del mes siguiente → "AAAA-MM"
        raise DatosInvalidos("Solo puede contar para el mes de su fecha o el siguiente")
    return mes


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


def validar_nombre(valor):
    """Nombre de persona sin espacios sobrantes, entre 1 y MAX_NOMBRE caracteres."""
    if not isinstance(valor, str):
        raise DatosInvalidos("Nombre obligatorio")
    # split() + join() quita espacios del principio y del final y deja uno
    # solo entre palabras ("  Ana   María " -> "Ana María").
    nombre = " ".join(valor.split())
    if not nombre:
        raise DatosInvalidos("Nombre obligatorio")
    if len(nombre) > MAX_NOMBRE:
        raise DatosInvalidos(f"Nombre demasiado largo (máximo {MAX_NOMBRE} caracteres)")
    return nombre


# ------------------------
# CÁLCULOS
# ------------------------

def calcular_resumen(confirmado, pendiente, objetivo):
    """Calcula el resumen del mes. Todos los importes en Decimal.

    - restante: lo que falta por recibir (negativo si se superó el objetivo).
    - restante_tras_pendiente: lo que faltaría si se confirmara lo pendiente.
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
        "restante_tras_pendiente": restante - pendiente,
        "porcentaje": porcentaje.quantize(una_cifra, rounding=ROUND_HALF_UP),
        "porcentaje_pendiente": porcentaje_pendiente.quantize(una_cifra, rounding=ROUND_HALF_UP),
    }
