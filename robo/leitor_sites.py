"""Baixa páginas dos sites com educação: identifica o robô, respeita robots.txt,
espera entre uma visita e outra e nunca fica pendurado esperando resposta."""

import random
import time
from urllib import robotparser
from urllib.parse import urlparse

import requests

USER_AGENT = "RoboDeVagasBelem/1.0 (aviso de editais de PSS; uso pessoal, sem fins comerciais)"
TEMPO_LIMITE_SEGUNDOS = 30
PAUSA_MINIMA = 2
PAUSA_MAXIMA = 5

# Sinais de telas anti-robô. Se aparecerem, a gente desiste do site (não burla).
SINAIS_DE_BLOQUEIO = (
    "just a moment",
    "security check required",
    "attention required",
    "captcha",
    "checking your browser",
)


class SiteNaoLido(Exception):
    """O site não pôde ser lido (fora do ar, bloqueio, robots.txt...)."""


# Guarda o robots.txt já baixado de cada domínio, pra não baixar de novo a cada página.
_robots_por_dominio = {}


def pausar_entre_requisicoes():
    # Pausa aleatória: evita martelar o servidor e parece menos com ataque.
    time.sleep(random.uniform(PAUSA_MINIMA, PAUSA_MAXIMA))


def _carregar_robots(url):
    partes = urlparse(url)
    dominio = f"{partes.scheme}://{partes.netloc}"
    if dominio not in _robots_por_dominio:
        leitor = robotparser.RobotFileParser()
        try:
            resposta = requests.get(
                dominio + "/robots.txt",
                headers={"User-Agent": USER_AGENT},
                timeout=TEMPO_LIMITE_SEGUNDOS,
            )
            # Sem robots.txt (404 etc.) = site não impôs regra, pode ler.
            leitor.parse(resposta.text.splitlines() if resposta.status_code == 200 else [])
        except requests.RequestException:
            leitor.parse([])
        _robots_por_dominio[dominio] = leitor
    return _robots_por_dominio[dominio]


def robots_permite(url):
    return _carregar_robots(url).can_fetch(USER_AGENT, url)


def parece_tela_de_bloqueio(html):
    # Olha só o título da página: muito site normal tem a palavra "captcha"
    # escondida num script de formulário, e isso dava alarme falso (Senai/Sesi).
    html_minusculo = html.lower()
    inicio_titulo = html_minusculo.find("<title")
    fim_titulo = html_minusculo.find("</title>")
    if inicio_titulo == -1 or fim_titulo == -1:
        return False
    titulo = html_minusculo[inicio_titulo:fim_titulo]
    return any(sinal in titulo for sinal in SINAIS_DE_BLOQUEIO)


def baixar(url):
    """Devolve a resposta da página ou levanta SiteNaoLido explicando o motivo."""
    if not robots_permite(url):
        raise SiteNaoLido("robots.txt não permite a leitura")
    try:
        resposta = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=TEMPO_LIMITE_SEGUNDOS
        )
    except requests.Timeout:
        raise SiteNaoLido("demorou demais para responder")
    except requests.ConnectionError:
        raise SiteNaoLido("conexão recusada ou derrubada (site fora do ar ou bloqueando)")
    except requests.RequestException as erro:
        raise SiteNaoLido(f"erro de rede ({type(erro).__name__})")

    # Sem charset no cabeçalho, o requests chuta ISO-8859-1 e os acentos viram
    # "Ã§Ã£o" (aconteceu no site de Benevides). Nesse caso, deixa ele deduzir.
    if resposta.encoding and resposta.encoding.lower() == "iso-8859-1":
        resposta.encoding = resposta.apparent_encoding

    eh_html = "html" in resposta.headers.get("Content-Type", "")
    if eh_html and parece_tela_de_bloqueio(resposta.text):
        raise SiteNaoLido("tela de verificação anti-robô")
    if resposta.status_code >= 400:
        raise SiteNaoLido(f"site respondeu com erro {resposta.status_code}")
    return resposta
