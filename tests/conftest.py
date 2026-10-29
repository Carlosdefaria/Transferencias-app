"""Configuración común de los tests.

Por seguridad, los tests NUNCA usan la base de datos de producción:
- DATABASE_URL se vacía antes de importar la app (load_dotenv no pisa una
  variable que ya existe, así que tampoco se lee la del .env).
- Por defecto se usa un SQLite temporal.
- Para probar contra un PostgreSQL de pruebas, define TEST_DATABASE_URL
  apuntando a una base de datos cuyo nombre contenga "test".
"""

import os
import sys
import tempfile
from decimal import Decimal

import pytest

_url_test = os.environ.get("TEST_DATABASE_URL", "")
if _url_test and "test" not in _url_test.rsplit("/", 1)[-1]:
    raise RuntimeError("TEST_DATABASE_URL debe apuntar a una BD con 'test' en el nombre")

os.environ["DATABASE_URL"] = _url_test
os.environ["SECRET_KEY"] = "clave-solo-para-tests"
os.environ["APP_PIN"] = "4321"
os.environ["SQLITE_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402
import logica  # noqa: E402
from app import crear_app  # noqa: E402

PIN = "4321"
TASAS_PRUEBA = {"EUR": Decimal("1"), "USD": Decimal("1.10"), "GBP": Decimal("0.85")}


@pytest.fixture(autouse=True)
def tasas_falsas(monkeypatch):
    """Ningún test llama a Internet: las tasas son siempre las de prueba."""
    logica.vaciar_cache_tasas()
    monkeypatch.setattr(logica, "descargar_tasas", lambda: dict(TASAS_PRUEBA))
    yield
    logica.vaciar_cache_tasas()


@pytest.fixture
def app():
    with db.conexion() as conn:
        db.ejecutar(conn, "DROP TABLE IF EXISTS transferencias")
        db.ejecutar(conn, "DROP TABLE IF EXISTS config")
    aplicacion = crear_app()
    aplicacion.config["TESTING"] = True
    return aplicacion


@pytest.fixture
def cliente(app):
    """Cliente HTTP sin sesión iniciada."""
    return app.test_client()


@pytest.fixture
def sesion(cliente):
    """Cliente HTTP con la sesión ya iniciada."""
    respuesta = cliente.post("/login", json={"pin": PIN})
    assert respuesta.status_code == 200
    return cliente


def crear(sesion, monto="100", fecha="2026-10-05", persona="Carlos", descripcion=""):
    """Crea una transferencia y devuelve su id."""
    respuesta = sesion.post("/transferencias", json={
        "monto": monto, "fecha": fecha, "persona": persona, "descripcion": descripcion,
    })
    assert respuesta.status_code == 201, respuesta.get_json()
    return respuesta.get_json()["id"]
