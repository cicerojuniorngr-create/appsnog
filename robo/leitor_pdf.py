"""Extrai o texto de um edital em PDF.

Se o PDF for escaneado (foto do papel), não há texto pra extrair: devolve
vazio e o e-mail sai com "Prazo não identificado, confira o edital".
"""

import io
import logging

from pypdf import PdfReader

MAXIMO_DE_PAGINAS = 40  # Prazo e cargos ficam no começo; anexo gigante só atrasa.
TAMANHO_MAXIMO_BYTES = 20 * 1024 * 1024

# O pypdf reclama muito de PDF "malformado" de órgão público; não é problema nosso.
logging.getLogger("pypdf").setLevel(logging.ERROR)


def eh_pdf(resposta):
    tipo = resposta.headers.get("Content-Type", "").lower()
    return "pdf" in tipo or resposta.content[:5] == b"%PDF-"


def texto_do_pdf(conteudo):
    if len(conteudo) > TAMANHO_MAXIMO_BYTES:
        return ""
    try:
        leitor = PdfReader(io.BytesIO(conteudo))
        paginas = leitor.pages[:MAXIMO_DE_PAGINAS]
        return " ".join((pagina.extract_text() or "") for pagina in paginas)
    except Exception:
        # PDF corrompido ou protegido: segue sem texto em vez de travar o robô.
        return ""
