# Contexto e decisões — M1

## Decisão aprovada

O bootstrap administrativo é seguro e utilizável:

- enquanto não houver cargo administrativo configurado, o dono da guild ou alguém com a permissão Discord `Manage Server` pode executar comandos administrativos;
- depois que existir ao menos um cargo configurado, somente membros que possuam um dos cargos configurados podem administrar;
- a remoção do último cargo é recusada, evitando reabrir o modo bootstrap por acidente.

## Decisões de implementação

- A data da sessão é calculada em `America/Belem`, configurável por guild no banco.
- As quatro perguntas iniciais vêm da especificação e são criadas na inicialização da guild; projetos não são pré-cadastrados.
- Uma associação removida ganha `left_at`; reentrada cria novo registro histórico.
- Participantes e nomes de exibição são copiados para assignments ao abrir a sessão.
- Perguntas são copiadas para uma tabela de snapshots antes de aceitar respostas.
- O Discord limita modais a cinco campos; a M1 usa as quatro perguntas padrão.
- O botão persistente tem um `custom_id` estável e encontra a sessão pelo `message_id` da interação.
- Se a sessão for criada mas a publicação falhar, uma nova execução de `/daily abrir` reutiliza a sessão sem mensagem e tenta publicar novamente.
- Sessões permanecem abertas nesta etapa; fechamento pertence ao próximo milestone.

## Comandos

- `/config admin role-adicionar cargo`
- `/config admin role-remover cargo`
- `/config admin roles`
- `/projeto criar nome canal`
- `/projeto listar`
- `/projeto membro-adicionar projeto usuario`
- `/projeto membro-remover projeto usuario`
- `/projeto membros projeto`
- `/daily abrir projeto`

Todos os retornos administrativos são efêmeros. A mensagem da daily é pública no canal configurado, mas as respostas são privadas.
