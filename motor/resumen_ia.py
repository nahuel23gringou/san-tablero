# FUNCIONALIDAD: san_broker/resumen_ia
"""Resumen diario del mercado con IA a partir de titulares (nunca cuerpos de nota).

Proveedor: Claude (ANTHROPIC_API_KEY) si está la clave; si no, Gemini (GEMINI_API_KEY).
Sin ninguna de las dos, o si la llamada falla, devuelve un dict con "error" y el tablero
sale igual, avisando que ese día no hubo resumen. La IA no decide nada: sólo resume y
etiqueta el tono de las noticias por activo.

El mensaje de error nunca incluye URL ni clave (27/10/2026: un 429 de Gemini metió la URL
con la key en datos.json y GitHub frenó el push dos días seguidos).
"""
import json
import os
import re
import time

import requests

MODELO_CLAUDE = os.environ.get("CLAUDE_MODELO", "claude-opus-5-5")
MODELO_GEMINI = os.environ.get("GEMINI_MODELO", "gemini-2.5-flash")
URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={key}"
REINTENTOS = 4
ESPERA = 30  # segundos entre reintentos ante 429 / 5xx

INSTRUCCION = """Sos un analista financiero que escribe para un inversor argentino minorista.
Te doy titulares y bajadas de noticias de las últimas 48 horas (medios argentinos e internacionales)
y la lista de activos que sigue el inversor con su señal técnica del día.

Devolvé SOLO un JSON con esta forma exacta, sin texto antes ni después:
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


def _prompt(noticias, activos_con_senal, maximo):
    lineas = []
    for n in noticias[:maximo]:
        lineas.append(f"- [{n['fuente']}] {n['titulo']}" + (f" — {n['bajada']}" if n.get("bajada") else ""))
    lista = ", ".join(f"{a['simbolo']} ({a['nombre']}: {a.get('etiqueta', a.get('senal', ''))})" for a in activos_con_senal)
    return INSTRUCCION + "\n\nACTIVOS QUE SIGUE:\n" + lista + "\n\nTITULARES:\n" + "\n".join(lineas)


def _json_de(texto):
    """El modelo devuelve sólo JSON, pero por las dudas se toma del primer { al último }."""
    i, j = texto.find("{"), texto.rfind("}")
    if i < 0 or j < 0:
        raise ValueError("sin JSON en la respuesta")
    return json.loads(texto[i:j + 1])


def _completar(datos, modelo):
    datos.setdefault("resumen_mercado", [])
    datos.setdefault("activos", {})
    datos.setdefault("para_mirar", [])
    datos.setdefault("clima", "mixto")
    datos["modelo"] = modelo
    return datos


def _con_claude(prompt, key):
    import anthropic

    client = anthropic.Anthropic(api_key=key, max_retries=3)
    try:
        r = client.beta.messages.create(
            model=MODELO_CLAUDE,
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system="Respondés únicamente con el JSON pedido.",
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.RateLimitError:
        return {"error": "Claude respondió HTTP 429 (límite de uso o crédito agotado)"}
    except anthropic.AuthenticationError:
        return {"error": "Claude rechazó la clave (ANTHROPIC_API_KEY inválida)"}
    except anthropic.APIStatusError as e:
        return {"error": f"Claude respondió HTTP {e.status_code}"}
    except anthropic.APIConnectionError:
        return {"error": "sin conexión con Claude"}
    if r.stop_reason == "refusal":
        return {"error": "Claude no quiso responder (refusal)"}
    texto = "".join(b.text for b in r.content if b.type == "text")
    try:
        return _completar(_json_de(texto), r.model)
    except (ValueError, json.JSONDecodeError):
        return {"error": "Claude no devolvió un JSON válido"}


def _con_gemini(prompt, key):
    cuerpo = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    error = "sin respuesta"
    for intento in range(REINTENTOS):
        try:
            r = requests.post(URL_GEMINI.format(modelo=MODELO_GEMINI, key=key), json=cuerpo, timeout=90)
            if r.status_code in (429, 500, 502, 503, 504):
                error = f"Gemini respondió HTTP {r.status_code}"
                time.sleep(ESPERA * (intento + 1))
                continue
            r.raise_for_status()
            texto = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return _completar(_json_de(texto), MODELO_GEMINI)
        except requests.HTTPError as e:
            return {"error": f"Gemini respondió HTTP {e.response.status_code if e.response is not None else '?'}"}
        except Exception as e:
            error = f"{type(e).__name__} al llamar a Gemini"
            time.sleep(ESPERA)
    return {"error": error + f" ({REINTENTOS} intentos)"}


def resumir(noticias, activos_con_senal, maximo=140):
    key_claude = os.environ.get("ANTHROPIC_API_KEY")
    key_gemini = os.environ.get("GEMINI_API_KEY")
    if not key_claude and not key_gemini:
        return None
    if not noticias:
        return {"error": "sin noticias"}
    prompt = _prompt(noticias, activos_con_senal, maximo)
    if key_claude:
        return _con_claude(prompt, key_claude)
    return _con_gemini(prompt, key_gemini)
