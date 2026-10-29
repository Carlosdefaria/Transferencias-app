"""Tests de las rutas principales con un cliente HTTP de prueba."""

import pytest
import requests

import logica
from conftest import PIN, crear


# ------------------------
# SESIÓN
# ------------------------

def test_login_correcto_e_incorrecto(cliente):
    assert cliente.post("/login", json={"pin": "0000"}).status_code == 401
    assert cliente.get("/check-auth").status_code == 401
    assert cliente.post("/login", json={"pin": PIN}).status_code == 200
    assert cliente.get("/check-auth").get_json() == {"auth": True}


def test_login_sin_json_no_rompe(cliente):
    respuesta = cliente.post("/login", data="esto no es json")
    assert respuesta.status_code == 401


def test_logout(sesion):
    sesion.post("/logout")
    assert sesion.get("/check-auth").status_code == 401


@pytest.mark.parametrize("metodo, url", [
    ("get", "/transferencias?persona=Carlos"),
    ("post", "/transferencias"),
    ("put", "/transferencias/1"),
    ("delete", "/transferencias/1"),
    ("patch", "/transferencias/1/confirmar"),
    ("get", "/resumen?persona=Carlos"),
    ("post", "/objetivo"),
    ("get", "/convertir?cantidad=1&de=EUR&a=USD"),
])
def test_rutas_protegidas(cliente, metodo, url):
    assert getattr(cliente, metodo)(url).status_code == 401


# ------------------------
# CREAR Y LISTAR
# ------------------------

def test_crear_y_listar(sesion):
    crear(sesion, monto="150.5", fecha="2026-10-05", descripcion="alquiler")
    datos = sesion.get("/transferencias?persona=Carlos&mes=2026-10").get_json()

    assert datos["mes"] == "2026-10"
    [t] = datos["transferencias"]
    assert t["monto"] == "150.50"
    assert t["monto_eur"] == "150.50"
    assert t["fecha"] == "2026-10-05"  # siempre AAAA-MM-DD, también en PostgreSQL
    assert t["descripcion"] == "alquiler"
    assert t["confirmada"] is False


def test_lista_y_resumen_usan_el_mismo_mes(sesion):
    crear(sesion, monto="100", fecha="2026-09-30")
    crear(sesion, monto="200", fecha="2026-10-01")
    crear(sesion, monto="300", fecha="2026-10-31")
    crear(sesion, monto="400", fecha="2026-11-01")

    lista = sesion.get("/transferencias?persona=Carlos&mes=2026-10").get_json()
    resumen = sesion.get("/resumen?persona=Carlos&mes=2026-10").get_json()

    assert [t["monto"] for t in lista["transferencias"]] == ["300.00", "200.00"]
    assert resumen["pendiente"] == "500.00"


def test_sin_mes_se_usa_el_mes_actual(sesion):
    from datetime import date
    hoy = date.today().isoformat()
    crear(sesion, fecha=hoy)
    crear(sesion, fecha="2001-01-01")

    lista = sesion.get("/transferencias?persona=Carlos").get_json()
    assert [t["fecha"] for t in lista["transferencias"]] == [hoy]


def test_personas_separadas(sesion):
    crear(sesion, persona="Carlos")
    crear(sesion, persona="Pito", monto="7")
    lista = sesion.get("/transferencias?persona=Pito&mes=2026-10").get_json()
    assert [t["monto"] for t in lista["transferencias"]] == ["7.00"]


@pytest.mark.parametrize("cuerpo, mensaje", [
    ({"monto": "-1", "fecha": "2026-10-01", "persona": "Carlos"}, "Monto"),
    ({"monto": "10", "fecha": "01/10/2026", "persona": "Carlos"}, "Fecha"),
    ({"monto": "10", "fecha": "2026-10-01"}, "persona"),
    ({"monto": "10", "fecha": "2026-10-01", "persona": "Nadie"}, "Persona"),
])
def test_crear_valida_los_datos(sesion, cuerpo, mensaje):
    respuesta = sesion.post("/transferencias", json=cuerpo)
    assert respuesta.status_code == 400
    assert mensaje in respuesta.get_json()["error"]


def test_parametros_invalidos(sesion):
    assert sesion.get("/transferencias?persona=Carlos&mes=octubre").status_code == 400
    assert sesion.get("/resumen?persona=Carlos&moneda=JPY").status_code == 400
    assert sesion.get("/resumen").status_code == 400


# ------------------------
# EDITAR, CONFIRMAR, ELIMINAR
# ------------------------

def test_editar(sesion):
    id = crear(sesion)
    respuesta = sesion.put(f"/transferencias/{id}", json={
        "monto": "99.90", "fecha": "2026-10-20", "descripcion": "nuevo"})
    assert respuesta.status_code == 200

    [t] = sesion.get("/transferencias?persona=Carlos&mes=2026-10").get_json()["transferencias"]
    assert (t["monto"], t["fecha"], t["descripcion"]) == ("99.90", "2026-10-20", "nuevo")


def test_editar_valida_y_comprueba_que_existe(sesion):
    id = crear(sesion)
    assert sesion.put(f"/transferencias/{id}", json={
        "monto": "10", "fecha": "mal"}).status_code == 400
    assert sesion.put("/transferencias/9999", json={
        "monto": "10", "fecha": "2026-10-01"}).status_code == 404


def test_no_se_edita_ni_elimina_una_confirmada(sesion):
    id = crear(sesion)
    assert sesion.patch(f"/transferencias/{id}/confirmar").get_json() == {"confirmada": True}

    assert sesion.put(f"/transferencias/{id}", json={
        "monto": "1", "fecha": "2026-10-01"}).status_code == 409
    assert sesion.delete(f"/transferencias/{id}").status_code == 409


def test_confirmar_y_desconfirmar(sesion):
    id = crear(sesion)
    assert sesion.patch(f"/transferencias/{id}/confirmar").get_json()["confirmada"] is True
    assert sesion.patch(f"/transferencias/{id}/confirmar").get_json()["confirmada"] is False
    assert sesion.patch("/transferencias/9999/confirmar").status_code == 404


def test_eliminar(sesion):
    id = crear(sesion)
    assert sesion.delete(f"/transferencias/{id}").status_code == 200
    assert sesion.delete(f"/transferencias/{id}").status_code == 404


# ------------------------
# RESUMEN, OBJETIVO Y DIVISAS
# ------------------------

def test_resumen_totales(sesion):
    a = crear(sesion, monto="500")
    crear(sesion, monto="200")
    sesion.patch(f"/transferencias/{a}/confirmar")

    r = sesion.get("/resumen?persona=Carlos&mes=2026-10").get_json()
    assert r["total_confirmado"] == "500.00"
    assert r["pendiente"] == "200.00"
    assert r["objetivo"] == "1070.00"
    assert r["restante"] == "570.00"
    assert r["restante_tras_pendiente"] == "370.00"
    assert r["porcentaje"] == 46.7
    assert r["moneda"] == "EUR"
    assert r["aviso"] is None


def test_resumen_suma_centimos_sin_errores(sesion):
    for _ in range(3):
        id = crear(sesion, monto="0.1")
        sesion.patch(f"/transferencias/{id}/confirmar")
    r = sesion.get("/resumen?persona=Carlos&mes=2026-10").get_json()
    assert r["total_confirmado"] == "0.30"


def test_objetivo(sesion):
    assert sesion.post("/objetivo", json={"persona": "Pito", "objetivo": "800"}).status_code == 200
    assert sesion.get("/resumen?persona=Pito&mes=2026-10").get_json()["objetivo"] == "800.00"
    # El de Carlos no cambia
    assert sesion.get("/resumen?persona=Carlos&mes=2026-10").get_json()["objetivo"] == "1070.00"

    assert sesion.post("/objetivo", json={"persona": "Pito", "objetivo": "0"}).status_code == 400
    assert sesion.post("/objetivo", json={"persona": "Nadie", "objetivo": "5"}).status_code == 400


def test_resumen_y_lista_en_otra_moneda(sesion):
    crear(sesion, monto="100")
    r = sesion.get("/resumen?persona=Carlos&mes=2026-10&moneda=USD").get_json()
    assert r["moneda"] == "USD"
    assert r["objetivo"] == "1177.00"   # 1070 * 1.10
    assert r["objetivo_eur"] == "1070.00"

    [t] = sesion.get("/transferencias?persona=Carlos&mes=2026-10&moneda=USD").get_json()["transferencias"]
    assert t["monto"] == "110.00"
    assert t["monto_eur"] == "100.00"   # el que se usa al editar


def test_si_no_hay_tasas_se_muestra_en_eur_y_se_avisa(sesion, monkeypatch):
    def descarga_rota():
        raise requests.ConnectionError("sin red")

    monkeypatch.setattr(logica, "descargar_tasas", descarga_rota)
    r = sesion.get("/resumen?persona=Carlos&mes=2026-10&moneda=USD").get_json()
    assert r["moneda"] == "EUR"
    assert r["objetivo"] == "1070.00"
    assert "no disponible" in r["aviso"]


def test_convertir(sesion):
    r = sesion.get("/convertir?cantidad=100&de=EUR&a=GBP").get_json()
    assert r["resultado"] == "85.00"
    assert r["tasa"] == "0.8500"
    assert sesion.get("/convertir?cantidad=abc&de=EUR&a=GBP").status_code == 400


def test_convertir_sin_tasas_da_503(sesion, monkeypatch):
    def descarga_rota():
        raise requests.ConnectionError("sin red")

    monkeypatch.setattr(logica, "descargar_tasas", descarga_rota)
    respuesta = sesion.get("/convertir?cantidad=100&de=EUR&a=GBP")
    assert respuesta.status_code == 503
    assert "error" in respuesta.get_json()


def test_errores_http_son_json(sesion):
    respuesta = sesion.get("/no-existe")
    assert respuesta.status_code == 404
    assert "error" in respuesta.get_json()
