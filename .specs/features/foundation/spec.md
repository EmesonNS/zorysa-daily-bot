# Foundation Specification

## Problem Statement

O projeto possui requisitos funcionais completos, mas ainda não tem aplicação executável. A fundação deve tornar Discord e PostgreSQL acessíveis com configuração segura e uma estrutura que permita evoluir os módulos do domínio sem acoplamento.

## Goals

- [x] Executar um único ponto de entrada Python localmente e em Docker.
- [x] Validar configuração antes de conectar a serviços externos.
- [x] Registrar um Slash Command de diagnóstico sem expor segredos.
- [x] Criar e versionar o banco por migrations reproduzíveis.

## Out of Scope

| Feature | Reason |
|---|---|
| Projetos, membros e dailies | Pertencem ao milestone M1 |
| Scheduler operacional | Pertence ao milestone M2 |
| Relatórios | Pertencem aos milestones M3 e M4 |

## Requirements

### FND-01 — Estrutura modular

WHEN o projeto for instalado THEN o sistema SHALL expor um ponto de entrada único e separar apresentação Discord, aplicação, domínio e infraestrutura.

### FND-02 — Configuração segura

WHEN a aplicação iniciar THEN o sistema SHALL carregar token e banco do ambiente, rejeitar valores ausentes e nunca registrar o token.

### FND-03 — Aplicação Discord

WHEN o bot estiver pronto THEN o sistema SHALL sincronizar Slash Commands e expor `/health` com nome, latência e guild atual.

### FND-04 — Persistência

WHEN a conexão for inicializada THEN o sistema SHALL usar SQLAlchemy assíncrono e produzir erro operacional compreensível se PostgreSQL estiver indisponível.

### FND-05 — Migrations

WHEN `alembic upgrade head` executar em banco vazio THEN o sistema SHALL criar o schema base e registrar sua revisão sem reaplicá-la.

### FND-06 — Containerização

WHEN `docker compose up` executar com ambiente válido THEN o sistema SHALL iniciar PostgreSQL saudável, aplicar migrations e iniciar o bot usando volume persistente.

### FND-07 — Qualidade e documentação

WHEN o gate de build executar THEN lint, formato, tipos e testes SHALL passar; o README SHALL documentar setup e permissões mínimas do Discord.

## Edge Cases

- WHEN DISCORD_TOKEN estiver vazio THEN a aplicação SHALL falhar antes de tentar rede e sem imprimir o valor.
- WHEN DATABASE_URL for inválida ou o banco estiver indisponível THEN a aplicação SHALL encerrar com mensagem clara e código não zero.
- WHEN a migration já estiver aplicada THEN nova execução SHALL ser idempotente.

## Requirement Traceability

| Requirement | Backlog | Status |
|---|---|---|
| FND-01 | US-001 | Verified |
| FND-02 | US-002, US-003, US-059 | Verified |
| FND-03 | US-002 | Verified |
| FND-04 | US-003 | Verified |
| FND-05 | US-004 | Verified |
| FND-06 | US-005 | Verified |
| FND-07 | US-006, US-056, US-057, US-060, US-061 | Verified |

**Coverage:** 7 total, 7 mapped, 0 unmapped.
