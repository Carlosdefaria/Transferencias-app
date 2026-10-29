# Migraciones de base de datos

Las tablas nuevas ya se crean con el esquema bueno (`db.crear_tablas`), pero
`CREATE TABLE IF NOT EXISTS` **no modifica tablas que ya existen**. Por eso la
base de datos de producción necesita este script, que se ejecuta **a mano**
y **una sola vez**.

> Nada de esto se ejecuta solo al desplegar. Si no lo aplicas, la app sigue
> funcionando igual con las columnas FLOAT.

## 001 — Importes a NUMERIC(12,2) (`m001_numeric.py`)

**Qué hace**

| Tabla | Antes | Después |
|---|---|---|
| `transferencias.monto` | `FLOAT` | `NUMERIC(12,2)` (redondeado a céntimos) |
| `config.objetivo_total` | `FLOAT` | `NUMERIC(12,2)` |
| `config.persona` | sin restricción | `UNIQUE` (una fila por persona) |

**Por qué:** `FLOAT` guarda aproximaciones binarias (0,1 se guarda como
0,1000000000000000055…). `NUMERIC(12,2)` guarda exactamente los céntimos.

**Seguridad del script**

- `comprobar` solo lee: muestra tipos, filas, sumas e importes con más de 2 decimales.
- `aplicar` se niega si hay problemas (personas repetidas, ya aplicada…) y pide
  escribir el nombre de la base de datos.
- Todo va en **una transacción**: si cualquier paso falla, no cambia nada.
- Compara número de filas y sumas (en céntimos) antes y después; si no
  coinciden, aborta.
- `revertir` deshace los cambios (vuelve a `DOUBLE PRECISION`, que es lo mismo
  que `FLOAT` en PostgreSQL).

## Pasos recomendados (cuando decidas hacerlo)

1. **Haz un backup**: `python backup.py` y comprueba que el `.sql` no está vacío.
2. Despliega primero el código (funciona con FLOAT y con NUMERIC).
3. Desde tu ordenador, con la URL **externa** de la BD de Render:

   ```bash
   python -m migraciones.m001_numeric comprobar --url "postgresql://..."
   ```

4. Si no hay problemas:

   ```bash
   python -m migraciones.m001_numeric aplicar --url "postgresql://..."
   ```

5. Abre la app y comprueba que los totales del mes son los mismos de antes.
6. Si algo va mal:

   ```bash
   python -m migraciones.m001_numeric revertir --url "postgresql://..."
   ```

El cambio de tipo bloquea las tablas durante un instante (con pocas filas,
milisegundos), así que conviene hacerlo cuando nadie esté usando la app.

## SQLite (local)

SQLite no permite cambiar el tipo de una columna, pero tampoco hace falta:
trata `REAL` y `NUMERIC` de forma muy parecida y el código ya trabaja con
`Decimal`. Si quieres el esquema nuevo en local, borra `database.db` y se
creará de nuevo al arrancar (perderás los datos de prueba).

## Probar el script sin tocar producción

`tests/test_migracion.py` crea el esquema antiguo en un PostgreSQL de pruebas,
aplica y revierte la migración:

```bash
TEST_DATABASE_URL=postgresql://usuario:clave@localhost/transferencias_test python -m pytest
```

## 002 — Mes para el que cuenta una transferencia (`m002_mes_cuenta.py`)

**Qué hace:** añade a `transferencias` la columna opcional `mes_cuenta`
(texto `AAAA-MM`). Si está vacía, la transferencia cuenta para el mes de su
fecha, como siempre; si tiene un mes, cuenta para ese mes (transferencias
adelantadas o atrasadas). **No cambia ningún dato existente.**

**Hay que aplicarla antes de desplegar el código que la usa**: ese código
lee la columna y fallaría si no existe.

**Opción fácil — editor SQL de Neon:** en la consola de Neon, *SQL Editor*,
pega y ejecuta:

```sql
ALTER TABLE transferencias ADD COLUMN mes_cuenta TEXT;
```

Para deshacerla (las transferencias adelantadas volverían a contar por su fecha):

```sql
ALTER TABLE transferencias DROP COLUMN mes_cuenta;
```

**Opción con el script:**

```bash
python -m migraciones.m002_mes_cuenta comprobar --url "postgresql://..."
python -m migraciones.m002_mes_cuenta aplicar --url "postgresql://..."
```

En SQLite (local) no hace falta nada si borras `database.db`; si quieres
conservarla, ejecuta el mismo `ALTER TABLE ... ADD COLUMN` con cualquier
cliente de SQLite.
