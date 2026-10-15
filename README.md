# Terminal Rescue — Osmar y Miguel

## Descripción

Sistema de cierre mensual de afiliados de una Caja de Compensación Familiar, rescatado desde un entorno averiado. Genera para el área de Subsidios el archivo de afiliados activos, reporta las excepciones de calidad de datos que exige Auditoría, concilia los totales con la hoja de control de Operaciones y expone una API para consultar un afiliado por su documento. El cierre es repetible: puede ejecutarse varias veces seguidas y después de un reinicio completo del entorno.

## Integrantes

- Osmar Carrillo
- Miguel Marquez

## Requisitos

- Linux (o WSL2) con Docker Engine y el plugin Docker Compose v2.
- Python 3.8 o superior (el cierre y el validador).
- Git y curl; opcionalmente `jq` y `psql` para inspeccionar la base.
- Puerto 8081 libre en el equipo (configurable con `API_PORT`).

## Instalación y ejecución

Desde una copia limpia del repositorio, en este orden:

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
./run.sh
```

`docker compose up -d --build` construye y levanta la base, la API y el worker; la base se carga sola desde `data/` y se limpia con `db/init/03_limpieza.sql`. `./run.sh` genera los archivos en `output/`. Para volver al estado inicial: `./reset.sh`.

## Configuración

Las variables viven en `.env` (que no se versiona); `.env.example` trae la plantilla con valores de ejemplo.

- `POSTGRES_DB`: nombre de la base que crea el contenedor `cierre-db`. Ejemplo: `cierre`.
- `POSTGRES_USER`: usuario administrador de la base. Ejemplo: `cierre`.
- `POSTGRES_PASSWORD`: clave de ese usuario; debe coincidir con `DATABASE_PASSWORD`. Ejemplo: `cambiar-clave-local`.
- `DATABASE_HOST`: host de la base visto desde la API y el worker; es el nombre del servicio del compose. Ejemplo: `cierre-db`.
- `DATABASE_PORT`: puerto de PostgreSQL dentro de la red de Docker. Ejemplo: `5432`.
- `DATABASE_NAME`: base a la que se conectan la API y el worker. Ejemplo: `cierre`.
- `DATABASE_USER`: usuario de conexión de la API y el worker. Ejemplo: `cierre`.
- `DATABASE_PASSWORD`: clave de conexión de la API y el worker. Ejemplo: `cambiar-clave-local`.
- `API_PORT`: puerto del equipo donde se publica la API. Ejemplo: `8081`.
- `WORKER_INTERVAL_SECONDS`: cada cuántos segundos concilia el worker; debe ser un entero, sin sufijo. Ejemplo: `30`.

## Arquitectura

El sistema tiene tres servicios definidos en `docker-compose.yml`. `cierre-db` es PostgreSQL 16 y carga los CSV de `data/` al iniciar. `cierre-api` es un servicio HTTP en Python que consulta la base por el nombre de servicio `cierre-db` y atiende `/afiliados/{documento}`. `cierre-worker` es un proceso en Python que, cada cierto intervalo, concilia el conteo de afiliados contra la misma base. El cierre mensual (`run.sh` y `scripts/cierre.py`) corre en el equipo anfitrión: lee `data/` y `logs/` y escribe `output/`.

## Uso

Consultar un afiliado con `GET /afiliados/{documento}` (devuelve 200 con `documento`, `nombre`, `estado` y `empresa`, o 404 si no existe):

```bash
curl -s http://localhost:8081/afiliados/3756530718
```

`./run.sh` genera en `output/`:

- `afiliados_activos.csv`: `documento,nombre,estado,cod_empresa,empresa,beneficiarios,ultimo_aporte`.
- `excepciones.csv`: `documento,tipo,detalle` con los tipos DUPLICADO, SIN_EMPRESA, BENEFICIARIO_HUERFANO, CODIGO_INVALIDO, FECHA_INVALIDA y CRUCE_NO_COINCIDE.
- `totales.txt`: `total_afiliados`, `activos`, `inactivos` y `excepciones` en formato `clave=valor`.
- `top_error.txt`: `codigo_error` y `ocurrencias` del error más frecuente de los logs.

## Pruebas

Con el entorno levantado, ejecutar `./validator check`: debe mostrar las diez pruebas T01 a T10 en PASS. Para revisar los documentos, el historial Git y la evidencia sin Docker, ejecutar `./validator entregables`. Para comprobar la repetibilidad, correr `./run.sh` dos veces y comparar con `md5sum output/*`: las sumas deben ser idénticas, también después de `./reset.sh`.

## Documentación

- [incident-report.md](incident-report.md): los diez incidentes con síntoma, diagnóstico, comandos, solución y evidencia.
- [evidence/](evidence/): salida de terminal que demuestra cada incidente.
- [AI_USAGE.md](AI_USAGE.md): usos de inteligencia artificial y qué corrigió el equipo.

## Qué resolvimos

Corregimos la configuración (`WORKER_INTERVAL_SECONDS` con sufijo y `DATABASE_HOST` apuntando a un servicio inexistente), arreglamos la API (nombres NULL, empresa inexistente y estados inválidos provocaban 500) y reescribimos el cierre heredado: ahora lee `data/`, aplica las reglas del diccionario, reporta las excepciones, cuadra con la hoja de control (1500 afiliados, 1194 activos, 274 inactivos), identifica `CIE-4012` como error más frecuente y es repetible. La base elimina duplicados al iniciar.

## Limitaciones y pendientes

El cierre lee los CSV de `data/` y no consulta la base de datos directamente. Los logs de `logs/` son una foto estática de la noche del incidente; el worker solo concilia conteos y no corrige datos. Falta automatizar la ejecución mensual del cierre.
