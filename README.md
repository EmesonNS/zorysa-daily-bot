# Zorysa Daily Bot

Bot de daily para Discord, com Slash Commands, PostgreSQL assíncrono e migrations Alembic.

## Requisitos

- Python 3.12 para execução local
- Docker com Docker Compose para a stack em containers
- Uma aplicação de bot criada no Discord Developer Portal

## Configuração

Crie o arquivo local de ambiente e substitua todos os valores `replace-with-*`:

```bash
cp .env.example .env
```

Nunca publique o `.env` nem o token do Discord. `DISCORD_GUILD_ID` é opcional e acelera a
sincronização dos comandos durante o desenvolvimento; sem ele, os comandos são globais.

## Execução com Docker

O `DATABASE_URL` do exemplo já usa o hostname `db`, adequado à rede do Compose:

```bash
docker compose up --build
```

O Compose inicia PostgreSQL 17 com volume persistente, aguarda o healthcheck, executa
`alembic upgrade head` e só então inicia o bot. Para encerrar:

```bash
docker compose down
```

O volume `postgres_data` é preservado por esse comando.

## Execução local

Crie o ambiente virtual e instale as dependências:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

Inicie PostgreSQL e altere no `.env` o hostname do banco de `db` para `localhost`. Depois,
aplique as migrations e execute o ponto de entrada:

```bash
.venv/bin/alembic upgrade head
.venv/bin/python -m app.main
```

## Configuração mínima no Discord

No Discord Developer Portal:

1. Em **Bot**, copie o token para `DISCORD_TOKEN` e mantenha desabilitados os intents
   privilegiados (`Presence`, `Server Members` e `Message Content`). O bot usa apenas o intent
   de guilds.
2. Em **OAuth2 > URL Generator**, selecione os escopos `bot` e `applications.commands`.
3. Nas permissões do bot, selecione `View Channels`, `Send Messages` e `Embed Links`, gere o
   convite e adicione o bot ao servidor desejado.

Após conectar, use `/health` para verificar o nome do bot, a latência e a guild atual.

## Daily manual

O primeiro cargo administrativo deve ser cadastrado pelo dono do servidor ou por alguém com
`Gerenciar Servidor`. Depois disso, somente os cargos cadastrados administram o bot:

1. `/config admin role-adicionar cargo:@Administradores`
2. `/projeto criar nome:AmazHealth canal:#daily-amazhealth`
3. `/projeto membro-adicionar projeto:amazhealth usuario:@Pessoa`
4. `/daily abrir projeto:amazhealth`

Use `/projeto listar`, `/projeto membros` e `/config admin roles` para consultar a configuração.
Participantes respondem pelo botão **Responder daily** e pelo modal privado. A mensagem pública
mostra apenas quem respondeu; o conteúdo das respostas permanece no banco.

Se `DISCORD_GUILD_ID` estiver configurado, reinicie o container para sincronizar os novos comandos
imediatamente nessa guild. Sem essa variável, a sincronização é global e pode levar mais tempo.

## Gate de qualidade

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
.venv/bin/pytest -q
docker compose --env-file .env.example config
docker compose --env-file .env.example build bot
```
