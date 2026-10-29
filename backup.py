"""Copia de seguridad local de la base de datos PostgreSQL con pg_dump.

Uso:  python backup.py

Variables de entorno (en .env):
- DATABASE_URL   (obligatoria) URL de la base de datos a copiar.
- DB_PASSWORD    (opcional) contraseña, si no va incluida en la URL.
- BACKUP_DIR     (opcional) carpeta de destino.
- PG_DUMP_PATH   (opcional) ruta al ejecutable pg_dump.
- BACKUP_DIAS    (opcional) días que se conservan las copias (7 por defecto).

Solo lee la base de datos: pg_dump nunca modifica nada.
"""

import os
import subprocess
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

CARPETA = os.getenv("BACKUP_DIR", "C:/backups_transferencias")
PG_DUMP_PATH = os.getenv(
    "PG_DUMP_PATH", r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe")
DIAS_MAX = int(os.getenv("BACKUP_DIAS", "7"))


def crear_backup(db_url):
    """Crea la copia y devuelve su ruta. Lanza RuntimeError si falla."""
    os.makedirs(CARPETA, exist_ok=True)

    fecha = datetime.now().strftime("%Y-%m-%d_%H-%M")
    archivo = os.path.join(CARPETA, f"backup_{fecha}.sql")
    # Se escribe primero en un archivo temporal: si pg_dump falla a medias,
    # nunca queda un .sql incompleto que parezca una copia válida.
    temporal = archivo + ".parcial"

    env = os.environ.copy()
    password = os.getenv("DB_PASSWORD")
    if password:
        env["PGPASSWORD"] = password

    try:
        resultado = subprocess.run(
            [PG_DUMP_PATH, "--dbname", db_url, "--file", temporal],
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
    except FileNotFoundError:
        raise RuntimeError(f"No se encontró pg_dump en: {PG_DUMP_PATH}")

    if resultado.returncode != 0:
        if os.path.exists(temporal):
            os.remove(temporal)
        raise RuntimeError(resultado.stderr.strip() or "pg_dump falló")

    os.replace(temporal, archivo)
    return archivo


def limpiar_backups_antiguos():
    """Borra las copias .sql con más de DIAS_MAX días."""
    limite = datetime.now() - timedelta(days=DIAS_MAX)

    for nombre in os.listdir(CARPETA):
        if not nombre.endswith(".sql"):
            continue

        ruta = os.path.join(CARPETA, nombre)
        if datetime.fromtimestamp(os.path.getmtime(ruta)) < limite:
            os.remove(ruta)
            print(f"Backup eliminado: {nombre}")


def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: falta DATABASE_URL en el entorno o en .env")
        return 1

    try:
        archivo = crear_backup(db_url)
    except RuntimeError as error:
        print("Error al crear backup:")
        print(error)
        # No se borran copias antiguas: si el backup falla, son las únicas.
        return 1

    print(f"Backup creado: {archivo}")
    limpiar_backups_antiguos()
    return 0


if __name__ == "__main__":
    sys.exit(main())
