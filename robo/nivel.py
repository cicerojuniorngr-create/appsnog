"""Deduz o nível do cargo (médio, técnico, superior) pelo texto do edital."""

import re

from robo.texto import normalizar

NAO_IDENTIFICADO = "não identificado"

# Expressões completas de propósito: "superior" sozinho casaria com
# "Superior Tribunal de Justiça" ou "nota igual ou superior a 12".
PADROES_POR_NIVEL = {
    "médio": r"\bnivel medio\b|\bensino medio\b|\bmedio completo\b",
    "técnico": (
        r"\bnivel tecnico\b|\bcurso tecnico\b|\bensino tecnico\b|"
        r"\btecnico de nivel medio\b|\bmedio\s*/\s*tecnico\b|\bmedio tecnico\b"
    ),
    "superior": (
        r"\bnivel superior\b|\bensino superior\b|\bcurso superior\b|"
        r"\bsuperior completo\b|\bformacao superior\b|\bgraduacao em\b|"
        r"\bbacharel(?:ado)?\b|\blicenciatura\b"
    ),
}


def identificar_niveis(texto):
    """Devolve, por exemplo, ["médio", "superior"] ou ["não identificado"]."""
    texto = normalizar(texto)
    niveis = [nivel for nivel, padrao in PADROES_POR_NIVEL.items() if re.search(padrao, texto)]
    return niveis or [NAO_IDENTIFICADO]
