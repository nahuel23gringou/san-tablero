# FUNCIONALIDAD: san_broker/precios
"""Baja precios diarios (OHLCV) de Yahoo Finance con yfinance.

Un solo pedido en lote para todo el universo y reintento individual de lo que falte.
Devuelve {simbolo: DataFrame[Open, High, Low, Close, Volume]} con índice de fechas,
sólo los que trajeron datos suficientes.
"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

COLUMNAS = ["Open", "High", "Low", "Close", "Volume"]
MINIMO_FILAS = 120  # Koncorde mira 90 ruedas para atrás + EMA 15; con menos no hay señal seria


def _hoy_incompleto():
    """True mientras la rueda de hoy sigue abierta (Nueva York). Yahoo manda la vela parcial y
    un MACD sobre una vela a medio hacer miente: se descarta hasta el cierre."""
    ahora = datetime.now(ZoneInfo("America/New_York"))
    return ahora.weekday() < 5 and ahora.hour < 17


def _limpiar(df):
    if df is None or df.empty:
        return None
    df = df[COLUMNAS].copy()
    df = df.dropna(subset=["Close"])
    df = df[df["Volume"].fillna(0) >= 0]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    if len(df) and _hoy_incompleto() and df.index[-1].date() == datetime.now(ZoneInfo("America/New_York")).date():
        df = df.iloc[:-1]
    return df if len(df) >= MINIMO_FILAS else None


def bajar(simbolos, periodo="2y", reintentos=2):
    """Baja el lote completo; lo que falte se pide de a uno (Yahoo a veces pierde tickers)."""
    resultado = {}
    try:
        lote = yf.download(list(simbolos), period=periodo, group_by="ticker",
                           auto_adjust=False, threads=True, progress=False)
    except Exception:
        lote = pd.DataFrame()

    for s in simbolos:
        df = None
        try:
            if isinstance(lote.columns, pd.MultiIndex) and s in lote.columns.get_level_values(0):
                df = _limpiar(lote[s])
            elif len(simbolos) == 1 and not lote.empty:
                df = _limpiar(lote)
        except Exception:
            df = None
        if df is not None:
            resultado[s] = df

    faltan = [s for s in simbolos if s not in resultado]
    for s in faltan:
        for intento in range(reintentos):
            try:
                df = _limpiar(yf.Ticker(s).history(period=periodo, auto_adjust=False))
                if df is not None:
                    resultado[s] = df
                    break
            except Exception:
                pass
            time.sleep(1.5 * (intento + 1))
    return resultado
