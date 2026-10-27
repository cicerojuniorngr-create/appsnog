# Robô de Vagas (PSS Belém/PA)

Robô que monitora sites de órgãos públicos, empresas públicas, bancas e Sistema S
em Belém/PA e região, procurando editais de processo seletivo simplificado (PSS)
e similares para cargos administrativos, financeiros e de DP/RH. Quando acha
edital novo, manda e-mail com o prazo de inscrição em destaque. Só AVISA: nunca
faz inscrição, login ou preenche formulário.

O dono do projeto é iniciante: explicar tudo em português simples, com analogias.

## Stack
- Python 3.11+ (local do dono: Windows).
- requests + BeautifulSoup (leitura), PyYAML (config), python-dotenv (.env local), pypdf (PDF).
- Roda no PC Windows do dono via Agendador de Tarefas (8h, ou ao ligar o PC). GitHub = só guarda o código.
- E-mail via SMTP do Gmail com senha de app.
- Sem banco, servidor, painel, Docker, LLM. Playwright só se indispensável (o dono liberou decidir).

## Estrutura
- `robo/` código, um arquivo por função (leitura, extração, filtro, prazo, nível, memória, e-mail).
- `config/sites.yaml` lista de sites; `config/palavras_chave.yaml` filtros.
- `dados/editais_vistos.json` memória; `dados/saude_sites.json` saúde dos sites; `dados/log_execucoes.txt`.
- `tests/` pytest (filtro, prazo, nível, memória/fluxo com internet falsa).

## Como rodar
- Instalar: `pip install -r requirements-dev.txt`
- Testes: `python -m pytest`
- Simulação (não envia e-mail, não grava memória): `python -m robo.principal --simulacao`
- Real: `python -m robo.principal`

## Segredos (arquivo .env no PC, NUNCA no código nem em log)
EMAIL_REMETENTE, SENHA_APP_EMAIL, EMAIL_DESTINATARIO (avisos de edital), EMAIL_ADMIN (resumo semanal e alerta de falha geral).

## Convenções
- Código e comentários em português, nomes claros, funções pequenas, comentário explica o PORQUÊ.
- Nunca chutar prazo: sem certeza → "Prazo não identificado, confira o edital".
- Nunca enviar e-mail de teste ao destinatário real sem o dono pedir.
- Respeitar sites: User-Agent identificado, pausa 2–5 s, robots.txt, timeout. Não burlar captcha/bloqueio.
- Não colocar nenhum dado pessoal da pessoa beneficiada no projeto.
- Não inventar URL de site: só entra em sites.yaml o que foi aberto e confirmado.

## Decisões tomadas
- Filtro (robo/filtro.py; regras explicadas no topo do palavras_chave.yaml):
  1. Triagem só com título/resumo da listagem: `tipos_selecao` (ou, se o site tem `pagina_so_de_vagas`,
     já citar cargo/área). Descarta se título/resumo tem `bloqueio` (estágio, concurso público)
     ou se o TÍTULO tem `nao_e_abertura` (convocação, resultado, gabarito...). Retificação passa.
  2. Só para os triados: abre página + até 2 PDFs (robo/edital.py) e procura:
     `cargos` (nomes de cargo) em qualquer lugar; `areas` (orçamento, RH...) só no título/resumo,
     e só se o título/resumo não tiver `fora_do_perfil`.
  Motivos: "estágio"/"concurso público" aparecem no corpo de PSS bons ("estágio não conta como
  experiência"); "Recursos Humanos"/"Gestão de Pessoas" aparecem no corpo como nome de setor.
  Assim "contabilidade" em cargo financeiro não exclui, e Contador com "orçamento" não passa.
- Prazo (robo/prazo.py): âncoras (inscrição, candidatura, envio de currículo) + período/"até" logo depois,
  ou logo antes (tabela de cronograma). Ignora âncoras de isenção/recurso/resultado. Se as âncoras
  discordam → None. Data sem ano: ano da referência; se cair >270 dias no passado, ano seguinte.
- Nível (robo/nivel.py): só expressões completas ("nível superior", não "superior" sozinho).
- "secretária" virou "secretaria executiva/secretário executivo": sem acento, "secretaria" casaria
  com "Secretaria de Estado de ..." em todo site do governo.
- "agente administrativo" adicionado (cargo comum no Pará).
- Comparação por palavra inteira, sem acento e sem maiúscula.
- Duplicata: chave 1 = link+título normalizados; chave 2 = número/ano do edital + órgão.
- Primeira execução (memória vazia): um único e-mail com prazos abertos/não identificados; o resto vira "visto".
- Saúde dos sites em arquivo separado da memória de editais (dados/saude_sites.json): por site última
  leitura ok/falha + histórico das últimas 60 execuções + data do último resumo semanal.
- Memória: dict editais[id] com titulo, orgao, link, visto_em, prazo, niveis, cargos, relevante, avisado,
  chave_duplicata. Itens triados e irrelevantes também são anotados (evita reabrir todo dia).
  Itens cujo edital não abriu e que o título não confirma NÃO são anotados (tenta no dia seguinte).
- Duplicata: número/ano do edital (no título) + prazo final. Sem número ou sem prazo → sem checagem.
- Máximo de 15 editais abertos por site por dia (o resto fica pra amanhã).
- Fuso: UTC-3 fixo (Belém não tem horário de verão; evita depender de tzdata no Windows).
- Resumo semanal: na primeira execução de cada semana ISO (segunda, ou depois se o PC ficou desligado).
- dados/*.json e *.txt estão no .gitignore: memória fica só no PC.
- Resumo semanal (segunda) e alerta "todos os sites falharam" vão para EMAIL_ADMIN, não para a destinatária.
- Repositório: cicerojuniorngr-create/appsnog (PRIVADO, confirmado), branch main.

- Playwright NÃO adotado por ora: os sites que exigem JS (Portal CR2, Senai/Sesi, SEST SENAT) trazem pouco valor
  e o custo (≈150 MB de navegador, execução lenta) não compensa.

## Descoberta crítica (Etapa 2)
- Quase todos os sites do Governo do Pará (.pa.gov.br hospedados na Prodepa, uepa.br, banpara.b.br, sipros)
  DERRUBAM conexões vindas de IP estrangeiro. O ambiente de teste e os runners do GitHub Actions ficam nos EUA.
  Logo, em GitHub Actions o robô NÃO lê SESPA/SEAD/SEDUC/UEPA/Hemopa/Prodepa/Banpará/Sipros/Prefeitura de Belém.
  Confirmado pelo dono: do PC dele (Brasil, sem VPN) o Sipros abre.
- DECISÃO: o robô roda no PC Windows do dono pelo Agendador de Tarefas (liga todo dia; tarefa configurada
  para rodar assim que o PC ligar se perdeu o horário das 8h). Segredos ficam no .env do PC.
  GitHub vira só o "cofre" do código (repo privado). GitHub Actions/commit automático da memória saem do plano.
- Proteção contra rodar 2x no mesmo dia (PC reiniciado): o robô anota a data da última execução e pula se já rodou hoje.

## Comandos úteis
- Testar leitura dos sites: `python -m robo.testar_sites` (ou `python -m robo.testar_sites Senac`)

## Status
- Etapa 1 concluída.
- Etapa 2 concluída: config/sites.yaml testada (11 legíveis, 5 parciais, 14 não lidos daqui dos EUA).
- Etapa 3 concluída: filtro, prazo, nível, extrator de itens, leitor de PDF; 65 testes.
  Teste real: Senac (PRS 34/39/40 Assistente de Administração) e Sesc (Auxiliar Administrativo I)
  detectados com prazo e nível corretos. Sites do Estado (Sipros etc.) ainda não testados: só do PC do dono.
- Etapa 4 concluída: robo/memoria.py, robo/saude_sites.py, robo/principal.py (--simulacao, --forcar); 74 testes.
  Modo real ainda BLOQUEADO em principal.main() até a Etapa 5 (e-mail), pra não anotar como "avisado" sem enviar.
  Simulação real daqui: ~4 min, 14 sites lidos, 0 avisos (todos os editais do perfil com prazo vencido).
- Próxima: Etapa 5 (e-mail de aviso, resumo semanal, alerta de falha geral).
