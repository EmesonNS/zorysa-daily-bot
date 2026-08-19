# State

**Last Updated:** 2026-08-19
**Current Work:** M1 implementada e aguardando UAT manual no Discord

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

### AD-004: Bootstrap administrativo (2026-08-19)

**Decision:** Sem cargos configurados, dono da guild ou membro com `Manage Server` pode cadastrar o primeiro cargo; depois disso, somente cargos configurados administram.
**Reason:** Decisão explícita do responsável do produto para permitir configuração inicial segura.
**Trade-off:** A remoção do último cargo é bloqueada para não reabrir o bootstrap acidentalmente.
**Impact:** Todos os comandos administrativos passam pela mesma política de autorização.

## Active Blockers

- Executar o UAT da M1 na guild real com administrador, participante e usuário externo.

## Lessons Learned

- O wrapper de apply_patch apresentou falha temporária do sandbox no início do projeto; alterações posteriores voltaram a funcionar.
- Testes de configuração precisam remover explicitamente variáveis do ambiente durante gates de integração.

## Deferred Ideas

- [ ] Renomear os arquivos de origem para remover LACIS, se desejado.

## Todos

- [x] Especificar e implementar M1 — Daily manual completa.
- [ ] Aprovar o UAT manual da M1 no Discord.

## Preferences

**Model Guidance Shown:** never
