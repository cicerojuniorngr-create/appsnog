"""Testes do filtro, usando o palavras_chave.yaml de verdade.

Se alguém editar o YAML e quebrar uma regra importante, estes testes avisam.
"""

import pytest

from robo.config import carregar_palavras_chave
from robo.filtro import avaliar
from robo.texto import contem_termo, normalizar

PALAVRAS = carregar_palavras_chave()


def interessa(titulo, resumo="", texto="", pagina_so_de_vagas=False):
    return avaliar(titulo, resumo, texto, PALAVRAS, pagina_so_de_vagas)[0]


# ------------------------- DEVE PASSAR -------------------------

@pytest.mark.parametrize(
    "titulo, resumo, texto",
    [
        ("PSS 03/2026 - Assistente Administrativo", "", ""),
        ("Processo Seletivo Simplificado nº 01/2026", "Vagas para Auxiliar Administrativo e Motorista", ""),
        ("Edital de Contratação Temporária - Agente Administrativo", "", ""),
        ("Seleção Pública - Analista Financeiro", "", ""),
        ("PSS 02/2026 - Técnico em RH", "", ""),
        ("Processo seletivo: Assistente de Departamento Pessoal", "", ""),
        ("Processo Seletivo - Setor de Folha de Pagamento", "", ""),
        ("Credenciamento para serviços de faturamento", "", ""),
        ("Cadastro Reserva - Contas a Pagar e Contas a Receber", "", ""),
        # Edital genérico: o cargo só aparece dentro do edital.
        (
            "Edital PSS nº 05/2026 - diversos cargos",
            "",
            "Cargos: Médico, Enfermeiro, Técnico de Enfermagem, Assistente Administrativo, Motorista.",
        ),
        # "Contabilidade" como tarefa de um cargo financeiro NÃO derruba.
        (
            "PSS - Assistente Financeiro",
            "Atribuições: apoiar a contabilidade, conciliação bancária e contas a pagar.",
            "",
        ),
        # Real: UEPA 080/2026 cita Agente Administrativo-A.
        (
            "Edital nº 080/2026 - Processo Seletivo Simplificado UEPA",
            "",
            "para as funções de Técnico-A e Agente Administrativo-A, entrevista",
        ),
        # Acento e maiúscula não importam.
        ("PROCESSO SELETIVO - ASSISTENTE ADMINISTRATIVO", "", ""),
        ("processo seletivo - tecnico administrativo", "", ""),
    ],
)
def test_passa(titulo, resumo, texto):
    assert interessa(titulo, resumo, texto)


def test_pagina_so_de_vagas_pula_a_etapa_1():
    # Títulos reais do Senac e do Sesc: não têm "processo seletivo" no nome.
    titulo_senac = "PRS 39/2026- Belém - Assistente de Administração - Almoxarifado/Infraestrutura"
    assert interessa(titulo_senac, pagina_so_de_vagas=True)
    assert interessa("Auxiliar Administrativo I", pagina_so_de_vagas=True)
    assert not interessa("Auxiliar Administrativo I", pagina_so_de_vagas=False)


# ------------------------- NÃO DEVE PASSAR -------------------------

@pytest.mark.parametrize(
    "titulo, resumo, texto",
    [
        # Contador (exige CRC), mesmo falando em orçamento.
        ("PSS 04/2026 - Contador", "Elaboração de orçamento e balanços", ""),
        ("Processo Seletivo - Técnico em Contabilidade", "Atuar na tesouraria", ""),
        # Estágio.
        ("Processo Seletivo de Estágio - Assistente Administrativo", "", ""),
        ("Seleção de Estagiários para área administrativa", "", ""),
        # Saúde.
        ("PSS - Médico Plantonista", "", ""),
        ("PSS Hemopa 02/2026 - Enfermeiro", "", ""),
        ("Processo Seletivo - Técnico de Enfermagem e Farmacêutico", "", ""),
        # Engenharia / TI.
        ("Seleção Pública - Engenheiro Civil", "", ""),
        ("PSS Prodepa - Analista de TI", "", ""),
        ("Processo Seletivo - Tecnologia da Informação", "Orçamento de projetos de TI", ""),
        # Concurso público tradicional (fora do MVP).
        ("Concurso Público 2026 - Assistente Administrativo", "", ""),
        # Não é seleção.
        ("Edital de Licitação - Pregão Eletrônico 12/2026", "", ""),
        ("Assistente Administrativo recebe homenagem", "", ""),
        # "Recursos Humanos" como nome de setor dentro do edital não conta.
        (
            "PSS 07/2026 - Agente de Portaria",
            "",
            "Os documentos deverão ser entregues na Diretoria de Recursos Humanos e Gestão de Pessoas.",
        ),
        # "Secretaria de Estado" não é o cargo de secretária.
        ("PSS da Secretaria de Estado de Saúde - Vigilante", "", ""),
    ],
)
def test_nao_passa(titulo, resumo, texto):
    assert not interessa(titulo, resumo, texto)


def test_estagio_no_corpo_do_edital_nao_bloqueia():
    # Frase comum em PSS: não pode derrubar um edital bom.
    texto = "Não será considerado estágio como experiência profissional. Cargo: Auxiliar Administrativo."
    assert interessa("Processo Seletivo Simplificado 01/2026", "", texto)


def test_cargos_encontrados_sao_listados():
    _, _, cargos = avaliar(
        "PSS - diversos cargos", "", "Assistente Administrativo, Médico e Analista Financeiro", PALAVRAS
    )
    assert cargos == ["assistente administrativo", "analista financeiro"]


def test_palavra_inteira():
    assert not contem_termo(normalizar("Atividades diversas"), "TI")
    assert contem_termo(normalizar("Analista de TI"), "ti")


@pytest.mark.parametrize(
    "titulo",
    [
        # Real (Santa Bárbara do Pará): chamada de aprovados, não inscrição nova.
        "Edital de Convocação 001/2025-PMSBP/SEMSAU – Processo Seletivo Público Nº 001/2023",
        "Resultado Final do PSS 02/2026 - Assistente Administrativo",
        "PRS 039/2026 - Gabarito Oficial - Assistente de Administração",
        "Homologação das inscrições - Processo Seletivo - Auxiliar Administrativo",
    ],
)
def test_publicacao_de_processo_andando_nao_passa(titulo):
    assert not interessa(titulo)


def test_retificacao_passa():
    # Retificação pode prorrogar prazo: tem que avisar.
    assert interessa("Retificação do Edital do PSS 03/2026 - Assistente Administrativo")


def test_menu_do_site_nao_passa_em_pagina_so_de_vagas():
    assert not interessa("Espaço do Cliente", pagina_so_de_vagas=True)
    assert not interessa("PRS 41/2026- Belém - Analista I - Pedagogia", pagina_so_de_vagas=True)
