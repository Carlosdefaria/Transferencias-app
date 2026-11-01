"""Tests de la lógica pura: validaciones y cálculos."""

from decimal import Decimal

import pytest

from logica import (DatosInvalidos, calcular_resumen, rango_mes,
                    validar_descripcion, validar_fecha, validar_mes,
                    validar_monto)


# ------------------------
# VALIDACIONES
# ------------------------

@pytest.mark.parametrize("entrada, esperado", [
    (100, Decimal("100.00")),
    ("1070", Decimal("1070.00")),
    ("12,5", Decimal("12.50")),
    (0.1, Decimal("0.10")),
    ("  99.99 ", Decimal("99.99")),
])
def test_validar_monto_correcto(entrada, esperado):
    assert validar_monto(entrada) == esperado


@pytest.mark.parametrize("entrada", [
    None, "", "abc", 0, -5, "1.005", "NaN", "Infinity", True, "2000000",
])
def test_validar_monto_incorrecto(entrada):
    with pytest.raises(DatosInvalidos):
        validar_monto(entrada)


def test_validar_fecha():
    assert validar_fecha("2026-02-28") == "2026-02-28"
    for mala in ("2026-02-30", "28/02/2026", "", None, "2026-2-1x"):
        with pytest.raises(DatosInvalidos):
            validar_fecha(mala)


def test_validar_mes_por_defecto_es_el_actual():
    from datetime import datetime
    assert validar_mes(None) == datetime.now().strftime("%Y-%m")
    assert validar_mes("2026-03") == "2026-03"
    with pytest.raises(DatosInvalidos):
        validar_mes("2026-13")


def test_rango_mes():
    assert rango_mes("2026-10") == ("2026-10-01", "2026-11-01")
    assert rango_mes("2026-12") == ("2026-12-01", "2027-01-01")


def test_validar_descripcion():
    assert validar_descripcion(None) == ""
    assert validar_descripcion("  alquiler ") == "alquiler"
    with pytest.raises(DatosInvalidos):
        validar_descripcion("x" * 201)
    with pytest.raises(DatosInvalidos):
        validar_descripcion(123)


# ------------------------
# CÁLCULOS
# ------------------------

def test_resumen_a_medias():
    r = calcular_resumen(Decimal("500.00"), Decimal("200.00"), Decimal("1070.00"))
    assert r["restante"] == Decimal("570.00")
    assert r["restante_tras_pendiente"] == Decimal("370.00")
    assert r["porcentaje"] == Decimal("46.7")
    assert r["porcentaje_pendiente"] == Decimal("18.7")


def test_resumen_objetivo_superado_da_restante_negativo():
    r = calcular_resumen(Decimal("1200.00"), Decimal("0.00"), Decimal("1070.00"))
    assert r["restante"] == Decimal("-130.00")
    assert r["porcentaje"] > 100


def test_resumen_sin_objetivo_no_divide_entre_cero():
    r = calcular_resumen(Decimal("10.00"), Decimal("0.00"), Decimal("0.00"))
    assert r["porcentaje"] == 0


def test_decimal_no_pierde_centimos():
    # Con float, 0.1 + 0.2 = 0.30000000000000004
    total = validar_monto("0.1") + validar_monto("0.2")
    assert total == Decimal("0.30")
