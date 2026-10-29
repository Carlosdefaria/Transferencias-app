"""Tests de la gestión de personas (añadir, renombrar, eliminar)."""

import pytest

from conftest import crear
from logica import DatosInvalidos, validar_nombre


def personas(sesion):
    return sesion.get("/personas").get_json()


def id_de(sesion, nombre):
    return next(p["id"] for p in personas(sesion) if p["nombre"] == nombre)


# ------------------------
# VALIDACIÓN DEL NOMBRE
# ------------------------

def test_validar_nombre():
    assert validar_nombre("  Ana   María ") == "Ana María"
    for malo in (None, "", "   ", 5, "x" * 41):
        with pytest.raises(DatosInvalidos):
            validar_nombre(malo)


# ------------------------
# LISTAR Y AÑADIR
# ------------------------

def test_listar_personas_iniciales(sesion):
    lista = personas(sesion)
    assert [p["nombre"] for p in lista] == ["Carlos", "Pito"]
    assert lista[0]["objetivo"] == "1070.00"
    assert lista[0]["transferencias"] == 0


def test_cuenta_las_transferencias(sesion):
    crear(sesion, persona="Carlos")
    crear(sesion, persona="Carlos")
    assert personas(sesion)[0]["transferencias"] == 2


def test_anadir_persona(sesion):
    respuesta = sesion.post("/personas", json={"nombre": " Ana ", "objetivo": "800"})
    assert respuesta.status_code == 201
    assert respuesta.get_json()["nombre"] == "Ana"

    assert [p["nombre"] for p in personas(sesion)] == ["Carlos", "Pito", "Ana"]
    # La nueva persona funciona en el resto de la app
    crear(sesion, persona="Ana", monto="50")
    resumen = sesion.get("/resumen?persona=Ana&mes=2026-10").get_json()
    assert resumen["objetivo"] == "800.00"
    assert resumen["pendiente"] == "50.00"


def test_anadir_sin_objetivo_usa_el_de_por_defecto(sesion):
    respuesta = sesion.post("/personas", json={"nombre": "Ana"})
    assert respuesta.get_json()["objetivo"] == "1070.00"


def test_no_se_repiten_nombres(sesion):
    respuesta = sesion.post("/personas", json={"nombre": "carlos"})
    assert respuesta.status_code == 409
    assert sesion.post("/personas", json={"nombre": ""}).status_code == 400
    assert sesion.post("/personas", json={"nombre": "Ana", "objetivo": "-5"}).status_code == 400


# ------------------------
# RENOMBRAR
# ------------------------

def test_renombrar_mueve_sus_transferencias(sesion):
    crear(sesion, persona="Pito", monto="25")
    respuesta = sesion.put(f"/personas/{id_de(sesion, 'Pito')}", json={"nombre": "Pedro"})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["nombre"] == "Pedro"

    lista = sesion.get("/transferencias?persona=Pedro&mes=2026-10").get_json()
    assert [t["monto"] for t in lista["transferencias"]] == ["25.00"]
    assert sesion.get("/resumen?persona=Pito").status_code == 400  # el nombre viejo ya no existe


def test_renombrar_validaciones(sesion):
    pito = id_de(sesion, "Pito")
    assert sesion.put(f"/personas/{pito}", json={"nombre": "CARLOS"}).status_code == 409
    assert sesion.put(f"/personas/{pito}", json={"nombre": "  "}).status_code == 400
    assert sesion.put("/personas/9999", json={"nombre": "Ana"}).status_code == 404
    # Cambiar solo mayúsculas del propio nombre sí se permite
    assert sesion.put(f"/personas/{pito}", json={"nombre": "PITO"}).status_code == 200


# ------------------------
# ELIMINAR
# ------------------------

def test_eliminar_persona_sin_transferencias(sesion):
    assert sesion.delete(f"/personas/{id_de(sesion, 'Pito')}").status_code == 200
    assert [p["nombre"] for p in personas(sesion)] == ["Carlos"]
    assert sesion.get("/resumen?persona=Pito").status_code == 400


def test_no_se_elimina_quien_tiene_transferencias(sesion):
    crear(sesion, persona="Pito")
    respuesta = sesion.delete(f"/personas/{id_de(sesion, 'Pito')}")
    assert respuesta.status_code == 409
    assert "transferencias" in respuesta.get_json()["error"]
    assert len(personas(sesion)) == 2


def test_no_se_elimina_la_ultima_persona(sesion):
    sesion.delete(f"/personas/{id_de(sesion, 'Pito')}")
    respuesta = sesion.delete(f"/personas/{id_de(sesion, 'Carlos')}")
    assert respuesta.status_code == 409
    assert sesion.delete("/personas/9999").status_code == 404


def test_rutas_de_personas_protegidas(cliente):
    assert cliente.get("/personas").status_code == 401
    assert cliente.post("/personas", json={"nombre": "Ana"}).status_code == 401
    assert cliente.put("/personas/1", json={"nombre": "Ana"}).status_code == 401
    assert cliente.delete("/personas/1").status_code == 401
