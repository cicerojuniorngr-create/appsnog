"""Carrega os arquivos de configuração (YAML) que o dono edita."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

PASTA_RAIZ = Path(__file__).resolve().parent.parent
PASTA_CONFIG = PASTA_RAIZ / "config"
PASTA_DADOS = PASTA_RAIZ / "dados"

# Belém é UTC-3 o ano todo (sem horário de verão). Fuso fixo evita depender do
# banco de fusos "America/Belem", que o Python no Windows não traz de fábrica.
FUSO_BELEM = timezone(timedelta(hours=-3), "America/Belem")


def agora():
    return datetime.now(FUSO_BELEM)


def hoje():
    return agora().date()


def _ler_yaml(nome_arquivo):
    with open(PASTA_CONFIG / nome_arquivo, encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def carregar_sites():
    return _ler_yaml("sites.yaml")["sites"]


def carregar_palavras_chave():
    return _ler_yaml("palavras_chave.yaml")
