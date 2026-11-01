"""Tests de las transferencias que cuentan para otro mes (adelantadas/atrasadas)."""

import pytest

from conftest import crear
from logica import DatosInvalidos, validar_mes_cuenta


def crear_para(sesion, monto, fecha, mes_cuenta):
    respuesta = sesion.post("/transferencias", json={
        "monto": monto, "fecha": fecha, "persona": "Carlos", "mes_cuenta": mes_cuenta})
    assert respuesta.status_code == 201, respuesta.get_json()
    return respuesta.get_json()["id"]


def lista(sesion, mes):
    return sesion.get(f"/transferencias?persona=Carlos&mes={mes}").get_json()["transferencias"]


def resumen(sesion, mes):
    return sesion.get(f"/resumen?persona=Carlos&mes={mes}").get_json()


def test_validar_mes_cuenta():
    # Vacío o igual al mes de la fecha: no se guarda nada (cuenta por la fecha)
    assert validar_mes_cuenta(None, "2026-10-28") is None
    assert validar_mes_cuenta("", "2026-10-28") is None
    assert validar_mes_cuenta("2026-10", "2026-10-28") is None
    assert validar_mes_cuenta("2026-11", "2026-10-28") == "2026-11"
    with pytest.raises(DatosInvalidos):
        validar_mes_cuenta("noviembre", "2026-10-28")


def test_adelantada_cuenta_para_el_mes_siguiente(sesion):
    crear(sesion, monto="1070", fecha="2026-10-05")              # cuota de octubre
    crear_para(sesion, "500", "2026-10-28", "2026-11")           # adelanto de noviembre

    # Octubre: solo la cuota de octubre
    assert [t["monto"] for t in lista(sesion, "2026-10")] == ["1070.00"]
    assert resumen(sesion, "2026-10")["pendiente"] == "1070.00"

    # Noviembre: el adelanto, con su fecha real
    [t] = lista(sesion, "2026-11")
    assert (t["monto"], t["fecha"], t["mes_cuenta"]) == ("500.00", "2026-10-28", "2026-11")
    assert resumen(sesion, "2026-11")["pendiente"] == "500.00"


def test_transferencia_normal_devuelve_el_mes_de_su_fecha(sesion):
    crear(sesion, fecha="2026-10-05")
    assert lista(sesion, "2026-10")[0]["mes_cuenta"] == "2026-10"


def test_atrasada_cuenta_para_el_mes_anterior(sesion):
    crear_para(sesion, "200", "2026-10-02", "2026-09")
    assert lista(sesion, "2026-10") == []
    assert resumen(sesion, "2026-09")["pendiente"] == "200.00"


def test_editar_cambia_el_mes_de_cuenta(sesion):
    id = crear(sesion, monto="300", fecha="2026-10-28")
    respuesta = sesion.put(f"/transferencias/{id}", json={
        "monto": "300", "fecha": "2026-10-28", "mes_cuenta": "2026-11"})
    assert respuesta.status_code == 200
    assert lista(sesion, "2026-10") == []
    assert lista(sesion, "2026-11")[0]["id"] == id

    # Volver a su mes: se deja vacío y cuenta otra vez por la fecha
    sesion.put(f"/transferencias/{id}", json={
        "monto": "300", "fecha": "2026-10-28", "mes_cuenta": "2026-10"})
    assert lista(sesion, "2026-10")[0]["id"] == id


def test_mes_cuenta_invalido(sesion):
    respuesta = sesion.post("/transferencias", json={
        "monto": "10", "fecha": "2026-10-01", "persona": "Carlos", "mes_cuenta": "2026-13"})
    assert respuesta.status_code == 400
