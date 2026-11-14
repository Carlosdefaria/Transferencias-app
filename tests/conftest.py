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

import pytest

_url_test = os.environ.get("TEST_DATABASE_URL", "")
if _url_test and "test" not in _url_test.rsplit("/", 1)[-1]:
    raise RuntimeError("TEST_DATABASE_URL debe apuntar a una BD con 'test' en el nombre")

os.environ["DATABASE_URL"] = _url_test
os.environ["SECRET_KEY"] = "clave-solo-para-tests"
os.environ["APP_PIN"] = "4321"
os.environ["SQLITE_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
# Los tests no simulan producción salvo que un test lo pida.
os.environ.pop("RENDER", None)
os.environ.pop("APP_ENV", None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402
import seguridad  # noqa: E402
from app import crear_app  # noqa: E402

PIN = "4321"
@pytest.fixture(autouse=True)
def limitador_limpio():
    seguridad.limitador_login._fallos.clear()
    yield
    seguridad.limitador_login._fallos.clear()


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


# La app no crea personas al empezar: los tests usan estas, creadas en 'sesion'.
PERSONAS_TEST = ("Marta", "Juan")
DESGLOSE_TEST = {"universidad": "570", "alquiler": "500"}   # objetivo: 1070


@pytest.fixture
def sesion_vacia(cliente):
    """Cliente HTTP con la sesión iniciada y la BD sin personas."""
    respuesta = cliente.post("/login", json={"pin": PIN})
    assert respuesta.status_code == 200
    return cliente


@pytest.fixture
def sesion(sesion_vacia):
    """Cliente HTTP con la sesión iniciada y las personas de PERSONAS_TEST."""
    for nombre in PERSONAS_TEST:
        respuesta = sesion_vacia.post("/personas", json={"nombre": nombre, "desglose": DESGLOSE_TEST})
        assert respuesta.status_code == 201, respuesta.get_json()
    return sesion_vacia


def crear(sesion, monto="100", fecha="2026-10-05", persona="Marta", descripcion=""):
    """Crea una transferencia y devuelve su id."""
    respuesta = sesion.post("/transferencias", json={
        "monto": monto, "fecha": fecha, "persona": persona, "descripcion": descripcion,
    })
    assert respuesta.status_code == 201, respuesta.get_json()
    return respuesta.get_json()["id"]
