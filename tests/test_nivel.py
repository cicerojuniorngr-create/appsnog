from robo.nivel import NAO_IDENTIFICADO, identificar_niveis


def test_medio_senac_real():
    texto = "2. INFORMAÇÕES SOBRE O CARGO: ESCOLARIDADE: NÍVEL MÉDIO Pré–Requisitos: ➢ Ensino Médio Completo"
    assert identificar_niveis(texto) == ["médio"]


def test_tecnico_e_superior():
    texto = "Cargo A: Técnico de nível médio com curso técnico. Cargo B: graduação em Administração."
    assert identificar_niveis(texto) == ["médio", "técnico", "superior"]


def test_superior():
    assert identificar_niveis("Requisito: Ensino Superior completo em Gestão de RH") == ["superior"]


def test_superior_falso_nao_conta():
    # Trechos reais do edital do Senac que NÃO falam de escolaridade.
    texto = (
        "conforme Súmula 377 do Superior Tribunal de Justiça; candidatos que atingirem "
        "a pontuação igual ou superior a 12 (doze) pontos"
    )
    assert identificar_niveis(texto) == [NAO_IDENTIFICADO]
