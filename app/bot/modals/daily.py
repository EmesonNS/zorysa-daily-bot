"""Dynamic modal for private daily responses."""

import discord

from app.bot.contracts import DailyPresentationService, DailyResponseForm, PresentationError
from app.bot.embeds.daily import render_daily_panel


class DailyResponseModal(discord.ui.Modal):
    """Modal built from immutable question snapshots."""

    def __init__(
        self,
        service: DailyPresentationService,
        form: DailyResponseForm,
        *,
        original_message: discord.Message,
    ) -> None:
        if len(form.questions) > 5:
            raise ValueError("O Discord aceita no máximo cinco perguntas por modal.")

        title = f"{form.project_name} • {form.local_date.strftime('%d/%m/%Y')}"
        super().__init__(title=title[:45])
        self._service = service
        self._form = form
        self._original_message = original_message
        self._inputs: dict[int, discord.ui.TextInput[DailyResponseModal]] = {}

        for question in sorted(form.questions, key=lambda item: item.position):
            text_input = discord.ui.TextInput[DailyResponseModal](
                label=question.text[:45],
                style=discord.TextStyle.paragraph,
                required=question.required,
                max_length=2_000,
            )
            self._inputs[question.id] = text_input
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        answers = {question_id: item.value for question_id, item in self._inputs.items()}
        try:
            panel = await self._service.submit_response(
                message_id=self._form.message_id,
                user_id=interaction.user.id,
                answers=answers,
            )
        except PresentationError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return

        from app.bot.views.daily import DailyResponseView

        await self._original_message.edit(
            embed=render_daily_panel(panel),
            view=DailyResponseView(self._service),
        )
        await interaction.response.send_message("Daily respondida com sucesso.", ephemeral=True)
