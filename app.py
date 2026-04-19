import sqlite3
import os
import psycopg
from flask import Flask, request, jsonify, render_template
import requests
from datetime import datetime


app = Flask(__name__)


def convertir_moneda(monto, de="EUR", a="EUR"):
    if de == a:
        return monto

    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{de}"
        response = requests.get(url)
        data = response.json()

        tasa = data["rates"].get(a, 1)
        return monto * tasa

    except:
        return monto  # fallback


def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL no está configurada")

    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql://", 1)

    return psycopg.connect(database_url)


def crear_tablas_postgres():
    conn = get_db_connection()
    cur = conn.cursor()

    # Tabla transferencias
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
# ROUTES
# ------------------------


@app.route("/")
def home():
    return render_template("index.html")

# 👉 CREAR TRANSFERENCIA


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    pin = data.get("pin")

    PIN_CORRECTO = "1234"  # luego esto lo puedes mover a variable de entorno

    if pin == PIN_CORRECTO:
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False}), 401


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
    moneda = request.args.get("moneda", "EUR")

    if not persona:
        return jsonify({"error": "Falta persona"}), 400

    cursor.execute("""
        SELECT id, monto, fecha, descripcion, persona, confirmada
        FROM transferencias
        WHERE persona = %s
        ORDER BY fecha DESC
    """, (persona,))

    filas = cursor.fetchall()

    cursor.close()
    conn.close()

    resultado = []

    for fila in filas:
        monto_convertido = convertir_moneda(fila[1], "EUR", moneda)

        resultado.append({
            "id": fila[0],
            "monto": monto_convertido,
            "fecha": fila[2],
            "descripcion": fila[3],
            "persona": fila[4],
            "confirmada": fila[5]
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


@app.route("/transferencias/<int:id>/confirmar", methods=["PATCH"])
def confirmar_transferencia(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener estado actual
    cursor.execute(
        "SELECT confirmada FROM transferencias WHERE id = %s",
        (id,)
    )
    resultado = cursor.fetchone()

    if not resultado:
        return jsonify({"error": "Transferencia no encontrada"}), 404

    estado_actual = resultado[0]

    # Toggle (cambiar true/false)
    nuevo_estado = not estado_actual

    cursor.execute(
        "UPDATE transferencias SET confirmada = %s WHERE id = %s",
        (nuevo_estado, id)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "mensaje": "Estado actualizado",
        "confirmada": nuevo_estado
    })


@app.route("/resumen", methods=["GET"])
def obtener_resumen():
    conn = get_db_connection()
    cursor = conn.cursor()

    mes = request.args.get("mes")
    persona = request.args.get("persona")
    moneda = request.args.get("moneda", "EUR")

    if not persona:
        return jsonify({"error": "Falta persona"}), 400

    if mes:
        mes_a_usar = mes
    else:
        hoy = datetime.now()
        mes_a_usar = hoy.strftime("%Y-%m")

    # ✅ CONFIRMADO
    cursor.execute("""
        SELECT COALESCE(SUM(monto), 0)
        FROM transferencias
        WHERE TO_CHAR(fecha, 'YYYY-MM') = %s
        AND persona = %s
        AND confirmada = TRUE
    """, (mes_a_usar, persona))
    total_confirmado = cursor.fetchone()[0]

    # ✅ PENDIENTE
    cursor.execute("""
        SELECT COALESCE(SUM(monto), 0)
        FROM transferencias
        WHERE TO_CHAR(fecha, 'YYYY-MM') = %s
        AND persona = %s
        AND confirmada = FALSE
    """, (mes_a_usar, persona))
    pendiente = cursor.fetchone()[0]

    # OBJETIVO
    cursor.execute(
        "SELECT objetivo_total FROM config WHERE persona = %s LIMIT 1",
        (persona,)
    )
    objetivo_row = cursor.fetchone()
    objetivo = objetivo_row[0] if objetivo_row else 0

    restante = objetivo - total_confirmado

    cursor.close()
    conn.close()

    total_confirmado = convertir_moneda(total_confirmado, "EUR", moneda)
    objetivo = convertir_moneda(objetivo, "EUR", moneda)
    restante = convertir_moneda(restante, "EUR", moneda)
    pendiente = convertir_moneda(pendiente, "EUR", moneda)

    return jsonify({
        "total_confirmado": total_confirmado,
        "pendiente": pendiente,
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


if __name__ == "__main__":
    app.run(debug=True)
