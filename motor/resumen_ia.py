# FUNCIONALIDAD: san_broker/resumen_ia
"""Resumen diario del mercado con Gemini a partir de titulares (nunca cuerpos de nota).

Si no hay GEMINI_API_KEY o la llamada falla, devuelve un dict con "error" y el tablero sale
igual, avisando que ese día no hubo resumen. La IA no decide nada: sólo resume y etiqueta
el tono de las noticias por activo.

El mensaje de error nunca incluye la URL ni la key (27/10/2026: un 429 metió la URL con la
key en datos.json y GitHub frenó el push dos días seguidos).
"""
import json
import os
import time

import requests

MODELO = os.environ.get("GEMINI_MODELO", "gemini-2.5-flash")
URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={key}"
REINTENTOS = 4
ESPERA = 30  # segundos entre reintentos ante 429 / 5xx

INSTRUCCION = """Sos un analista financiero que escribe para un inversor argentino minorista.
Te doy titulares y bajadas de noticias de las últimas 48 horas (medios argentinos e internacionales)
y la lista de activos que sigue el inversor con su señal técnica del día.

Devolvé SOLO un JSON con esta forma exacta:
{
  "resumen_mercado": ["frase 1", "frase 2", "frase 3", "frase 4", "frase 5"],
  "clima": "positivo" | "negativo" | "mixto",
  "activos": {
    "SIMBOLO": {"tono": -1 | 0 | 1, "nota": "una frase concreta sobre qué dice la noticia de ese activo"}
  },
  "para_mirar": ["hasta 3 frases sobre hechos que pueden mover el mercado hoy (balances, Fed, dólar, riesgo país)"]
}

Reglas:
- resumen_mercado: 5 frases cortas, en español rioplatense neutro, sin adjetivos vacíos. Qué pasó y por qué importa.
- activos: SOLO los símbolos de la lista que tengan al menos una noticia relevante. tono -1 negativo, 0 neutro, 1 positivo.
- No inventes datos ni cifras que no estén en los titulares. Si no hay noticias de un activo, no lo incluyas.
- No des recomendaciones de compra o venta: describí hechos y tono.
"""


def resumir(noticias, activos_con_senal, key=None, maximo=140):
    key = key or os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    if not noticias:
        return {"error": "sin noticias"}
    lineas = []
    for n in noticias[:maximo]:
        lineas.append(f"- [{n['fuente']}] {n['titulo']}" + (f" — {n['bajada']}" if n.get("bajada") else ""))
    lista = ", ".join(f"{a['simbolo']} ({a['nombre']}: {a.get('etiqueta', a.get('senal', ''))})" for a in activos_con_senal)
    prompt = INSTRUCCION + "\n\nACTIVOS QUE SIGUE:\n" + lista + "\n\nTITULARES:\n" + "\n".join(lineas)
    cuerpo = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    error = "sin respuesta"
    for intento in range(REINTENTOS):
        try:
            r = requests.post(URL.format(modelo=MODELO, key=key), json=cuerpo, timeout=90)
            if r.status_code in (429, 500, 502, 503, 504):
                error = f"Gemini respondió HTTP {r.status_code}"
                time.sleep(ESPERA * (intento + 1))
                continue
            r.raise_for_status()
            texto = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            datos = json.loads(texto)
            break
        except requests.HTTPError as e:
            return {"error": f"Gemini respondió HTTP {e.response.status_code if e.response is not None else '?'}"}
        except Exception as e:
            error = f"{type(e).__name__} al llamar a Gemini"
            time.sleep(ESPERA)
    else:
        return {"error": error + f" ({REINTENTOS} intentos)"}
    datos.setdefault("resumen_mercado", [])
    datos.setdefault("activos", {})
    datos.setdefault("para_mirar", [])
    datos.setdefault("clima", "mixto")
    datos["modelo"] = MODELO
    return datos
