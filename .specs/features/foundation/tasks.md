# Foundation Tasks

**Design:** `.specs/features/foundation/design.md`
**Status:** Done

## Execution Plan

```text
T1 → T2 ─┬→ T3 ─┐
         └→ T4 → T5 ─┬→ T6
                 T3 ─┘
```

### T1: Criar scaffold e tooling
**Status:** Complete

**What:** Criar pacotes, dependências e configuração de pytest, Ruff e mypy.
**Where:** `app/`, `tests/`, `requirements*.txt`, `pyproject.toml`, `.gitignore`
**Depends on:** None
**Requirement:** FND-01, FND-07
**Tools:** apply_patch, shell; skills tlc-spec-driven e codenavi
**Tests:** none
**Gate:** build
**Done when:** imports compilam, ferramentas instalam e configuração é aceita.
**Verify:** `python -m compileall app && .venv/bin/ruff check . && .venv/bin/mypy app`
**Commit:** `build(foundation): scaffold python application`

### T2: Implementar configuração e logging
**Status:** Complete

**What:** Carregar e validar ambiente com segredos ocultos e logging seguro.
**Where:** `app/settings.py`, `app/logging.py`, `tests/unit/test_settings.py`
**Depends on:** T1
**Requirement:** FND-02, FND-07
**Tools:** apply_patch, shell
**Tests:** unit
**Gate:** quick
**Done when:** 4 testes cobrem defaults, ausências, DSN e ocultação do token.
**Verify:** `.venv/bin/pytest -q tests/unit/test_settings.py`
**Commit:** `feat(config): add validated environment settings`

### T3: Implementar cliente Discord [P]
**Status:** Complete

**What:** Criar o bot, sincronização e Slash Command `/health` testável sem rede.
**Where:** `app/bot/client.py`, `app/bot/commands/health.py`, `tests/unit/bot/`
**Depends on:** T2
**Requirement:** FND-03
**Tools:** apply_patch, shell, documentação oficial discord.py
**Tests:** unit
**Gate:** quick
**Done when:** 3 testes validam intents, resposta do health e registro do comando.
**Verify:** `.venv/bin/pytest -q tests/unit/bot`
**Commit:** `feat(discord): add bot client and health command`

### T4: Implementar infraestrutura de banco [P]
**Status:** Complete

**What:** Criar engine, sessões e readiness assíncrono com erro controlado.
**Where:** `app/infrastructure/database/`, `tests/unit/infrastructure/test_database.py`
**Depends on:** T2
**Requirement:** FND-04
**Tools:** apply_patch, shell, documentação oficial SQLAlchemy
**Tests:** unit
**Gate:** quick
**Done when:** 3 testes validam engine, `SELECT 1` e falha sanitizada.
**Verify:** `.venv/bin/pytest -q tests/unit/infrastructure/test_database.py`
**Commit:** `feat(database): add async sqlalchemy infrastructure`

### T5: Configurar Alembic e migration base
**Status:** Complete

**What:** Criar ambiente Alembic e uma revisão base reproduzível e idempotente.
**Where:** `alembic.ini`, `migrations/`, `tests/integration/test_migrations.py`
**Depends on:** T4
**Requirement:** FND-05
**Tools:** apply_patch, shell, Docker
**Tests:** integration
**Gate:** full
**Done when:** migration aplica duas vezes e `alembic_version` contém uma revisão.
**Verify:** `.venv/bin/pytest -q tests/integration/test_migrations.py`
**Commit:** `feat(database): add baseline alembic migration`

### T6: Containerizar e documentar
**Status:** Complete

**What:** Orquestrar bot e banco e documentar instalação, ambiente e permissões.
**Where:** `Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md`, `app/main.py`
**Depends on:** T3, T5
**Requirement:** FND-06, FND-07
**Tools:** apply_patch, shell, Docker
**Tests:** none
**Gate:** build
**Done when:** Compose é válido, imagem constrói e gate completo passa.
**Verify:** `docker compose config && docker compose build bot` e gate build.
**Commit:** `build(docker): add local application stack`

## Parallelism Map

T3 e T4 podem executar em paralelo após T2; seus arquivos e testes são independentes. Integração com PostgreSQL permanece sequencial.

## Task Granularity Check

| Task | Deliverable | Status |
|---|---|---|
| T1 | scaffold executável | ✅ Granular |
| T2 | configuração tipada | ✅ Granular |
| T3 | adaptador Discord | ✅ Granular |
| T4 | adaptador PostgreSQL | ✅ Granular |
| T5 | mecanismo de migrations | ✅ Granular |
| T6 | stack operacional | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends on | Diagram shows | Status |
|---|---|---|---|
| T1 | None | None | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T2 | T2 → T3 | ✅ |
| T4 | T2 | T2 → T4 | ✅ |
| T5 | T4 | T4 → T5 | ✅ |
| T6 | T3, T5 | T3/T5 → T6 | ✅ |

## Test Co-location Validation

| Task | Layer | Matrix requires | Task says | Status |
|---|---|---|---|---|
| T1 | tooling | none | none | ✅ |
| T2 | config/logging | unit | unit | ✅ |
| T3 | Discord | unit | unit | ✅ |
| T4 | database | unit | unit | ✅ |
| T5 | migrations | integration | integration | ✅ |
| T6 | declarative/runtime | none | none | ✅ |
