"""
Configuración compartida de la suite.

Contiene la barrera que impide que los tests llamen al endpoint web de Google
Translate. Ver docs/legal/COMPLIANCE-REVIEW.md, hallazgo H-11.
"""

import json
import urllib.parse
import urllib.request

import pytest

_REAL_URLOPEN = urllib.request.urlopen
_TRANSLATE_HOST = "translate.googleapis.com"


class _EchoTranslateResponse:
    """
    Imita la respuesta de `translate_a/single` devolviendo el texto recibido.

    La identidad es deliberada: el camino gratuito sustituye los términos del
    glosario por marcadores `__SKY_n__` antes de enviar el texto y los restaura
    al recibirlo. Devolviendo la entrada intacta, el marcador sobrevive al viaje
    y el test ejercita la lógica real de protección y restauración, que es la
    unidad bajo prueba. Lo que no se ejercita es la calidad de la traducción de
    Google, que nunca fue responsabilidad de este repositorio.
    """

    def __init__(self, text: str):
        self._text = text

    def read(self) -> bytes:
        return json.dumps([[[self._text, self._text, None, None, 0]]]).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _extract_query_text(url: str) -> str:
    """Recupera el parámetro `q` de la URL de traducción."""
    query = urllib.parse.urlparse(url).query
    values = urllib.parse.parse_qs(query).get("q", [""])
    return values[0]


@pytest.fixture(autouse=True)
def block_google_translate_network(monkeypatch):
    """
    Intercepta las llamadas a `translate.googleapis.com` en toda la suite.

    Existe por dos motivos:

    1. **Cumplimiento.** Ese endpoint es interno de Google y su uso programado
       queda fuera de sus Términos de Servicio. Sin esta barrera, cada push y
       cada pull request generaban tráfico no autorizado contra un tercero desde
       la infraestructura de CI.
    2. **Determinismo.** Los tests que lo llamaban fallaban con `HTTP 429: Too
       Many Requests` en cuanto Google limitaba la IP del runner, convirtiendo
       la suite en un test de la cuota de Google y no del código.

    Cualquier otro destino pasa sin tocar al `urlopen` real, así que los tests
    que simulan otras APIs (el camino LLM, por ejemplo) no se ven afectados.
    """

    def _guarded_urlopen(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if _TRANSLATE_HOST in url:
            return _EchoTranslateResponse(_extract_query_text(url))
        return _REAL_URLOPEN(req, *args, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", _guarded_urlopen)
