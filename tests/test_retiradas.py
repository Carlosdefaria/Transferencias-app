"""Tests de las retiradas del pote: dinero que se coge de lo recaudado y resta."""

from decimal import Decimal

import pytest

from conftest import crear
from logica import DatosInvalidos, calcular_resumen, validar_tipo


def crear_retirada(sesion, monto, fecha="2026-11-10", mes_cuenta=None):
    respuesta = sesion.post("/transferencias", json={
        "monto": monto, "fecha": fecha, "persona": "Carlos",
        "descripcion": "Regalo", "tipo": "retirada", "mes_cuenta": mes_cuenta})
    assert respuesta.status_code == 201, respuesta.get_json()
    return respuesta.get_json()["id"]


def confirmar(sesion, id):
    assert sesion.patch(f"/transferencias/{id}/confirmar").get_json()["confirmada"] is True


def resumen(sesion, mes="2026-11"):
    return sesion.get(f"/resumen?persona=Carlos&mes={mes}").get_json()


def lista(sesion, mes="2026-11"):
    return sesion.get(f"/transferencias?persona=Carlos&mes={mes}").get_json()["transferencias"]


# ------------------------
# LÓGICA
# ------------------------

def test_validar_tipo():
    assert validar_tipo(None) == "ingreso"
    assert validar_tipo("") == "ingreso"
    assert validar_tipo("ingreso") == "ingreso"
    assert validar_tipo("retirada") == "retirada"
    for malo in ("gasto", "RETIRADA", 1, True):
        with pytest.raises(DatosInvalidos):
            validar_tipo(malo)


def test_resumen_resta_lo_retirado():
    r = calcular_resumen(Decimal("1070.00"), Decimal("0.00"), Decimal("1070.00"),
                         retirado=Decimal("50.00"))
    assert r["total_confirmado"] == Decimal("1020.00")
    assert r["retirado"] == Decimal("50.00")
    assert r["restante"] == Decimal("50.00")
    assert r["porcentaje"] == Decimal("95.3")


def test_resumen_retirada_pendiente_resta_de_lo_pendiente():
    r = calcular_resumen(Decimal("500.00"), Decimal("200.00"), Decimal("1070.00"),
                         retirado_pendiente=Decimal("30.00"))
    assert r["pendiente"] == Decimal("170.00")
    assert r["restante_tras_pendiente"] == Decimal("400.00")


def test_resumen_retirar_mas_de_lo_recibido_da_neto_negativo():
    r = calcular_resumen(Decimal("0.00"), Decimal("0.00"), Decimal("1070.00"),
                         retirado=Decimal("40.00"))
    assert r["total_confirmado"] == Decimal("-40.00")
    assert r["restante"] == Decimal("1110.00")


# ------------------------
# API
# ------------------------

def test_sin_tipo_es_un_ingreso(sesion):
    crear(sesion, fecha="2026-11-02")
    assert lista(sesion)[0]["tipo"] == "ingreso"
    assert resumen(sesion)["retirado"] == "0.00"


def test_retirada_confirmada_resta_del_pote(sesion):
    confirmar(sesion, crear(sesion, monto="1070", fecha="2026-11-02"))
    assert resumen(sesion)["restante"] == "0.00"

    id = crear_retirada(sesion, "50")
    # Pendiente: todavía no cambia lo confirmado
    r = resumen(sesion)
    assert (r["total_confirmado"], r["pendiente"], r["retirado"]) == ("1070.00", "-50.00", "0.00")
    assert r["restante_tras_pendiente"] == "50.00"

    confirmar(sesion, id)
    r = resumen(sesion)
    assert (r["total_confirmado"], r["pendiente"], r["retirado"]) == ("1020.00", "0.00", "50.00")
    assert r["restante"] == "50.00"

    t = next(t for t in lista(sesion) if t["id"] == id)
    assert (t["tipo"], t["monto"]) == ("retirada", "50.00")


def test_retirada_para_el_mes_siguiente(sesion):
    id = crear_retirada(sesion, "20", fecha="2026-11-28", mes_cuenta="2026-12")
    confirmar(sesion, id)
    assert resumen(sesion, "2026-11")["retirado"] == "0.00"
    assert resumen(sesion, "2026-12")["retirado"] == "20.00"
    assert resumen(sesion, "2026-12")["total_confirmado"] == "-20.00"


def test_tipo_invalido(sesion):
    respuesta = sesion.post("/transferencias", json={
        "monto": "10", "fecha": "2026-11-01", "persona": "Carlos", "tipo": "gasto"})
    assert respuesta.status_code == 400


def test_editar_cambia_el_tipo(sesion):
    id = crear(sesion, monto="30", fecha="2026-11-03")
    respuesta = sesion.put(f"/transferencias/{id}", json={
        "monto": "30", "fecha": "2026-11-03", "tipo": "retirada"})
    assert respuesta.status_code == 200
    assert lista(sesion)[0]["tipo"] == "retirada"
    assert resumen(sesion)["pendiente"] == "-30.00"


def test_retirada_confirmada_no_se_puede_eliminar(sesion):
    id = crear_retirada(sesion, "15")
    confirmar(sesion, id)
    assert sesion.delete(f"/transferencias/{id}").status_code == 409
