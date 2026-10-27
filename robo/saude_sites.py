"""Diário de bordo do robô (dados/saude_sites.json).

Fica separado da memória de editais porque é outro assunto: aqui é "como
os sites e o próprio robô estão se comportando". Guarda:
- por site: última leitura que deu certo e última falha (com motivo);
- as últimas execuções: quando rodou, quantos sites leu, quantos editais achou;
- quando foi o último resumo semanal.
"""

import json
from datetime import date, timedelta

from robo.config import PASTA_DADOS

ARQUIVO_SAUDE = PASTA_DADOS / "saude_sites.json"
EXECUCOES_GUARDADAS = 60


def carregar(arquivo=ARQUIVO_SAUDE):
    if not arquivo.exists():
        return {"sites": {}, "execucoes": [], "ultimo_resumo_semanal": None}
    with open(arquivo, encoding="utf-8") as entrada:
        return json.load(entrada)


def salvar(saude, arquivo=ARQUIVO_SAUDE):
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".tmp")
    with open(temporario, "w", encoding="utf-8") as saida:
        json.dump(saude, saida, ensure_ascii=False, indent=2)
    temporario.replace(arquivo)


def _registro_do_site(saude, nome):
    return saude["sites"].setdefault(
        nome, {"ultima_leitura_ok": None, "ultima_falha": None, "motivo_ultima_falha": None}
    )


def registrar_sucesso(saude, nome, momento):
    _registro_do_site(saude, nome)["ultima_leitura_ok"] = momento.isoformat(timespec="minutes")


def registrar_falha(saude, nome, motivo, momento):
    registro = _registro_do_site(saude, nome)
    registro["ultima_falha"] = momento.isoformat(timespec="minutes")
    registro["motivo_ultima_falha"] = motivo


def registrar_execucao(saude, data_execucao, sites_lidos, falhas, editais_novos):
    """`falhas` é uma lista de (nome do site, motivo)."""
    saude["execucoes"].append({
        "data": data_execucao.isoformat(),
        "sites_lidos": sites_lidos,
        "falhas": [{"site": nome, "motivo": motivo} for nome, motivo in falhas],
        "editais_novos": editais_novos,
    })
    saude["execucoes"] = saude["execucoes"][-EXECUCOES_GUARDADAS:]


def ja_rodou_hoje(saude, data_hoje):
    return any(execucao["data"] == data_hoje.isoformat() for execucao in saude["execucoes"])


def resumo_semanal_pendente(saude, data_hoje):
    """O resumo vai na primeira execução de cada semana (segunda, ou depois se o PC ficou desligado)."""
    ultimo = saude.get("ultimo_resumo_semanal")
    if not ultimo:
        return True
    return date.fromisoformat(ultimo).isocalendar()[:2] != data_hoje.isocalendar()[:2]


def marcar_resumo_enviado(saude, data_hoje):
    saude["ultimo_resumo_semanal"] = data_hoje.isoformat()


def numeros_da_semana(saude, data_hoje):
    """Junta as execuções dos últimos 7 dias para o e-mail de "robô vivo"."""
    inicio = data_hoje - timedelta(days=7)
    recentes = [e for e in saude["execucoes"] if date.fromisoformat(e["data"]) > inicio]
    sites_lidos = {site for execucao in recentes for site in execucao["sites_lidos"]}
    falhas = {}
    for execucao in recentes:
        for falha in execucao["falhas"]:
            falhas[falha["site"]] = falha["motivo"]  # fica o motivo mais recente
    return {
        "execucoes": len(recentes),
        "sites_lidos": sorted(sites_lidos),
        "editais_novos": sum(e["editais_novos"] for e in recentes),
        # Site que falhou em algum dia mas também leu em outro é instável, não morto.
        "sites_com_falha": {
            site: motivo + (" (instável: em outro dia leu normal)" if site in sites_lidos else "")
            for site, motivo in sorted(falhas.items())
        },
    }
