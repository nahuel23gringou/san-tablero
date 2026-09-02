# FUNCIONALIDAD: san_broker/noticias
"""Lee feeds RSS públicos y vincula cada noticia con los activos del universo.

Sólo título + bajada corta del propio feed + fuente + link (Ley 11.723 art. 28: las
noticias de interés general pueden retransmitirse citando la fuente). Nunca el cuerpo
del artículo ni imágenes.
"""
import re
import time
from datetime import datetime, timedelta, timezone

import feedparser

FEEDS = [
    # Argentina
    ("Ámbito", "https://www.ambito.com/rss/finanzas.xml"),
    ("Ámbito", "https://www.ambito.com/rss/economia.xml"),
    ("El Cronista", "https://www.cronista.com/files/rss/finanzas.xml"),
    ("El Cronista", "https://www.cronista.com/files/rss/economia-politica.xml"),
    ("Infobae", "https://www.infobae.com/arc/outboundfeeds/rss/category/economia/"),
    ("iProfesional", "https://www.iprofesional.com/rss/finanzas"),
    # Internacional
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("CNBC", "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    ("CNBC", "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_marketpulse"),
]

MAX_BAJADA = 220


def _fecha(entrada):
    for campo in ("published_parsed", "updated_parsed"):
        t = entrada.get(campo)
        if t:
            try:
                return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
            except Exception:
                pass
    return None


def _limpiar_html(texto):
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    texto = re.sub(r"\s+", " ", texto).strip()
    if len(texto) > MAX_BAJADA:
        texto = texto[:MAX_BAJADA].rsplit(" ", 1)[0] + "…"
    return texto


def leer(feeds=FEEDS, horas=48):
    limite = datetime.now(timezone.utc) - timedelta(hours=horas)
    vistas = set()
    noticias = []
    for fuente, url in feeds:
        try:
            fp = feedparser.parse(url)
        except Exception:
            continue
        for e in fp.entries[:60]:
            titulo = _limpiar_html(e.get("title", ""))
            link = e.get("link", "")
            if not titulo or not link or link in vistas:
                continue
            fecha = _fecha(e)
            if fecha and fecha < limite:
                continue
            vistas.add(link)
            noticias.append({
                "titulo": titulo,
                "bajada": _limpiar_html(e.get("summary", "") or e.get("description", "")),
                "fuente": fuente,
                "link": link,
                "fecha": fecha.isoformat() if fecha else None,
            })
    noticias.sort(key=lambda n: n["fecha"] or "", reverse=True)
    return noticias


def _patron(alias):
    partes = [re.escape(a.strip()) for a in alias if a.strip()]
    return re.compile(r"(?<![\w])(" + "|".join(partes) + r")(?![\w])", re.IGNORECASE) if partes else None


def vincular(noticias, activos):
    """Devuelve {simbolo: [noticias]} buscando alias en título + bajada."""
    patrones = {a["simbolo"]: _patron(a.get("alias", []) + [a["simbolo"]] if len(a["simbolo"]) >= 3 else a.get("alias", []))
                for a in activos}
    por_activo = {a["simbolo"]: [] for a in activos}
    for n in noticias:
        texto = n["titulo"] + " " + n["bajada"]
        for simbolo, p in patrones.items():
            if p and p.search(texto):
                por_activo[simbolo].append(n)
    return por_activo
