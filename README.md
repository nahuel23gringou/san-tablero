<!-- FUNCIONALIDAD: san_broker/documentacion -->
# SAN · Señales de mercado

Tablero diario para Santiago: cada día hábil, antes de la apertura, se bajan los precios de 50
instrumentos (28 CEDEARs y 22 acciones argentinas), se calculan Williams %R (14) y el histograma
del MACD (12, 26, 9), y se publica una página con la señal de cada activo según el **machete de
trading** que definió Santiago el 27/10/2026, más un resumen del día hecho por IA a partir de
titulares y las noticias vinculadas a cada activo.

| Señal | Williams %R (14) | Histograma MACD |
|---|---|---|
| Compra fuerte | -80 a -50 | hoy entre -0,5 y 0,5 |
| Compra cauta | -50 a -20 | 0,1 a 0,7 |
| Mantener | -50 a -20 | 0,7 a 3,0 |
| No comprar (FOMO) | -20 a 0 | > 3,0 |
| Alerta salida | hoy > -20 | hoy > 0 y hoy < ayer |
| Venta fuerte | no importa | ayer > 0 y hoy < 0 |

Las dos columnas tienen que cumplirse a la vez. Lo que no cae en ninguna fila queda **Sin señal**,
con los dos números a la vista. El histograma se compara expresado **por cada US$100 de precio**
(`histograma_base` en `config/machete.json`); con `"absoluto"` se usa el número crudo de TradingView.

**No opera.** Fase 1 = mostrar. Operar por API de InvertirOnline es fase 2 y exige dictamen
jurídico propio antes de escribir la primera línea.

## Cómo corre

```
pip install -r requirements.txt
python3 prueba.py                # casos del motor, sin internet
python3 generar.py --sin-ia      # baja precios, calcula, deja docs/datos.json
GEMINI_API_KEY=... python3 generar.py   # con resumen IA
python3 -m http.server 8765 --directory docs   # abrir http://localhost:8765
```

En GitHub corre solo: `.github/workflows/diario.yml` (cron 08:30 UTC lunes a viernes; GitHub lo
atrasa varias horas) genera `docs/` y lo commitea. La key de Gemini va en *Settings → Secrets →
Actions → GEMINI_API_KEY*.

## Estructura

```
config/activos.json    universo de 50 (símbolo Yahoo, símbolo en IOL, categoría, alias para noticias)
config/machete.json    umbrales de las seis señales, períodos de los indicadores, base del histograma
motor/precios.py       yfinance, lote + reintento; descarta la vela de hoy si la rueda está abierta
motor/indicadores.py   MACD, Williams %R, volumen, EMAs (pandas puro)
motor/senales.py       el machete: clasificar(williams, hist_hoy, hist_ayer) -> señal + razón
motor/noticias.py      RSS (Ámbito, Cronista, Infobae, iProfesional, Yahoo, CNBC, MarketWatch)
motor/resumen_ia.py    Gemini: resumen del día + tono por activo (sólo titulares; reintenta ante 429)
generar.py             orquesta y escribe docs/datos.json + docs/historial/
docs/index.html        la página: botón CEDEARs / Acciones, filtro por señal, orden de compra a venta
prueba.py              casos del motor (una fila del machete por caso, bordes, series sintéticas)
```

## Ajustar

- Umbrales o períodos: `config/machete.json`.
- Cambiar un instrumento: `config/activos.json` (sacar una línea, poner otra; son 50).

## Marco

Herramienta de apoyo para uso personal; no es asesoramiento ni recomendación. Datos de Yahoo
Finance vía yfinance (uso personal, no comercial). Titulares con link a la fuente (Ley 11.723
art. 28). Resumen IA rotulado como tal. ADR-0014 y DICTAMEN_004 en NEURON P.
