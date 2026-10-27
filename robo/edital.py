"""Abre a página de um edital (e os PDFs dela) e junta todo o texto.

Isso é a "fase 2": só acontece para itens que já passaram na triagem
do título, porque cada edital aberto = mais visitas ao site.
"""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from robo.leitor_pdf import eh_pdf, texto_do_pdf
from robo.leitor_sites import SiteNaoLido, baixar, pausar_entre_requisicoes

MAXIMO_DE_PDFS = 2
# Entre vários PDFs na página, preferimos o de abertura/retificação ao gabarito.
NOME_DE_PDF_IMPORTANTE = re.compile(r"edital|abertura|comunicado|retifica|aviso", re.IGNORECASE)
NOME_DE_PDF_INUTIL = re.compile(r"gabarito|resultado|habilitad|convoca|classifica|recurso", re.IGNORECASE)


def _texto_da_pagina(html):
    pagina = BeautifulSoup(html, "html.parser")
    for lixo in pagina(["script", "style", "noscript", "header", "footer", "nav"]):
        lixo.decompose()
    return " ".join(pagina.get_text(" ").split())


def _pdfs_da_pagina(html, endereco):
    pagina = BeautifulSoup(html, "html.parser")
    pdfs = []
    for link in pagina.find_all("a", href=True):
        destino = urljoin(endereco, link["href"])
        nome = destino + " " + link.get_text(" ")
        if ".pdf" in destino.lower() and not NOME_DE_PDF_INUTIL.search(nome):
            pdfs.append((not NOME_DE_PDF_IMPORTANTE.search(nome), destino))
    # sorted coloca primeiro os "importantes" (False vem antes de True).
    return [destino for _, destino in sorted(dict.fromkeys(pdfs))][:MAXIMO_DE_PDFS]


def texto_completo_do_edital(link):
    """Devolve (texto, observação). Nunca levanta erro: falha vira texto vazio."""
    try:
        resposta = baixar(link)
    except SiteNaoLido as motivo:
        return "", f"não consegui abrir o edital ({motivo})"

    if eh_pdf(resposta):
        texto = texto_do_pdf(resposta.content)
        return texto, "" if texto else "PDF sem texto (talvez escaneado)"

    partes = [_texto_da_pagina(resposta.text)]
    for endereco_pdf in _pdfs_da_pagina(resposta.text, resposta.url):
        pausar_entre_requisicoes()
        try:
            resposta_pdf = baixar(endereco_pdf)
        except SiteNaoLido:
            continue
        if eh_pdf(resposta_pdf):
            partes.append(texto_do_pdf(resposta_pdf.content))
    return " ".join(partes), ""
