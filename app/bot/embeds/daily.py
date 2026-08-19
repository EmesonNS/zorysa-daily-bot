"""Public daily status renderer."""

import discord

from app.bot.contracts import DailyPanel


def render_daily_panel(panel: DailyPanel) -> discord.Embed:
    """Render only public status data, never private answer content."""

    answered = sum(participant.answered for participant in panel.participants)
    lines = [
        f"{'✅' if participant.answered else '⏳'} {participant.display_name}"
        for participant in panel.participants
    ]
    participants = "\n".join(lines) or "Nenhum participante atribuído."

    embed = discord.Embed(
        title=f"Daily • {panel.project_name}",
        description=f"Data: {panel.local_date.strftime('%d/%m/%Y')}",
        color=discord.Color.green()
        if answered == len(panel.participants)
        else discord.Color.blue(),
    )
    embed.add_field(
        name="Progresso",
        value=f"{answered}/{len(panel.participants)} responderam",
        inline=False,
    )
    embed.add_field(name="Participantes", value=participants, inline=False)
    return embed
