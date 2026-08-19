# Foundation Design

## Architecture

```text
app.main
  ├── app.settings
  ├── app.bot (Discord presentation)
  └── app.infrastructure
        └── database (engine, session, health check)
```

O domínio e a aplicação recebem pacotes vazios nesta etapa para fixar fronteiras, sem criar abstrações prematuras. O ponto de entrada compõe dependências, valida o banco e inicia o cliente Discord.

## Components

- `Settings`: configuração imutável via pydantic-settings e `.env` local.
- `ZorysaBot`: cliente Discord com intents mínimos, sincronização de comandos e `/health`.
- `Database`: engine assíncrono, factory de sessões e consulta `SELECT 1` para readiness.
- Alembic: ambiente conectado aos metadados SQLAlchemy e migration base mínima.
- Docker Compose: `db` com healthcheck e volume; `bot` depende do banco saudável e executa migration antes do processo.

## Error and Secret Handling

- Configuração inválida falha antes de construir clientes externos.
- Erros de autenticação e banco são registrados por tipo e contexto, sem credenciais.
- Logging usa biblioteca padrão e formato consistente; o objeto Settings oculta campos secretos.

## Dependency Policy

Versões de produção usam faixas compatíveis dentro da major estável, evitando betas. As versões iniciais foram verificadas no PyPI em 2026-08-19.

## Test Design

- Unitários importam módulos sem rede e usam doubles para Discord/engine.
- Integração aplica Alembic duas vezes em PostgreSQL e consulta `alembic_version`.
- O gate final também valida `docker compose config`.
