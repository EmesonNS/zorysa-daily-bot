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
3. Nas permissões do bot, selecione `View Channels`, `Send Messages`, `Embed Links` e
   `Read Message History`, gere o convite e adicione o bot ao servidor desejado.

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

As perguntas são administradas sem alterar o código:

- `/config perguntas listar`
- `/config perguntas adicionar texto obrigatoria`
- `/config perguntas editar pergunta texto obrigatoria`
- `/config perguntas mover pergunta posicao`
- `/config perguntas ativar pergunta`
- `/config perguntas desativar pergunta`

IDs de perguntas e projetos possuem autocomplete. A configuração aceita entre uma e cinco
perguntas ativas; sessões já abertas preservam seus snapshots.

Se `DISCORD_GUILD_ID` estiver configurado, reinicie o container para sincronizar os novos comandos
imediatamente nessa guild. Sem essa variável, a sincronização é global e pode levar mais tempo.

## Daily automática

Cada servidor possui uma agenda própria. Os defaults são segunda a sexta no timezone
`America/Belem`: abertura às `09:00`, primeiro lembrete às `10:30`, último lembrete às `11:30`,
fechamento às `12:00` e relatório diário às `12:10`.

Os comandos administrativos são:

- `/config agenda visualizar`
- `/config agenda horarios abertura primeiro-lembrete ultimo-lembrete fechamento relatorio`
- `/config agenda timezone valor`
- `/config agenda dia-adicionar dia`
- `/config agenda dia-remover dia`

Alterações são aplicadas sem reiniciar o bot. Na abertura, cada projeto ativo e habilitado com
participantes recebe uma sessão e todos são mencionados. Os lembretes mencionam somente quem
ainda não respondeu. No fechamento, pendentes passam para `NOT_ANSWERED`, o botão é removido e o
painel mostra ✅ para quem respondeu e ❌ para quem não respondeu; respostas privadas nunca são
publicadas.

Administradores podem registrar ausência com
`/daily justificar projeto membro motivo data`. A data é opcional (`AAAA-MM-DD`); sem ela, o bot
usa a data local do servidor. O painel mostra 🏖️, mas o motivo permanece privado no banco.

Destinos gerenciais são configurados por `/config relatorios canais`,
`/config relatorios canal-salvar` e `/config relatorios canal-remover`. Um canal pode ser marcado
para relatórios diários, semanais e mensais; nesta etapa somente o relatório diário é agendado.
O relatório apresenta métricas, estados e respostas completas, pagina automaticamente dentro dos
limites do Discord e desabilita todas as menções. Reservations persistidas e nonces determinísticos
evitam uma segunda publicação lógica em retries. Uma falha em um canal não impede os demais.

Se o bot reconectar entre abertura e fechamento, ele cria sessões que estiverem faltando e segue
somente com as próximas etapas. Lembretes vencidos não são repetidos. Sessões abertas cujo prazo
já passou são encerradas imediatamente, inclusive se forem de um dia anterior.

### UAT rápido em uma guild de teste

1. Confirme `/health`, um cargo administrativo, um projeto, seu canal e ao menos um participante.
2. Use `/config agenda visualizar` e confirme timezone e dia atual.
3. Configure duas perguntas de teste e dois canais com relatório diário habilitado.
4. Em `/config agenda horarios`, informe cinco horários futuros separados por poucos minutos,
   sempre na ordem abertura < primeiro lembrete < último lembrete < fechamento < relatório.
5. Observe a abertura; faça um participante responder, justifique outro com `/daily justificar` e
   deixe um terceiro sem resposta. Confirme ✅, 🏖️ e ❌ no painel após o fechamento.
6. Confirme que os dois canais recebem o relatório paginado uma única vez, com métricas corretas,
   respostas completas e nenhuma notificação por menção.
7. Restaure os defaults `09:00`, `10:30`, `11:30`, `12:00` e `12:10`, além das perguntas e canais.

Faça esse teste apenas em uma guild e canal de desenvolvimento. O bot real usa o relógio e o
timezone configurados; não é necessário expor token, URL do banco ou qualquer resposta privada.

## Gate de qualidade

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
.venv/bin/pytest -q
docker compose --env-file .env.example config
docker compose --env-file .env.example build bot
```
