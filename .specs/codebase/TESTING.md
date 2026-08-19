# Testing

## Strategy

- Regras puras, configuração e adaptadores: testes unitários com pytest.
- Código assíncrono: pytest-asyncio.
- PostgreSQL e migrations: testes de integração contra o serviço do Docker Compose.
- Integração real com Discord: smoke test manual somente após configurar credenciais locais.

## Test Coverage Matrix

| Layer | Required test | Parallel-safe |
|---|---|---|
| Configuração e logging | unit | Yes |
| Apresentação Discord | unit com doubles | Yes |
| Infraestrutura de banco | unit | Yes |
| Migrations PostgreSQL | integration | No |
| Docker e arquivos declarativos | none | Yes |

## Gate Check Commands

| Gate | Command |
|---|---|
| Quick | `.venv/bin/pytest -q tests/unit` |
| Full | `.venv/bin/pytest -q` |
| Build | `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app && .venv/bin/pytest -q` |

## Integration Prerequisites

1. `docker compose up -d db`
2. Exportar `DATABASE_URL=postgresql+asyncpg://zorysa:zorysa@localhost:5432/zorysa_daily`
3. Executar `.venv/bin/pytest -q tests/integration`

Os testes unitários não dependem de rede, Discord ou Docker.
