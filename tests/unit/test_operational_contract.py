from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_compose_restarts_bot_and_database_while_preserving_postgresql_volume() -> None:
    compose = _read("docker-compose.yml")

    assert compose.count("restart: unless-stopped") == 2
    assert "postgres_data:/var/lib/postgresql/data" in compose
    assert "condition: service_healthy" in compose


def test_readme_documents_only_required_discord_intents_and_permissions() -> None:
    readme = _read("README.md")

    assert "Server Members Intent" in readme
    assert "habilite" in readme.casefold()
    assert "Presence Intent" in readme and "Message Content Intent" in readme
    for permission in ("View Channels", "Send Messages", "Embed Links", "Read Message History"):
        assert permission in readme


@pytest.mark.parametrize(
    "command",
    [
        "/config admin roles",
        "/config agenda relatorios",
        "/config auditoria listar",
        "/projeto editar",
        "/membro projetos",
        "/daily status",
        "/daily fechar",
        "/relatorio gerar",
    ],
)
def test_readme_documents_historical_management_commands(command: str) -> None:
    assert command in _read("README.md")


def test_readme_uat_covers_reports_audit_restart_and_isolated_failures() -> None:
    readme = _read("README.md").casefold()

    for subject in ("diário", "semanal", "mensal", "auditoria", "restart", "falha"):
        assert subject in readme
    assert "docker compose logs -f bot" in readme


def test_example_environment_contains_placeholders_instead_of_live_secrets() -> None:
    example = _read(".env.example")

    assert "replace-with-your-discord-bot-token" in example
    assert "replace-with-a-strong-password" in example
    assert "discord.com/api" not in example.casefold()
