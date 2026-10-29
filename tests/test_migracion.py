"""Test de la migración FLOAT -> NUMERIC. Solo con PostgreSQL de pruebas.

Se ejecuta con:  TEST_DATABASE_URL=postgresql://.../algo_test python -m pytest
Sin TEST_DATABASE_URL, se salta.
"""

import os
from decimal import Decimal

import psycopg
import pytest

from conftest import crear
from migraciones import m001_numeric

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="Necesita TEST_DATABASE_URL (PostgreSQL)")

ESQUEMA_ANTIGUO = [
    "DROP TABLE IF EXISTS transferencias",
    "DROP TABLE IF EXISTS config",
    """CREATE TABLE transferencias (
        id SERIAL PRIMARY KEY, monto FLOAT NOT NULL, fecha DATE NOT NULL,
        descripcion TEXT, persona TEXT NOT NULL, confirmada BOOLEAN DEFAULT FALSE)""",
    """CREATE TABLE config (
        id SERIAL PRIMARY KEY, persona TEXT NOT NULL, objetivo_total FLOAT)""",
    "INSERT INTO config (persona, objetivo_total) VALUES ('Carlos', 1070), ('Pito', 1070)",
    """INSERT INTO transferencias (monto, fecha, persona, confirmada) VALUES
        (0.1, '2026-10-01', 'Carlos', TRUE), (0.2, '2026-10-02', 'Carlos', TRUE),
        (535.555, '2026-10-03', 'Pito', FALSE)""",
]


@pytest.fixture
def conn_antigua():
    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as conn:
        for sql in ESQUEMA_ANTIGUO:
            conn.execute(sql)
        conn.commit()
        yield conn


def test_aplicar_y_revertir(conn_antigua):
    assert m001_numeric.comprobar(conn_antigua) == []

    m001_numeric.aplicar(conn_antigua)
    conn_antigua.commit()
    assert m001_numeric.tipos_actuales(conn_antigua) == {
        "transferencias.monto": "numeric", "config.objetivo_total": "numeric"}
    montos = [m for (m,) in conn_antigua.execute("SELECT monto FROM transferencias ORDER BY id")]
    assert montos == [Decimal("0.10"), Decimal("0.20"), Decimal("535.56")]

    # Aplicarla dos veces no está permitido
    assert m001_numeric.comprobar(conn_antigua) == ["La migración ya está aplicada"]

    m001_numeric.revertir(conn_antigua)
    conn_antigua.commit()
    assert m001_numeric.tipos_actuales(conn_antigua) == {
        "transferencias.monto": "double precision", "config.objetivo_total": "double precision"}


def test_no_se_aplica_con_personas_repetidas(conn_antigua):
    conn_antigua.execute("INSERT INTO config (persona, objetivo_total) VALUES ('Pito', 900)")
    problemas = m001_numeric.comprobar(conn_antigua)
    assert any("repetidas" in p for p in problemas)


def test_si_falla_no_cambia_nada(conn_antigua):
    conn_antigua.execute("INSERT INTO config (persona, objetivo_total) VALUES ('Pito', 900)")
    conn_antigua.commit()
    with pytest.raises(psycopg.errors.UniqueViolation):
        m001_numeric.aplicar(conn_antigua)
    conn_antigua.rollback()
    assert m001_numeric.tipos_actuales(conn_antigua)["transferencias.monto"] == "double precision"


def test_la_app_funciona_antes_y_despues_de_migrar(conn_antigua, sesion):
    # 'sesion' ha creado tablas nuevas; se vuelve al esquema antiguo.
    for sql in ESQUEMA_ANTIGUO:
        conn_antigua.execute(sql)
    conn_antigua.commit()

    def resumen():
        return sesion.get("/resumen?persona=Carlos&mes=2026-10").get_json()

    assert resumen()["total_confirmado"] == "0.30"
    crear(sesion, monto="10.05", fecha="2026-10-04")

    m001_numeric.aplicar(conn_antigua)
    conn_antigua.commit()
    assert resumen()["total_confirmado"] == "0.30"
    assert resumen()["pendiente"] == "10.05"
    crear(sesion, monto="1.01", fecha="2026-10-05")
    assert resumen()["pendiente"] == "11.06"
