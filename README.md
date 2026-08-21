# Zorysa Daily Bot

Bot de daily para Discord com Slash Commands, PostgreSQL assíncrono, migrations Alembic,
automação por guild, relatórios históricos e auditoria administrativa.

## Requisitos

- Docker com Docker Compose para a execução recomendada;
- Python 3.12 para desenvolvimento local;
- uma aplicação de bot criada no Discord Developer Portal.

## Configuração

Crie o arquivo local e substitua todos os valores `replace-with-*`:

```bash
cp .env.example .env
```

Nunca publique `.env`, `DISCORD_TOKEN` ou `DATABASE_URL`. `DISCORD_GUILD_ID` é opcional: use o
ID de uma guild de desenvolvimento para sincronizar comandos imediatamente. Sem ele, os comandos
são globais e podem demorar para aparecer.

## Configuração mínima no Discord

No Discord Developer Portal:

1. Em **Bot > Privileged Gateway Intents**, habilite somente **Server Members Intent**. Mantenha
   **Presence Intent** e **Message Content Intent** desabilitados.
2. Em **OAuth2 > URL Generator**, selecione os escopos `bot` e `applications.commands`.
3. Conceda somente `View Channels`, `Send Messages`, `Embed Links` e `Read Message History` nos
   canais usados pelo bot. Não conceda `Administrator`.
4. Convide o bot e execute `/health` para conferir nome, latência e guild atual.

O intent `members` permite receber a saída de membros e encerrar memberships futuras. O bot não lê
mensagens, presença nem conteúdo fora das interações explícitas.

## Execução com Docker

O `DATABASE_URL` de `.env.example` usa o hostname `db`, correto dentro do Compose:

```bash
docker compose up --build -d
docker compose logs -f bot
```

PostgreSQL e bot usam `restart: unless-stopped`. O bot aguarda o healthcheck, executa
`alembic upgrade head` e inicia apenas depois. Para reiniciar ou inspecionar:

```bash
docker compose restart bot
docker compose ps
docker compose logs --tail=200 bot db
```

Para encerrar sem perder o banco:

```bash
docker compose down
```

O volume nomeado `postgres_data` é preservado. Só use `docker compose down -v` se quiser remover
deliberadamente todos os dados locais.

## Execução local

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

Altere apenas o hostname do `DATABASE_URL` de `db` para `localhost`, mantenha o PostgreSQL ativo e
execute:

```bash
.venv/bin/alembic upgrade head
.venv/bin/python -m app.main
```

## Administração inicial

O primeiro cargo administrativo pode ser cadastrado pelo dono ou por alguém com `Gerenciar
Servidor`. Depois disso, somente cargos cadastrados administram o bot.

- `/config admin role-adicionar cargo`
- `/config admin role-remover cargo`
- `/config admin roles`

Respostas administrativas são efêmeras. Tokens, respostas de daily e motivos de ausência não são
gravados nem exibidos na auditoria.

## Comandos da V1

### Projetos e membros

- `/projeto criar nome canal`
- `/projeto editar projeto nome canal daily-habilitada`
- `/projeto detalhes projeto`
- `/projeto arquivar projeto`
- `/projeto listar`
- `/projeto membro-adicionar projeto usuario`
- `/projeto membro-remover projeto usuario`
- `/projeto membros projeto`
- `/membro projetos usuario`

Os campos de projeto oferecem autocomplete. Arquivar preserva sessões, assignments, respostas e
relatórios históricos, encerra memberships ativas e impede novas dailies.

### Daily

- `/daily abrir projeto`
- `/daily justificar projeto membro motivo data`
- `/daily status projeto data`
- `/daily fechar projeto data`

`data` é opcional no formato `AAAA-MM-DD` e usa o dia local da guild quando omitida. A abertura
menciona participantes; lembretes mencionam somente pendentes. O painel público mostra estado, não
respostas. No fechamento, pendentes passam para `NOT_ANSWERED`, o botão é removido e justificativas
continuam privadas.

### Perguntas

- `/config perguntas listar`
- `/config perguntas adicionar texto obrigatoria`
- `/config perguntas editar pergunta texto obrigatoria`
- `/config perguntas mover pergunta posicao`
- `/config perguntas ativar pergunta`
- `/config perguntas desativar pergunta`

São permitidas de uma a cinco perguntas ativas. Sessões abertas preservam snapshots, portanto
alterações posteriores não reescrevem o histórico.

### Agenda automática

- `/config agenda visualizar`
- `/config agenda horarios abertura primeiro-lembrete ultimo-lembrete fechamento relatorio`
- `/config agenda timezone valor`
- `/config agenda dia-adicionar dia`
- `/config agenda dia-remover dia`
- `/config agenda relatorios dia-semanal horario-semanal horario-mensal`

Defaults em `America/Belem`: segunda a sexta, abertura `09:00`, lembretes `10:30` e `11:30`,
fechamento `12:00`, diário `12:10`, semanal sexta-feira `12:20` e mensal `12:20` no último dia de
execução configurado do mês. Horários gerenciais precisam ser posteriores ao fechamento. Mudanças
persistem, são auditadas e reconciliam os sete jobs sem reiniciar o bot.

### Destinos e relatórios

- `/config relatorios canais`
- `/config relatorios canal-salvar canal diario semanal mensal`
- `/config relatorios canal-remover canal`
- `/relatorio gerar tipo periodo projeto`

O relatório manual aceita diário (`AAAA-MM-DD`), semanal (`AAAA-MM-DD`, semana ISO da data) e
mensal (`AAAA-MM`); período e projeto são opcionais. Relatórios automáticos diário, semanal e mensal
usam somente os destinos habilitados para o tipo. O conteúdo é paginado sem truncamento e usa
`AllowedMentions.none()`. Reservations persistidas e nonces determinísticos impedem segunda
publicação lógica em retries; uma falha de canal não bloqueia os demais destinos.

### Auditoria

- `/config auditoria listar acao ator alvo-tipo alvo-id inicio fim cursor`

Todos os filtros são opcionais; datas usam `AAAA-MM-DD`. O comando retorna dez eventos por página
e fornece o próximo `cursor`. A consulta é efêmera e mostra apenas ação, instante e IDs operacionais,
sem respostas, justificativas ou segredos.

## Recuperação e consistência

Ao conectar ou reiniciar, o bot reconstrói os sete jobs por guild. Ele fecha sessões abertas já
vencidas, garante a abertura do dia quando aplicável e recupera no máximo os relatórios diário,
semanal ou mensal devidos no dia local corrente. Não há rajada retroativa; períodos antigos ficam
disponíveis por `/relatorio gerar`.

Sessões, respostas, reservations e auditoria ficam no PostgreSQL. A saída de um membro encerra
somente memberships ativas para sessões futuras e preserva assignments já criados. Falhas de canal,
membro, guild ou banco são isoladas por IDs operacionais para que outras guilds e projetos continuem.

## UAT histórico em uma guild de desenvolvimento

Faça este roteiro somente em uma guild/canais de teste e nunca compartilhe token, URL do banco ou
respostas privadas.

1. Habilite **Server Members Intent**, inicie com `docker compose up --build -d` e acompanhe
   `docker compose logs -f bot`; confirme `/health`.
2. Cadastre cargo, dois projetos, três participantes e perguntas. Confira `/projeto detalhes`,
   `/membro projetos` e `/config auditoria listar`.
3. Configure dias e horários futuros próximos, respeitando abertura < lembretes < fechamento <
   diário. Configure semanal para o dia atual e, se o dia for o último habilitado do mês, valide
   também o mensal.
4. Configure dois canais para diário, semanal e mensal. Remova temporariamente `Send Messages` de
   um deles para simular falha; confirme que o outro recebe o relatório e o bot permanece online.
5. Aguarde a abertura, responda por um participante, justifique outro e deixe o terceiro pendente.
   Confirme ✅, 🏖️ e ❌ após o fechamento, sem respostas ou motivo no painel.
6. Confirme uma única publicação automática diária e semanal; no último dia configurado do mês,
   confirme a mensal. Use `/relatorio gerar` para validar manualmente os três períodos.
7. Execute `docker compose restart bot` após a abertura e depois de uma publicação. Confirme que a
   daily e os jobs voltam, sem duplicar mensagens lógicas nem recuperar períodos anteriores.
8. Remova um membro da guild e confirme que `/projeto membros` deixa de mostrá-lo em projetos
   futuros, enquanto relatórios antigos permanecem iguais.
9. Arquive um projeto, confira `/projeto detalhes` e gere relatório histórico filtrado para ele.
10. Consulte a auditoria por ação, ator, alvo e período; valide paginação e ausência de respostas,
    motivo, token ou credencial.
11. Restaure permissões, agenda, perguntas, destinos e participantes de teste.

## Gate de qualidade

Com PostgreSQL acessível pelo `DATABASE_URL` local:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
.venv/bin/pytest -q
.venv/bin/alembic check
docker compose --env-file .env.example config
docker compose --env-file .env.example build bot
```
