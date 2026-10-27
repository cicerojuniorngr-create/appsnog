"""Testes dos e-mails. Nenhum e-mail de verdade é enviado aqui."""

import smtplib
from datetime import date, timedelta

import pytest

from robo import email_envio, enviar_teste, principal
from robo import memoria as mem
from robo import saude_sites
from robo.email_envio import (
    ErroDeEmail, assunto_do_aviso, carregar_credenciais, montar_aviso, ordenar_por_prazo,
)

HOJE = date(2026, 10, 27)
CREDENCIAIS = {
    "EMAIL_REMETENTE": "robo@exemplo.com", "SENHA_APP_EMAIL": "senhasecreta123",
    "EMAIL_DESTINATARIO": "pessoa@exemplo.com", "EMAIL_ADMIN": "admin@exemplo.com",
}


def edital(titulo, prazo):
    return {"orgao": "Órgão", "titulo": titulo, "prazo": prazo, "niveis": ["médio"],
            "cargos": ["assistente administrativo"], "link": "https://exemplo.com/edital"}


def test_assunto_com_prazo_mais_proximo():
    editais = [edital("A", HOJE + timedelta(days=10)), edital("B", HOJE + timedelta(days=3)), edital("C", None)]
    assert assunto_do_aviso(editais) == "[Robô de Vagas] 3 editais novos – prazo mais próximo: 30/10"


def test_assunto_sem_prazo_e_singular():
    assert assunto_do_aviso([edital("A", None)]) == "[Robô de Vagas] 1 edital novo – prazo não identificado"


def test_ordem_prazo_mais_proximo_primeiro_e_sem_prazo_no_fim():
    com_prazo, sem_prazo = ordenar_por_prazo(
        [edital("longe", HOJE + timedelta(days=20)), edital("sem", None), edital("perto", HOJE + timedelta(days=1))]
    )
    assert [e["titulo"] for e in com_prazo] == ["perto", "longe"]
    assert [e["titulo"] for e in sem_prazo] == ["sem"]


def test_html_destaca_prazo_em_vermelho_so_quando_faltam_3_dias_ou_menos():
    _, html_urgente, _ = montar_aviso([edital("A", HOJE + timedelta(days=3))], HOJE)
    _, html_tranquilo, _ = montar_aviso([edital("A", HOJE + timedelta(days=4))], HOJE)
    assert email_envio.VERMELHO in html_urgente
    assert email_envio.VERMELHO not in html_tranquilo


def test_html_mostra_aviso_de_prazo_nao_identificado():
    _, html, texto = montar_aviso([edital("A", None)], HOJE)
    assert "Prazo não identificado, confira o edital" in html
    assert "Prazo não identificado" in texto


def test_html_escapa_titulo_malicioso():
    _, html, _ = montar_aviso([edital("<script>alert(1)</script>", None)], HOJE)
    assert "<script>" not in html


def test_credencial_faltando_diz_qual_sem_mostrar_valores(monkeypatch, tmp_path):
    monkeypatch.setattr(email_envio, "PASTA_RAIZ", tmp_path)  # sem .env
    for nome in email_envio.VARIAVEIS_OBRIGATORIAS:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("SENHA_APP_EMAIL", "senhasecreta123")
    with pytest.raises(ErroDeEmail) as erro:
        carregar_credenciais()
    assert "EMAIL_REMETENTE" in str(erro.value)
    assert "senhasecreta123" not in str(erro.value)


def test_senha_de_app_perde_os_espacos(monkeypatch, tmp_path):
    monkeypatch.setattr(email_envio, "PASTA_RAIZ", tmp_path)
    for nome, valor in CREDENCIAIS.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv("SENHA_APP_EMAIL", "abcd efgh ijkl mnop")
    assert carregar_credenciais()["SENHA_APP_EMAIL"] == "abcdefghijklmnop"


class GmailFalso:
    """Imita o servidor do Gmail: guarda as mensagens em vez de enviar."""
    enviadas = []
    recusar_login = False

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def login(self, usuario, senha):
        if GmailFalso.recusar_login:
            raise smtplib.SMTPAuthenticationError(535, b"senhasecreta123 recusada")

    def send_message(self, mensagem):
        GmailFalso.enviadas.append(mensagem)


@pytest.fixture
def gmail_falso(monkeypatch):
    GmailFalso.enviadas = []
    GmailFalso.recusar_login = False
    monkeypatch.setattr(email_envio.smtplib, "SMTP_SSL", GmailFalso)
    return GmailFalso


def test_login_recusado_nao_vaza_senha(gmail_falso):
    gmail_falso.recusar_login = True
    with pytest.raises(ErroDeEmail) as erro:
        email_envio.enviar("a", "<p>b</p>", "b", "x@exemplo.com", CREDENCIAIS)
    assert "senhasecreta123" not in str(erro.value)
    assert "robo@exemplo.com" not in str(erro.value)


def test_enviar_teste_se_recusa_a_mandar_para_a_destinataria(gmail_falso, monkeypatch, capsys):
    monkeypatch.setattr(enviar_teste, "carregar_credenciais", lambda: CREDENCIAIS)
    monkeypatch.setattr("sys.argv", ["enviar_teste", "--para", "PESSOA@exemplo.com"])
    assert enviar_teste.main() == 1
    assert gmail_falso.enviadas == []
    assert "Recusado" in capsys.readouterr().out


def test_enviar_teste_vai_para_o_admin(gmail_falso, monkeypatch):
    monkeypatch.setattr(enviar_teste, "carregar_credenciais", lambda: CREDENCIAIS)
    monkeypatch.setattr("sys.argv", ["enviar_teste"])
    assert enviar_teste.main() == 0
    assert [m["To"] for m in gmail_falso.enviadas] == ["admin@exemplo.com"] * 3


# ------------------ fluxo do modo real (finalizar) ------------------

def resultado_com(avisos, sites_lidos=("Site A",), falhas=()):
    analisados = [(dict(e, id=f"id{n}", relevante=True, chave_duplicata=None), "avisar")
                  for n, e in enumerate(avisos)]
    return {"sites_lidos": list(sites_lidos), "falhas": list(falhas),
            "analisados": analisados, "nao_visitados": []}


@pytest.fixture
def dados_temporarios(monkeypatch, tmp_path):
    monkeypatch.setattr(mem, "ARQUIVO_MEMORIA", tmp_path / "editais_vistos.json")
    monkeypatch.setattr(saude_sites, "ARQUIVO_SAUDE", tmp_path / "saude_sites.json")
    # salvar() usa o valor padrão do argumento, definido na importação; troca as funções.
    monkeypatch.setattr(mem, "salvar", lambda m, a=tmp_path / "editais_vistos.json": _salvar(m, a))
    monkeypatch.setattr(saude_sites, "salvar", lambda s, a=tmp_path / "saude_sites.json": _salvar(s, a))
    return tmp_path


def _salvar(dados, arquivo):
    import json
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, default=str), encoding="utf-8")


def saude_vazia():
    return {"sites": {}, "execucoes": [], "ultimo_resumo_semanal": None}


def test_segunda_feira_com_edital_manda_dois_emails_separados(gmail_falso, dados_temporarios):
    resultado = resultado_com([edital("PSS X", HOJE + timedelta(days=5))])
    principal.finalizar(resultado, {"editais": {}}, saude_vazia(), CREDENCIAIS, HOJE,
                        primeira_execucao=False, resumo_pendente=True)
    destinos = [m["To"] for m in gmail_falso.enviadas]
    assert destinos == ["pessoa@exemplo.com", "admin@exemplo.com"]
    assert "Resumo semanal" in gmail_falso.enviadas[1]["Subject"]


def test_sem_edital_novo_nao_manda_aviso(gmail_falso, dados_temporarios):
    principal.finalizar(resultado_com([]), {"editais": {}}, saude_vazia(), CREDENCIAIS, HOJE,
                        primeira_execucao=False, resumo_pendente=False)
    assert gmail_falso.enviadas == []


def test_todos_os_sites_falharam_manda_alerta_ao_admin(gmail_falso, dados_temporarios):
    resultado = resultado_com([], sites_lidos=(), falhas=[("A", "fora do ar"), ("B", "fora do ar")])
    principal.finalizar(resultado, {"editais": {}}, saude_vazia(), CREDENCIAIS, HOJE,
                        primeira_execucao=False, resumo_pendente=False)
    assert [m["To"] for m in gmail_falso.enviadas] == ["admin@exemplo.com"]
    assert "ALERTA" in gmail_falso.enviadas[0]["Subject"]


def test_se_o_aviso_falha_a_memoria_nao_e_gravada(gmail_falso, dados_temporarios):
    gmail_falso.recusar_login = True
    resultado = resultado_com([edital("PSS X", HOJE + timedelta(days=5))])
    codigo = principal.finalizar(resultado, {"editais": {"id0": {}}}, saude_vazia(), CREDENCIAIS,
                                 HOJE, primeira_execucao=False, resumo_pendente=False)
    assert codigo == 1
    assert not (dados_temporarios / "editais_vistos.json").exists()
    # E a execução não conta como "já rodou hoje": a próxima tentativa roda de novo.
    saude = saude_sites.carregar(dados_temporarios / "saude_sites.json")
    assert not saude_sites.ja_rodou_hoje(saude, HOJE)
