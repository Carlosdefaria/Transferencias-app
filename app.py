"""Punto de entrada. Gunicorn arranca la app con 'gunicorn app:app'."""

import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

import db
from logica import ErrorNegocio
from rutas import bp

load_dotenv()
logging.basicConfig(level=logging.INFO)


def crear_app():
    app = Flask(__name__)

    secret = os.environ.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY no configurada")
    app.secret_key = secret

    app.register_blueprint(bp)

    # Todas las respuestas de error son JSON con la forma {"error": "..."},
    # que es lo que espera el frontend.
    @app.errorhandler(ErrorNegocio)
    def error_negocio(error):
        return jsonify({"error": str(error)}), error.codigo

    @app.errorhandler(HTTPException)
    def error_http(error):
        return jsonify({"error": error.description}), error.code

    @app.errorhandler(500)
    def error_interno(error):
        # Flask ya ha escrito el detalle en el log; al usuario no se le
        # enseña nada interno.
        return jsonify({"error": "Error interno del servidor"}), 500

    db.crear_tablas()
    return app


app = crear_app()


if __name__ == "__main__":
    app.run(debug=True)
