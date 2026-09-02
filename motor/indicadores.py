# FUNCIONALIDAD: san_broker/indicadores
"""Indicadores técnicos, en pandas puro (sin TA-Lib).

MACD (12, 26, 9): lo que Santiago mostró en TradingView. "Línea azul" = macd,
"línea naranja" = señal, "cuadraditos rojos y verdes" = histograma, "línea de
flotación" = cero.

Koncorde (Blai5, v0.9 de 2008, fórmula publicada): "azul" = manos fuertes (NVI),
"verde" = manos débiles (PVI sobre la montaña), "marrón" = tendencia (RSI + MFI +
oscilador de Bollinger + estocástico), "roja" = EMA(15) de marrón.
"""
import numpy as np
import pandas as pd


def ema(serie, n):
    return serie.ewm(span=n, adjust=False).mean()


def macd(close, rapida=12, lenta=26, senal=9):
    linea = ema(close, rapida) - ema(close, lenta)
    sen = ema(linea, senal)
    return pd.DataFrame({"macd": linea, "senal": sen, "hist": linea - sen})


def rsi(serie, n=14):
    delta = serie.diff()
    sube = delta.clip(lower=0)
    baja = -delta.clip(upper=0)
    # Wilder: media móvil exponencial con alpha = 1/n
    ms = sube.ewm(alpha=1 / n, adjust=False).mean()
    mb = baja.ewm(alpha=1 / n, adjust=False).mean()
    rs = ms / mb.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def mfi(tp, volumen, n=14):
    flujo = tp * volumen
    signo = np.sign(tp.diff()).fillna(0)
    pos = flujo.where(signo > 0, 0.0).rolling(n).sum()
    neg = flujo.where(signo < 0, 0.0).rolling(n).sum()
    ratio = pos / neg.replace(0, np.nan)
    return (100 - 100 / (1 + ratio)).fillna(50)


def _indice_volumen(close, volumen, positivo=True):
    """PVI (positivo=True) o NVI: acumula la variación del precio sólo los días en que el
    volumen sube (PVI) o baja (NVI). Arranca en 1000."""
    ret = close.pct_change().fillna(0).values
    dv = volumen.diff().fillna(0).values
    out = np.empty(len(close))
    out[0] = 1000.0
    for i in range(1, len(close)):
        aplica = dv[i] > 0 if positivo else dv[i] < 0
        out[i] = out[i - 1] * (1 + ret[i]) if aplica else out[i - 1]
    return pd.Series(out, index=close.index)


def koncorde(df, m=15, ventana=90):
    close, high, low, vol = df["Close"], df["High"], df["Low"], df["Volume"].astype(float)
    tp = (high + low + close) / 3

    pvi = _indice_volumen(close, vol, positivo=True)
    pvim = ema(pvi, m)
    rango_p = (pvim.rolling(ventana).max() - pvim.rolling(ventana).min()).replace(0, np.nan)
    oscp = (pvi - pvim) * 100 / rango_p

    nvi = _indice_volumen(close, vol, positivo=False)
    nvim = ema(nvi, m)
    rango_n = (nvim.rolling(ventana).max() - nvim.rolling(ventana).min()).replace(0, np.nan)
    azul = (nvi - nvim) * 100 / rango_n

    xmf = mfi(tp, vol, 14)
    media_b = tp.rolling(25).mean()
    desvio_b = tp.rolling(25).std(ddof=0)
    ob1 = media_b
    ob2 = (4 * desvio_b).replace(0, np.nan)
    boll_osc = (tp - ob1) / ob2 * 100
    xrsi = rsi(tp, 14)
    minimo = tp.rolling(21).min()
    maximo = tp.rolling(21).max()
    k = ((tp - minimo) / (maximo - minimo).replace(0, np.nan) * 100)
    stoc = k.rolling(3).mean()

    marron = (xrsi + xmf + boll_osc + stoc / 3) / 2
    verde = marron + oscp
    media = ema(marron.bfill(), m)
    return pd.DataFrame({"azul": azul, "verde": verde, "marron": marron, "media": media, "oscp": oscp})


def volumen(df, n=20):
    vol = df["Volume"].astype(float)
    return pd.DataFrame({
        "vol": vol,
        "vol_media": vol.rolling(n).mean(),
        "vol_ratio": vol / vol.rolling(n).mean().replace(0, np.nan),
        "vela_verde": df["Close"] >= df["Open"],
    })


def calcular_todo(df):
    """Un DataFrame con precio + los tres bloques, alineado por fecha."""
    partes = [df[["Open", "High", "Low", "Close", "Volume"]], macd(df["Close"]), koncorde(df), volumen(df)]
    out = pd.concat(partes, axis=1)
    out["ema50"] = ema(df["Close"], 50)
    out["ema200"] = ema(df["Close"], 200)
    return out
