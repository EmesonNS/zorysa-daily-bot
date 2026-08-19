# Zorysa Daily Bot

**Vision:** Automatizar no Discord o ciclo diário dos projetos da LACIS com configuração dinâmica, histórico confiável e baixa poluição nos canais.
**For:** Participantes, administradores e gestores dos projetos da LACIS.
**Solves:** Coleta manual, cobranças dispersas e dificuldade de consolidar o andamento de pessoas em múltiplos projetos.

## Goals

- Executar uma daily de ponta a ponta sem intervenção manual.
- Preservar o histórico após mudanças de equipe, arquivamentos e reinicializações.
- Administrar configurações operacionais pelo Discord sem alterar código.

## Tech Stack

- Python 3.12, discord.py, SQLAlchemy 2, Alembic e APScheduler.
- PostgreSQL, Docker e Docker Compose.
- pytest, pytest-asyncio, Ruff e mypy.

## Scope

**V1 includes:** projetos, participantes, daily automática, formulário, lembretes, ausências, relatórios, configuração, histórico e recuperação.

**Explicitly out of scope:** dashboard web, aplicativo móvel, IA obrigatória, integrações externas, ranking e microserviços.

## Constraints

- Timezone inicial America/Belem, configurável por guild.
- IDs do Discord são identificadores permanentes.
- Segredos existem somente em variáveis de ambiente e nunca nos logs.
