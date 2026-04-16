import os
import subprocess
from datetime import datetime, timedelta


# Config
DB_URL = "postgresql://transferencias_app_bjtt_user:WkUIOVHbvPJO0egVJa1QU60Hp49Htekd@dpg-d7ejh7gsfn5c738dija0-a.ohio-postgres.render.com/transferencias_app_bjtt"

# Carpeta backups
CARPETA = "C:/backups_transferencias"
os.makedirs(CARPETA, exist_ok=True)

# Nombre archivo
fecha = datetime.now().strftime("%Y-%m-%d_%H-%M")
archivo = f"{CARPETA}/backup_{fecha}.sql"

PG_DUMP_PATH = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"

with open(archivo, "w") as f:
    resultado = subprocess.run(
        [PG_DUMP_PATH, DB_URL],
        stdout=f,
        stderr=subprocess.PIPE,
        text=True
    )

if resultado.returncode == 0:
    print(f"✅ Backup creado: {archivo}")
else:
    print("❌ Error al crear backup")
    print(resultado.stderr)


# 🔥 CONFIG
DIAS_MAX = 7  # mantener solo últimos 7 días

ahora = datetime.now()

for archivo_nombre in os.listdir(CARPETA):
    ruta_archivo = os.path.join(CARPETA, archivo_nombre)

    # Solo archivos .sql
    if archivo_nombre.endswith(".sql"):
        fecha_mod = datetime.fromtimestamp(os.path.getmtime(ruta_archivo))
        diferencia = ahora - fecha_mod

        if diferencia > timedelta(days=DIAS_MAX):
            os.remove(ruta_archivo)
            print(f"🧹 Backup eliminado: {archivo_nombre}")
