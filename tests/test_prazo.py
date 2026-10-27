"""Testes da extração de prazo. Vários trechos são cópia de editais reais."""

from datetime import date

import pytest

from robo.prazo import TEXTO_SEM_PRAZO, extrair_prazo, formatar_prazo

REFERENCIA = date(2026, 10, 27)


@pytest.mark.parametrize(
    "texto, esperado",
    [
        # --- Trechos reais ---
        # Senac PA, PRS 39/2026 (texto corrido)
        (
            "5.1.3 As inscrições ficarão abertas através da Internet, no período de "
            "29/09/2026 a 30/09/2026 e serão recebidas dentro do período divulgado pelo SENAC/PA.",
            date(2026, 9, 30),
        ),
        # Senac PA, PRS 39/2026 (tabela do cronograma: data ANTES da palavra)
        (
            "PERÍODO ETAPAS 29/09/2026 Lançamento do Comunicado de Vaga 29/09/2026 a "
            "30/09/2026 Inscrição 09/10/2026 Divulgação da Lista de Aprovados para a Prova "
            "17/10/2026 Prova de Conhecimentos 19/10/2026 Gabarito Preliminar 19/10 e "
            "20/10/2026 Solicitação de Recursos",
            date(2026, 9, 30),
        ),
        # Sesc PA, Auxiliar Administrativo (crase e dia sem mês no início)
        (
            "Atividade Período Divulgação da vaga 23/10/2026 Prazo para envio de currículos "
            "23 à 26/10/2026 Divulgação dos habilitados para realização da Prova de "
            "Conhecimentos 30/10/2026",
            date(2026, 10, 26),
        ),
        # --- Formatos pedidos pelo dono ---
        ("As inscrições estarão abertas até 15 de novembro de 2026.", date(2026, 11, 15)),
        ("Inscrições de 10/11 a 20/11.", date(2026, 11, 20)),
        # --- Outras variações comuns ---
        ("Período de inscrição: 10 a 20 de novembro de 2026", date(2026, 11, 20)),
        ("Inscrições: de 03/11/2026 a 07/11/2026, exclusivamente pela internet.", date(2026, 11, 7)),
        ("As inscrições poderão ser feitas até o dia 05/12/2026.", date(2026, 12, 5)),
        (
            "As inscrições serão realizadas no período compreendido entre as 10h do dia "
            "10/11/2026 e as 23h59 do dia 20/11/2026.",
            date(2026, 11, 20),
        ),
        ("Inscrições das 8h do dia 01/12/2026 às 23h59 do dia 04/12/2026", date(2026, 12, 4)),
        ("Inscrições: 01/12/26 a 04/12/26", date(2026, 12, 4)),
        ("período de inscrição: 1º de dezembro de 2026 a 4 de dezembro de 2026", date(2026, 12, 4)),
        # Edital de dezembro falando de janeiro, sem ano: vira o ano seguinte.
        ("Inscrições de 05/01 a 15/01.", date(2027, 1, 15)),
    ],
)
def test_acha_prazo(texto, esperado):
    assert extrair_prazo(texto, REFERENCIA) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        # Sem nenhuma data perto de "inscrição".
        "As inscrições serão divulgadas em breve no site oficial.",
        # Datas de outros assuntos não podem virar prazo de inscrição.
        "Resultado das inscrições homologadas: 25/11/2026.",
        "Pedido de isenção da taxa de inscrição de 01/11/2026 a 03/11/2026.",
        "Recurso contra o indeferimento da inscrição: 10/11/2026 a 11/11/2026.",
        # Data solta sem "até" nem período: não dá pra saber se é início ou fim.
        "Inscrição 09/10/2026 Divulgação da lista",
        # Duas datas finais diferentes: não chuta, devolve "não identificado".
        "Inscrições presenciais de 01/11/2026 a 05/11/2026. "
        "Inscrições online de 01/11/2026 a 10/11/2026.",
        # Data impossível.
        "Inscrições de 25/02/2026 a 31/02/2026.",
        # Texto vazio.
        "",
    ],
)
def test_nao_chuta_prazo(texto):
    assert extrair_prazo(texto, REFERENCIA) is None


def test_formatar_prazo():
    assert formatar_prazo(date(2026, 11, 5)) == "05/11/2026"
    assert formatar_prazo(None) == TEXTO_SEM_PRAZO
    assert TEXTO_SEM_PRAZO == "Prazo não identificado, confira o edital"
