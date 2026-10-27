"""Manda os 3 e-mails do robô com dados de EXEMPLO, pra conferir como chegam.

Uso:
  python -m robo.enviar_teste --previa          (só gera arquivos HTML em dados/, não envia)
  python -m robo.enviar_teste                   (envia para o EMAIL_ADMIN do .env)
  python -m robo.enviar_teste --para x@y.com    (envia para outro endereço de teste)

Por segurança, este comando se recusa a mandar teste para o EMAIL_DESTINATARIO
(a pessoa que recebe os avisos de verdade).
"""

import argparse
import sys
from datetime import timedelta

from robo.config import PASTA_DADOS, hoje
from robo.email_envio import (
    ErroDeEmail, carregar_credenciais, enviar, montar_alerta_falha_geral, montar_aviso,
    montar_resumo_semanal,
)


def editais_de_exemplo(data_hoje):
    """Dados inventados, marcados como TESTE, cobrindo os casos do e-mail."""
    return [
        {
            "orgao": "Órgão de Exemplo", "titulo": "[TESTE] PSS 01/2026 - Assistente Administrativo",
            "prazo": data_hoje + timedelta(days=10), "niveis": ["médio"],
            "cargos": ["assistente administrativo"], "link": "https://www.pa.senac.br/prs",
        },
        {
            "orgao": "Banca de Exemplo", "titulo": "[TESTE] Seleção Pública - Analista Financeiro",
            "prazo": data_hoje + timedelta(days=2), "niveis": ["superior"],
            "cargos": ["analista financeiro"], "link": "https://www.sesc-pa.com.br/processo-seletivo",
        },
        {
            "orgao": "Prefeitura de Exemplo", "titulo": "[TESTE] Processo Seletivo - Técnico em RH",
            "prazo": None, "niveis": ["não identificado"],
            "cargos": ["técnico em rh"], "link": "https://portalfadesp.org.br/?page_id=33858",
        },
    ]


def numeros_de_exemplo():
    return {
        "execucoes": 7,
        "sites_lidos": ["Senac Pará", "Sesc Pará", "FADESP"],
        "editais_novos": 3,
        "sites_com_falha": {"Site de Exemplo": "demorou demais para responder (instável: em outro dia leu normal)"},
    }


def montar_os_tres(data_hoje):
    return {
        "aviso": montar_aviso(editais_de_exemplo(data_hoje), data_hoje),
        "resumo": montar_resumo_semanal(numeros_de_exemplo(), ["Câmara de Exemplo"], data_hoje),
        "alerta": montar_alerta_falha_geral([("Site A", "conexão recusada"), ("Site B", "fora do ar")], data_hoje),
    }


def main():
    parser = argparse.ArgumentParser(description="Envia e-mails de teste do robô")
    parser.add_argument("--previa", action="store_true", help="só gera arquivos HTML, não envia")
    parser.add_argument("--para", help="endereço de teste (padrão: EMAIL_ADMIN do .env)")
    argumentos = parser.parse_args()

    emails = montar_os_tres(hoje())

    if argumentos.previa:
        PASTA_DADOS.mkdir(parents=True, exist_ok=True)
        for nome, (assunto, html, _) in emails.items():
            arquivo = PASTA_DADOS / f"previa_{nome}.html"
            arquivo.write_text(html, encoding="utf-8")
            print(f"Assunto: {assunto}\n  -> {arquivo}")
        print("Abra os arquivos acima no navegador (duplo clique).")
        return 0

    try:
        credenciais = carregar_credenciais()
    except ErroDeEmail as erro:
        print(erro)
        return 1

    destino = (argumentos.para or credenciais["EMAIL_ADMIN"]).strip()
    if destino.lower() == credenciais["EMAIL_DESTINATARIO"].lower():
        print("Recusado: esse é o e-mail de quem recebe os avisos de verdade. "
              "Use um endereço de teste (--para) ou o EMAIL_ADMIN.")
        return 1

    for nome, (assunto, html, texto) in emails.items():
        try:
            enviar(f"[TESTE] {assunto}", html, texto, destino, credenciais)
            print(f"Enviado: {nome}")
        except ErroDeEmail as erro:
            print(f"Falhou ({nome}): {erro}")
            return 1
    print("Pronto! Confira a caixa de entrada (e o spam) do e-mail de teste.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
