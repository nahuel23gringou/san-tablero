# FUNCIONALIDAD: san_broker/indicadores
"""Indicadores técnicos, en pandas puro (sin TA-Lib).

Desde el 27/10/2026 la señal sale de dos indicadores, los que pidió Santiago:
- MACD (12, 26, 9): "línea azul" = macd, "línea naranja" = señal, "cuadraditos" = histograma.
- Williams %R (14): oscila entre -100 (sobrevendido) y 0 (sobrecomprado).
El volumen y las medias de 50/200 se muestran como información, no deciden.
"""
import numpy as np
import pandas as pd


def ema(serie, n):
    return serie.ewm(span=n, adjust=False).mean()


def macd(close, rapida=12, lenta=26, senal=9):
    linea = ema(close, rapida) - ema(close, lenta)
    sen = ema(linea, senal)
    return pd.DataFrame({"macd": linea, "senal": sen, "hist": linea - sen})


def williams_r(df, n=14):
    maximo = df["High"].rolling(n).max()
    minimo = df["Low"].rolling(n).min()
    return (maximo - df["Close"]) / (maximo - minimo).replace(0, np.nan) * -100


def volumen(df, n=20):
    vol = df["Volume"].astype(float)
    return pd.DataFrame({
        "vol": vol,
        "vol_media": vol.rolling(n).mean(),
        "vol_ratio": vol / vol.rolling(n).mean().replace(0, np.nan),
        "vela_verde": df["Close"] >= df["Open"],
    })


def calcular_todo(df, machete=None):
    """Un DataFrame con precio + MACD + Williams + volumen + medias, alineado por fecha."""
    m = (machete or {}).get("macd", {})
    n_will = (machete or {}).get("williams_periodo", 14)
    partes = [
        df[["Open", "High", "Low", "Close", "Volume"]],
        macd(df["Close"], m.get("rapida", 12), m.get("lenta", 26), m.get("senal", 9)),
        volumen(df),
    ]
    out = pd.concat(partes, axis=1)
    out["williams"] = williams_r(df, n_will)
    out["ema50"] = ema(df["Close"], 50)
    out["ema200"] = ema(df["Close"], 200)
    return out
