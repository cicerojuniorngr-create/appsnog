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
- GitHub Actions (cron 11:00 UTC = 8h America/Belem). Memória gravada por commit automático.
- E-mail via SMTP do Gmail com senha de app.
- Sem banco, servidor, painel, Docker, LLM. Playwright só se indispensável (o dono liberou decidir).

## Estrutura
- `robo/` código, um arquivo por função (leitura, extração, filtro, prazo, nível, memória, e-mail).
- `config/sites.yaml` lista de sites; `config/palavras_chave.yaml` filtros.
- `dados/editais_vistos.json` memória; `dados/saude_sites.json` saúde dos sites; `dados/log_execucoes.txt`.
- `tests/` pytest (filtro, prazo, nível).

## Como rodar
- Instalar: `pip install -r requirements-dev.txt`
- Testes: `python -m pytest`
- Simulação (não envia e-mail, não grava memória): `python -m robo.principal --simulacao`
- Real: `python -m robo.principal`

## Segredos (GitHub Secrets / .env local, NUNCA no código nem em log)
EMAIL_REMETENTE, SENHA_APP_EMAIL, EMAIL_DESTINATARIO (avisos de edital), EMAIL_ADMIN (resumo semanal e alerta de falha geral).

## Convenções
- Código e comentários em português, nomes claros, funções pequenas, comentário explica o PORQUÊ.
- Nunca chutar prazo: sem certeza → "Prazo não identificado, confira o edital".
- Nunca enviar e-mail de teste ao destinatário real sem o dono pedir.
- Respeitar sites: User-Agent identificado, pausa 2–5 s, robots.txt, timeout. Não burlar captcha/bloqueio.
- Não colocar nenhum dado pessoal da pessoa beneficiada no projeto.
- Não inventar URL de site: só entra em sites.yaml o que foi aberto e confirmado.

## Decisões tomadas
- Filtro em duas fases: (1) título/resumo indica seleção (`tipos_selecao`); (2) só para itens novos,
  abre a página/PDF do edital e procura cargos do perfil (`inclusao`).
- Exclusão em 3 níveis: `bloqueio_total` (estágio: descarta sempre), `bloqueio_titulo`
  (concurso público: só se estiver no título), `cargos_fora_do_perfil` (nunca descarta sozinho,
  só tira o cargo da lista do e-mail). Por isso "contabilidade" dentro de cargo financeiro não exclui.
- "secretária" virou "secretaria executiva/secretário executivo": sem acento, "secretaria" casaria
  com "Secretaria de Estado de ..." em todo site do governo.
- "agente administrativo" adicionado (cargo comum no Pará).
- Comparação por palavra inteira, sem acento e sem maiúscula.
- Duplicata: chave 1 = link+título normalizados; chave 2 = número/ano do edital + órgão.
- Primeira execução (memória vazia): um único e-mail com prazos abertos/não identificados; o resto vira "visto".
- Saúde dos sites em arquivo separado da memória de editais.
- Resumo semanal (segunda) e alerta "todos os sites falharam" vão para EMAIL_ADMIN, não para a destinatária.
- Repositório: cicerojuniorngr-create/appsnog (dono precisa deixar PRIVADO antes do primeiro push).

- Playwright NÃO adotado por ora: os sites que exigem JS (Portal CR2, Senai/Sesi, SEST SENAT) trazem pouco valor
  e o custo (≈150 MB de navegador, execução lenta) não compensa.

## Descoberta crítica (Etapa 2)
- Quase todos os sites do Governo do Pará (.pa.gov.br hospedados na Prodepa, uepa.br, banpara.b.br, sipros)
  DERRUBAM conexões vindas de IP estrangeiro. O ambiente de teste e os runners do GitHub Actions ficam nos EUA.
  Logo, em GitHub Actions o robô NÃO lê SESPA/SEAD/SEDUC/UEPA/Hemopa/Prodepa/Banpará/Sipros/Prefeitura de Belém.
  Pendente: dono testar do PC (Brasil) com `python -m robo.testar_sites` e decidir onde o robô roda.

## Comandos úteis
- Testar leitura dos sites: `python -m robo.testar_sites` (ou `python -m robo.testar_sites Senac`)

## Status
- Etapa 1 concluída.
- Etapa 2: lista em config/sites.yaml testada (12 legíveis, 4 parciais, 14 não lidos daqui dos EUA).
  AGUARDANDO ok do dono + decisão sobre onde rodar (problema do bloqueio de IP estrangeiro).
