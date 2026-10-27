"""Testa se o robô consegue ler cada site do sites.yaml e mostra uma tabela.

Uso:  python -m robo.testar_sites
      python -m robo.testar_sites Senac      (testa só os sites com "Senac" no nome)

Não envia e-mail nem grava nada: só visita as páginas e conta o que achou.
"""

import sys

from bs4 import BeautifulSoup

from robo.config import carregar_sites
from robo.leitor_sites import SiteNaoLido, baixar, pausar_entre_requisicoes

# Abaixo disso a página quase não tem conteúdo: provavelmente depende de JavaScript.
MINIMO_DE_TEXTO = 1500
MINIMO_DE_LINKS = 15


def classificar(url):
    """Devolve (situação, explicação) para uma URL."""
    try:
        resposta = baixar(url)
    except SiteNaoLido as motivo:
        return "NÃO LIDO", str(motivo)

    pagina = BeautifulSoup(resposta.text, "html.parser")
    quantidade_links = len(pagina.find_all("a", href=True))
    for elemento in pagina(["script", "style", "noscript"]):
        elemento.decompose()
    tamanho_texto = len(" ".join(pagina.get_text(" ").split()))

    resumo = f"{tamanho_texto} letras de texto, {quantidade_links} links"
    if tamanho_texto < MINIMO_DE_TEXTO or quantidade_links < MINIMO_DE_LINKS:
        return "PARCIAL", f"pouco conteúdo sem JavaScript ({resumo})"
    return "LEGÍVEL", resumo


def main():
    filtro_nome = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    sites = [s for s in carregar_sites() if filtro_nome in s["nome"].lower()]

    print(f"Testando {len(sites)} site(s). Isso demora (pausa de 2-5 s entre sites)...\n")
    resultados = []
    for indice, site in enumerate(sites):
        if indice > 0:
            pausar_entre_requisicoes()
        situacao, explicacao = classificar(site["url"])
        resultados.append((site["nome"], situacao, explicacao))
        print(f"  {situacao:9} | {site['nome']} -> {explicacao}")

    print("\nResumo:")
    for situacao in ("LEGÍVEL", "PARCIAL", "NÃO LIDO"):
        total = sum(1 for _, s, _ in resultados if s == situacao)
        print(f"  {situacao:9}: {total}")


if __name__ == "__main__":
    main()
