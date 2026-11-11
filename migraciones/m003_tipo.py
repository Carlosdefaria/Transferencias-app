"""Migración 003: columna tipo en transferencias (ingreso o retirada).

Permite registrar retiradas del pote: dinero que se coge de lo recaudado y
que resta del mes en vez de sumar. El monto se sigue guardando positivo; el
signo lo da el tipo. La columna tiene 'ingreso' por defecto, así que todas
las transferencias existentes siguen sumando como siempre.

Solo para PostgreSQL. Ejecutar desde la raíz del proyecto:

    python -m migraciones.m003_tipo comprobar   # solo lee
    python -m migraciones.m003_tipo aplicar     # añade la columna
    python -m migraciones.m003_tipo revertir    # la quita

También se puede hacer pegando el SQL de migraciones/README.md en el
editor SQL de Neon. Hay que aplicarla ANTES de desplegar el código que la usa.
"""

import argparse
import os
import sys

import psycopg
from dotenv import load_dotenv

from migraciones.m001_numeric import confirmar_destino

SQL_APLICAR = """
    ALTER TABLE transferencias
    ADD COLUMN tipo TEXT NOT NULL DEFAULT 'ingreso'
    CHECK (tipo IN ('ingreso', 'retirada'))
"""
SQL_REVERTIR = "ALTER TABLE transferencias DROP COLUMN tipo"


def columna_existe(conn):
    return conn.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'transferencias' AND column_name = 'tipo'
    """).fetchone() is not None


def contar_retiradas(conn):
    """Cuántas retiradas hay (al revertir pasarían a sumar como ingresos)."""
    return conn.execute(
        "SELECT COUNT(*) FROM transferencias WHERE tipo = 'retirada'").fetchone()[0]


def comprobar(conn):
    existe = columna_existe(conn)
    print("Columna tipo:", "ya existe" if existe else "no existe")
    if existe:
        print(f"Retiradas guardadas: {contar_retiradas(conn)}")
    return existe


def aplicar(conn):
    """Añade la columna dentro de la transacción de 'conn' (sin commit)."""
    conn.execute(SQL_APLICAR)


def revertir(conn):
    """Quita la columna dentro de la transacción de 'conn' (sin commit)."""
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
        if args.accion == "aplicar" and existe:
            print("La migración ya está aplicada.")
            return 1
        if args.accion == "revertir":
            if not existe:
                print("No hay nada que revertir.")
                return 1
            retiradas = contar_retiradas(conn)
            if retiradas:
                print(f"AVISO: {retiradas} retiradas pasarán a SUMAR como transferencias normales. "
                      "Elimínalas antes si no quieres que cambien los totales.")

        if not confirmar_destino(conn):
            print("Cancelado.")
            return 1

        aplicar(conn) if args.accion == "aplicar" else revertir(conn)
        conn.commit()
        print("Hecho.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
