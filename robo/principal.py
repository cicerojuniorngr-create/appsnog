"""Maestro do robô: chama cada etapa na ordem.

Uso:
  python -m robo.principal --simulacao   (ensaio: mostra na tela, não manda e-mail, não grava nada)
  python -m robo.principal               (de verdade)
  python -m robo.principal --forcar      (roda mesmo se já rodou hoje)

Fluxo:
 1. Carrega configuração, memória e diário de saúde.
 2. Visita cada site, pega os itens, faz a triagem pelo título.
 3. Para cada item NOVO que passou: abre o edital, confirma cargo, acha prazo e nível.
 4. Decide: avisar (prazo aberto ou não identificado) ou só anotar (prazo vencido / duplicata).
 5. Manda os e-mails (aviso, resumo semanal, alerta de falha geral).
 6. Grava memória, saúde e log.
"""

import argparse
import logging
import sys

from robo import memoria as mem
from robo import saude_sites as saude_mod
from robo.config import PASTA_DADOS, agora, carregar_palavras_chave, carregar_sites, hoje
from robo.edital import texto_completo_do_edital
from robo.email_envio import (
    ErroDeEmail, carregar_credenciais, enviar, montar_alerta_falha_geral, montar_aviso,
    montar_resumo_semanal,
)
from robo.extrator_itens import extrair_itens
from robo.filtro import avaliar, passa_na_triagem
from robo.leitor_sites import SiteNaoLido, baixar, pausar_entre_requisicoes
from robo.nivel import identificar_niveis
from robo.prazo import extrair_prazo, formatar_prazo

ARQUIVO_LOG = PASTA_DADOS / "log_execucoes.txt"
# Na primeira vez um site pode ter dezenas de itens. Abrimos no máximo isto
# por dia; o resto fica para amanhã (não é anotado, então volta na fila).
MAXIMO_DE_EDITAIS_ABERTOS_POR_SITE = 15

log = logging.getLogger("robo")


# --------------------------------------------------------------------------
# Análise de um item (sem internet: fácil de testar)
# --------------------------------------------------------------------------

def analisar_item(item, site, texto_do_edital, palavras, data_hoje):
    """Monta o "dossiê" do edital a partir do item da listagem e do texto dele."""
    relevante, motivo, cargos = avaliar(
        item["titulo"], item["resumo"], texto_do_edital, palavras,
        site.get("pagina_so_de_vagas", False),
    )
    texto_para_datas = f"{item['resumo']} {texto_do_edital}"
    prazo = extrair_prazo(texto_para_datas, data_hoje) if relevante else None
    return {
        "id": mem.identificador(item["link"], item["titulo"]),
        "titulo": item["titulo"],
        "orgao": site["nome"],
        "link": item["link"],
        "data_publicacao": item.get("data_publicacao"),
        "relevante": relevante,
        "motivo": motivo,
        "cargos": cargos,
        "prazo": prazo,
        "niveis": identificar_niveis(texto_para_datas) if relevante else [],
        "chave_duplicata": mem.chave_de_duplicata(item["titulo"], prazo) if relevante else None,
    }


def decidir(edital, memoria, data_hoje):
    """Devolve "avisar", "prazo_vencido", "duplicata" ou "irrelevante"."""
    if not edital["relevante"]:
        return "irrelevante"
    if mem.duplicata_de(memoria, edital["chave_duplicata"]):
        return "duplicata"
    if edital["prazo"] and edital["prazo"] < data_hoje:
        return "prazo_vencido"
    return "avisar"


# --------------------------------------------------------------------------
# Visita aos sites (com internet)
# --------------------------------------------------------------------------

def processar_site(site, palavras, memoria, data_hoje, resultado):
    """Lê um site e preenche `resultado`. Qualquer erro vira falha do site, nunca derruba o robô."""
    nome = site["nome"]
    try:
        resposta = baixar(site["url"])
        itens = extrair_itens(resposta.text, resposta.url)
    except SiteNaoLido as motivo:
        resultado["falhas"].append((nome, str(motivo)))
        return
    except Exception as erro:  # Layout mudou, HTML quebrado... segue o baile.
        resultado["falhas"].append((nome, f"erro inesperado ao ler ({type(erro).__name__})"))
        return

    resultado["sites_lidos"].append(nome)
    so_vagas = site.get("pagina_so_de_vagas", False)
    novos = [
        item for item in itens
        if passa_na_triagem(item["titulo"], item["resumo"], palavras, so_vagas)
        and not mem.ja_visto(memoria, mem.identificador(item["link"], item["titulo"]))
    ]
    for item in novos[:MAXIMO_DE_EDITAIS_ABERTOS_POR_SITE]:
        pausar_entre_requisicoes()
        texto, observacao = texto_completo_do_edital(item["link"])
        edital = analisar_item(item, site, texto, palavras, data_hoje)
        edital["observacao"] = observacao
        if observacao and not edital["relevante"]:
            # Não abriu o edital e o título sozinho não convenceu: tenta de novo amanhã.
            continue
        situacao = decidir(edital, memoria, data_hoje)
        resultado["analisados"].append((edital, situacao))
        # Anota já agora: se o mesmo edital aparecer em outro site nesta mesma
        # execução, a checagem de duplicata pega.
        mem.anotar(memoria, edital, avisado=(situacao == "avisar"), visto_em=data_hoje)


def executar(sites, palavras, memoria, data_hoje):
    resultado = {"sites_lidos": [], "falhas": [], "analisados": [], "nao_visitados": []}
    ativos = [s for s in sites if s.get("ativo") and s.get("confirmada")]
    resultado["nao_visitados"] = [s["nome"] for s in sites if s not in ativos]
    for indice, site in enumerate(ativos):
        if indice > 0:
            pausar_entre_requisicoes()
        log.info("Lendo %s ...", site["nome"])
        processar_site(site, palavras, memoria, data_hoje, resultado)
    return resultado


def editais_para_avisar(resultado):
    return [edital for edital, situacao in resultado["analisados"] if situacao == "avisar"]


# --------------------------------------------------------------------------
# Saída na tela (modo simulação)
# --------------------------------------------------------------------------

def mostrar_resultado(resultado, primeira_execucao, resumo_pendente):
    print("\n" + "=" * 70)
    print("RESULTADO" + (" (PRIMEIRA EXECUÇÃO)" if primeira_execucao else ""))
    print("=" * 70)
    print(f"Sites lidos: {len(resultado['sites_lidos'])}")
    for nome, motivo in resultado["falhas"]:
        print(f"  NÃO LIDO: {nome} -> {motivo}")

    avisar = editais_para_avisar(resultado)
    print(f"\nEditais que iriam no e-mail de aviso: {len(avisar)}")
    for edital in avisar:
        print(f"  * [{edital['orgao']}] {edital['titulo']}")
        print(f"      Prazo: {formatar_prazo(edital['prazo'])} | Nível: {', '.join(edital['niveis'])}")
        print(f"      Cargos: {', '.join(edital['cargos'])}")
        print(f"      Link: {edital['link']}")
        if edital.get("observacao"):
            print(f"      Obs.: {edital['observacao']}")

    outros = [(e, s) for e, s in resultado["analisados"] if s != "avisar"]
    if outros:
        print("\nAnotados sem aviso:")
        for edital, situacao in outros:
            detalhe = {
                "prazo_vencido": f"prazo vencido em {formatar_prazo(edital['prazo'])}",
                "duplicata": "mesmo edital já visto em outro site",
                "irrelevante": edital["motivo"],
            }[situacao]
            print(f"  - [{edital['orgao']}] {edital['titulo'][:80]} ({detalhe})")

    if not resultado["sites_lidos"]:
        print("\n!!! Nenhum site pôde ser lido: iria um ALERTA para o e-mail do administrador.")
    if resumo_pendente:
        print("\nHoje iria também o RESUMO SEMANAL para o e-mail do administrador.")


# --------------------------------------------------------------------------
# Programa principal
# --------------------------------------------------------------------------

def configurar_log(simulacao):
    manipuladores = [logging.StreamHandler(sys.stdout)]
    if not simulacao:
        PASTA_DADOS.mkdir(parents=True, exist_ok=True)
        manipuladores.append(logging.FileHandler(ARQUIVO_LOG, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(message)s",
        datefmt="%d/%m/%Y %H:%M", handlers=manipuladores,
    )


def ler_argumentos():
    parser = argparse.ArgumentParser(description="Robô de avisos de PSS em Belém/PA")
    parser.add_argument("--simulacao", action="store_true",
                        help="só mostra na tela; não envia e-mail nem grava memória")
    parser.add_argument("--forcar", action="store_true",
                        help="roda mesmo que já tenha rodado hoje")
    return parser.parse_args()


def main():
    argumentos = ler_argumentos()
    simulacao = argumentos.simulacao
    configurar_log(simulacao)

    credenciais = None
    if not simulacao:
        # Confere o .env ANTES de visitar os sites: melhor falhar em 1 segundo
        # do que depois de 5 minutos lendo sites.
        try:
            credenciais = carregar_credenciais()
        except ErroDeEmail as erro:
            log.error("%s", erro)
            return 1

    data_hoje = hoje()
    memoria = mem.carregar()
    saude = saude_mod.carregar()

    if saude_mod.ja_rodou_hoje(saude, data_hoje) and not argumentos.forcar and not simulacao:
        log.info("Já rodou hoje (%s). Nada a fazer.", data_hoje.strftime("%d/%m/%Y"))
        return 0

    primeira_execucao = mem.esta_vazia(memoria)
    log.info("Início da execução%s.", " em MODO SIMULAÇÃO" if simulacao else "")

    sites = carregar_sites()
    resultado = executar(sites, carregar_palavras_chave(), memoria, data_hoje)
    resumo_pendente = saude_mod.resumo_semanal_pendente(saude, data_hoje)

    if simulacao:
        mostrar_resultado(resultado, primeira_execucao, resumo_pendente)
        print("\n(Modo simulação: nenhum e-mail enviado, nada gravado.)")
        return 0

    return finalizar(resultado, memoria, saude, credenciais, data_hoje, primeira_execucao, resumo_pendente)


def finalizar(resultado, memoria, saude, credenciais, data_hoje, primeira_execucao, resumo_pendente):
    """Manda os e-mails e grava tudo. Separado do main() pra ficar legível."""
    momento = agora()
    for nome in resultado["sites_lidos"]:
        saude_mod.registrar_sucesso(saude, nome, momento)
    for nome, motivo in resultado["falhas"]:
        saude_mod.registrar_falha(saude, nome, motivo, momento)

    avisar = editais_para_avisar(resultado)
    if avisar:
        try:
            enviar(*montar_aviso(avisar, data_hoje, primeira_execucao),
                   credenciais["EMAIL_DESTINATARIO"], credenciais)
            log.info("E-mail de aviso enviado com %d edital(is).", len(avisar))
        except ErroDeEmail as erro:
            # NÃO grava a memória nem a execução: assim, na próxima vez que o
            # robô rodar, esses editais continuam "novos" e o aviso sai de novo.
            log.error("Aviso NÃO enviado: %s A memória não foi gravada.", erro)
            saude_mod.salvar(saude)
            return 1

    if not resultado["sites_lidos"] and resultado["falhas"]:
        enviar_sem_derrubar(montar_alerta_falha_geral(resultado["falhas"], data_hoje),
                            credenciais["EMAIL_ADMIN"], credenciais, "alerta de falha geral")

    saude_mod.registrar_execucao(
        saude, data_hoje, resultado["sites_lidos"], resultado["falhas"], len(avisar)
    )
    if resumo_pendente:
        numeros = saude_mod.numeros_da_semana(saude, data_hoje)
        if enviar_sem_derrubar(montar_resumo_semanal(numeros, resultado["nao_visitados"], data_hoje),
                               credenciais["EMAIL_ADMIN"], credenciais, "resumo semanal"):
            saude_mod.marcar_resumo_enviado(saude, data_hoje)

    esquecidos = mem.limpar_antigos(memoria, data_hoje)
    mem.salvar(memoria)
    saude_mod.salvar(saude)
    log.info(
        "Fim: %d sites lidos, %d falhas, %d avisados, %d anotados sem aviso, %d esquecidos (>12 meses).",
        len(resultado["sites_lidos"]), len(resultado["falhas"]), len(avisar),
        len(resultado["analisados"]) - len(avisar), esquecidos,
    )
    return 0


def enviar_sem_derrubar(email_montado, destinatario, credenciais, descricao):
    """Para e-mails ao administrador: se falhar, registra e segue."""
    try:
        enviar(*email_montado, destinatario, credenciais)
        log.info("E-mail de %s enviado.", descricao)
        return True
    except ErroDeEmail as erro:
        log.error("E-mail de %s NÃO enviado: %s", descricao, erro)
        return False


if __name__ == "__main__":
    sys.exit(main())
