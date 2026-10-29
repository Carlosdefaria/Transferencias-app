"""Tests de seguridad: límite de intentos, PIN obligatorio, cookies y cabeceras."""

import pytest

from app import crear_app
from conftest import PIN
from seguridad import LimitadorIntentos


# ------------------------
# LÍMITE DE INTENTOS
# ------------------------

def test_limitador_bloquea_y_se_libera_con_el_tiempo():
    reloj = [0.0]
    limitador = LimitadorIntentos(maximo=3, ventana=60, reloj=lambda: reloj[0])

    for _ in range(3):
        assert limitador.segundos_bloqueo("1.1.1.1") == 0
        limitador.registrar_fallo("1.1.1.1")

    assert limitador.segundos_bloqueo("1.1.1.1") > 0
    assert limitador.segundos_bloqueo("2.2.2.2") == 0  # otra IP no se ve afectada

    reloj[0] = 61
    assert limitador.segundos_bloqueo("1.1.1.1") == 0


def test_login_se_bloquea_tras_5_fallos(cliente):
    for _ in range(5):
        assert cliente.post("/login", json={"pin": "0000"}).status_code == 401

    respuesta = cliente.post("/login", json={"pin": PIN})
    assert respuesta.status_code == 429  # bloqueado incluso con el PIN correcto
    assert "Retry-After" in respuesta.headers
    assert "Demasiados intentos" in respuesta.get_json()["error"]


def test_acertar_reinicia_el_contador(cliente):
    for _ in range(4):
        cliente.post("/login", json={"pin": "0000"})
    assert cliente.post("/login", json={"pin": PIN}).status_code == 200
    for _ in range(4):
        assert cliente.post("/login", json={"pin": "0000"}).status_code == 401


# ------------------------
# CONFIGURACIÓN DE PRODUCCIÓN
# ------------------------

def test_en_produccion_app_pin_es_obligatorio(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("APP_PIN")
    with pytest.raises(RuntimeError, match="APP_PIN"):
        crear_app()


def test_en_local_sin_app_pin_se_usa_el_de_desarrollo(monkeypatch):
    monkeypatch.delenv("APP_PIN")
    assert crear_app().config["APP_PIN"] == "1234"


def test_cookie_de_sesion_segura_en_produccion(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    app = crear_app()
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"

    respuesta = app.test_client().post(
        "/login", json={"pin": PIN}, base_url="https://localhost")
    cookie = respuesta.headers["Set-Cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert respuesta.headers["Strict-Transport-Security"].startswith("max-age=")


def test_en_produccion_se_usa_la_ip_real_tras_el_proxy(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    cliente = crear_app().test_client()
    for _ in range(5):
        cliente.post("/login", json={"pin": "0000"}, base_url="https://localhost",
                     headers={"X-Forwarded-For": "9.9.9.9"})
    # Otra IP real (mismo proxy) sigue pudiendo entrar
    respuesta = cliente.post("/login", json={"pin": PIN}, base_url="https://localhost",
                             headers={"X-Forwarded-For": "8.8.8.8"})
    assert respuesta.status_code == 200


# ------------------------
# CABECERAS Y CSRF
# ------------------------

def test_cabeceras_de_seguridad(cliente):
    respuesta = cliente.get("/")
    csp = respuesta.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert respuesta.headers["X-Content-Type-Options"] == "nosniff"
    assert respuesta.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" not in respuesta.headers  # solo en producción


def test_respuestas_json_no_se_guardan_en_cache(sesion):
    assert sesion.get("/resumen?persona=Carlos").headers["Cache-Control"] == "no-store"


def test_peticion_desde_otra_web_se_rechaza(sesion):
    respuesta = sesion.post("/objetivo", json={"persona": "Carlos", "objetivo": "1"},
                            headers={"Origin": "https://web-maliciosa.example"})
    assert respuesta.status_code == 403
    # Desde la propia web sí funciona
    respuesta = sesion.post("/objetivo", json={"persona": "Carlos", "objetivo": "1"},
                            headers={"Origin": "http://localhost"})
    assert respuesta.status_code == 200


def test_cuerpo_demasiado_grande(sesion):
    respuesta = sesion.post("/transferencias", data="x" * 20000,
                            content_type="application/json")
    assert respuesta.status_code == 413
