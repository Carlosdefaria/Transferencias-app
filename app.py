import sqlite3
import os
import psycopg
from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)


# ------------------------
# DB CONNECTION
# ------------------------


def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")

    # 👉 Si estamos en producción (Render)
    if database_url:
        # fix postgres:// → postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace(
                "postgres://", "postgresql://", 1)

        conn = psycopg.connect(database_url)
        return conn

    # 👉 Si estamos en local (SQLite)
    else:
        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        return conn


def crear_tablas_postgres():
    conn = get_db_connection()
    cur = conn.cursor()

    # Tabla transferencias
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transferencias (
            id SERIAL PRIMARY KEY,
            monto FLOAT NOT NULL,
            fecha DATE NOT NULL,
            descripcion TEXT
        );
    """)

    # Tabla config
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config (
            id SERIAL PRIMARY KEY,
            objetivo_total FLOAT
        );
    """)

    # Insert inicial si no existe
    cur.execute("SELECT COUNT(*) FROM config")
    count = cur.fetchone()[0]

    if count == 0:
        cur.execute("INSERT INTO config (objetivo_total) VALUES (1070)")

    conn.commit()
    cur.close()
    conn.close()


with app.app_context():
    crear_tablas_postgres()


# ------------------------
# INIT DB
# ------------------------


def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS transferencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monto REAL NOT NULL,
            fecha TEXT NOT NULL,
            descripcion TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objetivo_total REAL
        )
    """)

    # 👉 NUEVO BLOQUE (objetivo fijo automático)
    existe = conn.execute("SELECT COUNT(*) as count FROM config").fetchone()

    if existe["count"] == 0:
        conn.execute(
            "INSERT INTO config (objetivo_total) VALUES (?)",
            (1070,)
        )

    conn.commit()
    conn.close()

# ------------------------
# ROUTES
# ------------------------


@app.route("/")
def home():
    return render_template("index.html")

# 👉 CREAR TRANSFERENCIA


@app.route("/transferencias", methods=["POST"])
def crear_transferencia():
    data = request.get_json()

    monto = data.get("monto")
    fecha = data.get("fecha")
    descripcion = data.get("descripcion", "")

    # Validaciones
    try:
        monto = float(monto)
    except:
        return jsonify({"error": "Monto inválido"}), 400

    if monto <= 0:
        return jsonify({"error": "El monto debe ser mayor a 0"}), 400

    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except:
        return jsonify({"error": "Fecha inválida"}), 400

    descripcion = data.get("descripcion")

    if not monto or not fecha:
        return jsonify({"error": "Faltan datos"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO transferencias (monto, fecha, descripcion) VALUES (%s, %s, %s)",
        (monto, fecha, descripcion)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"mensaje": "Transferencia creada"})


@app.route("/transferencias", methods=["GET"])
def obtener_transferencias():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, monto, fecha, descripcion FROM transferencias")
    filas = cursor.fetchall()

    cursor.close()
    conn.close()

    resultado = []

    for fila in filas:
        resultado.append({
            "id": fila[0],
            "monto": fila[1],
            "fecha": fila[2],
            "descripcion": fila[3]
        })

    return jsonify(resultado)


@app.route("/transferencias/<int:id>", methods=["DELETE"])
def eliminar_transferencia(id):
    conn = get_db_connection()

    cursor = conn.cursor()
    cursor.execute("DELETE FROM transferencias WHERE id = %s", (id,))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"mensaje": "Transferencia eliminada"})


@app.route("/resumen", methods=["GET"])
def obtener_resumen():
    conn = get_db_connection()
    cursor = conn.cursor()

    hoy = datetime.now()
    mes_actual = hoy.strftime("%Y-%m")

    # TOTAL DEL MES
    cursor.execute(
        """
        SELECT COALESCE(SUM(monto), 0)
        FROM transferencias
        WHERE TO_CHAR(fecha, 'YYYY-MM') = %s
        """,
        (mes_actual,)
    )
    total = cursor.fetchone()[0]

    # OBJETIVO
    cursor.execute("SELECT objetivo_total FROM config LIMIT 1")
    objetivo_row = cursor.fetchone()

    objetivo = objetivo_row[0] if objetivo_row else 0

    restante = objetivo - total

    cursor.close()
    conn.close()

    return jsonify({
        "total": total,
        "objetivo": objetivo,
        "restante": restante
    })


@app.route("/objetivo", methods=["POST"])
def guardar_objetivo():
    try:
        data = request.get_json()
        objetivo = data.get("objetivo")

        if not objetivo or objetivo <= 0:
            return jsonify({"error": "Objetivo inválido"}), 400

        conn = get_db_connection()

        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM config")
            cursor.execute(
                "INSERT INTO config (objetivo_total) VALUES (%s)",
                (objetivo,)
            )

        conn.commit()
        conn.close()

        return jsonify({"mensaje": "Objetivo guardado"})

    except Exception as e:
        print("ERROR OBJETIVO:", e)
        return jsonify({"error": "Error interno"}), 500
