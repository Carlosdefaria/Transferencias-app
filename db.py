"""Acceso a datos: conexión, creación de tablas y consultas SQL.

Las consultas se escriben con %s (estilo PostgreSQL) y ejecutar() las adapta
a ? cuando el motor es SQLite. Todo el SQL debe funcionar en los dos motores.
"""

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import psycopg

from logica import a_decimal

log = logging.getLogger(__name__)

# sqlite3 no sabe guardar Decimal: se lo pasamos como texto y SQLite lo
# convierte a número porque la columna es numérica.
sqlite3.register_adapter(Decimal, str)

PERSONAS_INICIALES = ("Carlos", "Pito")
OBJETIVO_INICIAL = Decimal("1070")


def conectar():
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return psycopg.connect(database_url)

    return sqlite3.connect(os.environ.get("SQLITE_PATH", "database.db"))


@contextmanager
def conexion():
    """Abre una conexión y garantiza que se cierra pase lo que pase.

    Si el bloque 'with' termina bien, guarda los cambios (commit); si lanza
    una excepción, los deshace (rollback). Antes, cualquier 'return'
    temprano dejaba la conexión abierta.
    """
    conn = conectar()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def es_sqlite(conn):
    return isinstance(conn, sqlite3.Connection)


def ejecutar(conn, query, params=()):
    if es_sqlite(conn):
        query = query.replace("%s", "?")
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor


def crear_tablas():
    with conexion() as conn:
        if es_sqlite(conn):
            log.warning("Usando SQLite en local (%s)",
                        os.environ.get("SQLITE_PATH", "database.db"))
            id_columna = "INTEGER PRIMARY KEY AUTOINCREMENT"
            tipo_fecha = "TEXT"
            falso = "0"
        else:
            id_columna = "SERIAL PRIMARY KEY"
            tipo_fecha = "DATE"
            falso = "FALSE"

        # NUMERIC(12,2) guarda los importes exactos, con 2 decimales.
        # Las tablas que ya existan en producción no cambian: para ellas está
        # el script migraciones/m001_numeric.py.
        ejecutar(conn, f"""
            CREATE TABLE IF NOT EXISTS transferencias (
                id {id_columna},
                monto NUMERIC(12,2) NOT NULL,
                fecha {tipo_fecha} NOT NULL,
                descripcion TEXT,
                persona TEXT NOT NULL,
                confirmada BOOLEAN DEFAULT {falso}
            )
        """)
        ejecutar(conn, f"""
            CREATE TABLE IF NOT EXISTS config (
                id {id_columna},
                persona TEXT NOT NULL,
                objetivo_total NUMERIC(12,2),
                CONSTRAINT config_persona_unica UNIQUE (persona)
            )
        """)

        if ejecutar(conn, "SELECT COUNT(*) FROM config").fetchone()[0] == 0:
            for persona in PERSONAS_INICIALES:
                ejecutar(conn,
                         "INSERT INTO config (persona, objetivo_total) VALUES (%s, %s)",
                         (persona, OBJETIVO_INICIAL))


# ------------------------
# CONSULTAS
# ------------------------

def _fecha_a_texto(valor):
    # PostgreSQL devuelve un objeto date y SQLite un texto. Se unifica a
    # 'YYYY-MM-DD'; si no, Flask convertiría el date a "Wed, 28 Oct 2026 ...".
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)[:10]


def _fila_a_transferencia(fila):
    return {
        "id": fila[0],
        "monto": a_decimal(fila[1]),
        "fecha": _fecha_a_texto(fila[2]),
        "descripcion": fila[3] or "",
        "persona": fila[4],
        "confirmada": bool(fila[5]),
    }


def obtener_objetivo(conn, persona):
    """Objetivo de la persona en Decimal, o None si la persona no existe."""
    fila = ejecutar(conn,
                    "SELECT objetivo_total FROM config WHERE persona = %s ORDER BY id LIMIT 1",
                    (persona,)).fetchone()
    if fila is None:
        return None
    return a_decimal(fila[0] or 0)


def guardar_objetivo(conn, persona, objetivo):
    ejecutar(conn, "UPDATE config SET objetivo_total = %s WHERE persona = %s",
             (objetivo, persona))


# Las transferencias guardan el nombre de la persona (no su id), así que
# para saber cuántas tiene cada una se cruzan las tablas por el nombre.
_SELECT_PERSONAS = """
    SELECT c.id, c.persona, c.objetivo_total, COUNT(t.id)
    FROM config c
    LEFT JOIN transferencias t ON t.persona = c.persona
"""


def _fila_a_persona(fila):
    return {
        "id": fila[0],
        "nombre": fila[1],
        "objetivo": a_decimal(fila[2] or 0),
        "transferencias": fila[3],
    }


def listar_personas(conn):
    filas = ejecutar(conn, _SELECT_PERSONAS + """
        GROUP BY c.id, c.persona, c.objetivo_total
        ORDER BY c.id
    """).fetchall()
    return [_fila_a_persona(fila) for fila in filas]


def obtener_persona(conn, id):
    fila = ejecutar(conn, _SELECT_PERSONAS + """
        WHERE c.id = %s
        GROUP BY c.id, c.persona, c.objetivo_total
    """, (id,)).fetchone()
    return _fila_a_persona(fila) if fila else None


def existe_persona(conn, nombre, excepto_id=None):
    """True si ya hay otra persona con ese nombre (sin distinguir mayúsculas)."""
    fila = ejecutar(conn,
                    "SELECT id FROM config WHERE LOWER(persona) = LOWER(%s) AND id <> %s",
                    (nombre, excepto_id or 0)).fetchone()
    return fila is not None


def contar_personas(conn):
    return ejecutar(conn, "SELECT COUNT(*) FROM config").fetchone()[0]


def insertar_persona(conn, nombre, objetivo):
    return ejecutar(conn,
                    "INSERT INTO config (persona, objetivo_total) VALUES (%s, %s) RETURNING id",
                    (nombre, objetivo)).fetchone()[0]


def renombrar_persona(conn, id, nombre_actual, nombre_nuevo):
    """Cambia el nombre en config y en todas sus transferencias.

    Las dos consultas van en la misma transacción (la de conexion()): o se
    cambian las dos o ninguna, y nunca quedan transferencias "huérfanas".
    """
    ejecutar(conn, "UPDATE transferencias SET persona = %s WHERE persona = %s",
             (nombre_nuevo, nombre_actual))
    ejecutar(conn, "UPDATE config SET persona = %s WHERE id = %s", (nombre_nuevo, id))


def eliminar_persona(conn, id):
    ejecutar(conn, "DELETE FROM config WHERE id = %s", (id,))


def listar_transferencias(conn, persona, desde, hasta):
    filas = ejecutar(conn, """
        SELECT id, monto, fecha, descripcion, persona, confirmada
        FROM transferencias
        WHERE persona = %s AND fecha >= %s AND fecha < %s
        ORDER BY fecha DESC, id DESC
    """, (persona, desde, hasta)).fetchall()
    return [_fila_a_transferencia(fila) for fila in filas]


def sumar_por_estado(conn, persona, desde, hasta):
    """Devuelve (total confirmado, total pendiente) del periodo en Decimal."""
    filas = ejecutar(conn, """
        SELECT confirmada, COALESCE(SUM(monto), 0)
        FROM transferencias
        WHERE persona = %s AND fecha >= %s AND fecha < %s
        GROUP BY confirmada
    """, (persona, desde, hasta)).fetchall()

    totales = {True: Decimal("0.00"), False: Decimal("0.00")}
    for confirmada, total in filas:
        totales[bool(confirmada)] = a_decimal(total)
    return totales[True], totales[False]


def obtener_transferencia(conn, id):
    fila = ejecutar(conn, """
        SELECT id, monto, fecha, descripcion, persona, confirmada
        FROM transferencias WHERE id = %s
    """, (id,)).fetchone()
    return _fila_a_transferencia(fila) if fila else None


def insertar_transferencia(conn, monto, fecha, descripcion, persona):
    return ejecutar(conn, """
        INSERT INTO transferencias (monto, fecha, descripcion, persona, confirmada)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (monto, fecha, descripcion, persona, False)).fetchone()[0]


def actualizar_transferencia(conn, id, monto, fecha, descripcion):
    ejecutar(conn,
             "UPDATE transferencias SET monto = %s, fecha = %s, descripcion = %s WHERE id = %s",
             (monto, fecha, descripcion, id))


def alternar_confirmacion(conn, id):
    """Invierte 'confirmada' en una sola consulta y devuelve el nuevo valor (o None)."""
    fila = ejecutar(conn,
                    "UPDATE transferencias SET confirmada = NOT confirmada WHERE id = %s RETURNING confirmada",
                    (id,)).fetchone()
    return bool(fila[0]) if fila else None


def eliminar_transferencia(conn, id):
    ejecutar(conn, "DELETE FROM transferencias WHERE id = %s", (id,))
