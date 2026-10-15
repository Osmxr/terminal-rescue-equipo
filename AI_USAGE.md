# Uso de inteligencia artificial

## Uso 1
- Herramienta: Claude (Anthropic)
- Para qué se usó: diagnosticar los fallos del kit leyendo el compose, `.env.example`, el worker y la API
- Prompt principal (resumido): "analiza todos los archivos del reto Terminal Rescue y dime qué está roto en cada incidente"
- Qué produjo: identificó `WORKER_INTERVAL_SECONDS=30s`, el host `cierre-database` inexistente y el TypeError por NOM2 nulo en la API
- Qué modificó o corrigió el equipo: levantamos Docker en nuestra máquina, probamos la API con curl y confirmamos respuestas 200 y 404 antes de aceptar la corrección

## Uso 2
- Herramienta: Claude (Anthropic)
- Para qué se usó: escribir el script de cierre repetible que genera los cuatro archivos de `output/`
- Prompt principal (resumido): "reescribe el cierre aplicando las reglas del diccionario, con excepciones, cruce de Caja Oriente y totales"
- Qué produjo: `scripts/cierre.py` y `scripts/cierre.sh`, que leen `data/` y escriben `output/` de forma determinista
- Qué modificó o corrigió el equipo: revisamos cada regla contra diccionario.md, ejecutamos el cierre dos veces y comprobamos con md5sum que las salidas fueran idénticas

## Uso 3
- Herramienta: Claude (Anthropic)
- Para qué se usó: generar la evidencia de terminal, el informe de incidentes y la documentación
- Prompt principal (resumido): "arma incident-report.md, evidence/ y el README con el formato obligatorio del reto"
- Qué produjo: diez archivos en `evidence/` con salidas de grep, awk, sort, uniq, sed, wc, find y chmod, más las plantillas llenas
- Qué modificó o corrigió el equipo: la primera evidencia salió con comillas rotas en awk y se regeneró; también corregimos un cp sin punto final que copió carpetas dentro de docs y rehicimos ese commit
