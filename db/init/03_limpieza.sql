-- Limpieza de la base del cierre (incidente 5). Se ejecuta tras la carga inicial.
-- Los duplicados de afi_mae se eliminan conservando la primera aparición (orden de carga).
-- Lo irreparable (estado inválido, sin empresa, huérfanos, fechas) NO se borra:
-- lo reporta scripts/cierre.py en output/excepciones.csv.
DELETE FROM afi_mae a
USING afi_mae b
WHERE a.nro_doc = b.nro_doc
  AND a.ctid > b.ctid;

-- Un documento por afiliado a partir de aquí.
CREATE UNIQUE INDEX uq_afi_mae_doc ON afi_mae (nro_doc);
