# FUNCIONALIDAD: san_broker/pruebas
"""Casos del motor con series sintéticas (sin internet). Sale con exit 1 si algo falla.

    python3 prueba.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
from motor import indicadores, senales, noticias  # noqa: E402

MACHETE = json.load(open(os.path.join(RAIZ, "config", "machete.json"), encoding="utf-8"))
U = MACHETE["umbrales"]
fallos = []


def caso(nombre, cond, detalle=""):
    print(("  ok   " if cond else "  FALLA") + " " + nombre + (f"  ({detalle})" if detalle and not cond else ""))
    if not cond:
        fallos.append(nombre)


RNG = np.random.default_rng(7)


def serie(closes):
    n = len(closes)
    idx = pd.bdate_range("2024-01-01", periods=n)
    c = pd.Series(closes, index=idx, dtype=float)
    o = c.shift(1).fillna(c.iloc[0])
    v = pd.Series(RNG.integers(800_000, 1_200_000, n).astype(float), index=idx)
    return pd.DataFrame({"Open": o, "High": np.maximum(o, c) * 1.01, "Low": np.minimum(o, c) * 0.99, "Close": c, "Volume": v})


print("Machete: una fila por señal (valores directos)")
cl = lambda w, h, ha: senales.clasificar(w, h, ha, U)[0]  # noqa: E731
caso("Williams -65, hist 0.2 -> COMPRA_FUERTE", cl(-65, 0.2, 0.1) == "COMPRA_FUERTE")
caso("Williams -65, hist -0.4 -> COMPRA_FUERTE (histograma puede ser negativo chico)", cl(-65, -0.4, -0.6) == "COMPRA_FUERTE")
caso("Williams -35, hist 0.4 -> COMPRA_CAUTA", cl(-35, 0.4, 0.3) == "COMPRA_CAUTA")
caso("Williams -35, hist 1.5 -> MANTENER", cl(-35, 1.5, 1.2) == "MANTENER")
caso("Williams -10, hist 3.5 subiendo -> NO_COMPRAR", cl(-10, 3.5, 3.2) == "NO_COMPRAR")
caso("Williams -10, hist 0.8 achicándose -> ALERTA_SALIDA", cl(-10, 0.8, 1.0) == "ALERTA_SALIDA")
caso("Williams -10, hist 3.5 achicándose -> ALERTA_SALIDA gana a NO_COMPRAR", cl(-10, 3.5, 3.8) == "ALERTA_SALIDA")
caso("hist ayer +0.3, hoy -0.1 -> VENTA_FUERTE con cualquier Williams", cl(-70, -0.1, 0.3) == "VENTA_FUERTE" and cl(-5, -0.1, 0.3) == "VENTA_FUERTE")
caso("Williams -91, hist -2 -> SIN_SENAL (el machete no lo cubre)", cl(-91, -2.0, -2.5) == "SIN_SENAL")
caso("Williams -65, hist 2.0 -> SIN_SENAL", cl(-65, 2.0, 1.5) == "SIN_SENAL")
caso("Williams -35, hist 0.05 -> SIN_SENAL", cl(-35, 0.05, 0.02) == "SIN_SENAL")
caso("borde: Williams -50 con hist 0.3 -> COMPRA_CAUTA (banda -50 a -20 incluye -50)", cl(-50, 0.3, 0.2) == "COMPRA_CAUTA")
caso("borde: hist 0.7 con Williams -35 -> MANTENER (0,7 cae en mantener)", cl(-35, 0.7, 0.6) == "MANTENER")
caso("la razón trae los dos números", "Williams -35" in senales.clasificar(-35, 0.4, 0.3, U)[1] and "+0.40" in senales.clasificar(-35, 0.4, 0.3, U)[1])

print("Indicadores")
n = 260
x = np.concatenate([np.linspace(100, 60, 180), np.linspace(60, 80, 80)]) + np.sin(np.arange(n) / 3) * 0.3
df = serie(x)
m = indicadores.macd(df["Close"])
caso("macd tiene 3 columnas sin NaN al final", not m.iloc[-1].isna().any())
caso("macd negativo en plena caída", m["macd"].iloc[150] < 0)
w = indicadores.williams_r(df, 14)
caso("williams entre -100 y 0", float(w.dropna().min()) >= -100 and float(w.dropna().max()) <= 0)
caso("williams cerca de -100 en el piso de la caída", float(w.iloc[179]) < -80)
caso("williams cerca de 0 tras subir 80 ruedas", float(w.iloc[-1]) > -20)
ind = indicadores.calcular_todo(df, MACHETE)
caso("calcular_todo trae williams, hist, ema50/200 sin duplicar columnas", not ind.columns.duplicated().any() and {"williams", "hist", "ema50", "ema200"} <= set(ind.columns))

print("Evaluar sobre una serie")
ev = senales.evaluar(ind, MACHETE)
caso("evaluar devuelve señal del machete y etiqueta", ev["senal"] in senales.ORDEN and ev["etiqueta"] == MACHETE["etiquetas"][ev["senal"]])
caso("orden coincide con la posición en ORDEN", ev["orden"] == senales.ORDEN.index(ev["senal"]))
caso("hist normalizado por 100 = bruto / precio * 100", abs(ev["hist"] - ev["hist_bruto"] / ev["precio"] * 100) < 0.01)
caso("serie de 60 cierres y fechas para el gráfico", len(ev["serie"]) == 60 and len(ev["serie_fechas"]) == 60 and len(ev["serie_williams"]) == 60)
caso("tendencia larga alcista en subida sostenida",
     senales.evaluar(indicadores.calcular_todo(serie(np.linspace(60, 100, 260)), MACHETE), MACHETE)["tendencia_larga"] == "alcista")
# cruce bajista del histograma en la serie: el último día del cruce tiene que dar VENTA_FUERTE
y = np.concatenate([np.linspace(60, 100, 200), np.linspace(100, 85, 60)]) + np.sin(np.arange(n) / 3) * 0.3
ind2 = indicadores.calcular_todo(serie(y), MACHETE)
h = ind2["hist"].values
cruce = next(i for i in range(190, len(h)) if h[i - 1] > 0 > h[i])
caso("el día que el histograma cruza abajo -> VENTA_FUERTE", senales.evaluar(ind2.iloc[: cruce + 1], MACHETE)["senal"] == "VENTA_FUERTE")

print("Noticias")
activos = [{"simbolo": "AAPL", "alias": ["Apple", "iPhone"]}, {"simbolo": "GGAL", "alias": ["Galicia"]}, {"simbolo": "C", "alias": ["Citigroup"]}]
lista = [
    {"titulo": "Apple presentó el nuevo iPhone", "bajada": ""},
    {"titulo": "Banco Galicia gana en la bolsa", "bajada": ""},
    {"titulo": "Cae la acción de Citigroup", "bajada": ""},
    {"titulo": "El clima en la Ciudad", "bajada": "sin relación con nada"},
]
v = noticias.vincular(lista, activos)
caso("Apple vinculada a AAPL", len(v["AAPL"]) == 1)
caso("Galicia vinculada a GGAL", len(v["GGAL"]) == 1)
caso("símbolo de 1 letra no matchea por sí solo", len(v["C"]) == 1)
caso("la noticia sin relación no se vincula", sum(len(x) for x in v.values()) == 3)
caso("limpiar_html saca etiquetas", noticias._limpiar_html("<p>Hola <b>mundo</b></p>") == "Hola mundo")

print("Versión (norma del 30/09/2026)")
import generar  # noqa: E402
from datetime import datetime  # noqa: E402
s = generar.sello(datetime(2026, 10, 27, 14, 5), "V1.1")
caso("sello legible «V1.1 · 27/10 14:05»", f"{s['version']} · {s['sello']}" == "V1.1 · 27/10 14:05", str(s))
caso("id distinto en otro minuto", generar.sello(datetime(2026, 10, 27, 14, 6), "V1.1")["id"] != s["id"])
caso("id igual en el mismo minuto", generar.sello(datetime(2026, 10, 27, 14, 5, 59), "V1.1")["id"] == s["id"])
html = open(os.path.join(RAIZ, "docs", "index.html"), encoding="utf-8").read()
caso("la página tiene el sello en el pie y el cartel con botón Actualizar",
     'id="selloVersion"' in html and 'id="avisoVersion"' in html and 'id="btnActualizar"' in html and "Hay una versión nueva de la app" in html)
caso("la página pregunta al volver al frente, al recuperar señal y cada 5 min",
     "visibilitychange" in html and '"online"' in html and "5 * 60 * 1000" in html)
caso("nunca recarga sola: sólo el botón llama a location.replace", html.count("location.replace") == 1 and "btnActualizar" in html.split("location.replace")[0][-200:])

print("Universo")
act = json.load(open(os.path.join(RAIZ, "config", "activos.json"), encoding="utf-8"))["activos"]
caso("50 instrumentos", len(act) == 50, str(len(act)))
caso("sólo dos categorías: cedear y argentina", set(a["categoria"] for a in act) == {"cedear", "argentina"})
caso("símbolos únicos", len(set(a["simbolo"] for a in act)) == len(act))

print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    sys.exit(1)
print("Todos los casos pasan.")
