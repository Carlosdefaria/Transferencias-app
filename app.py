import sqlite3
from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

# ------------------------
# DB CONNECTION
# ------------------------


def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

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
    descripcion = data.get("descripcion")

    if not monto or not fecha:
        return jsonify({"error": "Faltan datos"}), 400

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO transferencias (monto, fecha, descripcion) VALUES (?, ?, ?)",
        (monto, fecha, descripcion)
    )
    conn.commit()
    conn.close()

    return jsonify({"mensaje": "Transferencia creada"})


@app.route("/transferencias", methods=["GET"])
def obtener_transferencias():
    conn = get_db_connection()
    transferencias = conn.execute("SELECT * FROM transferencias").fetchall()
    conn.close()

    resultado = []

    for t in transferencias:
        resultado.append({
            "id": t["id"],
            "monto": t["monto"],
            "fecha": t["fecha"],
            "descripcion": t["descripcion"]
        })

    return jsonify(resultado)


@app.route("/transferencias/<int:id>", methods=["DELETE"])
def eliminar_transferencia(id):
    conn = get_db_connection()

    conn.execute("DELETE FROM transferencias WHERE id = ?", (id,))

    conn.commit()
    conn.close()

    return jsonify({"mensaje": "Transferencia eliminada"})


@app.route("/resumen", methods=["GET"])
def obtener_resumen():
    conn = get_db_connection()

    from datetime import datetime

    hoy = datetime.now()
    mes_actual = hoy.strftime("%Y-%m")

    total = conn.execute(
        "SELECT SUM(monto) as total FROM transferencias WHERE fecha LIKE ?",
        (f"{mes_actual}%",)
    ).fetchone()

    # objetivo
    objetivo = conn.execute(
        "SELECT objetivo_total FROM config LIMIT 1"
    ).fetchone()

    conn.close()

    total_valor = total["total"] if total["total"] else 0
    objetivo_valor = objetivo["objetivo_total"] if objetivo else 0

    restante = objetivo_valor - total_valor

    return jsonify({
        "total": total_valor,
        "objetivo": objetivo_valor,
        "restante": restante
    })


@app.route("/objetivo", methods=["POST"])
def guardar_objetivo():
    data = request.get_json()
    objetivo = data.get("objetivo")

    if not objetivo:
        return jsonify({"error": "Falta el objetivo"}), 400

    conn = get_db_connection()

    conn.execute("DELETE FROM config")

    conn.execute(
        "INSERT INTO config (objetivo_total) VALUES (?)",
        (objetivo,)
    )

    conn.commit()
    conn.close()

    return jsonify({"mensaje": "Objetivo guardado"})


# ------------------------
# RUN APP
# ------------------------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
