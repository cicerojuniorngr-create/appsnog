"""Decide se um edital interessa, usando as listas do palavras_chave.yaml.

A regra completa está explicada no topo do palavras_chave.yaml.
"""

from robo.texto import achatar, normalizar, termos_encontrados


def parece_selecao(titulo_e_resumo, palavras):
    """O título/resumo fala de PSS, seleção, credenciamento...?"""
    return bool(termos_encontrados(normalizar(titulo_e_resumo), palavras["tipos_selecao"]))


def cita_o_perfil(titulo_e_resumo, palavras):
    """O título/resumo já cita um cargo ou área do perfil?"""
    termos = achatar(palavras["cargos"]) + achatar(palavras["areas"])
    return bool(termos_encontrados(normalizar(titulo_e_resumo), termos))


def esta_bloqueado(titulo, resumo, palavras):
    if termos_encontrados(normalizar(f"{titulo} {resumo}"), palavras["bloqueio"]):
        return True
    return bool(termos_encontrados(normalizar(titulo), palavras.get("nao_e_abertura", [])))


def passa_na_triagem(titulo, resumo, palavras, pagina_so_de_vagas=False):
    """Etapa 1, só com o que aparece na listagem (sem abrir o edital).

    Serve pra não visitar à toa centenas de notícias que nada têm a ver.
    """
    if esta_bloqueado(titulo, resumo, palavras):
        return False
    titulo_e_resumo = f"{titulo} {resumo}"
    if pagina_so_de_vagas:
        # Página que só lista vagas: título sem "processo seletivo", mas com o
        # nome do cargo. Se o cargo não for do perfil, nem abre.
        return cita_o_perfil(titulo_e_resumo, palavras)
    return parece_selecao(titulo_e_resumo, palavras)


def cargos_do_perfil(titulo_e_resumo, texto_do_edital, palavras):
    """Devolve a lista de cargos/áreas do perfil encontrados (vazia = não interessa)."""
    cabecalho = normalizar(titulo_e_resumo)
    corpo = normalizar(texto_do_edital)

    cargos = termos_encontrados(cabecalho + " | " + corpo, achatar(palavras["cargos"]))

    areas = termos_encontrados(cabecalho, achatar(palavras["areas"]))
    if areas and termos_encontrados(cabecalho, palavras["fora_do_perfil"]):
        # Ex.: "PSS para Contador - orçamento": a área sozinha não basta.
        areas = []

    return cargos + [area for area in areas if area not in cargos]


def avaliar(titulo, resumo, texto_do_edital, palavras, pagina_so_de_vagas=False):
    """Diz se o item interessa e por quê.

    Devolve (interessa: bool, motivo: str, cargos: list).
    """
    if not passa_na_triagem(titulo, resumo, palavras, pagina_so_de_vagas):
        return False, "não passou na triagem do título", []
    cargos = cargos_do_perfil(f"{titulo} {resumo}", texto_do_edital, palavras)
    if not cargos:
        return False, "nenhum cargo do perfil", []
    return True, "ok", cargos
