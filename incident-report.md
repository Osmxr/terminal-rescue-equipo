# Informe de incidentes — Terminal Rescue

## Incidente 1
- **Síntoma:** `docker compose ps` mostraba `cierre-worker  Exited (1)` y en los logs el worker se reiniciaba una y otra vez.
- **Diagnóstico:** el log del worker trae `CIE-1107` (158 veces): WORKER_INTERVAL_SECONDS debe ser un entero y en `.env.example` valía `30s`, que `int()` no acepta y el worker termina con código 1.
- **Comandos:** `docker compose ps`, `docker compose logs cierre-worker | tail -5`, `grep CIE-1107 logs/worker.log`, `grep -n WORKER_INTERVAL .env.example`
- **Solución:** se cambió a WORKER_INTERVAL_SECONDS=30 en `.env.example`, se recreó `.env` y se levantó de nuevo con `docker compose up -d --build`; el worker queda en `running` sin reinicios.
- **Evidencia:** evidence/01-worker.txt

## Incidente 2
- **Síntoma:** la API respondía 503 y en worker y base aparecía `CIE-2210`: sin conexión con la base de datos.
- **Diagnóstico:** `DATABASE_HOST=cierre-database`, pero el servicio del compose se llama `cierre-db`; entre contenedores el host es el nombre del servicio, así que el nombre no resolvía.
- **Comandos:** `docker compose logs cierre-api`, `grep CIE-2210 logs/worker.log`, `grep -n DATABASE_HOST .env.example`, `grep -n '^  cierre-' docker-compose.yml`
- **Solución:** DATABASE_HOST=cierre-db en `.env.example` (y en `.env`); la API y el worker se recrean con `docker compose up -d --build`.
- **Evidencia:** evidence/02-api-base.txt

## Incidente 3
- **Síntoma:** `./run.sh` fallaba: el script heredado no encontraba su archivo de entrada.
- **Diagnóstico:** `scripts/cierre.sh` leía `/opt/cierre/entrada`, una ruta que no existe en el repositorio (los CSV están en `data/`), y además no tenía permisos de ejecución garantizados.
- **Comandos:** `grep -n 'ENTRADA=' scripts/cierre.sh`, `find data -name '*.csv'`, `ls -l run.sh scripts/`, `chmod +x run.sh scripts/cierre.sh scripts/cierre.py`
- **Solución:** el cierre se reescribió en `scripts/cierre.py`, que lee `data/` con ruta relativa a la raíz del repositorio; `chmod +x` a `run.sh` y a los scripts y primera línea `#!`.
- **Evidencia:** evidence/03-script-cierre.txt

## Incidente 4
- **Síntoma:** miles de líneas de error en `logs/api.log`, `logs/worker.log` y `logs/database.log`.
- **Diagnóstico:** se contaron los códigos `CIE-####` de los tres logs con `grep -o`, `sort` y `uniq -c`; el más frecuente es `CIE-4012` (registro de afiliado sin empresa) con 1424 ocurrencias, por delante de `CIE-5003` con 700.
- **Comandos:** `cat logs/*.log | grep -oE 'CIE-[0-9]{4}' | sort | uniq -c | sort -rn`, `grep -c CIE-4012 logs/api.log logs/worker.log`, `wc -l logs/*.log`
- **Solución:** `scripts/cierre.py` cuenta los códigos de los logs y escribe `output/top_error.txt` con `codigo_error=CIE-4012` y `ocurrencias=1424`.
- **Evidencia:** evidence/04-error-frecuente.txt

## Incidente 5
- **Síntoma:** duplicados, afiliados sin empresa, beneficiarios huérfanos y estados inválidos en los datos de origen.
- **Diagnóstico:** 20 documentos repetidos en AFI_MAE, 18 activos con empresa vacía o inexistente, 15 beneficiarios sin afiliado y 14 afiliados con estado distinto de A/I (se verificó con `awk`, `cut`, `sort` y `uniq -d`).
- **Comandos:** `tail -n +2 data/AFI_MAE.csv | cut -d, -f1 | sort | uniq -d | wc -l`, `awk -F, '$8==""' data/AFI_MAE.csv | wc -l`, `docker compose exec cierre-db psql -U cierre -d cierre -c 'SELECT count(*) FROM afi_mae'`
- **Solución:** en la base, `db/init/03_limpieza.sql` elimina los duplicados conservando la primera aparición y crea un índice único; lo irreparable no se borra: se reporta en `output/excepciones.csv` como DUPLICADO, SIN_EMPRESA, BENEFICIARIO_HUERFANO y CODIGO_INVALIDO.
- **Evidencia:** evidence/05-calidad-datos.txt

## Incidente 6
- **Síntoma:** `GET /afiliados/{documento}` respondía 500 para algunos afiliados (700 errores `CIE-5003`).
- **Diagnóstico:** los afiliados sin segundo nombre quedan con NOM2 en NULL al cargar el CSV y `app.py` concatenaba `nom1 + " " + nom2`, lo que lanza TypeError; además el JOIN interno y `ESTADOS[est_afi]` fallaban con empresa inexistente o estado inválido.
- **Comandos:** `grep -c CIE-5003 logs/api.log`, `awk -F, '$4==""' data/AFI_MAE.csv | wc -l`, `docker compose logs cierre-api`, `curl -s localhost:8081/afiliados/3756530718`
- **Solución:** en `services/api/app.py` el nombre se arma solo con las partes no vacías, el JOIN pasa a LEFT JOIN y el estado usa `ESTADOS.get(...)`; la API responde 200 con los datos y 404 si no existe.
- **Evidencia:** evidence/06-api-500.txt

## Incidente 7
- **Síntoma:** fechas de afiliación en formatos que el cierre no entiende (`CIE-3301` en el log del worker).
- **Diagnóstico:** `FEC_AFI` trae `YYYY-MM-DD`, `DD/MM/YYYY`, `YYYYMMDD` y valores basura como `SIN FECHA`, `N/A`, `00000000`, `31/13/2024` o `2023/02/29`; se contaron los patrones con `sed` y `sort | uniq -c`.
- **Comandos:** `cut -d, -f9 data/AFI_MAE.csv | sed -E 's/[0-9]/9/g' | sort | uniq -c`, `grep -c CIE-3301 logs/worker.log`
- **Solución:** el cierre normaliza los tres formatos válidos y reporta como FECHA_INVALIDA (12 documentos) las fechas que no existen; ningún registro se descarta y el afiliado sigue contando en los totales.
- **Evidencia:** evidence/07-fechas.txt

## Incidente 8
- **Síntoma:** el extracto de Caja Oriente trae otras columnas, separador `;`, documentos de 12 dígitos y fechas `DD/MM/YYYY`.
- **Diagnóstico:** `extracto_caja_oriente.csv` usa `id_afiliado;nombres_apellidos;situacion;fecha_reporte`; hay que quitar los ceros a la izquierda y comparar VIGENTE/RETIRADO con A/I.
- **Comandos:** `head -3 data/extracto_caja_oriente.csv`, `cut -d';' -f3 data/extracto_caja_oriente.csv | sort | uniq -c`, `wc -l data/extracto_caja_oriente.csv`
- **Solución:** `scripts/cierre.py` lee el extracto con `;`, normaliza el documento y reporta CRUCE_NO_COINCIDE (25 casos: documento inexistente o situación distinta); `afiliados_activos.csv` conserva su encabezado.
- **Evidencia:** evidence/08-cruce-caja-oriente.txt

## Incidente 9
- **Síntoma:** `totales.txt` del script heredado no cuadraba con la hoja de control de Operaciones.
- **Diagnóstico:** el script contaba líneas de AFI_MAE (1520 con duplicados) y los activos sin validar empresa ni estado; la hoja de control espera 1500, 1194 y 274.
- **Comandos:** `cat control/hoja_control.csv`, `wc -l data/AFI_MAE.csv`, `grep -c . output/afiliados_activos.csv`, `awk -F= '{print $1, $2}' output/totales.txt`
- **Solución:** se calcula sobre documentos distintos aplicando las reglas del diccionario: `total_afiliados=1500`, `activos=1194`, `inactivos=274`, `excepciones=104`, iguales a la hoja de control.
- **Evidencia:** evidence/09-totales.txt

## Incidente 10
- **Síntoma:** el cierre solo funcionaba una vez: la segunda corrida fallaba.
- **Diagnóstico:** el script heredado hacía `mkdir output` sin `-p` (falla si ya existe), agregaba a `totales.txt` con `>>` y movía `AFI_MAE.csv` a `procesados/`, de modo que la entrada desaparecía tras la primera corrida.
- **Comandos:** `grep -n 'mkdir\|mv ' scripts/cierre.sh`, `./run.sh`, `md5sum output/*`, `diff`, `./reset.sh`
- **Solución:** el nuevo cierre no mueve ni modifica `data/`, crea `output/` con `os.makedirs(exist_ok=True)`, reescribe cada archivo completo y produce salidas deterministas: dos corridas seguidas y una tras borrar `output/` dan el mismo `md5sum`.
- **Evidencia:** evidence/10-repetible.txt
