import os
import psycopg
from flask import Flask, request, jsonify, render_template, session
import requests
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
import sqlite3

load_dotenv()

app = Flask(__name__)

secret = os.environ.get("SECRET_KEY")
if not secret:
    raise Exception("SECRET_KEY no configurada")

app.secret_key = secret


# ------------------------
# UTILIDADES
# ------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("auth"):
            return jsonify({"error": "No autorizado"}), 401
        return f(*args, **kwargs)
    return decorated_function


def convertir_moneda(monto, de="EUR", a="EUR"):
    if de == a:
        return monto

    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{de}"
        response = requests.get(url, timeout=3)
        data = response.json()

        tasa = data["rates"].get(a, 1)
        return monto * tasa

    except Exception as e:
        print("ERROR CONVERSION:", e)
        return monto


def es_sqlite(conn):
    return isinstance(conn, sqlite3.Connection)


def ejecutar(conn, cursor, query, params=()):
    if es_sqlite(conn):
        query = query.replace("%s", "?")
    cursor.execute(query, params)


def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace(
                "postgres://", "postgresql://", 1)
        return psycopg.connect(database_url)

    print("⚠️ Usando SQLite en local")
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def crear_tablas():
    conn = get_db_connection()
    cur = conn.cursor()

    if es_sqlite(conn):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transferencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monto REAL NOT NULL,
                fecha TEXT NOT NULL,
                descripcion TEXT,
                persona TEXT NOT NULL,
                confirmada BOOLEAN DEFAULT 0
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                persona TEXT NOT NULL,
                objetivo_total REAL
            );
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transferencias (
                id SERIAL PRIMARY KEY,
                monto FLOAT NOT NULL,
                fecha DATE NOT NULL,
                descripcion TEXT,
                persona TEXT NOT NULL,
                confirmada BOOLEAN DEFAULT FALSE
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS config (
                id SERIAL PRIMARY KEY,
                persona TEXT NOT NULL,
                objetivo_total FLOAT
            );
        """)

    cur.execute("SELECT COUNT(*) FROM config")
    count = cur.fetchone()[0]

    if count == 0:
        ejecutar(conn, cur,
                 "INSERT INTO config (persona, objetivo_total) VALUES (%s, %s)",
                 ("Carlos", 1070))
        ejecutar(conn, cur,
                 "INSERT INTO config (persona, objetivo_total) VALUES (%s, %s)",
                 ("Pito", 1070))

    conn.commit()
    cur.close()
    conn.close()


with app.app_context():
    crear_tablas()


# ------------------------
# ROUTES
# ------------------------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    pin = data.get("pin")

    PIN_CORRECTO = os.environ.get("APP_PIN", "1234")

    if pin == PIN_CORRECTO:
        session["auth"] = True
        return jsonify({"ok": True})

    return jsonify({"ok": False}), 401


@app.route("/check-auth", methods=["GET"])
def check_auth():
    if session.get("auth"):
        return jsonify({"auth": True})
    return jsonify({"auth": False}), 401


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


# ------------------------
# TRANSFERENCIAS
# ------------------------

@app.route("/transferencias", methods=["POST"])
@login_required
def crear_transferencia():
    data = request.get_json()

    monto = data.get("monto")
    fecha = data.get("fecha")
    descripcion = data.get("descripcion", "")
    persona = data.get("persona")

    if not persona:
        return jsonify({"error": "Falta la persona"}), 400

    try:
        monto = float(monto)
        if monto <= 0:
            return jsonify({"error": "Monto inválido"}), 400
    except:
        return jsonify({"error": "Monto inválido"}), 400

    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except:
        return jsonify({"error": "Fecha inválida"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    ejecutar(conn, cursor,
             "INSERT INTO transferencias (monto, fecha, descripcion, persona) VALUES (%s, %s, %s, %s)",
             (monto, fecha, descripcion, persona))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"mensaje": "Transferencia creada"})


@app.route("/transferencias/<int:id>/confirmar", methods=["PATCH"])
@login_required
def confirmar_transferencia(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    ejecutar(conn, cursor,
             "SELECT confirmada FROM transferencias WHERE id = %s",
             (id,))
    resultado = cursor.fetchone()

    if not resultado:
        return jsonify({"error": "No encontrada"}), 404

    estado_actual = bool(resultado[0])

    if es_sqlite(conn):
        nuevo_estado = 0 if estado_actual else 1
    else:
        nuevo_estado = not estado_actual

    ejecutar(conn, cursor,
             "UPDATE transferencias SET confirmada = %s WHERE id = %s",
             (nuevo_estado, id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"confirmada": bool(nuevo_estado)})


@app.route("/transferencias/<int:id>", methods=["PUT"])
@login_required
def editar_transferencia(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    data = request.get_json()

    monto = data.get("monto")
    fecha = data.get("fecha")
    descripcion = data.get("descripcion", "")

    if monto is None or fecha is None:
        return jsonify({"error": "Datos incompletos"}), 400

    try:
        monto = float(monto)
        if monto <= 0:
            return jsonify({"error": "Monto inválido"}), 400
    except:
        return jsonify({"error": "Monto inválido"}), 400

    ejecutar(conn, cursor,
             "UPDATE transferencias SET monto=%s, fecha=%s, descripcion=%s WHERE id=%s",
             (monto, fecha, descripcion, id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"ok": True})


@app.route("/transferencias/<int:id>", methods=["DELETE"])
@login_required
def eliminar_transferencia(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    ejecutar(conn, cursor,
             "SELECT confirmada FROM transferencias WHERE id = %s",
             (id,))
    resultado = cursor.fetchone()

    if not resultado:
        return jsonify({"error": "No existe"}), 404

    if resultado[0]:
        return jsonify({"error": "No se puede eliminar confirmada"}), 400

    ejecutar(conn, cursor,
             "DELETE FROM transferencias WHERE id = %s",
             (id,))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"mensaje": "ok"})


@app.route("/resumen", methods=["GET"])
@login_required
def obtener_resumen():
    conn = get_db_connection()
    cursor = conn.cursor()

    persona = request.args.get("persona")
    moneda = request.args.get("moneda", "EUR")
    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    if not persona:
        return jsonify({"error": "Falta persona"}), 400

    if es_sqlite(conn):
        filtro = "substr(fecha,1,7) = %s"
        confirmada_true = 1
        confirmada_false = 0
    else:
        filtro = "TO_CHAR(fecha,'YYYY-MM') = %s"
        confirmada_true = True
        confirmada_false = False

    ejecutar(conn, cursor, f"""
        SELECT COALESCE(SUM(monto),0)
        FROM transferencias
        WHERE {filtro}
        AND persona = %s
        AND confirmada = %s
    """, (mes, persona, confirmada_true))

    total = cursor.fetchone()[0]

    ejecutar(conn, cursor, f"""
        SELECT COALESCE(SUM(monto),0)
        FROM transferencias
        WHERE {filtro}
        AND persona = %s
        AND confirmada = %s
    """, (mes, persona, confirmada_false))

    pendiente = cursor.fetchone()[0]

    ejecutar(conn, cursor,
             "SELECT objetivo_total FROM config WHERE persona = %s LIMIT 1",
             (persona,))
    row = cursor.fetchone()
    objetivo = row[0] if row else 0

    restante = objetivo - total

    cursor.close()
    conn.close()

    return jsonify({
        "total_confirmado": convertir_moneda(total, "EUR", moneda),
        "pendiente": convertir_moneda(pendiente, "EUR", moneda),
        "objetivo": convertir_moneda(objetivo, "EUR", moneda),
        "restante": convertir_moneda(restante, "EUR", moneda)
    })


@app.route("/transferencias", methods=["GET"])
@login_required
def obtener_transferencias():
    conn = get_db_connection()
    cursor = conn.cursor()

    persona = request.args.get("persona")
    moneda = request.args.get("moneda", "EUR")

    if not persona:
        return jsonify({"error": "Falta persona"}), 400

    ejecutar(conn, cursor, """
        SELECT id, monto, fecha, descripcion, persona, confirmada
        FROM transferencias
        WHERE persona = %s
        ORDER BY fecha DESC, id DESC
    """, (persona,))

    filas = cursor.fetchall()

    cursor.close()
    conn.close()

    resultado = []

    for fila in filas:
        resultado.append({
            "id": fila[0],
            "monto": convertir_moneda(fila[1], "EUR", moneda),
            "fecha": fila[2],
            "descripcion": fila[3],
            "persona": fila[4],
            "confirmada": fila[5]
        })

    return jsonify(resultado)


@app.route("/objetivo", methods=["POST"])
@login_required
def guardar_objetivo():
    data = request.get_json()

    objetivo = data.get("objetivo")
    persona = data.get("persona")

    try:
        objetivo = float(objetivo)
        if objetivo <= 0:
            return jsonify({"error": "Objetivo inválido"}), 400
    except:
        return jsonify({"error": "Objetivo inválido"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    ejecutar(conn, cursor,
             "UPDATE config SET objetivo_total = %s WHERE persona = %s",
             (objetivo, persona))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"mensaje": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
