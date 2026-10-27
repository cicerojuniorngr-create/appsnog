"""Tira de uma página de listagem os itens (título, link, resumo, data).

Cada site tem um layout diferente, então em vez de uma receita por site
usamos uma regra geral: todo link com texto razoável é um "item", e o
bloco de texto em volta dele (linha de tabela, item de lista, card) é o
resumo. Os itens que não interessam são descartados depois pelo filtro.
"""

import re
from urllib.parse import urldefrag, urljoin

from bs4 import BeautifulSoup

TAMANHO_MINIMO_TITULO = 8
TAMANHO_MAXIMO_RESUMO = 400
BLOCOS_DE_ITEM = ("li", "tr", "article", "p", "div")
DATA_PUBLICACAO = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
# Lixo de acessibilidade que alguns sites colocam no texto do link.
TEXTO_DE_ACESSIBILIDADE = re.compile(r"\((?:abre|abrir)[^)]*\)", re.IGNORECASE)


def _texto_limpo(elemento):
    return " ".join(elemento.get_text(" ").split())


def _link_vale_a_pena(endereco):
    endereco_minusculo = endereco.lower()
    return endereco_minusculo.startswith("http") and not any(
        rede in endereco_minusculo
        for rede in ("facebook.com", "instagram.com", "twitter.com", "x.com/", "whatsapp", "youtube.com")
    )


def _resumo_em_volta(link):
    """Sobe na árvore do HTML até achar o bloco que "embrulha" o link."""
    for bloco in link.parents:
        if bloco.name in BLOCOS_DE_ITEM:
            texto = _texto_limpo(bloco)
            if len(texto) > TAMANHO_MAXIMO_RESUMO:
                return ""  # Subiu demais: virou a página inteira.
            if len(texto) > len(_texto_limpo(link)) + 10:
                return texto
    return ""


def extrair_itens(html, endereco_da_pagina):
    pagina = BeautifulSoup(html, "html.parser")
    for lixo in pagina(["script", "style", "noscript", "header", "footer", "nav"]):
        lixo.decompose()

    itens = {}
    for link in pagina.find_all("a", href=True):
        titulo = TEXTO_DE_ACESSIBILIDADE.sub("", _texto_limpo(link)).strip()
        endereco = urldefrag(urljoin(endereco_da_pagina, link["href"]))[0]
        if len(titulo) < TAMANHO_MINIMO_TITULO or not _link_vale_a_pena(endereco):
            continue
        if endereco.rstrip("/") == urldefrag(endereco_da_pagina)[0].rstrip("/"):
            continue  # "Pular para o conteúdo" e afins apontam pra própria página.
        if endereco in itens:
            continue  # Mesmo link repetido (ex.: imagem + título do mesmo card).
        resumo = _resumo_em_volta(link)
        data = DATA_PUBLICACAO.search(resumo)
        itens[endereco] = {
            "titulo": titulo,
            "link": endereco,
            "resumo": resumo,
            "data_publicacao": data.group(0) if data else None,
        }
    return list(itens.values())
