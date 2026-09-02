<!-- FUNCIONALIDAD: san_broker/documentacion -->
# SAN · Tablero de señales

Tablero diario para Santiago: todos los días hábiles a las 08:00 (Argentina), antes de la apertura,
se bajan los precios de ~90 activos (CEDEARs, ETFs y acciones argentinas), se calculan MACD,
Koncorde (fórmula publicada por Blai5) y volumen, se arma un score ponderado y se publica una
página con la lectura de cada activo (alcista / bajista / neutral), las razones, un resumen del
día hecho por IA a partir de titulares, y las noticias vinculadas a cada activo.

Nace de la charla del 09/04/2026 en la que Santiago explicó cómo lee TradingView: el cruce de la
línea azul sobre la naranja del MACD, la línea de flotación, el histograma y el volumen.

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

En GitHub corre solo: `.github/workflows/diario.yml` (cron 11:00 UTC lunes a viernes) genera
`docs/` y lo commitea. La key de Gemini va en *Settings → Secrets → Actions → GEMINI_API_KEY*.

## Estructura

```
config/activos.json    universo (símbolo Yahoo, símbolo en IOL, alias para noticias)
config/pesos.json      ponderación de cada indicador y umbrales de la señal
motor/precios.py       yfinance, lote + reintento; descarta la vela de hoy si la rueda está abierta
motor/indicadores.py   MACD, Koncorde, volumen, EMAs (pandas puro)
motor/senales.py       reglas de la charla -> componentes [-1, 1] -> score -> señal + razones
motor/noticias.py      RSS (Ámbito, Cronista, Infobae, iProfesional, Yahoo, CNBC, MarketWatch)
motor/resumen_ia.py    Gemini: resumen del día + tono por activo (sólo titulares)
generar.py             orquesta y escribe docs/datos.json + docs/historial/
docs/index.html        la página (lee datos.json)
prueba.py              casos del motor con series sintéticas
```

## Ajustar la lectura

- Cambiar qué pesa más: `config/pesos.json` (suman 100). Umbrales `comprar` / `vender` sobre el score.
- Agregar o sacar activos: `config/activos.json`. Para CEDEARs se usa el ticker de origen en USD.
- Las reglas en palabras están en el encabezado de `motor/senales.py`.

## Marco

Herramienta de apoyo para uso personal; no es asesoramiento ni recomendación. Datos de Yahoo
Finance vía yfinance (uso personal, no comercial). Titulares con link a la fuente (Ley 11.723
art. 28). Resumen IA rotulado como tal. Dictamen jurídico del 02/09/2026: ver
`Areas/Juridica` en NEURON P.
