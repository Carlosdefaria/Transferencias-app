"""Migración 002: columna mes_cuenta en transferencias.

Permite que una transferencia cuente para un mes distinto al de su fecha
(por ejemplo, recibida el 28 de octubre para la cuota de noviembre).
La columna es opcional: si está vacía, la transferencia cuenta por su fecha,
así que las transferencias existentes no cambian.

Solo para PostgreSQL. Ejecutar desde la raíz del proyecto:

    python -m migraciones.m002_mes_cuenta comprobar   # solo lee
    python -m migraciones.m002_mes_cuenta aplicar     # añade la columna
    python -m migraciones.m002_mes_cuenta revertir    # la quita

También se puede hacer pegando el SQL de migraciones/README.md en el
editor SQL de Neon. Hay que aplicarla ANTES de desplegar el código que la usa.
"""

import argparse
import os
import sys

import psycopg
from dotenv import load_dotenv

from migraciones.m001_numeric import confirmar_destino

SQL_APLICAR = "ALTER TABLE transferencias ADD COLUMN mes_cuenta TEXT"
SQL_REVERTIR = "ALTER TABLE transferencias DROP COLUMN mes_cuenta"


def columna_existe(conn):
    return conn.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'transferencias' AND column_name = 'mes_cuenta'
    """).fetchone() is not None


def con_mes_distinto(conn):
    """Cuántas transferencias cuentan para otro mes (se perdería al revertir)."""
    return conn.execute(
        "SELECT COUNT(*) FROM transferencias WHERE mes_cuenta IS NOT NULL").fetchone()[0]


def comprobar(conn):
    existe = columna_existe(conn)
    print("Columna mes_cuenta:", "ya existe" if existe else "no existe")
    if existe:
        print(f"Transferencias que cuentan para otro mes: {con_mes_distinto(conn)}")
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
            perdidas = con_mes_distinto(conn)
            if perdidas:
                print(f"AVISO: {perdidas} transferencias volverán a contar por su fecha.")

        if not confirmar_destino(conn):
            print("Cancelado.")
            return 1

        aplicar(conn) if args.accion == "aplicar" else revertir(conn)
        conn.commit()
        print("Hecho.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
