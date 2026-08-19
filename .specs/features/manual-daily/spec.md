# M1 — Daily manual completa

## Objetivo

Permitir que uma guild configure administradores, projetos e membros e execute uma daily manual completa pelo Discord, preservando histórico e mantendo as respostas privadas no banco.

## Requisitos

| ID | Requisito | Critério de aceitação |
|---|---|---|
| M1-01 | Inicializar guild automaticamente | O primeiro comando administrativo cria guild, configurações e as quatro perguntas padrão a partir do `guild_id` do Discord. |
| M1-02 | Autorizar bootstrap administrativo | Sem cargos configurados, apenas o dono da guild ou usuário com `Manage Server` administra; após o primeiro cargo, apenas membros com cargo configurado administram. |
| M1-03 | Gerenciar cargos administrativos | É possível adicionar, remover e listar múltiplos cargos, sem duplicidade e sem deixar a guild sem cargo por remoção acidental. |
| M1-04 | Gerenciar projetos | Administrador cria e lista projetos com nome, slug, canal, status, daily habilitada e quantidade de participantes ativos. |
| M1-05 | Gerenciar membros | Administrador adiciona, lista e remove membros; duplicidade ativa é rejeitada e remoção registra `left_at` sem apagar histórico. |
| M1-06 | Abrir daily manualmente | Administrador abre no máximo uma sessão por projeto e data local, com snapshots transacionais dos membros ativos e perguntas. |
| M1-07 | Publicar mensagem principal | O bot publica uma mensagem por sessão no canal do projeto, persiste seu ID e mostra contagem e estado de cada participante. |
| M1-08 | Restringir resposta | O botão só abre o modal para participante atribuído à sessão; terceiros recebem erro efêmero. |
| M1-09 | Coletar respostas privadas | O modal exibe as perguntas do snapshot, valida obrigatórias, persiste respostas e marca a atribuição como respondida sem publicar conteúdo no canal. |
| M1-10 | Atualizar estado visível | Após envio válido, a mensagem original é atualizada com o novo total e o check do participante. |
| M1-11 | Sobreviver a reinício | O botão usa `custom_id` persistente e resolve a sessão pelo ID da mensagem, funcionando após reinício do processo. |

## Fora de escopo

- Agendamento automático, lembretes, fechamento e ausência automática.
- Relatório consolidado e canal de relatórios.
- Edição de perguntas e horários pela interface.
- Publicação do conteúdo individual das respostas.

## Cenário de aceite

1. O dono da guild adiciona o primeiro cargo administrativo.
2. Um administrador cria o projeto `AmazHealth` e adiciona dois membros.
3. O administrador abre a daily no canal do projeto.
4. Um membro usa o botão, responde às quatro perguntas e envia.
5. A mensagem passa de `0/2` para `1/2` e mostra o check nesse membro.
6. Um usuário não participante não consegue abrir o modal.
7. Nenhuma resposta textual aparece no canal.
