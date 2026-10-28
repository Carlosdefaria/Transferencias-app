"""Medidas de seguridad: entorno, límite de intentos de login y cabeceras HTTP."""

import os
import threading
import time

# Render define RENDER=true en todos sus servicios. APP_ENV=produccion
# permite activar el modo producción en otro sitio.
def es_produccion():
    return os.environ.get("RENDER") == "true" or os.environ.get("APP_ENV") == "produccion"


def pin_configurado():
    """PIN de acceso. En producción es obligatorio definir APP_PIN."""
    pin = os.environ.get("APP_PIN")
    if pin:
        return pin
    if es_produccion():
        raise RuntimeError("APP_PIN no configurado: es obligatorio en producción")
    return "1234"  # solo para desarrollo local


class LimitadorIntentos:
    """Bloquea una IP tras demasiados PIN incorrectos seguidos.

    Con un PIN de 4 cifras solo hay 10.000 combinaciones: sin límite, un
    programa las prueba todas en minutos. Con 5 intentos cada 15 minutos
    tardaría semanas.

    Se guarda en memoria: se vacía al reiniciar el servidor y cada worker de
    Gunicorn tiene el suyo. Para esta app (un worker) es suficiente.
    """

    def __init__(self, maximo=5, ventana=15 * 60, reloj=time.monotonic):
        self.maximo = maximo
        self.ventana = ventana
        self.reloj = reloj
        self._fallos = {}  # ip -> lista de momentos de los fallos recientes
        self._candado = threading.Lock()

    def _recientes(self, ip):
        limite = self.reloj() - self.ventana
        fallos = [t for t in self._fallos.get(ip, []) if t > limite]
        if fallos:
            self._fallos[ip] = fallos
        else:
            self._fallos.pop(ip, None)
        return fallos

    def segundos_bloqueo(self, ip):
        """0 si la IP puede intentarlo; si no, segundos hasta que pueda."""
        with self._candado:
            fallos = self._recientes(ip)
            if len(fallos) < self.maximo:
                return 0
            return max(1, int(fallos[0] + self.ventana - self.reloj()) + 1)

    def registrar_fallo(self, ip):
        with self._candado:
            self._recientes(ip)
            self._fallos.setdefault(ip, []).append(self.reloj())

    def reiniciar(self, ip):
        with self._candado:
            self._fallos.pop(ip, None)


limitador_login = LimitadorIntentos()


# Content-Security-Policy: el navegador solo ejecuta scripts y estilos
# servidos por esta misma web. Si alguien consiguiera inyectar HTML, su
# <script> no se ejecutaría.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


def anadir_cabeceras(respuesta):
    respuesta.headers.setdefault("Content-Security-Policy", CSP)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("X-Frame-Options", "DENY")
    respuesta.headers.setdefault("Referrer-Policy", "same-origin")
    if respuesta.mimetype == "application/json":
        # Los datos no se guardan en la caché del navegador (útil en
        # ordenadores compartidos).
        respuesta.headers.setdefault("Cache-Control", "no-store")
    if es_produccion():
        # Obliga al navegador a usar siempre HTTPS con esta web.
        respuesta.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return respuesta
