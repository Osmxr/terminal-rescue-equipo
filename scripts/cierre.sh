#!/usr/bin/env bash
# Cierre mensual de afiliados activos. Delegado en scripts/cierre.py (lee data/, escribe output/).
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/cierre.py
