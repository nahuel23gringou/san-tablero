# FUNCIONALIDAD: san_broker/senales
"""El machete de trading de Santiago (27/10/2026): dos indicadores, seis señales.

| Señal            | Williams %R(14)   | Histograma MACD (12,26,9)          |
|------------------|-------------------|------------------------------------|
| COMPRA FUERTE    | -80 a -50         | hoy entre -0,5 y 0,5               |
| COMPRA CAUTA     | -50 a -20         | 0,1 a 0,7                          |
| MANTENER         | -50 a -20         | 0,7 a 3,0                          |
| NO COMPRAR (FOMO)| -20 a 0           | > 3,0                              |
| ALERTA SALIDA    | hoy > -20         | hoy > 0 y hoy < ayer (se achica)   |
| VENTA FUERTE     | no importa        | ayer > 0 y hoy < 0 (cruzó abajo)   |

Lo que el machete no cubre (por ejemplo Williams -91, o -80 a -50 con histograma 2) queda
como SIN SEÑAL, con los dos números a la vista. Orden de prioridad cuando dos filas
coinciden: venta, alerta, no comprar, mantener, compra cauta, compra fuerte.
Umbrales en config/machete.json.
"""
import numpy as np

ORDEN = ["COMPRA_FUERTE", "COMPRA_CAUTA", "MANTENER", "NO_COMPRAR", "ALERTA_SALIDA", "VENTA_FUERTE", "SIN_SENAL"]


def _en(x, banda):
    return banda[0] <= x <= banda[1]


def clasificar(will, h_hoy, h_ayer, umbrales):
    """Devuelve (señal, razón). `h_hoy`/`h_ayer` ya vienen en la base que diga el machete."""
    u = umbrales
    if h_ayer > 0 and h_hoy < 0:
        return "VENTA_FUERTE", f"el histograma cruzó de positivo a negativo (ayer {h_ayer:+.2f}, hoy {h_hoy:+.2f})"
    if will > u["alerta_salida"]["williams_min"] and h_hoy > 0 and h_hoy < h_ayer:
        return "ALERTA_SALIDA", f"Williams {will:.0f} (> {u['alerta_salida']['williams_min']}) y el histograma positivo se achica (ayer {h_ayer:+.2f}, hoy {h_hoy:+.2f})"
    nc = u["no_comprar"]
    if _en(will, nc["williams"]) and h_hoy > nc["hist_min"]:
        return "NO_COMPRAR", f"Williams {will:.0f} (sobrecomprado) e histograma {h_hoy:+.2f} > {nc['hist_min']}: ya subió, entrar ahora es FOMO"
    m = u["mantener"]
    if _en(will, m["williams"]) and _en(h_hoy, m["hist"]):
        return "MANTENER", f"Williams {will:.0f} e histograma {h_hoy:+.2f} entre {m['hist'][0]} y {m['hist'][1]}"
    c = u["compra_cauta"]
    if _en(will, c["williams"]) and _en(h_hoy, c["hist"]):
        return "COMPRA_CAUTA", f"Williams {will:.0f} e histograma {h_hoy:+.2f} entre {c['hist'][0]} y {c['hist'][1]}"
    f = u["compra_fuerte"]
    if _en(will, f["williams"]) and _en(h_hoy, f["hist"]):
        return "COMPRA_FUERTE", f"Williams {will:.0f} (sobrevendido) e histograma {h_hoy:+.2f} entre {f['hist'][0]} y {f['hist'][1]}"
    return "SIN_SENAL", f"Williams {will:.0f} e histograma {h_hoy:+.2f}: ninguna fila del machete cubre esta combinación"


def _normalizar(hist, close, base):
    return hist / close * 100 if base == "por_100" else hist


def evaluar(ind, machete):
    """ind: DataFrame de indicadores.calcular_todo. Devuelve dict con señal, razones y datos."""
    u = ind.iloc[-1]
    ayer = ind.iloc[-2]
    base = machete.get("histograma_base", "por_100")
    etiquetas = machete.get("etiquetas", {})
    will = float(u["williams"])
    h_hoy = float(_normalizar(u["hist"], u["Close"], base))
    h_ayer = float(_normalizar(ayer["hist"], ayer["Close"], base))
    if np.isnan(will) or np.isnan(h_hoy) or np.isnan(h_ayer):
        senal, razon = "SIN_SENAL", "faltan datos para calcular Williams o MACD"
    else:
        senal, razon = clasificar(will, h_hoy, h_ayer, machete["umbrales"])

    razones = [razon]
    if will <= -80:
        razones.append("Williams por debajo de -80: sobrevendido extremo")
    elif will >= -20:
        razones.append("Williams por arriba de -20: sobrecomprado")
    azul_sobre_naranja = u["macd"] > u["senal"]
    razones.append("MACD: línea azul por arriba de la naranja" if azul_sobre_naranja else "MACD: línea azul por debajo de la naranja")
    if u["Close"] > u["ema50"] > u["ema200"]:
        tendencia_larga = "alcista"
    elif u["Close"] < u["ema50"] < u["ema200"]:
        tendencia_larga = "bajista"
    else:
        tendencia_larga = "lateral"

    cierres = ind["Close"]
    ratio = float(u["vol_ratio"]) if not np.isnan(u["vol_ratio"]) else 1.0
    return {
        "senal": senal,
        "etiqueta": etiquetas.get(senal, senal),
        "orden": ORDEN.index(senal),
        "razones": razones,
        "williams": round(will, 1) if not np.isnan(will) else None,
        "hist": round(h_hoy, 3) if not np.isnan(h_hoy) else None,
        "hist_ayer": round(h_ayer, 3) if not np.isnan(h_ayer) else None,
        "hist_bruto": round(float(u["hist"]), 3),
        "macd": {"azul": round(float(u["macd"]), 3), "naranja": round(float(u["senal"]), 3)},
        "tendencia_larga": tendencia_larga,
        "precio": round(float(u["Close"]), 2),
        "var_dia": round(float(cierres.pct_change().iloc[-1] * 100), 2),
        "var_5d": round(float((cierres.iloc[-1] / cierres.iloc[-6] - 1) * 100), 2) if len(cierres) > 6 else None,
        "var_30d": round(float((cierres.iloc[-1] / cierres.iloc[-31] - 1) * 100), 2) if len(cierres) > 31 else None,
        "volumen": {"ratio": round(ratio, 2), "verde": bool(u["vela_verde"])},
        "fecha": ind.index[-1].strftime("%Y-%m-%d"),
        "serie": [round(float(x), 2) for x in cierres.tail(60)],
        "serie_fechas": [d.strftime("%d/%m") for d in cierres.tail(60).index],
        "serie_hist": [round(float(x), 3) for x in ind["hist"].tail(60)],
        "serie_williams": [None if np.isnan(x) else round(float(x), 1) for x in ind["williams"].tail(60)],
    }
