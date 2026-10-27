"""Carrega os arquivos de configuração (YAML) que o dono edita."""

from pathlib import Path

import yaml

PASTA_RAIZ = Path(__file__).resolve().parent.parent
PASTA_CONFIG = PASTA_RAIZ / "config"
PASTA_DADOS = PASTA_RAIZ / "dados"


def _ler_yaml(nome_arquivo):
    with open(PASTA_CONFIG / nome_arquivo, encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def carregar_sites():
    return _ler_yaml("sites.yaml")["sites"]


def carregar_palavras_chave():
    return _ler_yaml("palavras_chave.yaml")
