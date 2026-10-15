#!/usr/bin/env bash
# Guarda en evidence/ la salida real de docker/curl con el entorno levantado.
# Uso: docker compose up -d --build && ./scripts/capturar_evidencia.sh
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p evidence
{ echo '$ docker compose ps'; docker compose ps; echo; echo '$ docker compose logs cierre-worker | tail -5'; docker compose logs cierre-worker | tail -5; } > evidence/01b-docker-worker.txt 2>&1
{ echo '$ docker compose logs cierre-api | tail -5'; docker compose logs cierre-api | tail -5; echo; echo '$ docker compose exec cierre-db psql -U cierre -d cierre -c "SELECT count(*), count(DISTINCT nro_doc) FROM afi_mae"'; docker compose exec -T cierre-db psql -U cierre -d cierre -c "SELECT count(*), count(DISTINCT nro_doc) FROM afi_mae"; } > evidence/02b-docker-api-base.txt 2>&1
{ for d in 3756530718 88121168 6015866271 0000000001; do echo "\$ curl -s -w ' [%{http_code}]' localhost:8081/afiliados/$d"; curl -s -w ' [%{http_code}]\n' "localhost:${API_PORT:-8081}/afiliados/$d"; done; } > evidence/06b-api-consulta.txt 2>&1
echo "Evidencia guardada en evidence/"
