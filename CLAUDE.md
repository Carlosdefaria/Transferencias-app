# Control de Transferencias

App web Flask para controlar las transferencias mensuales que me envía mi padre y compararlas con un objetivo mensual (1.070 € por persona por defecto, editable desde la app).

## Funcionalidades actuales
- CRUD de transferencias (monto, fecha, descripción); confirmar/desconfirmar. Las confirmadas no se pueden eliminar.
- Filtro por mes (por defecto, el actual) con totales del mes: confirmado, pendiente, objetivo, restante y barra de progreso.
- Objetivo mensual editable por persona (`POST /objetivo`, tabla `config`).
- Login con un único PIN compartido (`APP_PIN`) y sesión de Flask. Carlos y Pito no son usuarios con login propio: son "personas" que se eligen en un selector y filtran los datos.
- Visualización en EUR/USD/GBP con ExchangeRate-API (`convertir_moneda` en el backend y también en `index.html`). Los importes se guardan siempre en EUR.

## Estructura
- `app.py`: toda la app (configuración, conexión a BD, creación de tablas, rutas JSON).
- `templates/index.html`: interfaz y JS (llamadas `fetch` a la API).
- `static/styles.css`: estilos.
- `backup.py`: copia de seguridad local con `pg_dump` (rutas de Windows), conserva 7 días.
- `Procfile` (`web: gunicorn app:app`), `runtime.txt` (python-3.11.9), `requirements.txt`.

Rutas: `/`, `/login`, `/check-auth`, `/logout`, `/transferencias` (GET/POST), `/transferencias/<id>` (PUT/DELETE), `/transferencias/<id>/confirmar` (PATCH), `/resumen`, `/objetivo`. Todas las de datos usan `@login_required`.

## Stack
Python 3.11 + Flask, HTML/CSS/JS básico (sin React), SQLite (`database.db`) en desarrollo y PostgreSQL (psycopg 3) en producción, Render + Gunicorn, Git/GitHub.

Variables en `.env` (python-dotenv): `SECRET_KEY` (obligatoria), `DATABASE_URL` (si falta, se usa SQLite), `APP_PIN` (por defecto `1234`), `DB_PASSWORD` (solo `backup.py`).

Las consultas se escriben con `%s` y se ejecutan con `ejecutar()`, que las adapta a `?` en SQLite. Cualquier SQL nuevo debe funcionar en ambos motores.

## Prioridades técnicas
- Arquitectura simple, sin dependencias ni abstracciones innecesarias.
- Código legible; lógica de negocio separada de la presentación; sin duplicación.
- Validar datos en el backend, gestionar errores, consultas parametrizadas.
- Nunca exponer claves ni credenciales.
- Importes con Decimal, nunca float. Ojo: hoy el código usa `float` y columnas `REAL`/`FLOAT`; migrarlo es una mejora pendiente, no el estado actual.
- Preservar funcionalidades existentes y compatibilidad con Render.

## Cómo trabajar conmigo
- Soy estudiante de Ingeniería Informática (Python, HTML/CSS, JS básico) y quiero aprender, no solo copiar código.
- Analiza antes de proponer; explica brevemente qué cambia y por qué.
- Cambios incrementales, una mejora por rama, sin funcionalidades que no pida.
- No inventes nombres de funciones, rutas o variables que no hayas comprobado.
- No elimines funcionalidades sin consultarme; si falta información, pregunta.
- No propongas reescribir desde cero; mejoras graduales y probadas.
- Estilo profesional, directo y sin tecnicismos sin explicar.
