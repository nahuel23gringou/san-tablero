# FUNCIONALIDAD: san_broker/pruebas
"""Casos del motor con series sintéticas (sin internet). Sale con exit 1 si algo falla.

    python3 prueba.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motor import indicadores, senales, noticias  # noqa: E402

PESOS = {"macd_cruce": 35, "macd_histograma": 15, "koncorde_tendencia": 20, "koncorde_manos_fuertes": 15, "volumen": 15}
UMBRALES = {"comprar": 35, "vender": -35, "dias_cruce_reciente": 5}
fallos = []


def caso(nombre, cond, detalle=""):
    print(("  ok   " if cond else "  FALLA") + " " + nombre + (f"  ({detalle})" if detalle and not cond else ""))
    if not cond:
        fallos.append(nombre)


RNG = np.random.default_rng(7)


def serie(closes, vol=None):
    n = len(closes)
    idx = pd.bdate_range("2024-01-01", periods=n)
    c = pd.Series(closes, index=idx, dtype=float)
    o = c.shift(1).fillna(c.iloc[0])
    # volumen variable: PVI/NVI necesitan días con más y con menos volumen que el anterior
    v = pd.Series(vol if vol is not None else RNG.integers(800_000, 1_200_000, n).astype(float), index=idx)
    return pd.DataFrame({"Open": o, "High": np.maximum(o, c) * 1.01, "Low": np.minimum(o, c) * 0.99, "Close": c, "Volume": v})


def caida_y_rebote(n=260, piso=180):
    # cae 40 % en 180 ruedas y rebota fuerte: el MACD tiene que cruzar por abajo de cero
    x = np.concatenate([np.linspace(100, 60, piso), np.linspace(60, 80, n - piso)])
    return x + np.sin(np.arange(n) / 3) * 0.3


def subida_y_techo(n=260, techo=200):
    x = np.concatenate([np.linspace(60, 100, techo), np.linspace(100, 85, n - techo)])
    return x + np.sin(np.arange(n) / 3) * 0.3


print("MACD")
df = serie(caida_y_rebote())
m = indicadores.macd(df["Close"])
caso("macd tiene 3 columnas sin NaN al final", not m.iloc[-1].isna().any())
caso("macd sube después del piso", m["macd"].iloc[-1] > m["macd"].iloc[180])
caso("macd negativo en plena caída", m["macd"].iloc[150] < 0)

print("Koncorde")
k = indicadores.koncorde(df)
caso("koncorde devuelve las 4 líneas", set(["azul", "verde", "marron", "media"]) <= set(k.columns))
caso("koncorde sin NaN en la última rueda", not k.iloc[-1][["azul", "verde", "marron", "media"]].isna().any())
caso("marrón sobre la roja 20 ruedas después del piso", k["marron"].iloc[200] > k["media"].iloc[200])

print("Señales")
ind = indicadores.calcular_todo(df)
caso("calcular_todo no duplica columnas", not ind.columns.duplicated().any())
# recorto la serie hasta 2 ruedas después del último cruce alcista bajo cero cerca del piso
diff = (ind["macd"] - ind["senal"]).values
cruce = next(i for i in range(165, len(diff)) if diff[i - 1] <= 0 < diff[i] and ind["macd"].iloc[i] < 0)
ev = senales.evaluar(ind.iloc[: cruce + 3], PESOS, UMBRALES)
caso("rebote desde el piso -> COMPRAR", ev["senal"] == "COMPRAR", f"{ev['senal']} {ev['score']}")
caso("componente macd_cruce = 1 (cruce bajo la flotación)", ev["componentes"]["macd_cruce"] == 1.0)
caso("razones mencionan el piso", any("piso" in r for r in ev["razones"]))

df2 = serie(subida_y_techo())
ind2 = indicadores.calcular_todo(df2)
diff2 = (ind2["macd"] - ind2["senal"]).values
cruce2 = next(i for i in range(190, len(diff2)) if diff2[i - 1] >= 0 > diff2[i])
ev2 = senales.evaluar(ind2.iloc[: cruce2 + 2], PESOS, UMBRALES)
caso("cruce bajista reciente -> macd_cruce negativo y score < 0", ev2["componentes"]["macd_cruce"] < 0 and ev2["score"] < 0,
     f"{ev2['senal']} {ev2['score']} {ev2['componentes']}")
ev2b = senales.evaluar(ind2, PESOS, UMBRALES)
caso("techo y caída sostenida -> VENDER", ev2b["senal"] == "VENDER", f"{ev2b['senal']} {ev2b['score']}")
caso("tendencia larga alcista en subida", senales.evaluar(ind2.iloc[:200], PESOS, UMBRALES)["tendencia_larga"] == "alcista")

vol = np.full(260, 1_000_000.0)
vol[-1] = 3_000_000.0
ev3 = senales.evaluar(indicadores.calcular_todo(serie(caida_y_rebote(), vol)), PESOS, UMBRALES)
caso("volumen 3x con vela verde suma", ev3["componentes"]["volumen"] > 0.5, str(ev3["componentes"]["volumen"]))
caso("score dentro de [-100, 100]", -100 <= ev3["score"] <= 100)
caso("serie de 60 cierres para el gráfico", len(ev3["serie"]) == 60 and len(ev3["serie_fechas"]) == 60)

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

print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    sys.exit(1)
print("Todos los casos pasan.")
