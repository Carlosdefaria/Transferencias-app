"""Migración 004: desglose de gastos por persona (columnas gasto_* en config).

Añade a config una columna por partida del desglose (gasto_universidad y
gasto_alquiler). Desde ahora, el objetivo de cada persona es la suma de sus
partidas. Las personas que ya existen quedan con las columnas vacías (NULL):
conservan su objetivo actual y la app muestra "Sin desglose" hasta que se
rellene desde Ajustes. No cambia ningún dato existente.

Solo para PostgreSQL. Ejecutar desde la raíz del proyecto:

    python -m migraciones.m004_desglose comprobar   # solo lee
    python -m migraciones.m004_desglose aplicar     # añade las columnas
    python -m migraciones.m004_desglose revertir    # las quita

También se puede hacer pegando el SQL de migraciones/README.md en el
editor SQL de Neon. Hay que aplicarla ANTES de desplegar el código que la usa.
"""

import argparse
import os
import sys

import psycopg
from dotenv import load_dotenv

from migraciones.m001_numeric import confirmar_destino

# Escritas a mano (no desde db.COLUMNAS_GASTO): una migración describe un
# cambio concreto y no debe cambiar si mañana cambia el código.
COLUMNAS = ("gasto_universidad", "gasto_alquiler")

SQL_APLICAR = "ALTER TABLE config " + ", ".join(
    f"ADD COLUMN {columna} NUMERIC(12,2)" for columna in COLUMNAS)
SQL_REVERTIR = "ALTER TABLE config " + ", ".join(
    f"DROP COLUMN {columna}" for columna in COLUMNAS)


def columnas_existentes(conn):
    filas = conn.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'config' AND column_name = ANY(%s)
    """, (list(COLUMNAS),)).fetchall()
    return {columna for (columna,) in filas}


def contar_con_desglose(conn):
    """Cuántas personas tienen desglose (al revertir se perdería, el objetivo no)."""
    condicion = " OR ".join(f"{columna} IS NOT NULL" for columna in COLUMNAS)
    return conn.execute(f"SELECT COUNT(*) FROM config WHERE {condicion}").fetchone()[0]


def comprobar(conn):
    """Devuelve True si las columnas existen. Si solo existe alguna, avisa y devuelve None."""
    existentes = columnas_existentes(conn)
    for columna in COLUMNAS:
        print(f"Columna {columna}:", "ya existe" if columna in existentes else "no existe")
    if existentes and len(existentes) < len(COLUMNAS):
        print("AVISO: solo existe una parte de las columnas. Revisa el esquema a mano.")
        return None
    if existentes:
        print(f"Personas con desglose: {contar_con_desglose(conn)}")
    return bool(existentes)


def aplicar(conn):
    """Añade las columnas dentro de la transacción de 'conn' (sin commit)."""
    conn.execute(SQL_APLICAR)


def revertir(conn):
    """Quita las columnas dentro de la transacción de 'conn' (sin commit)."""
    conn.execute(SQL_REVERTIR)


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
        existe = comprobar(conn)

        if args.accion == "comprobar":
            conn.rollback()
            return 0
        if existe is None:
            return 1
        if args.accion == "aplicar" and existe:
            print("La migración ya está aplicada.")
            return 1
        if args.accion == "revertir":
            if not existe:
                print("No hay nada que revertir.")
                return 1
            con_desglose = contar_con_desglose(conn)
            if con_desglose:
                print(f"AVISO: se perderá el desglose de {con_desglose} personas. "
                      "Su objetivo (la suma) se conserva.")

        if not confirmar_destino(conn):
            print("Cancelado.")
            return 1

        aplicar(conn) if args.accion == "aplicar" else revertir(conn)
        conn.commit()
        print("Hecho.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
