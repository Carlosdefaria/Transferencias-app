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

    # Tabla transferencias (no se toca)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transferencias (
            id SERIAL PRIMARY KEY,
            monto FLOAT NOT NULL,
            fecha DATE NOT NULL,
            descripcion TEXT,
            persona TEXT NOT NULL
        );
    """)

    # ✅ NUEVA TABLA CONFIG (POR PERSONA)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config (
            id SERIAL PRIMARY KEY,
            persona TEXT NOT NULL,
            objetivo_total FLOAT
        );
    """)

    # Insert inicial (2 usuarios)
    cur.execute("SELECT COUNT(*) FROM config")
    count = cur.fetchone()[0]

    if count == 0:
        cur.execute(
            "INSERT INTO config (persona, objetivo_total) VALUES (%s, %s)",
            ("Carlos", 1070)
        )
        cur.execute(
            "INSERT INTO config (persona, objetivo_total) VALUES (%s, %s)",
            ("Pito", 1070)
        )

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
    persona = data.get("persona")

    # Validaciones

    if not persona:
        return jsonify({"error": "Falta la persona"}), 400

    try:
        monto = float(monto)
    except:
        return jsonify({"error": "Monto inválido"}), 400

    if monto <= 0:
        return jsonify({"error": "El monto debe ser mayor a 0"}), 400

    try:
        datetime.strptime(fecha, "%Y-%m-%d").date()
    except:
        return jsonify({"error": "Fecha inválida"}), 400

    descripcion = data.get("descripcion")

    if fecha is None:
        return jsonify({"error": "Faltan datos"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO transferencias (monto, fecha, descripcion, persona) VALUES (%s, %s, %s, %s)",
        (monto, fecha, descripcion, persona)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"mensaje": "Transferencia creada"})


@app.route("/transferencias", methods=["GET"])
def obtener_transferencias():
    conn = get_db_connection()
    cursor = conn.cursor()

    persona = request.args.get("persona")

    if not persona:
        return jsonify({"error": "Falta persona"}), 400

    cursor.execute("""
        SELECT id, monto, fecha, descripcion, persona
        FROM transferencias
        WHERE persona = %s
        ORDER BY fecha DESC
    """, (persona,))

    filas = cursor.fetchall()

    cursor.close()
    conn.close()

    resultado = []

    for fila in filas:
        resultado.append({
            "id": fila[0],
            "monto": fila[1],
            "fecha": fila[2],
            "descripcion": fila[3],
            "persona": fila[4]
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

    mes = request.args.get("mes")
    persona = request.args.get("persona")

    # 👉 Validación básica
    if not persona:
        return jsonify({"error": "Falta persona"}), 400

    # Mes dinámico
    if mes:
        mes_a_usar = mes
    else:
        hoy = datetime.now()
        mes_a_usar = hoy.strftime("%Y-%m")

    # 👉 TOTAL FILTRADO POR PERSONA
    cursor.execute(
        """
        SELECT COALESCE(SUM(monto), 0)
        FROM transferencias
        WHERE TO_CHAR(fecha, 'YYYY-MM') = %s
        AND persona = %s
        """,
        (mes_a_usar, persona)
    )
    total = cursor.fetchone()[0]

    # OBJETIVO (de momento global)
    cursor.execute(
        "SELECT objetivo_total FROM config WHERE persona = %s LIMIT 1",
        (persona,)
    )
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
        persona = data.get("persona")

        if not objetivo or objetivo <= 0:
            return jsonify({"error": "Objetivo inválido"}), 400

        if not persona:
            return jsonify({"error": "Falta persona"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE config SET objetivo_total = %s WHERE persona = %s",
            (objetivo, persona)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"mensaje": "Objetivo guardado"})

    except Exception as e:
        print("ERROR OBJETIVO:", e)
        return jsonify({"error": "Error interno"}), 500
