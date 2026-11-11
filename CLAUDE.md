# Control de Transferencias

App web Flask para controlar las transferencias mensuales que me envía mi padre y compararlas con un objetivo mensual (1.070 € por persona por defecto, editable desde la app).

## Funcionalidades actuales
- CRUD de transferencias (monto, fecha, descripción); confirmar/desconfirmar. Las confirmadas no se pueden eliminar.
- Una transferencia cuenta para el mes de su fecha salvo que tenga `mes_cuenta` (columna opcional, `AAAA-MM`): así se registran adelantos (recibida en octubre para noviembre). Solo puede ser el mes de la fecha o el siguiente, nunca uno pasado, y solo se guarda si es el siguiente (`logica.validar_mes_cuenta`); la API siempre devuelve el mes efectivo en `mes_cuenta`. En la interfaz se elige entre el mes de la fecha y el siguiente, y se muestra la etiqueta "Adelantada". Al añadir (no al editar), si uno de esos dos meses ya tiene el objetivo cumplido (lo confirmado llega al objetivo), su opción sale desactivada ("· completo") y se elige el otro (`marcarMesesCompletos()` en `static/app.js`, consulta `/resumen`); si los dos están completos, se dejan ambos con un aviso. Es solo una ayuda de la interfaz: la API no lo impide.
- Retiradas del pote: columna `tipo` (`ingreso` por defecto o `retirada`, `logica.validar_tipo`). Una retirada es dinero que se coge de lo recaudado (p. ej. un regalo): el monto se guarda positivo y resta del mes. Sigue el mismo flujo que una transferencia (pendiente → confirmada) y usa el mismo selector de mes, ahora "Del pote de" (así resta del pote que se está llenando). En el formulario de alta se elige "Recibida / Retirada del pote" (vuelve a "Recibida" tras añadir); en la edición, con un `<select>`. En el historial se muestra con "−", en rojo (`--retirada`, mismo tono que `--peligro`) y etiqueta "Retirada". `/resumen` devuelve `total_confirmado` y `pendiente` netos (ingresos − retiradas, pueden ser negativos) y `retirado` (retiradas confirmadas); la cifra "Retirado" solo aparece si es mayor que 0.
- Filtro por mes (por defecto, el actual): la lista y el resumen usan siempre el mismo mes. Si se ve otro mes, aparece el enlace "Volver a <mes actual>" (`#btn-mes-actual`, clase `.enlace`); en el mes actual está oculto. El formulario de alta propone una fecha del mes que se ve (hoy o, en otro mes, el día 1) y su título nombra a la persona; en móvil empieza plegado y se pliega tras añadir. Tras una acción, la lista se actualiza sin esqueleto (`recargar({ silenciosa: true })`). Totales del mes: confirmado, pendiente, objetivo, restante y barra de progreso. La barra cambia de color por tramos fijos del % confirmado (rojo <33 %, naranja 33–66 %, azul 66–99 %, verde cumplido) con una etiqueta de texto; los tramos están en `TRAMOS` de `static/app.js` y los colores en las variables `--tramo-*` de `styles.css`.
- Objetivo mensual editable por persona (`POST /objetivo`, tabla `config`).
- Login con un único PIN compartido (`APP_PIN`, obligatorio en producción) y sesión de Flask (30 días). Máximo 5 PIN incorrectos cada 15 minutos por IP (`seguridad.limitador_login`, en memoria). Las personas no son usuarios con login propio: se eligen en un selector y filtran los datos.
- Gestión de personas desde la app (botón "Personas" de la cabecera, que abre una ventana modal `<dialog>`): añadir, renombrar (también cambia el nombre en sus transferencias) y eliminar. Solo se elimina a quien no tiene transferencias y nunca a la última. El selector se construye con `GET /personas`; Carlos y Pito son solo los datos iniciales (`db.PERSONAS_INICIALES`) de una BD vacía.
- Tarjeta "Desglose de gastos" (debajo del historial): leyenda fija en `templates/index.html` con Universidad (2829 €), Alquiler y manutención (1200 €) y el total. Los importes se cambian a mano en el HTML; no usa BD ni JS.
- Todo se guarda, se muestra y se edita en euros. No hay conversión de divisas ni selector de moneda.

## Estructura
- `app.py`: crea la app (`crear_app()`), registra las rutas y convierte los errores en JSON. Gunicorn usa `app:app`.
- `rutas.py`: Blueprint con las rutas; solo leen la petición, llaman a `logica`/`db` y responden.
- `logica.py`: validaciones y cálculos (`calcular_resumen`). Sin Flask ni BD. Errores de negocio (`DatosInvalidos` 400, `NoEncontrada` 404, `Conflicto` 409).
- `seguridad.py`: detección de producción (`RENDER=true` o `APP_ENV=produccion`), PIN, límite de intentos y cabeceras (CSP, HSTS, nosniff…). `app.py` además rechaza peticiones que modifican datos desde otro `Origin` y en producción usa `ProxyFix` para ver la IP real.
- `db.py`: conexión (`conexion()` hace commit/rollback y siempre cierra), creación de tablas y todas las consultas SQL.
- `migraciones/`: scripts de cambio de esquema para PostgreSQL, que se ejecutan a mano (`comprobar`/`aplicar`/`revertir`). Nunca se ejecutan al desplegar.
- `tests/`: pytest (`python -m pytest`). Usan SQLite temporal y nunca `DATABASE_URL`; con `TEST_DATABASE_URL` (nombre de BD con "test") se prueban contra PostgreSQL.
- `templates/index.html`: estructura de la interfaz (sin JS en línea ni `onclick`; usa `<template>` para las filas del historial y el formulario de edición).
- `static/app.js`: comportamiento de la interfaz (`api()` centraliza las llamadas `fetch` y vuelve al login si la sesión caduca). Los textos se insertan con `textContent`, nunca con `innerHTML`.
- `static/manifest.json` e `static/iconos/`: hacen la app instalable en el móvil (icono y pantalla completa). Sin service worker: no funciona sin conexión.
- Fechas en DD/MM/AAAA: los campos `type="date"` van dentro de `.caja-fecha`, con el texto pintado por `pintarFecha()` y el campo nativo invisible encima (el formato nativo depende del idioma del dispositivo). El selector de mes usa la misma técnica (`.caja-mes`).
- `static/styles.css`: estilos mobile first, variables en `:root` (colores, escala de texto `--texto-*`, iconos `--ico-*`), espaciado en múltiplos de .25rem y modo oscuro con `prefers-color-scheme`.
- `backup.py`: copia de seguridad local con `pg_dump` (rutas de Windows por defecto, configurables con `BACKUP_DIR`/`PG_DUMP_PATH`), conserva `BACKUP_DIAS` días y no borra nada si el backup falla.
- `Procfile` (`web: gunicorn app:app`), `runtime.txt` (python-3.11.9), `requirements.txt` (producción, UTF-8), `requirements-dev.txt` (añade pytest), `.env.example`.

Rutas: `/`, `/login`, `/check-auth`, `/logout`, `/transferencias` (GET con `persona` y `mes` / POST), `/transferencias/<id>` (PUT/DELETE; no se permiten sobre confirmadas → 409), `/transferencias/<id>/confirmar` (PATCH), `/resumen` (incluye `retirado`), `/objetivo`, `/personas` (GET/POST), `/personas/<id>` (PUT renombra / DELETE; 409 si tiene transferencias o es la última). Todas las de datos usan `@login_required`. En la interfaz los importes se escriben en campos de texto (`inputmode="decimal"`) y `leerImporte()` acepta coma o punto. Los importes viajan en JSON como texto con 2 decimales (`"1070.00"`) y las fechas como `YYYY-MM-DD`.

## Stack
Python 3.11 + Flask, HTML/CSS/JS básico (sin React), SQLite (`database.db`) en desarrollo y PostgreSQL (psycopg 3) en producción, Render + Gunicorn, Git/GitHub.

Variables en `.env` (python-dotenv): `SECRET_KEY` (obligatoria), `DATABASE_URL` (si falta, se usa SQLite), `APP_PIN` (obligatoria en producción; en local, `1234` por defecto), `RENDER` (la pone Render: activa cookies `Secure`, HSTS y `ProxyFix`), `PROXY_SALTOS` (proxies delante de la app, 1 por defecto), `DB_PASSWORD`, `BACKUP_DIR`, `PG_DUMP_PATH`, `BACKUP_DIAS` (solo `backup.py`). Plantilla en `.env.example`.

Las consultas se escriben con `%s` y se ejecutan con `db.ejecutar(conn, query, params)`, que las adapta a `?` en SQLite. Cualquier SQL nuevo debe funcionar en ambos motores (los meses se filtran con `db._FILTRO_MES`: `mes_cuenta` si existe y, si no, `fecha >= inicio AND fecha < fin`). `SQLITE_PATH` cambia la ruta de la BD local.

## Prioridades técnicas
- Arquitectura simple, sin dependencias ni abstracciones innecesarias.
- Código legible; lógica de negocio separada de la presentación; sin duplicación.
- Validar datos en el backend, gestionar errores, consultas parametrizadas.
- Nunca exponer claves ni credenciales.
- La CSP solo permite scripts y estilos propios: nada de JS/CSS en línea ni `onclick` en el HTML, y nada de `innerHTML` con datos.
- Importes con Decimal, nunca float. El código usa Decimal y las tablas nuevas se crean con `NUMERIC(12,2)` y `config.persona` única. Las tablas ya existentes en producción se migran a mano con `migraciones/m001_numeric.py` (ver `migraciones/README.md`); el código funciona con ambos esquemas. Las columnas `mes_cuenta` (`m002_mes_cuenta.py`) y `tipo` (`m003_tipo.py`) sí son obligatorias: hay que añadirlas en producción antes de desplegar el código que las usa.
- Preservar funcionalidades existentes y compatibilidad con Render.

## Cómo trabajar conmigo
- Soy estudiante de Ingeniería Informática (Python, HTML/CSS, JS básico) y quiero aprender, no solo copiar código.
- Analiza antes de proponer; explica brevemente qué cambia y por qué.
- Cambios incrementales, una mejora por rama, sin funcionalidades que no pida.
- No inventes nombres de funciones, rutas o variables que no hayas comprobado.
- No elimines funcionalidades sin consultarme; si falta información, pregunta.
- No propongas reescribir desde cero; mejoras graduales y probadas.
- Estilo profesional, directo y sin tecnicismos sin explicar.

## Conectores MCP (`.mcp.json`)
- Neon (base de datos PostgreSQL) y Render (despliegue), definidos en `.mcp.json`.
- Render necesita la variable de entorno `RENDER_API_KEY` (nunca se guarda en el repo).
- Neon se autoriza con OAuth desde `/mcp`.
