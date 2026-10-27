"""Monta e envia os e-mails do robô pelo Gmail (SMTP com senha de app).

Três tipos de e-mail:
- aviso de edital novo  -> EMAIL_DESTINATARIO
- resumo semanal        -> EMAIL_ADMIN
- alerta "não li nada"  -> EMAIL_ADMIN

Segurança: senha e endereços NUNCA aparecem em log nem em mensagem de erro.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage
from html import escape

from dotenv import load_dotenv

from robo.config import PASTA_RAIZ
from robo.prazo import TEXTO_SEM_PRAZO

SERVIDOR_SMTP = "smtp.gmail.com"
PORTA_SMTP = 465  # SSL direto: a conexão já nasce criptografada.
TEMPO_LIMITE_SEGUNDOS = 60
DIAS_PARA_FICAR_VERMELHO = 3
VARIAVEIS_OBRIGATORIAS = ("EMAIL_REMETENTE", "SENHA_APP_EMAIL", "EMAIL_DESTINATARIO", "EMAIL_ADMIN")

VERMELHO = "#c62828"
CINZA = "#555555"


class ErroDeEmail(Exception):
    """Problema de configuração ou de envio (mensagem sem dados sensíveis)."""


# --------------------------------------------------------------------------
# Credenciais
# --------------------------------------------------------------------------

def carregar_credenciais():
    """Lê o .env (no PC) ou as variáveis de ambiente. Diz QUAL falta, nunca o valor."""
    load_dotenv(PASTA_RAIZ / ".env")
    faltando = [nome for nome in VARIAVEIS_OBRIGATORIAS if not os.environ.get(nome, "").strip()]
    if faltando:
        raise ErroDeEmail(
            "Faltam no arquivo .env: " + ", ".join(faltando)
            + ". Copie o .env.example para .env e preencha."
        )
    credenciais = {nome: os.environ[nome].strip() for nome in VARIAVEIS_OBRIGATORIAS}
    # O Google mostra a senha de app em blocos ("abcd efgh ..."); os espaços não fazem parte dela.
    credenciais["SENHA_APP_EMAIL"] = credenciais["SENHA_APP_EMAIL"].replace(" ", "")
    return credenciais


# --------------------------------------------------------------------------
# Envio
# --------------------------------------------------------------------------

def enviar(assunto, html, texto_simples, destinatario, credenciais):
    mensagem = EmailMessage()
    mensagem["Subject"] = assunto
    mensagem["From"] = f"Robô de Vagas <{credenciais['EMAIL_REMETENTE']}>"
    mensagem["To"] = destinatario
    # Texto simples é a "plano B" para leitores de e-mail que não mostram HTML.
    mensagem.set_content(texto_simples)
    mensagem.add_alternative(html, subtype="html")

    try:
        contexto = ssl.create_default_context()
        with smtplib.SMTP_SSL(SERVIDOR_SMTP, PORTA_SMTP, timeout=TEMPO_LIMITE_SEGUNDOS,
                              context=contexto) as servidor:
            servidor.login(credenciais["EMAIL_REMETENTE"], credenciais["SENHA_APP_EMAIL"])
            servidor.send_message(mensagem)
    except smtplib.SMTPAuthenticationError:
        raise ErroDeEmail("O Gmail recusou o login: confira EMAIL_REMETENTE e SENHA_APP_EMAIL no .env.")
    except (smtplib.SMTPException, OSError) as erro:
        # Só o TIPO do erro: a mensagem original pode conter endereços de e-mail.
        raise ErroDeEmail(f"Falha ao enviar e-mail ({type(erro).__name__}).")


# --------------------------------------------------------------------------
# Peças de HTML (simples de propósito: e-mail de celular não gosta de enfeite)
# --------------------------------------------------------------------------

def _pagina(titulo, conteudo):
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f4;">
<div style="max-width:600px;margin:0 auto;padding:16px;font-family:Arial,Helvetica,sans-serif;
font-size:16px;line-height:1.5;color:#222;">
<h1 style="font-size:20px;margin:0 0 16px;">{titulo}</h1>
{conteudo}
<p style="font-size:13px;color:{CINZA};margin-top:24px;">
Robô de Vagas: só avisa. A inscrição é feita por você, no site do órgão.</p>
</div></body></html>"""


def _dias_restantes(prazo, data_hoje):
    return (prazo - data_hoje).days


def _texto_do_prazo(prazo, data_hoje):
    if not prazo:
        return TEXTO_SEM_PRAZO
    dias = _dias_restantes(prazo, data_hoje)
    quando = {0: "termina HOJE", 1: "termina amanhã"}.get(dias, f"faltam {dias} dias")
    return f"{prazo.strftime('%d/%m/%Y')} ({quando})"


def _rotulo_do_prazo(prazo, data_hoje):
    if not prazo:
        return TEXTO_SEM_PRAZO
    return f"Inscrição até: {_texto_do_prazo(prazo, data_hoje)}"


def _lista_de_cargos(edital):
    return ", ".join(cargo[:1].upper() + cargo[1:] for cargo in edital["cargos"])


def _cartao_do_edital(edital, data_hoje):
    prazo = edital["prazo"]
    urgente = prazo is not None and _dias_restantes(prazo, data_hoje) <= DIAS_PARA_FICAR_VERMELHO
    cor_do_prazo = VERMELHO if (urgente or not prazo) else "#222"
    borda = VERMELHO if urgente else "#dddddd"
    return f"""
<div style="background:#fff;border:2px solid {borda};border-radius:8px;padding:16px;margin-bottom:16px;">
  <div style="font-size:13px;color:{CINZA};text-transform:uppercase;">{escape(edital['orgao'])}</div>
  <div style="font-size:17px;font-weight:bold;margin:4px 0 12px;">{escape(edital['titulo'])}</div>
  <div style="font-size:18px;color:{cor_do_prazo};margin-bottom:12px;">
    <b>{escape(_rotulo_do_prazo(prazo, data_hoje))}</b></div>
  <div><b>Nível:</b> {escape(', '.join(edital['niveis']) or 'não identificado')}</div>
  <div style="margin-bottom:16px;"><b>Cargos:</b> {escape(_lista_de_cargos(edital))}</div>
  <a href="{escape(edital['link'], quote=True)}" style="display:block;background:#1565c0;color:#fff;
  text-align:center;text-decoration:none;font-size:17px;font-weight:bold;padding:14px;border-radius:6px;">
  Abrir o edital</a>
</div>"""


def _texto_simples_do_edital(edital, data_hoje):
    return (
        f"{edital['orgao']}\n{edital['titulo']}\n"
        f"{_rotulo_do_prazo(edital['prazo'], data_hoje).upper()}\n"
        f"Nível: {', '.join(edital['niveis']) or 'não identificado'}\n"
        f"Cargos: {_lista_de_cargos(edital)}\n{edital['link']}\n"
    )


# --------------------------------------------------------------------------
# E-mail 1: aviso de edital novo
# --------------------------------------------------------------------------

def ordenar_por_prazo(editais):
    """Prazo mais próximo primeiro; os sem prazo identificado vão pro fim."""
    com_prazo = sorted((e for e in editais if e["prazo"]), key=lambda e: e["prazo"])
    sem_prazo = [e for e in editais if not e["prazo"]]
    return com_prazo, sem_prazo


def assunto_do_aviso(editais):
    com_prazo, _ = ordenar_por_prazo(editais)
    quantidade = len(editais)
    novidade = "1 edital novo" if quantidade == 1 else f"{quantidade} editais novos"
    proximo = com_prazo[0]["prazo"].strftime("%d/%m") if com_prazo else "prazo não identificado"
    if com_prazo:
        proximo = f"prazo mais próximo: {proximo}"
    return f"[Robô de Vagas] {novidade} – {proximo}"


def montar_aviso(editais, data_hoje, primeira_execucao=False):
    """Devolve (assunto, html, texto_simples)."""
    com_prazo, sem_prazo = ordenar_por_prazo(editais)
    partes_html, partes_texto = [], []

    if primeira_execucao:
        nota = ("Primeira execução do robô: abaixo estão todos os editais do perfil com "
                "inscrição aberta (ou sem prazo identificado) encontrados hoje.")
        partes_html.append(f'<p style="color:{CINZA};">{nota}</p>')
        partes_texto.append(nota + "\n")

    for edital in com_prazo:
        partes_html.append(_cartao_do_edital(edital, data_hoje))
        partes_texto.append(_texto_simples_do_edital(edital, data_hoje))

    if sem_prazo:
        aviso = ("⚠️ Prazo não identificado: o robô não conseguiu ler a data com segurança. "
                 "Abra o edital e confira o prazo HOJE.")
        partes_html.append(
            f'<div style="background:#fff3e0;border-left:4px solid {VERMELHO};padding:12px;'
            f'margin:24px 0 16px;"><b>{aviso}</b></div>'
        )
        partes_texto.append("\n" + aviso + "\n")
        for edital in sem_prazo:
            partes_html.append(_cartao_do_edital(edital, data_hoje))
            partes_texto.append(_texto_simples_do_edital(edital, data_hoje))

    quantidade = len(editais)
    titulo = "1 edital novo" if quantidade == 1 else f"{quantidade} editais novos"
    return (
        assunto_do_aviso(editais),
        _pagina(titulo, "".join(partes_html)),
        "\n".join(partes_texto),
    )


# --------------------------------------------------------------------------
# E-mail 2: resumo semanal ("robô vivo")
# --------------------------------------------------------------------------

def montar_resumo_semanal(numeros, nao_visitados, data_hoje):
    falhas = numeros["sites_com_falha"]
    linhas_falha = "".join(
        f"<li><b>{escape(site)}</b>: {escape(motivo)}</li>" for site, motivo in falhas.items()
    ) or "<li>Nenhuma 🎉</li>"
    linhas_nao_visitados = "".join(f"<li>{escape(site)}</li>" for site in nao_visitados) or "<li>Nenhum</li>"

    conteudo = f"""
<p>✅ O robô está funcionando.</p>
<p><b>Últimos 7 dias:</b><br>
Execuções: {numeros['execucoes']}<br>
Sites lidos com sucesso: {len(numeros['sites_lidos'])}<br>
Editais novos do perfil avisados: {numeros['editais_novos']}</p>
<p><b>Sites com erro na semana:</b></p><ul>{linhas_falha}</ul>
<p><b>Sites desligados ou com endereço a confirmar (o robô não visita):</b></p>
<ul style="color:{CINZA};">{linhas_nao_visitados}</ul>"""

    texto = (
        f"O robô está funcionando.\nÚltimos 7 dias: {numeros['execucoes']} execuções, "
        f"{len(numeros['sites_lidos'])} sites lidos, {numeros['editais_novos']} editais avisados.\n"
        "Sites com erro: " + ("; ".join(f"{s}: {m}" for s, m in falhas.items()) or "nenhum") + "\n"
        "Sites não visitados: " + (", ".join(nao_visitados) or "nenhum") + "\n"
    )
    assunto = f"[Robô de Vagas] Resumo semanal – {data_hoje.strftime('%d/%m')}"
    return assunto, _pagina("Resumo semanal", conteudo), texto


# --------------------------------------------------------------------------
# E-mail 3: alerta de falha geral
# --------------------------------------------------------------------------

def montar_alerta_falha_geral(falhas, data_hoje):
    linhas = "".join(f"<li><b>{escape(site)}</b>: {escape(motivo)}</li>" for site, motivo in falhas)
    conteudo = f"""
<p style="color:{VERMELHO};"><b>Hoje o robô não conseguiu ler NENHUM site.</b></p>
<p>Quase sempre é internet do PC fora do ar na hora da execução. Se repetir amanhã,
vale olhar com calma.</p><ul>{linhas}</ul>"""
    texto = "Hoje o robô não conseguiu ler NENHUM site.\n" + "\n".join(f"{s}: {m}" for s, m in falhas)
    assunto = f"[Robô de Vagas] ALERTA: nenhum site lido em {data_hoje.strftime('%d/%m')}"
    return assunto, _pagina("Alerta do robô", conteudo), texto
