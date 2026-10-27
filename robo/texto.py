"""Ferramentas de texto usadas pelo filtro, pelo prazo e pelo nível."""

import re
import unicodedata


def normalizar(texto):
    """Minúsculas, sem acento e com espaços simples.

    Assim "Contratação  Temporária" e "contratacao temporaria" viram a mesma
    coisa, e a comparação não depende de como o órgão digitou.
    """
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(letra for letra in sem_acento if not unicodedata.combining(letra))
    return " ".join(sem_acento.lower().split())


def _padrao_do_termo(termo):
    # \b = "fronteira de palavra": impede que "ti" case com "atividades".
    partes = [re.escape(parte) for parte in normalizar(termo).split()]
    return re.compile(r"\b" + r"\s+".join(partes) + r"\b")


def contem_termo(texto_normalizado, termo):
    return _padrao_do_termo(termo).search(texto_normalizado) is not None


def termos_encontrados(texto_normalizado, termos):
    """Devolve, na ordem da lista, os termos que aparecem no texto."""
    return [termo for termo in termos if contem_termo(texto_normalizado, termo)]


def achatar(lista_ou_grupos):
    """Transforma {'grupo': [a, b], ...} em [a, b, ...]. Lista simples passa direto."""
    if isinstance(lista_ou_grupos, dict):
        return [termo for grupo in lista_ou_grupos.values() for termo in (grupo or [])]
    return list(lista_ou_grupos or [])
