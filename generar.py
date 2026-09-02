# FUNCIONALIDAD: san_broker/generador
"""Corre todo el circuito y deja docs/datos.json listo para la página.

    python3 generar.py                 # todo el universo, con resumen IA si hay GEMINI_API_KEY
    python3 generar.py --sin-ia        # sin llamar a Gemini
    python3 generar.py --limite 8      # sólo los primeros 8 activos (para probar rápido)
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

from motor import precios, indicadores, senales, noticias, resumen_ia  # noqa: E402

ARG = timezone(timedelta(hours=-3))


def cargar(nombre):
    with open(os.path.join(RAIZ, "config", nombre), encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-ia", action="store_true")
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--salida", default=os.path.join(RAIZ, "docs"))
    args = ap.parse_args()

    activos = cargar("activos.json")["activos"]
    if args.limite:
        activos = activos[: args.limite]
    cfg = cargar("pesos.json")
    pesos, umbrales = cfg["pesos"], cfg["umbrales"]

    simbolos = [a["simbolo"] for a in activos]
    print(f"Bajando precios de {len(simbolos)} activos…", flush=True)
    series = precios.bajar(simbolos)
    faltantes = [s for s in simbolos if s not in series]
    print(f"  ok {len(series)} · sin datos {len(faltantes)} {faltantes if faltantes else ''}", flush=True)

    print("Calculando indicadores y señales…", flush=True)
    evaluados = []
    errores = []
    for a in activos:
        df = series.get(a["simbolo"])
        if df is None:
            continue
        try:
            ind = indicadores.calcular_todo(df)
            ev = senales.evaluar(ind, pesos, umbrales)
        except Exception as e:
            errores.append(f"{a['simbolo']}: {type(e).__name__}: {e}")
            continue
        ev.update({
            "simbolo": a["simbolo"], "byma": a.get("byma", a["simbolo"]), "nombre": a["nombre"],
            "categoria": a["categoria"], "moneda": a.get("moneda", "USD"),
        })
        evaluados.append(ev)
    evaluados.sort(key=lambda e: e["score"], reverse=True)
    for e in errores:
        print("  error", e)

    print("Leyendo noticias…", flush=True)
    todas = noticias.leer()
    por_activo = noticias.vincular(todas, activos)
    for ev in evaluados:
        ev["noticias"] = por_activo.get(ev["simbolo"], [])[:6]
    print(f"  {len(todas)} noticias · {sum(1 for e in evaluados if e['noticias'])} activos con noticia", flush=True)

    ia = None
    if not args.sin_ia:
        print("Resumen IA…", flush=True)
        ia = resumen_ia.resumir(todas, evaluados)
        if ia and "error" in ia:
            print("  sin resumen:", ia["error"])
        elif ia:
            for ev in evaluados:
                nota = ia.get("activos", {}).get(ev["simbolo"])
                if nota:
                    ev["ia"] = nota
        else:
            print("  sin GEMINI_API_KEY: se omite")

    ahora = datetime.now(ARG)
    fecha_datos = max((e["fecha"] for e in evaluados), default=None)
    conteo = {k: sum(1 for e in evaluados if e["senal"] == k) for k in ("COMPRAR", "VENDER", "ESPERAR")}
    salida = {
        "generado": ahora.strftime("%Y-%m-%d %H:%M"),
        "fecha_datos": fecha_datos,
        "conteo": conteo,
        "pesos": pesos,
        "umbrales": umbrales,
        "resumen_ia": ia if ia and "error" not in ia else None,
        "aviso_ia": ia.get("error") if ia and "error" in ia else (None if ia else "Sin resumen IA"),
        "faltantes": faltantes + errores,
        "activos": evaluados,
        "noticias": todas[:40],
    }

    os.makedirs(os.path.join(args.salida, "historial"), exist_ok=True)
    with open(os.path.join(args.salida, "datos.json"), "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
    if fecha_datos and not args.limite:
        resumen_dia = {"fecha": fecha_datos, "generado": salida["generado"], "conteo": conteo,
                       "activos": [{k: e[k] for k in ("simbolo", "senal", "score", "precio", "var_dia")} for e in evaluados]}
        with open(os.path.join(args.salida, "historial", f"{fecha_datos}.json"), "w", encoding="utf-8") as f:
            json.dump(resumen_dia, f, ensure_ascii=False, separators=(",", ":"))
        fechas = sorted(x[:-5] for x in os.listdir(os.path.join(args.salida, "historial")) if x.endswith(".json") and x[0].isdigit())
        with open(os.path.join(args.salida, "historial", "indice.json"), "w", encoding="utf-8") as f:
            json.dump(fechas[-90:], f)

    print(f"Listo: {len(evaluados)} activos · {conteo} · datos del {fecha_datos}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
