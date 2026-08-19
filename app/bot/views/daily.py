"""Persistent daily interaction view."""

import discord

from app.bot.contracts import DailyPresentationService, PresentationError
from app.bot.modals.daily import DailyResponseModal

DAILY_RESPONSE_CUSTOM_ID = "zorysa:daily:respond"


class DailyResponseView(discord.ui.View):
    """Persistent button that resolves sessions by the source message ID."""

    def __init__(self, service: DailyPresentationService) -> None:
        super().__init__(timeout=None)
        self._service = service

    @discord.ui.button(
        label="Responder daily",
        style=discord.ButtonStyle.primary,
        custom_id=DAILY_RESPONSE_CUSTOM_ID,
    )
    async def respond(
        self, interaction: discord.Interaction, _: discord.ui.Button["DailyResponseView"]
    ) -> None:
        if interaction.message is None:
            await interaction.response.send_message(
                "Não foi possível identificar esta daily.", ephemeral=True
            )
            return

        try:
            form = await self._service.prepare_response(
                message_id=interaction.message.id,
                user_id=interaction.user.id,
            )
        except PresentationError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return

        await interaction.response.send_modal(
            DailyResponseModal(
                self._service,
                form,
                original_message=interaction.message,
            )
        )
