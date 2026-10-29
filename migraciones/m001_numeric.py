"""Migración 001: importes de FLOAT a NUMERIC(12,2) y persona única en config.

Solo para PostgreSQL. Ejecutar desde la raíz del proyecto:

    python -m migraciones.m001_numeric comprobar   # solo lee, no cambia nada
    python -m migraciones.m001_numeric aplicar     # FLOAT -> NUMERIC(12,2)
    python -m migraciones.m001_numeric revertir    # NUMERIC -> FLOAT (vuelta atrás)

La URL se toma de --url o, si no se indica, de DATABASE_URL (.env).
'aplicar' y 'revertir' piden escribir el nombre de la base de datos para
confirmar, y todo ocurre en una sola transacción: si algo falla, no se
cambia nada. Lee migraciones/README.md antes de usarlo.
"""

import argparse
import os
import sys

import psycopg
from dotenv import load_dotenv

RESTRICCION = "config_persona_unica"

SQL_APLICAR = [
    "ALTER TABLE transferencias ALTER COLUMN monto TYPE NUMERIC(12,2) USING ROUND(monto::numeric, 2)",
    "ALTER TABLE config ALTER COLUMN objetivo_total TYPE NUMERIC(12,2) USING ROUND(objetivo_total::numeric, 2)",
    f"ALTER TABLE config ADD CONSTRAINT {RESTRICCION} UNIQUE (persona)",
]

SQL_REVERTIR = [
    f"ALTER TABLE config DROP CONSTRAINT IF EXISTS {RESTRICCION}",
    "ALTER TABLE transferencias ALTER COLUMN monto TYPE DOUBLE PRECISION",
    "ALTER TABLE config ALTER COLUMN objetivo_total TYPE DOUBLE PRECISION",
]


def tipos_actuales(conn):
    filas = conn.execute("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE (table_name, column_name) IN
              (('transferencias', 'monto'), ('config', 'objetivo_total'))
    """).fetchall()
    return {f"{tabla}.{columna}": tipo for tabla, columna, tipo in filas}


def totales(conn):
    """Sumas redondeadas a céntimos: deben ser iguales antes y después."""
    transferencias = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(ROUND(monto::numeric, 2)), 0) FROM transferencias").fetchone()
    objetivos = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(ROUND(objetivo_total::numeric, 2)), 0) FROM config").fetchone()
    return {"transferencias": tuple(transferencias), "config": tuple(objetivos)}


def comprobar(conn):
    """Informe de solo lectura. Devuelve la lista de problemas que impiden aplicar."""
    problemas = []

    print("Tipos actuales:", tipos_actuales(conn))
    print("Filas y sumas:", totales(conn))

    con_mas_decimales = conn.execute("""
        SELECT COUNT(*) FROM transferencias
        WHERE monto::numeric <> ROUND(monto::numeric, 2)
    """).fetchone()[0]
    print(f"Importes con más de 2 decimales (se redondearán): {con_mas_decimales}")

    demasiado_grandes = conn.execute(
        "SELECT COUNT(*) FROM transferencias WHERE ABS(monto) >= 10000000000").fetchone()[0]
    if demasiado_grandes:
        problemas.append(f"{demasiado_grandes} importes no caben en NUMERIC(12,2)")

    duplicadas = conn.execute("""
        SELECT persona, COUNT(*) FROM config GROUP BY persona HAVING COUNT(*) > 1
    """).fetchall()
    if duplicadas:
        problemas.append(f"Personas repetidas en config (hay que dejar una fila por persona): {duplicadas}")

    if tipos_actuales(conn).get("transferencias.monto") == "numeric":
        problemas.append("La migración ya está aplicada")

    for problema in problemas:
        print("PROBLEMA:", problema)
    return problemas


def aplicar(conn):
    """Aplica la migración dentro de la transacción de 'conn' (sin commit)."""
    antes = totales(conn)
    for sql in SQL_APLICAR:
        conn.execute(sql)
    despues = totales(conn)

    # Comprobación de seguridad: mismas filas y mismas sumas en céntimos.
    if antes != despues:
        raise RuntimeError(f"Los totales no coinciden: {antes} != {despues}")
    return despues


def revertir(conn):
    """Deshace la migración dentro de la transacción de 'conn' (sin commit)."""
    antes = totales(conn)
    for sql in SQL_REVERTIR:
        conn.execute(sql)
    despues = totales(conn)
    if antes != despues:
        raise RuntimeError(f"Los totales no coinciden: {antes} != {despues}")
    return despues


def confirmar_destino(conn):
    nombre = conn.info.dbname
    print(f"Base de datos destino: {conn.info.host} / {nombre}")
    respuesta = input(f"Escribe '{nombre}' para continuar: ")
    return respuesta.strip() == nombre


def main(argv=None):
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("accion", choices=["comprobar", "aplicar", "revertir"])
    parser.add_argument("--url", help="URL de PostgreSQL (por defecto DATABASE_URL)")
    args = parser.parse_args(argv)

    url = args.url or os.environ.get("DATABASE_URL")
    if not url:
        print("Falta la URL: usa --url o define DATABASE_URL")
        return 1
    url = url.replace("postgres://", "postgresql://", 1)

    with psycopg.connect(url) as conn:
        if args.accion == "comprobar":
            comprobar(conn)
            conn.rollback()
            return 0

        if args.accion == "aplicar":
            if comprobar(conn):
                print("No se aplica la migración. Resuelve los problemas primero.")
                return 1
            if not confirmar_destino(conn):
                print("Cancelado.")
                return 1
            resultado = aplicar(conn)
        else:
            if not confirmar_destino(conn):
                print("Cancelado.")
                return 1
            resultado = revertir(conn)

        conn.commit()
        print("Hecho. Tipos:", tipos_actuales(conn), "Totales:", resultado)
    return 0


if __name__ == "__main__":
    sys.exit(main())
