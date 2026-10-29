# Control de Transferencias

App web Flask para controlar las transferencias mensuales que me envía mi padre y compararlas con un objetivo mensual (1.070 € por persona por defecto, editable desde la app).

## Funcionalidades actuales
- CRUD de transferencias (monto, fecha, descripción); confirmar/desconfirmar. Las confirmadas no se pueden eliminar.
- Filtro por mes (por defecto, el actual): la lista y el resumen usan siempre el mismo mes. Totales del mes: confirmado, pendiente, objetivo, restante y barra de progreso.
- Objetivo mensual editable por persona (`POST /objetivo`, tabla `config`).
- Login con un único PIN compartido (`APP_PIN`) y sesión de Flask. Carlos y Pito no son usuarios con login propio: son "personas" que se eligen en un selector y filtran los datos.
- Visualización en EUR/USD/GBP con ExchangeRate-API. Las tasas se piden una vez (base EUR) y se guardan en caché 1 hora (`logica.obtener_tasas`); si la API falla, se muestra en EUR con un aviso. El conversor de la interfaz usa `/convertir`. Los importes se guardan siempre en EUR y se editan en EUR (`monto_eur`).

## Estructura
- `app.py`: crea la app (`crear_app()`), registra las rutas y convierte los errores en JSON. Gunicorn usa `app:app`.
- `rutas.py`: Blueprint con las rutas; solo leen la petición, llaman a `logica`/`db` y responden.
- `logica.py`: validaciones, cálculos (`calcular_resumen`) y divisas. Sin Flask ni BD. Errores de negocio (`DatosInvalidos` 400, `NoEncontrada` 404, `Conflicto` 409, `TasasNoDisponibles` 503).
- `db.py`: conexión (`conexion()` hace commit/rollback y siempre cierra), creación de tablas y todas las consultas SQL.
- `migraciones/`: scripts de cambio de esquema para PostgreSQL, que se ejecutan a mano (`comprobar`/`aplicar`/`revertir`). Nunca se ejecutan al desplegar.
- `tests/`: pytest (`python -m pytest`). Usan SQLite temporal y nunca `DATABASE_URL`; con `TEST_DATABASE_URL` (nombre de BD con "test") se prueban contra PostgreSQL.
- `templates/index.html`: interfaz y JS (llamadas `fetch` a la API).
- `static/styles.css`: estilos.
- `backup.py`: copia de seguridad local con `pg_dump` (rutas de Windows por defecto, configurables con `BACKUP_DIR`/`PG_DUMP_PATH`), conserva `BACKUP_DIAS` días y no borra nada si el backup falla.
- `Procfile` (`web: gunicorn app:app`), `runtime.txt` (python-3.11.9), `requirements.txt` (producción, UTF-8), `requirements-dev.txt` (añade pytest), `.env.example`.

Rutas: `/`, `/login`, `/check-auth`, `/logout`, `/transferencias` (GET con `persona`, `mes`, `moneda` / POST), `/transferencias/<id>` (PUT/DELETE; no se permiten sobre confirmadas → 409), `/transferencias/<id>/confirmar` (PATCH), `/resumen`, `/objetivo`, `/convertir`. Todas las de datos usan `@login_required`. Los importes viajan en JSON como texto con 2 decimales (`"1070.00"`) y las fechas como `YYYY-MM-DD`.

## Stack
Python 3.11 + Flask, HTML/CSS/JS básico (sin React), SQLite (`database.db`) en desarrollo y PostgreSQL (psycopg 3) en producción, Render + Gunicorn, Git/GitHub.

Variables en `.env` (python-dotenv): `SECRET_KEY` (obligatoria), `DATABASE_URL` (si falta, se usa SQLite), `APP_PIN` (por defecto `1234`), `DB_PASSWORD`, `BACKUP_DIR`, `PG_DUMP_PATH`, `BACKUP_DIAS` (solo `backup.py`). Plantilla en `.env.example`.

Las consultas se escriben con `%s` y se ejecutan con `db.ejecutar(conn, query, params)`, que las adapta a `?` en SQLite. Cualquier SQL nuevo debe funcionar en ambos motores (los meses se filtran con `fecha >= inicio AND fecha < fin`). `SQLITE_PATH` cambia la ruta de la BD local.

## Prioridades técnicas
- Arquitectura simple, sin dependencias ni abstracciones innecesarias.
- Código legible; lógica de negocio separada de la presentación; sin duplicación.
- Validar datos en el backend, gestionar errores, consultas parametrizadas.
- Nunca exponer claves ni credenciales.
- Importes con Decimal, nunca float. El código usa Decimal y las tablas nuevas se crean con `NUMERIC(12,2)` y `config.persona` única. Las tablas ya existentes en producción se migran a mano con `migraciones/m001_numeric.py` (ver `migraciones/README.md`); el código funciona con ambos esquemas.
- Preservar funcionalidades existentes y compatibilidad con Render.

## Cómo trabajar conmigo
- Soy estudiante de Ingeniería Informática (Python, HTML/CSS, JS básico) y quiero aprender, no solo copiar código.
- Analiza antes de proponer; explica brevemente qué cambia y por qué.
- Cambios incrementales, una mejora por rama, sin funcionalidades que no pida.
- No inventes nombres de funciones, rutas o variables que no hayas comprobado.
- No elimines funcionalidades sin consultarme; si falta información, pregunta.
- No propongas reescribir desde cero; mejoras graduales y probadas.
- Estilo profesional, directo y sin tecnicismos sin explicar.
