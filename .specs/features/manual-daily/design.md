# Design — M1 Daily manual

## Componentes

```text
Discord commands/views
        |
        v
Application services ── authorization and transactions
        |
        v
SQLAlchemy async models ── PostgreSQL
```

- `GuildAdminService`: inicialização da guild, autorização e cargos administrativos.
- `ProjectService`: projetos e memberships históricos.
- `DailyService`: abertura idempotente, snapshots, respostas e leitura do painel.
- Camada Discord: grupos de comandos, renderer da mensagem, view persistente e modal dinâmico.

## Modelo persistente

| Tabela | Responsabilidade | Invariantes principais |
|---|---|---|
| `guilds` | Guild Discord conhecida | `discord_guild_id` único |
| `guild_settings` | Timezone da guild | uma por guild |
| `admin_roles` | Cargos autorizados | par guild/cargo único |
| `projects` | Projeto e canal da daily | slug único por guild |
| `project_memberships` | Histórico de participação | apenas uma associação ativa por projeto/usuário |
| `daily_questions` | Perguntas ativas da guild | posição única por guild |
| `daily_sessions` | Sessão diária do projeto | projeto/data únicos |
| `daily_assignments` | Snapshot de participantes | sessão/usuário únicos |
| `daily_question_snapshots` | Snapshot das perguntas | sessão/posição únicos |
| `daily_answers` | Respostas privadas | assignment/pergunta únicos |

`BigInteger` é usado para IDs Discord. Estados são enums de domínio persistidos como strings estáveis. Datas são timezone-aware; a data local da sessão é armazenada separadamente.

## Fluxo de abertura

1. Autorizar administrador e resolver projeto ativo com daily habilitada.
2. Calcular a data local com a timezone da guild.
3. Reutilizar sessão existente ou criar sessão `OPEN`.
4. Na mesma transação, copiar memberships ativos e perguntas ativas.
5. Publicar a mensagem no canal e persistir `message_id`.

Restrições únicas tornam o fluxo seguro contra dupla abertura concorrente. Uma sessão sem `message_id` representa publicação pendente e pode ser retomada.

## Fluxo de resposta

1. A view persistente recebe a interação e resolve a sessão pelo ID da mensagem.
2. O serviço confirma que o usuário possui assignment pendente/aberto.
3. O modal é montado com os snapshots ordenados.
4. No envio, obrigatórias são validadas e respostas são gravadas em uma transação.
5. O assignment vira `ANSWERED`, com `answered_at`.
6. O renderer consulta o painel atualizado e edita a mensagem original.

O conteúdo das respostas nunca entra em embeds, logs ou mensagens de confirmação.

## Tratamento de erro

- Erros de domínio possuem mensagens próprias para interação efêmera.
- Falhas inesperadas são registradas sem token ou respostas e retornam mensagem genérica.
- Canal inexistente/inacessível impede a publicação, mantendo a sessão recuperável.
- Um segundo envio do mesmo usuário é recusado nesta etapa para preservar uma única entrega.

## Segurança

- Nenhum intent privilegiado é necessário.
- Autorização usa membro e cargos fornecidos pela interação, sempre limitada à guild atual.
- Consultas incluem a guild como limite de tenancy.
- Respostas são acessíveis apenas à camada de aplicação e não têm comando público de leitura na M1.
