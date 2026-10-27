"""Testes da memória, duplicatas e do fluxo completo com sites de mentira (sem internet)."""

from datetime import date
from types import SimpleNamespace

import pytest

from robo import memoria as mem
from robo import principal
from robo import saude_sites
from robo.config import carregar_palavras_chave
from robo.leitor_sites import SiteNaoLido

PALAVRAS = carregar_palavras_chave()
HOJE = date(2026, 10, 27)

LISTAGEM = """
<html><body><ul>
  <li><a href="https://orgao.exemplo/pss-03-2026">Edital PSS nº 03/2026 - Assistente Administrativo</a></li>
  <li><a href="https://orgao.exemplo/pss-01-2026">PSS 01/2026 - Auxiliar Administrativo (encerrado)</a></li>
  <li><a href="https://orgao.exemplo/noticia">Prefeitura inaugura praça no centro</a></li>
</ul></body></html>
"""
TEXTOS = {
    "https://orgao.exemplo/pss-03-2026": "Inscrições de 01/11/2026 a 10/11/2026. Nível médio.",
    "https://orgao.exemplo/pss-01-2026": "Inscrições de 01/03/2026 a 05/03/2026. Nível médio.",
}


@pytest.fixture
def internet_falsa(monkeypatch):
    """Troca a internet por respostas prontas, e tira as pausas pra o teste ser rápido."""
    sites_fora_do_ar = set()

    def baixar_falso(url):
        if url in sites_fora_do_ar:
            raise SiteNaoLido("conexão recusada")
        return SimpleNamespace(text=LISTAGEM, url=url)

    monkeypatch.setattr(principal, "baixar", baixar_falso)
    monkeypatch.setattr(principal, "pausar_entre_requisicoes", lambda: None)
    monkeypatch.setattr(principal, "texto_completo_do_edital", lambda link: (TEXTOS.get(link, ""), ""))
    return sites_fora_do_ar


def site(nome, url="https://orgao.exemplo/editais"):
    return {"nome": nome, "url": url, "ativo": True, "confirmada": True}


def test_rodar_duas_vezes_nao_repete_aviso(internet_falsa, tmp_path):
    arquivo = tmp_path / "editais_vistos.json"

    memoria = mem.carregar(arquivo)
    primeira = principal.executar([site("Órgão X")], PALAVRAS, memoria, HOJE)
    mem.salvar(memoria, arquivo)

    avisados = principal.editais_para_avisar(primeira)
    assert [e["titulo"] for e in avisados] == ["Edital PSS nº 03/2026 - Assistente Administrativo"]
    assert avisados[0]["prazo"] == date(2026, 11, 10)

    # Segunda rodada, lendo o caderno do disco como no dia seguinte.
    memoria = mem.carregar(arquivo)
    segunda = principal.executar([site("Órgão X")], PALAVRAS, memoria, HOJE)
    assert principal.editais_para_avisar(segunda) == []
    assert segunda["analisados"] == []  # nem abre de novo os editais já vistos


def test_prazo_vencido_e_anotado_sem_aviso(internet_falsa):
    memoria = {"editais": {}}
    resultado = principal.executar([site("Órgão X")], PALAVRAS, memoria, HOJE)
    situacoes = {e["titulo"]: s for e, s in resultado["analisados"]}
    assert situacoes["PSS 01/2026 - Auxiliar Administrativo (encerrado)"] == "prazo_vencido"
    registro = memoria["editais"][mem.identificador(
        "https://orgao.exemplo/pss-01-2026", "PSS 01/2026 - Auxiliar Administrativo (encerrado)")]
    assert registro["avisado"] is False


def test_mesmo_edital_em_dois_sites_avisa_uma_vez(internet_falsa, monkeypatch):
    # A banca publica o mesmo edital com outro link e outro título.
    listagem_banca = """<ul><li><a href="https://banca.exemplo/sespa">
        Processo Seletivo Simplificado 03/2026 - Órgão X - Assistente Administrativo</a></li></ul>"""
    monkeypatch.setitem(TEXTOS, "https://banca.exemplo/sespa", "Período de inscrição: 01/11/2026 a 10/11/2026")

    def baixar_falso(url):
        return SimpleNamespace(text=listagem_banca if "banca" in url else LISTAGEM, url=url)

    monkeypatch.setattr(principal, "baixar", baixar_falso)
    memoria = {"editais": {}}
    resultado = principal.executar(
        [site("Órgão X"), site("Banca", "https://banca.exemplo/editais")], PALAVRAS, memoria, HOJE
    )
    assert len(principal.editais_para_avisar(resultado)) == 1
    assert ("duplicata" in [s for _, s in resultado["analisados"]])


def test_site_fora_do_ar_nao_derruba(internet_falsa):
    internet_falsa.add("https://quebrado.exemplo/editais")
    resultado = principal.executar(
        [site("Quebrado", "https://quebrado.exemplo/editais"), site("Órgão X")],
        PALAVRAS, {"editais": {}}, HOJE,
    )
    assert resultado["falhas"] == [("Quebrado", "conexão recusada")]
    assert resultado["sites_lidos"] == ["Órgão X"]
    assert len(principal.editais_para_avisar(resultado)) == 1


def test_erro_inesperado_no_site_nao_derruba(internet_falsa, monkeypatch):
    def baixar_que_explode(url):
        raise ValueError("HTML maluco")

    monkeypatch.setattr(principal, "baixar", baixar_que_explode)
    resultado = principal.executar([site("Órgão X")], PALAVRAS, {"editais": {}}, HOJE)
    assert resultado["sites_lidos"] == []
    assert "erro inesperado" in resultado["falhas"][0][1]


def test_site_inativo_ou_nao_confirmado_nao_e_visitado(internet_falsa):
    inativo = dict(site("Inativo"), ativo=False)
    sem_confirmar = dict(site("Sem confirmar"), confirmada=False)
    resultado = principal.executar([inativo, sem_confirmar], PALAVRAS, {"editais": {}}, HOJE)
    assert resultado["sites_lidos"] == []
    assert resultado["nao_visitados"] == ["Inativo", "Sem confirmar"]


def test_limpeza_de_itens_com_mais_de_12_meses():
    memoria = {"editais": {}}
    edital = {"id": "a", "titulo": "t", "orgao": "o", "link": "l"}
    mem.anotar(memoria, edital, avisado=True, visto_em=date(2025, 10, 1))
    mem.anotar(memoria, dict(edital, id="b"), avisado=True, visto_em=date(2026, 5, 1))
    assert mem.limpar_antigos(memoria, HOJE) == 1
    assert list(memoria["editais"]) == ["b"]


def test_chave_de_duplicata():
    assert mem.chave_de_duplicata("Edital nº 003/2026 - PSS", date(2026, 11, 10)) == "3/2026|2026-11-10"
    assert mem.chave_de_duplicata("PRS 39/2026- Belém", date(2026, 9, 30)) == "39/2026|2026-09-30"
    assert mem.chave_de_duplicata("Edital nº 03/2026", None) is None
    assert mem.chave_de_duplicata("Vaga de Auxiliar Administrativo", date(2026, 9, 30)) is None


def test_ja_rodou_hoje_e_resumo_semanal():
    saude = {"sites": {}, "execucoes": [], "ultimo_resumo_semanal": None}
    assert saude_sites.resumo_semanal_pendente(saude, HOJE)
    saude_sites.registrar_execucao(saude, HOJE, ["A"], [("B", "fora do ar")], 2)
    saude_sites.marcar_resumo_enviado(saude, HOJE)  # terça, 27/10
    assert saude_sites.ja_rodou_hoje(saude, HOJE)
    assert not saude_sites.resumo_semanal_pendente(saude, date(2026, 10, 30))  # mesma semana
    assert saude_sites.resumo_semanal_pendente(saude, date(2026, 11, 2))       # segunda seguinte

    numeros = saude_sites.numeros_da_semana(saude, date(2026, 10, 30))
    assert numeros["sites_lidos"] == ["A"]
    assert numeros["editais_novos"] == 2
    assert numeros["sites_com_falha"] == {"B": "fora do ar"}
