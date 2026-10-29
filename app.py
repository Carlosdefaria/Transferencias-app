"""Punto de entrada. Gunicorn arranca la app con 'gunicorn app:app'."""

import logging
import os
from datetime import timedelta
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

import db
import seguridad
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

    # Falla al arrancar si falta APP_PIN en producción, en vez de quedar
    # abierta con un PIN conocido.
    app.config["APP_PIN"] = seguridad.pin_configurado()

    produccion = seguridad.es_produccion()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,      # el JavaScript no puede leer la cookie
        SESSION_COOKIE_SAMESITE="Lax",     # no se envía en peticiones desde otras webs
        SESSION_COOKIE_SECURE=produccion,  # en producción, solo por HTTPS
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        MAX_CONTENT_LENGTH=16 * 1024,      # rechaza cuerpos de más de 16 KB
    )

    if produccion:
        # Render pone un proxy delante: sin esto, todas las peticiones
        # parecerían venir de la misma IP (la del proxy) y el límite de
        # intentos de login bloquearía a todo el mundo a la vez.
        saltos = int(os.environ.get("PROXY_SALTOS", "1"))
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=saltos, x_proto=saltos)

    @app.before_request
    def comprobar_origen():
        # Protección CSRF: una petición que modifica datos debe venir de
        # esta misma web. Los navegadores añaden la cabecera Origin.
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        origen = request.headers.get("Origin")
        if origen and urlparse(origen).netloc != request.host:
            return jsonify({"error": "Origen no permitido"}), 403
        return None

    app.after_request(seguridad.anadir_cabeceras)

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
