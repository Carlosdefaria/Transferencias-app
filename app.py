import os
import psycopg
from flask import Flask, request, jsonify, render_template, session
import requests
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key")


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
    """
    Convierte un monto entre monedas usando una API externa.
    """

    if de == a:
        return monto

    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{de}"
        response = requests.get(url)
        data = response.json()

        tasa = data["rates"].get(a, 1)
        return monto * tasa

    except Exception as e:
        # fallback: devolver el monto original si falla la API
        print("ERROR CONVERSION:", e)
        return monto


def get_db_connection():
    """
    Crea y devuelve una conexión a PostgreSQL usando DATABASE_URL.

    Maneja el caso típico de Render donde la URL viene como 'postgres://'
    y debe convertirse a 'postgresql://'
    """

    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL no está configurada")

    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql://", 1)

    return psycopg.connect(database_url)


def crear_tablas_postgres():
    """
    Inicializa las tablas necesarias si no existen.

    - transferencias: guarda cada movimiento
    - config: guarda configuración por usuario (ej: objetivo mensual)
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Tabla principal
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

    # Tabla de configuración (objetivo por persona)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config (
            id SERIAL PRIMARY KEY,
            persona TEXT NOT NULL,
            objetivo_total FLOAT
        );
    """)

    # Insert inicial (solo si está vacía)
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


# Se ejecuta al iniciar la app
with app.app_context():
    crear_tablas_postgres()


# ------------------------
# ROUTES
# ------------------------

@app.route("/")
def home():
    """Renderiza el frontend"""
    return render_template("index.html")


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    pin = data.get("pin")

    PIN_CORRECTO = "1234"

    if pin == PIN_CORRECTO:
        session["auth"] = True
        return jsonify({"ok": True})
    else:
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
    """
    Crea una nueva transferencia.

    Valida:
    - monto válido
    - fecha válida
    - persona obligatoria
    """
    data = request.get_json()

    monto = data.get("monto")
    fecha = data.get("fecha")
    descripcion = data.get("descripcion", "")
    persona = data.get("persona")

    if not persona:
        return jsonify({"error": "Falta la persona"}), 400

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
@login_required
def obtener_transferencias():
    """
    Devuelve todas las transferencias de una persona.
    - Ordenadas por fecha descendente
    - Convierte moneda si es necesario
    """

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
        resultado.append({
            "id": fila[0],
            "monto": convertir_moneda(fila[1], "EUR", moneda),
            "fecha": fila[2],
            "descripcion": fila[3],
            "persona": fila[4],
            "confirmada": fila[5]
        })

    return jsonify(resultado)


@app.route("/transferencias/<int:id>", methods=["DELETE"])
@login_required
def eliminar_transferencia(id):
    """
    Elimina una transferencia por ID.
    Devuelve error si no existe.
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM transferencias WHERE id = %s", (id,))

    if cursor.rowcount == 0:
        return jsonify({"error": "No existe"}), 404

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"mensaje": "Transferencia eliminada"})


@app.route("/transferencias/<int:id>/confirmar", methods=["PATCH"])
@login_required
def confirmar_transferencia(id):
    """
    Toggle de estado:
    - confirmada = True / False
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT confirmada FROM transferencias WHERE id = %s",
        (id,)
    )
    resultado = cursor.fetchone()

    if not resultado:
        return jsonify({"error": "No encontrada"}), 404

    nuevo_estado = not resultado[0]

    cursor.execute(
        "UPDATE transferencias SET confirmada = %s WHERE id = %s",
        (nuevo_estado, id)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"confirmada": nuevo_estado})


@app.route("/transferencias/<int:id>", methods=["PUT"])
@login_required
def editar_transferencia(id):
    try:
        data = request.get_json()

        monto = data.get("monto")
        fecha = data.get("fecha")
        descripcion = data.get("descripcion")

        # Validaciones básicas
        if monto is not None:
            try:
                monto = float(monto)
                if monto <= 0:
                    return jsonify({"error": "Monto inválido"}), 400
            except:
                return jsonify({"error": "Monto inválido"}), 400
        if fecha:
            try:
                datetime.strptime(fecha, "%Y-%m-%d")
            except:
                return jsonify({"error": "Fecha inválida"}), 400
        else:
            # Si no viene fecha, mantenemos la actual
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT fecha FROM transferencias WHERE id = %s", (id,))
            fecha_actual = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            fecha = fecha_actual

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE transferencias
            SET monto = %s,
                fecha = %s,
                descripcion = %s
            WHERE id = %s
        """, (monto, fecha, descripcion, id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"mensaje": "Transferencia actualizada"})

    except Exception as e:
        print("ERROR EDITAR:", e)
        return jsonify({"error": "Error interno"}), 500


# ------------------------
# RESUMEN
# ------------------------

@app.route("/resumen", methods=["GET"])
@login_required
def obtener_resumen():
    """
    Calcula:
    - total confirmado
    - pendiente
    - objetivo
    - restante

    Todo filtrado por:
    - persona
    - mes (o mes actual por defecto)
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    persona = request.args.get("persona")
    moneda = request.args.get("moneda", "EUR")
    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    # Total confirmado
    cursor.execute("""
        SELECT COALESCE(SUM(monto), 0)
        FROM transferencias
        WHERE TO_CHAR(fecha, 'YYYY-MM') = %s
        AND persona = %s
        AND confirmada = TRUE
    """, (mes, persona))
    total = cursor.fetchone()[0]

    # Pendiente
    cursor.execute("""
        SELECT COALESCE(SUM(monto), 0)
        FROM transferencias
        WHERE TO_CHAR(fecha, 'YYYY-MM') = %s
        AND persona = %s
        AND confirmada = FALSE
    """, (mes, persona))
    pendiente = cursor.fetchone()[0]

    # Objetivo
    cursor.execute(
        "SELECT objetivo_total FROM config WHERE persona = %s LIMIT 1",
        (persona,)
    )
    objetivo = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return jsonify({
        "total_confirmado": convertir_moneda(total, "EUR", moneda),
        "pendiente": convertir_moneda(pendiente, "EUR", moneda),
        "objetivo": convertir_moneda(objetivo, "EUR", moneda),
        "restante": convertir_moneda(objetivo - total, "EUR", moneda)
    })


@app.route("/objetivo", methods=["POST"])
@login_required
def guardar_objetivo():
    """
    Actualiza el objetivo mensual de una persona.
    """
    data = request.get_json()

    objetivo = data.get("objetivo")
    persona = data.get("persona")

    if not objetivo or objetivo <= 0:
        return jsonify({"error": "Objetivo inválido"}), 400

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


if __name__ == "__main__":
    app.run(debug=True)
