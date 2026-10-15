#!/usr/bin/env python3
"""Cierre mensual de afiliados activos (reemplaza el script heredado).

Lee los CSV de data/, aplica las reglas de docs/diccionario.md y genera en output/:
afiliados_activos.csv, excepciones.csv, totales.txt y top_error.txt.
Es repetible: no modifica data/, reescribe output/ completo y produce salidas deterministas.
"""
import csv
import glob
import os
import re
import sys
from collections import Counter
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
LOGS = os.path.join(ROOT, "logs")
OUT = os.path.join(ROOT, "output")

TIPOS = ["DUPLICADO", "SIN_EMPRESA", "BENEFICIARIO_HUERFANO", "CODIGO_INVALIDO", "FECHA_INVALIDA", "CRUCE_NO_COINCIDE"]
FORMATOS_FECHA = [(r"\d{4}-\d{2}-\d{2}", "%Y-%m-%d"), (r"\d{2}/\d{2}/\d{4}", "%d/%m/%Y"), (r"\d{8}", "%Y%m%d")]


def leer(nombre, delimiter=","):
    ruta = os.path.join(DATA, nombre)
    with open(ruta, encoding="utf-8-sig", newline="") as fh:
        return [{k.strip().upper(): (v or "").strip() for k, v in fila.items()} for fila in csv.DictReader(fh, delimiter=delimiter)]


def fecha_valida(texto):
    """Devuelve la fecha normalizada YYYY-MM-DD o None si no se puede interpretar."""
    for patron, formato in FORMATOS_FECHA:
        if re.fullmatch(patron, texto):
            try:
                return datetime.strptime(texto, formato).strftime("%Y-%m-%d")
            except ValueError:
                return None
    return None


def error_mas_frecuente():
    conteo = Counter()
    for ruta in sorted(glob.glob(os.path.join(LOGS, "*.log"))):
        with open(ruta, encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                m = re.search(r"\bCIE-\d{4}\b", linea)
                if m:
                    conteo[m.group(0)] += 1
    if not conteo:
        return "", 0
    codigo, n = sorted(conteo.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return codigo, n


def main():
    empresas = {e["COD_EMP"]: e["NOM_EMP"] for e in leer("EMPRESA.csv")}
    maestro = leer("AFI_MAE.csv")
    beneficiarios = leer("AFI_BEN.csv")
    aportes = leer("APORTES.csv")
    extracto = leer("extracto_caja_oriente.csv", delimiter=";")

    excepciones = {t: {} for t in TIPOS}  # tipo -> {documento: detalle}

    # Regla 1: universo = documentos distintos; se conserva la primera aparición.
    afiliados, repeticiones = {}, Counter()
    for fila in maestro:
        doc = fila["NRO_DOC"]
        repeticiones[doc] += 1
        afiliados.setdefault(doc, fila)
    for doc, n in repeticiones.items():
        if n > 1:
            excepciones["DUPLICADO"][doc] = "documento repetido {0} veces en AFI_MAE; se conserva la primera aparicion".format(n)

    # Reglas 2, 3 y 5: estado, empresa y fecha.
    activos, inactivos = [], 0
    for doc, fila in afiliados.items():
        estado = fila["EST_AFI"]
        if estado not in ("A", "I"):
            excepciones["CODIGO_INVALIDO"][doc] = "EST_AFI={0} no es A ni I".format(estado)
        elif estado == "I":
            inactivos += 1
        elif fila["COD_EMP"] not in empresas:
            excepciones["SIN_EMPRESA"][doc] = "COD_EMP={0} vacio o inexistente en EMPRESA".format(fila["COD_EMP"])
        else:
            activos.append(doc)
        if fecha_valida(fila["FEC_AFI"]) is None:
            excepciones["FECHA_INVALIDA"][doc] = "FEC_AFI={0} no se puede interpretar como fecha".format(fila["FEC_AFI"])

    # Regla 4: beneficiarios huérfanos.
    cuenta_ben = Counter()
    for fila in beneficiarios:
        if fila["NRO_DOC_AFI"] in afiliados:
            cuenta_ben[fila["NRO_DOC_AFI"]] += 1
        else:
            excepciones["BENEFICIARIO_HUERFANO"][fila["NRO_DOC_BEN"]] = "afiliado {0} no existe en AFI_MAE".format(fila["NRO_DOC_AFI"])

    # Regla 6: cruce con Caja Oriente (documento de 12 dígitos con ceros a la izquierda).
    equivalencia = {"A": "VIGENTE", "I": "RETIRADO"}
    for fila in extracto:
        doc = fila["ID_AFILIADO"].lstrip("0")
        propio = afiliados.get(doc)
        if propio is None:
            excepciones["CRUCE_NO_COINCIDE"][doc] = "documento del extracto no existe en AFI_MAE"
        elif equivalencia.get(propio["EST_AFI"]) != fila["SITUACION"].upper():
            excepciones["CRUCE_NO_COINCIDE"][doc] = "Caja Oriente={0}, nuestro estado={1}".format(fila["SITUACION"], propio["EST_AFI"])

    # Regla 7: archivo de activos.
    ultimo = {}
    for fila in aportes:
        if fila["PERIODO"] > ultimo.get(fila["NRO_DOC"], ""):
            ultimo[fila["NRO_DOC"]] = fila["PERIODO"]

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "afiliados_activos.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["documento", "nombre", "estado", "cod_empresa", "empresa", "beneficiarios", "ultimo_aporte"])
        for doc in activos:
            f = afiliados[doc]
            nombre = " ".join(p for p in (f["NOM1"], f["NOM2"], f["APE1"], f["APE2"]) if p)
            w.writerow([doc, nombre, "ACTIVO", f["COD_EMP"], empresas[f["COD_EMP"]], cuenta_ben[doc], ultimo.get(doc, "")])

    total_excepciones = 0
    with open(os.path.join(OUT, "excepciones.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["documento", "tipo", "detalle"])
        for tipo in TIPOS:
            for doc in sorted(excepciones[tipo]):
                w.writerow([doc, tipo, excepciones[tipo][doc]])
                total_excepciones += 1

    # Regla 8: totales.
    with open(os.path.join(OUT, "totales.txt"), "w", encoding="utf-8", newline="") as fh:
        fh.write("total_afiliados={0}\nactivos={1}\ninactivos={2}\nexcepciones={3}\n".format(len(afiliados), len(activos), inactivos, total_excepciones))

    codigo, n = error_mas_frecuente()
    with open(os.path.join(OUT, "top_error.txt"), "w", encoding="utf-8", newline="") as fh:
        fh.write("codigo_error={0}\nocurrencias={1}\n".format(codigo, n))

    print("Cierre terminado: {0} afiliados, {1} activos, {2} inactivos, {3} excepciones".format(len(afiliados), len(activos), inactivos, total_excepciones))
    return 0


if __name__ == "__main__":
    sys.exit(main())
