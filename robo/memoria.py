"""Memória do robô: quais editais ele já viu (dados/editais_vistos.json).

Analogia: é o caderno do estagiário. Antes de avisar, ele confere se já
anotou aquele edital; depois de avisar, anota. Sem isso, todo dia ele
mandaria os mesmos editais de novo.
"""

import hashlib
import json
import re
from datetime import date, timedelta

from robo.config import PASTA_DADOS
from robo.texto import normalizar

ARQUIVO_MEMORIA = PASTA_DADOS / "editais_vistos.json"
DIAS_PARA_ESQUECER = 365

# "Edital nº 03/2026", "PSS 03/2026", "PRS 39/2026", "Processo Seletivo Nº 001/2023"
NUMERO_DO_EDITAL = re.compile(
    r"\b(?:edital|pss|prs|processo seletivo(?: simplificado)?|selecao publica)\b"
    r"\D{0,15}?(\d{1,4})\s*/\s*(\d{4})\b"
)


def identificador(link, titulo):
    """Impressão digital do item: mesmo link + mesmo título = mesmo edital."""
    base = normalizar(link).rstrip("/") + "|" + normalizar(titulo)
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def chave_de_duplicata(titulo, prazo):
    """Pega o mesmo edital publicado em dois sites (ex.: órgão e banca).

    Usa número/ano do edital + prazo final. Só o número não basta: "01/2026"
    existe em quase todo órgão. Sem número ou sem prazo, não arrisca: devolve
    None e, no pior caso, sai um aviso repetido (melhor que perder edital).
    """
    numero = NUMERO_DO_EDITAL.search(normalizar(titulo))
    if not numero or not prazo:
        return None
    return f"{int(numero.group(1))}/{numero.group(2)}|{prazo.isoformat()}"


def carregar(arquivo=ARQUIVO_MEMORIA):
    if not arquivo.exists():
        return {"editais": {}}
    with open(arquivo, encoding="utf-8") as entrada:
        return json.load(entrada)


def salvar(memoria, arquivo=ARQUIVO_MEMORIA):
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    # Grava num arquivo temporário e depois troca: se o PC desligar no meio,
    # o caderno antigo continua inteiro em vez de virar um arquivo corrompido.
    temporario = arquivo.with_suffix(".tmp")
    with open(temporario, "w", encoding="utf-8") as saida:
        json.dump(memoria, saida, ensure_ascii=False, indent=2)
    temporario.replace(arquivo)


def esta_vazia(memoria):
    return not memoria["editais"]


def ja_visto(memoria, id_item):
    return id_item in memoria["editais"]


def duplicata_de(memoria, chave):
    if not chave:
        return None
    for registro in memoria["editais"].values():
        if registro.get("chave_duplicata") == chave:
            return registro
    return None


def anotar(memoria, edital, avisado, visto_em):
    """Anota o edital no caderno. `edital` é o dicionário montado pelo principal."""
    prazo = edital.get("prazo")
    memoria["editais"][edital["id"]] = {
        "titulo": edital["titulo"],
        "orgao": edital["orgao"],
        "link": edital["link"],
        "visto_em": visto_em.isoformat(),
        "prazo": prazo.isoformat() if prazo else None,
        "niveis": edital.get("niveis", []),
        "cargos": edital.get("cargos", []),
        "relevante": edital.get("relevante", False),
        "avisado": avisado,
        "chave_duplicata": edital.get("chave_duplicata"),
    }


def limpar_antigos(memoria, data_hoje):
    """Esquece o que foi visto há mais de 12 meses, pro arquivo não crescer pra sempre."""
    limite = data_hoje - timedelta(days=DIAS_PARA_ESQUECER)
    antigos = [
        id_item for id_item, registro in memoria["editais"].items()
        if date.fromisoformat(registro["visto_em"]) < limite
    ]
    for id_item in antigos:
        del memoria["editais"][id_item]
    return len(antigos)
