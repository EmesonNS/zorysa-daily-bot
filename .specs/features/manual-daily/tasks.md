# Tarefas — M1 Daily manual

**Status:** implementação e gates automatizados concluídos; UAT manual pendente.

## Ordem e dependências

| ID | Entrega | Depende de | Verificação |
|---|---|---|---|
| T1 | Enums e modelos SQLAlchemy de guild/configuração | M0 | testes de metadata e constraints |
| T2 | Modelos de projeto e membership histórico | T1 | testes unitários de modelo |
| T3 | Modelos de sessão, snapshots, assignments e respostas | T1 | testes unitários de modelo |
| T4 | Migration `0002_manual_daily` com todas as tabelas e índices | T2, T3 | upgrade em PostgreSQL real, repetição e downgrade/upgrade |
| T5 | `GuildAdminService`, defaults e regra de bootstrap | T4 | testes unitários e integração de autorização/CRUD |
| T6 | `ProjectService` e memberships históricos | T4 | testes de criação, listagem, duplicidade, saída e reentrada |
| T7 | `DailyService` e abertura/resposta transacionais | T5, T6 | testes de idempotência, snapshots, bloqueios e persistência |
| T8 | Comandos `/config` e `/projeto` | T5, T6 | testes unitários com doubles Discord |
| T9 | `/daily abrir`, renderer, view persistente e modal | T7 | testes unitários de interação e renderização |
| T10 | Registro no bot, tratamento de erros e documentação | T8, T9 | suíte completa, Ruff, mypy, Compose e smoke manual |

## Regras de execução

- Cada tarefa inclui seus testes RED/GREEN antes de avançar.
- Alterações de schema entram somente pela migration Alembic.
- Testes unitários não dependem de Discord, rede ou Docker.
- Testes de integração usam PostgreSQL e limpam apenas os registros criados pelo teste.
- Commits são atômicos por tarefa ou por conjunto inseparável de schema/migration.

## Gate final

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
.venv/bin/pytest -q
docker compose --env-file .env.example config
docker compose --env-file .env.example build bot
```

## UAT manual

Executar o cenário de aceite de `spec.md` em uma guild de teste, incluindo um usuário de fora do projeto e reinício do container antes de clicar no botão.
