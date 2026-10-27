"""Acha a data FINAL de inscrição no texto de um edital.

Regra de ouro: na dúvida, devolve None (o e-mail mostra "Prazo não
identificado, confira o edital"). Uma data errada é pior que nenhuma data,
porque pode fazer a pessoa perder a inscrição achando que tem tempo.

Como funciona (analogia: um marca-texto):
1. Procura "âncoras" no texto: inscrição, candidatura, envio de currículo...
2. Ignora âncoras de outros assuntos: "resultado das inscrições",
   "isenção da taxa de inscrição", "recurso"...
3. Olha logo DEPOIS da âncora ("inscrições de 10/11 a 20/11/2026").
   Se não achar, olha logo ANTES, que é como aparece em tabela de
   cronograma ("29/09/2026 a 30/09/2026 Inscrição").
4. Se todas as âncoras apontam para a MESMA data final, é ela.
   Se apontam para datas diferentes, devolve None.
"""

import re
from datetime import date, timedelta

from robo.texto import normalizar

TEXTO_SEM_PRAZO = "Prazo não identificado, confira o edital"

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

_DATA_NUMERICA = r"\d{1,2}/\d{1,2}(?:/\d{2,4})?"
_DATA_POR_EXTENSO = r"\d{1,2}o?\s+de\s+(?:" + "|".join(MESES) + r")(?:\s+de\s+\d{4})?"
DATA = rf"(?:{_DATA_POR_EXTENSO}|{_DATA_NUMERICA})"

# Pedaços opcionais entre o conectivo e a data: "as 23h59 do dia ..."
_HORA = r"(?:\d{1,2}\s*h\s*\d{0,2}\s*(?:min)?\s*)"
_ANTES_DA_DATA = rf"(?:as\s+)?{_HORA}?(?:do\s+|o\s+)?(?:dia\s+)?"

PERIODO = re.compile(
    rf"(?:de\s+|do\s+dia\s+|dia\s+)?(?P<inicio>{DATA}|\d{{1,2}}o?)\s*"
    rf"(?:a|as|ate|-|–)\s+{_ANTES_DA_DATA}(?P<fim>{DATA})"
    # Variante sem espaço antes da data: "10/11-20/11/2026"
    rf"|(?P<inicio2>{DATA})\s*[-–]\s*(?P<fim2>{DATA})"
)
ATE = re.compile(rf"\bate\s+{_ANTES_DA_DATA}(?P<fim>{DATA})")
ENTRE = re.compile(rf"\bentre\s+.{{0,25}}?(?P<inicio>{DATA})\s+e\s+.{{0,25}}?(?P<fim>{DATA})")
QUALQUER_DATA = re.compile(DATA)

ANCORA = re.compile(
    r"inscri(?:cao|coes)|candidatura|(?:envio|recebimento|cadastro)\s+de\s+curriculos?"
)
# Palavras que, logo antes da âncora, mostram que o assunto é outro.
ASSUNTO_ERRADO_ANTES = re.compile(
    r"isencao|recurso|homologa|resultado|deferi|indeferi|convoca|divulga|"
    r"confirmacao|comprovante|taxa|pagamento|boleto|cancelamento|numero"
)
ASSUNTO_ERRADO_DEPOIS = re.compile(r"^\W*(?:homologad|deferid|indeferid|cancelad)")

JANELA_DEPOIS = 150
JANELA_ANTES = 60
# Data sem ano ("20/11") que, no ano da referência, cairia mais de 270 dias
# no passado é do ano seguinte (edital de dezembro falando de janeiro).
DIAS_PARA_VIRAR_O_ANO = 270


def _ano_completo(ano_texto):
    ano = int(ano_texto)
    return ano + 2000 if ano < 100 else ano


def _texto_para_data(texto_data, data_referencia, ano_sugerido=None):
    """Converte "20/11/2026", "20/11" ou "20 de novembro de 2026" em date."""
    numeros = re.match(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$", texto_data)
    if numeros:
        dia, mes, ano = int(numeros.group(1)), int(numeros.group(2)), numeros.group(3)
    else:
        extenso = re.match(r"(\d{1,2})o?\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?$", texto_data)
        if not extenso:
            return None
        dia, mes, ano = int(extenso.group(1)), MESES[extenso.group(2)], extenso.group(3)

    try:
        if ano:
            return date(_ano_completo(ano), mes, dia)
        ano_inferido = ano_sugerido or data_referencia.year
        data = date(ano_inferido, mes, dia)
        if not ano_sugerido and data < data_referencia - timedelta(days=DIAS_PARA_VIRAR_O_ANO):
            data = date(ano_inferido + 1, mes, dia)
        return data
    except ValueError:
        return None  # 31/02 e afins: data impossível, ignora


def _ano_do_inicio(texto_inicio):
    # Só conta como ano se for a 3ª parte de dd/mm/aaaa ou "de 2026" no fim.
    # (Antes, em "05/01", o "01" era confundido com o ano 2001.)
    ano = re.search(r"\d{1,2}/\d{1,2}/(\d{2,4})$|de\s+(\d{4})$", texto_inicio or "")
    if not ano:
        return None
    return _ano_completo(ano.group(1) or ano.group(2))


def _fim_do_periodo(encontrado, data_referencia):
    grupos = encontrado.groupdict()
    texto_inicio = grupos.get("inicio") or grupos.get("inicio2")
    texto_fim = grupos.get("fim") or grupos.get("fim2")
    # "de 10/11/2026 a 20/11": o fim herda o ano do início.
    return _texto_para_data(texto_fim, data_referencia, _ano_do_inicio(texto_inicio))


def _prazo_depois_da_ancora(trecho, data_referencia):
    """Pega o período/"até" que vier PRIMEIRO depois da âncora."""
    achados = [m for padrao in (PERIODO, ATE, ENTRE) for m in padrao.finditer(trecho)]
    if not achados:
        return None
    primeiro = min(achados, key=lambda m: m.start())
    # Se existe uma data solta antes do período, o período provavelmente é
    # de outra linha do cronograma. Melhor não arriscar.
    primeira_data = QUALQUER_DATA.search(trecho)
    if primeira_data and primeira_data.start() < primeiro.start():
        return None
    return _fim_do_periodo(primeiro, data_referencia)


def _prazo_antes_da_ancora(trecho, data_referencia):
    """Formato de tabela: "29/09/2026 a 30/09/2026 Inscrição"."""
    for encontrado in PERIODO.finditer(trecho):
        if re.fullmatch(r"[\s:|\-–]*", trecho[encontrado.end():]):
            return _fim_do_periodo(encontrado, data_referencia)
    return None


def _ancora_e_de_outro_assunto(texto, inicio, fim):
    antes = texto[max(0, inicio - JANELA_ANTES):inicio]
    # Só vale o que vem depois da última data (o resto é de outra linha da tabela).
    ultimas_datas = list(QUALQUER_DATA.finditer(antes))
    if ultimas_datas:
        antes = antes[ultimas_datas[-1].end():]
    if ASSUNTO_ERRADO_ANTES.search(antes):
        return True
    return bool(ASSUNTO_ERRADO_DEPOIS.search(texto[fim:fim + 30]))


def extrair_prazo(texto, data_referencia=None):
    """Devolve a data final de inscrição (date) ou None se não tiver certeza."""
    data_referencia = data_referencia or date.today()
    texto = normalizar(texto)
    candidatas = set()

    for ancora in ANCORA.finditer(texto):
        if _ancora_e_de_outro_assunto(texto, ancora.start(), ancora.end()):
            continue
        depois = texto[ancora.end():ancora.end() + JANELA_DEPOIS]
        prazo = _prazo_depois_da_ancora(depois, data_referencia)
        if prazo is None:
            antes = texto[max(0, ancora.start() - JANELA_ANTES):ancora.start()]
            prazo = _prazo_antes_da_ancora(antes, data_referencia)
        if prazo:
            candidatas.add(prazo)

    if len(candidatas) == 1:
        return candidatas.pop()
    return None


def formatar_prazo(prazo):
    return prazo.strftime("%d/%m/%Y") if prazo else TEXTO_SEM_PRAZO
