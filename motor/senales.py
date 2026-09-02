# FUNCIONALIDAD: san_broker/senales
"""De los indicadores a una decisión: COMPRAR / VENDER / ESPERAR, con score y razones.

Las reglas salen de la charla de Santiago (09/04/2026):
- Compra: la línea azul (MACD) cruza por arriba a la naranja (señal). Es "compra segura"
  cuando además el histograma está en verde. Vale más si el cruce se da por debajo de la
  línea de flotación (cero), porque agarra el piso.
- Venta: la naranja cruza por arriba a la azul y los dos promedios vienen bajando.
- Por arriba de la línea de flotación la acción está en etapa creciente; por abajo, bajando.
- Volumen: velas verdes = más compra que venta; rojas = al revés. Volumen chico = precio plano.
- Koncorde: marrón sobre roja = tendencia compradora; azul > 0 = manos fuertes comprando.

Cada componente da un valor en [-1, 1]; el score es la suma ponderada por config/pesos.json.
"""
import numpy as np


def _dias_desde_cruce(a, b, arriba=True, maximo=60):
    """Ruedas desde el último cruce de `a` por arriba de `b` (arriba=True) o por abajo."""
    diff = (a - b).values
    for i in range(1, min(maximo, len(diff))):
        hoy, ayer = diff[-i], diff[-i - 1]
        if np.isnan(hoy) or np.isnan(ayer):
            return None
        if arriba and ayer <= 0 < hoy:
            return i - 1
        if not arriba and ayer >= 0 > hoy:
            return i - 1
    return None


def _clip(x):
    return float(max(-1.0, min(1.0, x)))


def evaluar(ind, pesos, umbrales):
    """ind: DataFrame de indicadores.calcular_todo. Devuelve dict con score, señal, razones y datos."""
    u = ind.iloc[-1]
    ayer = ind.iloc[-2]
    reciente = umbrales.get("dias_cruce_reciente", 5)
    razones = []
    comp = {}

    # --- MACD: cruce -------------------------------------------------------
    cruce_arriba = _dias_desde_cruce(ind["macd"], ind["senal"], arriba=True)
    cruce_abajo = _dias_desde_cruce(ind["macd"], ind["senal"], arriba=False)
    azul_sobre_naranja = u["macd"] > u["senal"]
    bajo_flotacion = u["macd"] < 0
    # si hubo cruces en los dos sentidos, manda el más nuevo
    if cruce_arriba is not None and cruce_abajo is not None:
        if cruce_arriba <= cruce_abajo:
            cruce_abajo = None
        else:
            cruce_arriba = None
    if cruce_arriba is not None and cruce_arriba <= reciente:
        v = 1.0 if bajo_flotacion or ind["macd"].iloc[-1 - cruce_arriba] < 0 else 0.8
        razones.append(f"MACD: la azul cruzó por arriba a la naranja hace {cruce_arriba} rueda(s)"
                       + (" y por debajo de la línea de flotación (agarra el piso)" if v == 1.0 else ""))
    elif cruce_abajo is not None and cruce_abajo <= reciente:
        bajando = u["macd"] < ayer["macd"] and u["senal"] < ayer["senal"]
        v = -1.0 if bajando else -0.7
        razones.append(f"MACD: la naranja cruzó por arriba a la azul hace {cruce_abajo} rueda(s)"
                       + (" y los dos promedios bajan" if bajando else ""))
    else:
        v = 0.4 if azul_sobre_naranja else -0.4
        razones.append("MACD: azul por arriba de la naranja, sin cruce reciente" if azul_sobre_naranja
                       else "MACD: azul por debajo de la naranja, sin cruce reciente")
    comp["macd_cruce"] = v

    # --- MACD: histograma ----------------------------------------------------
    h, h1 = u["hist"], ayer["hist"]
    if h > 0:
        v = 1.0 if h > h1 else 0.5
        razones.append("Histograma en verde" + (" y creciendo" if h > h1 else " pero achicándose"))
    else:
        v = -1.0 if h < h1 else -0.5
        razones.append("Histograma en rojo" + (" y creciendo" if h < h1 else " pero achicándose"))
    if azul_sobre_naranja and h > 0:
        razones.append("Señal de compra segura (azul sobre naranja + histograma verde)")
    comp["macd_histograma"] = v

    # --- Koncorde: tendencia (marrón vs roja) ---------------------------------
    k_arriba = _dias_desde_cruce(ind["marron"], ind["media"], arriba=True)
    k_abajo = _dias_desde_cruce(ind["marron"], ind["media"], arriba=False)
    if k_arriba is not None and k_arriba <= reciente:
        v = 1.0
        razones.append(f"Koncorde: la montaña cruzó sobre la roja hace {k_arriba} rueda(s)")
    elif k_abajo is not None and k_abajo <= reciente:
        v = -1.0
        razones.append(f"Koncorde: la montaña cayó bajo la roja hace {k_abajo} rueda(s)")
    else:
        v = 0.6 if u["marron"] > u["media"] else -0.6
        razones.append("Koncorde: montaña sobre la roja" if v > 0 else "Koncorde: montaña bajo la roja")
    comp["koncorde_tendencia"] = v

    # --- Koncorde: manos fuertes (azul) --------------------------------------
    azul = u["azul"]
    if np.isnan(azul):
        v = 0.0
    else:
        v = _clip(azul / 25.0)
        if azul > 5:
            razones.append(f"Manos fuertes comprando (azul {azul:+.0f})")
        elif azul < -5:
            razones.append(f"Manos fuertes vendiendo (azul {azul:+.0f})")
    comp["koncorde_manos_fuertes"] = v

    # --- Volumen ---------------------------------------------------------------
    ratio = u["vol_ratio"] if not np.isnan(u["vol_ratio"]) else 1.0
    verde = bool(u["vela_verde"])
    fuerza = _clip((ratio - 1.0))  # 2x la media -> 1
    if ratio >= 1.3:
        v = fuerza if verde else -fuerza
        razones.append(f"Volumen {ratio:.1f}x la media, vela {'verde' if verde else 'roja'}")
    else:
        v = 0.15 if verde else -0.15
        if ratio < 0.6:
            razones.append("Volumen chico: precio sin fuerza")
    comp["volumen"] = v

    # --- Score y señal --------------------------------------------------------
    score = sum(pesos[k] * comp[k] for k in pesos)
    if score >= umbrales["comprar"]:
        senal = "COMPRAR"
    elif score <= umbrales["vender"]:
        senal = "VENDER"
    else:
        senal = "ESPERAR"

    tendencia = "alcista" if not bajo_flotacion else "bajista"
    if u["Close"] > u["ema50"] > u["ema200"]:
        tendencia_larga = "alcista"
    elif u["Close"] < u["ema50"] < u["ema200"]:
        tendencia_larga = "bajista"
    else:
        tendencia_larga = "lateral"

    cierres = ind["Close"]
    return {
        "score": round(float(score), 1),
        "senal": senal,
        "componentes": {k: round(v, 2) for k, v in comp.items()},
        "razones": razones,
        "tendencia": tendencia,
        "tendencia_larga": tendencia_larga,
        "precio": round(float(u["Close"]), 2),
        "var_dia": round(float(cierres.pct_change().iloc[-1] * 100), 2),
        "var_5d": round(float((cierres.iloc[-1] / cierres.iloc[-6] - 1) * 100), 2) if len(cierres) > 6 else None,
        "var_30d": round(float((cierres.iloc[-1] / cierres.iloc[-31] - 1) * 100), 2) if len(cierres) > 31 else None,
        "macd": {"azul": round(float(u["macd"]), 3), "naranja": round(float(u["senal"]), 3), "hist": round(float(u["hist"]), 3)},
        "koncorde": {k: (None if np.isnan(u[k]) else round(float(u[k]), 1)) for k in ("azul", "verde", "marron", "media")},
        "volumen": {"ratio": round(float(ratio), 2), "verde": verde},
        "fecha": ind.index[-1].strftime("%Y-%m-%d"),
        "serie": [round(float(x), 2) for x in cierres.tail(60)],
        "serie_fechas": [d.strftime("%d/%m") for d in cierres.tail(60).index],
        "serie_hist": [round(float(x), 3) for x in ind["hist"].tail(60)],
    }
