# State

**Last Updated:** 2026-08-19
**Current Work:** M0 — Fundação técnica

## Recent Decisions (Last 60 days)

### AD-001: Nome do produto (2026-08-19)

**Decision:** O nome oficial é Zorysa Daily Bot.
**Reason:** Correção solicitada pelo responsável do produto.
**Trade-off:** Os nomes dos documentos de origem mantêm LACIS para evitar renomeação de arquivos não solicitada.
**Impact:** Código, logs, documentação e mensagens usam Zorysa Daily Bot.

### AD-002: Baseline técnica (2026-08-19)

**Decision:** Python 3.12, requirements.txt, pytest, pytest-asyncio, Ruff e mypy, além da stack aprovada na especificação.
**Reason:** Confirmação explícita do responsável do produto.
**Trade-off:** Dependências de produção e desenvolvimento ficam separadas em dois arquivos requirements.
**Impact:** Gates locais validam lint, formatação, tipos e testes.

### AD-003: Monólito modular assíncrono (2026-08-19)

**Decision:** Discord, aplicação, domínio e infraestrutura ficam isolados; SQLAlchemy usa asyncpg.
**Reason:** Discord e banco são I/O assíncrono, e a especificação pede separação clara sem microserviços.
**Trade-off:** Migrations Alembic continuam com adaptação síncrona própria da ferramenta.
**Impact:** Casos de uso futuros não dependerão diretamente de objetos do Discord.

## Active Blockers

- A conexão real depende de DISCORD_TOKEN e de uma guild de teste configurados somente no .env local.

## Lessons Learned

- O wrapper de apply_patch apresentou falha temporária do sandbox no início do projeto; alterações posteriores voltaram a funcionar.

## Deferred Ideas

- [ ] Renomear os arquivos de origem para remover LACIS, se desejado.

## Todos

- [ ] Concluir as tarefas da fundação técnica.

## Preferences

**Model Guidance Shown:** never
