# Zorysa Daily Bot

**Versão:** 1.0
**Status:** Especificação inicial aprovada para planejamento
**Plataforma:** Discord
**Objetivo:** Automação de dailies dos projetos da LACIS

---

# 1. Visão Geral

O **Zorysa Daily Bot** será um bot para Discord responsável por automatizar o processo de acompanhamento diário dos integrantes dos projetos da LACIS.

O bot deverá gerenciar dinamicamente:

* projetos;
* canais dos projetos;
* participantes;
* associação entre participantes e projetos;
* horários das dailies;
* perguntas;
* lembretes;
* cargos administrativos;
* canais de relatório;
* ausências justificadas;
* relatórios diários;
* relatórios semanais;
* relatórios mensais.

O sistema não deverá possuir projetos, pessoas, cargos, canais, perguntas ou horários definidos diretamente no código.

Todas essas informações deverão ser configuráveis.

---

# 2. Problema

Atualmente existem diferentes projetos sendo desenvolvidos simultaneamente e cada projeto possui uma composição diferente de participantes.

Uma mesma pessoa pode:

* não participar de nenhum projeto;
* participar de um projeto;
* participar de vários projetos simultaneamente.

Essa composição também pode mudar ao longo do tempo.

Consequentemente, o processo de daily precisa considerar a relação:

```text
Pessoa N:N Projeto
```

Exemplo:

```text
Marcelle
├── AmazHealth
└── Campanhas Barbearia

Carlos
├── Campanhas Barbearia
├── TCM
└── outro projeto

Amanda
└── AmazHealth
```

O sistema deverá continuar funcionando sem alterações de código caso novos projetos sejam adicionados ou projetos existentes sejam encerrados.

---

# 3. Objetivos

O sistema deverá:

1. automatizar a abertura das dailies;
2. identificar quem precisa responder em cada projeto;
3. disponibilizar formulário padronizado para resposta;
4. acompanhar quem respondeu;
5. cobrar automaticamente quem não respondeu;
6. bloquear respostas depois do prazo;
7. registrar ausências justificadas;
8. preservar todo o histórico;
9. gerar relatórios gerenciais;
10. permitir consultas históricas;
11. permitir administração diretamente pelo Discord;
12. minimizar a poluição dos canais dos projetos.

---

# 4. Escopo Inicial

O sistema atenderá inicialmente quatro projetos:

```text
AmazHealth
Campanhas Barbearia BR
TCM
CRM Saúde Belém
```

Esses projetos representam apenas a configuração inicial.

Não existe limite conceitual de quatro projetos.

Projetos poderão ser:

```text
criados
editados
ativados
arquivados
```

sem alteração do código da aplicação.

---

# 5. Princípio de Configurabilidade

A seguinte regra deverá nortear o desenvolvimento:

> Informações que podem mudar durante a operação do bot devem ser armazenadas como configuração e não implementadas diretamente no código.

Isso inclui, entre outros:

```text
projetos
canais
participantes
perguntas
horários
cargos administrativos
canais de relatório
dias de execução
lembretes
horários de relatórios
```

---

# 6. Fluxo Geral

```text
                 Discord
                    │
                    ▼
          ┌──────────────────┐
          │ Zorysa Daily Bot │
          └─────────┬────────┘
                    │
       ┌────────────┼─────────────┐
       │            │             │
       ▼            ▼             ▼
   Projetos      Membros       Configuração
       │            │             │
       └────────────┼─────────────┘
                    │
                    ▼
               Daily Engine
                    │
          ┌─────────┼─────────┐
          │         │         │
          ▼         ▼         ▼
      Cobrança   Respostas  Lembretes
          │         │         │
          └─────────┼─────────┘
                    ▼
               PostgreSQL
                    │
                    ▼
             Report Engine
            ┌───────┼────────┐
            ▼       ▼        ▼
          Diário  Semanal  Mensal
```

---

# 7. Dias de Funcionamento

Inicialmente as dailies serão obrigatórias:

```text
Segunda-feira ✅
Terça-feira   ✅
Quarta-feira  ✅
Quinta-feira  ✅
Sexta-feira   ✅

Sábado        ❌
Domingo       ❌
```

Os dias de execução deverão ser configuráveis.

---

# 8. Horários Iniciais

Configuração inicial:

```text
09:00 → abertura da daily

10:30 → primeiro lembrete

11:30 → último lembrete

12:00 → encerramento

12:10 → relatório diário

Sexta-feira 12:20
→ relatório semanal

Último dia útil do mês 12:20
→ relatório mensal
```

Todos os horários deverão ser configuráveis.

O timezone utilizado pelo servidor também deverá ser configurável.

---

# 9. Projeto

Cada projeto deverá possuir pelo menos:

```text
id
guild_id
nome
slug
discord_channel_id
status
daily_enabled
created_at
updated_at
archived_at
```

Possíveis status:

```text
ACTIVE
ARCHIVED
```

Um projeto arquivado:

* não gera novas dailies;
* não gera novas cobranças;
* não perde participantes históricos;
* não perde respostas;
* continua disponível para consultas e relatórios históricos.

---

# 10. Participantes

O bot deverá utilizar como identificador principal do usuário o:

```text
Discord User ID
```

e não seu nome ou nickname.

Isso permite que mudanças no nome exibido não quebrem o histórico.

Informações auxiliares poderão incluir:

```text
discord_user_id
username
display_name
active
created_at
updated_at
```

---

# 11. Associação Pessoa x Projeto

A relação será N:N.

```text
User
  │
  │
  ▼
ProjectMembership
  │
  ▼
Project
```

Uma participação deverá possuir histórico.

Exemplo conceitual:

```text
Carlos → TCM

joined_at: 01/08/2026
left_at:   31/10/2026
```

Se Carlos posteriormente entrar no AmazHealth, o registro anterior não deverá ser sobrescrito.

---

# 12. Abertura da Daily

Às 09:00 o bot deverá:

1. localizar projetos ativos;
2. verificar quais possuem daily habilitada;
3. identificar seus participantes ativos;
4. criar a sessão da daily;
5. criar um snapshot dos participantes esperados;
6. criar os registros de cobrança;
7. publicar a mensagem principal no canal do projeto.

---

# 13. Snapshot da Daily

A lista de participantes deverá ser congelada no momento da abertura.

Exemplo:

```text
AmazHealth — 19/08

Participantes esperados:

Amanda
Carlos
Lira
Marcelle
Matheus
```

Se às 10:00 Carlos for removido do AmazHealth, a daily do dia continuará esperando uma resposta de Carlos.

A alteração será considerada somente para as próximas dailies.

Da mesma forma, se alguém for adicionado ao projeto às 10:00, essa pessoa começará a ser cobrada a partir da próxima sessão.

---

# 14. Mensagem Principal

O bot deverá publicar apenas uma mensagem principal da daily em cada projeto.

Exemplo:

```text
📋 DAILY — AMAZHEALTH
19/08/2026

Prazo para resposta: 12:00

Participantes:

⏳ Amanda Lopes
⏳ Carlos Lucas
⏳ Lira
⏳ Marcelle
⏳ Matheus

0/5 responderam

[ Responder Daily ]
```

Essa mensagem deverá ser atualizada durante a manhã.

---

# 15. Status Visual

Enquanto a daily estiver aberta:

```text
⏳ Pendente
✅ Respondida
🏖️ Ausência justificada
```

Após o encerramento:

```text
✅ Respondida
❌ Não respondida
🏖️ Ausência justificada
```

---

# 16. Resposta da Daily

O participante deverá clicar:

```text
[ Responder Daily ]
```

O bot deverá validar:

```text
Usuário pertence ao snapshot dessa daily?
```

Caso negativo:

```text
❌ Você não está registrado como participante desta daily.
```

Caso positivo, o formulário será aberto.

---

# 17. Formulário

Configuração inicial:

```text
┌────────────────────────────────────┐
│ Daily — AmazHealth                 │
│                                    │
│ O que você fez desde a última      │
│ daily?                             │
│ [...............................]  │
│                                    │
│ O que pretende fazer hoje?         │
│ [...............................]  │
│                                    │
│ Possui algum impedimento?          │
│ [...............................]  │
│                                    │
│ Alguma observação importante?      │
│ [...............................]  │
│                                    │
│                       [ Enviar ]   │
└────────────────────────────────────┘
```

---

# 18. Perguntas Padrão

Configuração inicial:

1. **O que você fez desde a última daily?**
2. **O que pretende fazer hoje?**
3. **Possui algum impedimento?**
4. **Alguma observação importante?**

As perguntas deverão ser configuráveis.

Cada pergunta deverá possuir conceitualmente:

```text
id
texto
ordem
obrigatoria
ativa
created_at
updated_at
```

---

# 19. Snapshot das Perguntas

Uma mudança futura nas perguntas não poderá modificar dailies anteriores.

Consequentemente, no momento da criação da daily o sistema deverá armazenar um snapshot das perguntas utilizadas.

Exemplo:

```text
Daily de 19/08

Pergunta:
"O que pretende fazer hoje?"

Resposta:
"Implementar endpoint..."
```

Mesmo que posteriormente a pergunta seja alterada para:

```text
"Quais são suas prioridades para hoje?"
```

o histórico de 19/08 deverá permanecer com a pergunta original.

---

# 20. Usuário em Vários Projetos

Cada combinação:

```text
Usuário + Projeto + Data
```

representa uma daily independente.

Exemplo:

```text
Marcelle
│
├── AmazHealth
│      └── Daily própria
│
└── Campanhas
       └── Daily própria
```

Responder:

```text
AmazHealth ✅
```

não deverá alterar:

```text
Campanhas ⏳
```

---

# 21. Após a Resposta

Depois do envio:

1. respostas são armazenadas;
2. horário é registrado;
3. assignment passa para `ANSWERED`;
4. mensagem principal é atualizada;
5. nenhuma mensagem contendo a resposta é publicada no canal.

Exemplo:

Antes:

```text
⏳ Amanda
⏳ Carlos
⏳ Marcelle

0/3
```

Depois que Amanda responde:

```text
✅ Amanda
⏳ Carlos
⏳ Marcelle

1/3
```

O conteúdo da resposta permanecerá privado para fins de relatório e consulta autorizada.

---

# 22. Não Publicação das Respostas

O bot não deverá publicar automaticamente algo como:

```text
Amanda:

Ontem:
...

Hoje:
...

Impedimentos:
...
```

no canal do projeto.

A mensagem principal será apenas atualizada.

Isso tem como objetivo reduzir a quantidade de mensagens nos canais.

---

# 23. Primeiro Lembrete

Às 10:30 o sistema deverá localizar apenas:

```text
status = PENDING
```

e publicar um lembrete no próprio canal do projeto.

Exemplo:

```text
⏰ Lembrete da Daily

Ainda precisam responder:

@Carlos
@Marcelle
@Matheus

Prazo: 12:00.
```

Participantes que já responderam não deverão ser mencionados.

---

# 24. Último Lembrete

Às 11:30:

```text
🚨 Último lembrete da Daily

Ainda precisam responder:

@Carlos
@Matheus

A daily será encerrada às 12:00.
```

Novamente, somente participantes pendentes deverão ser mencionados.

---

# 25. Encerramento

Às 12:00:

```text
PENDING → NOT_ANSWERED
```

A daily passa para:

```text
CLOSED
```

A mensagem principal deverá ser atualizada.

Exemplo:

```text
🔒 DAILY ENCERRADA — AMAZHEALTH
19/08/2026

✅ Amanda
❌ Carlos
✅ Lira
✅ Marcelle
🏖️ Matheus

3 respostas
1 não respondida
1 ausência justificada
```

---

# 26. Respostas Atrasadas

Depois do fechamento, nenhuma nova resposta será aceita.

Caso o usuário tente responder:

```text
❌ Esta daily já foi encerrada.

Prazo encerrado às 12:00.
```

Não haverá status `LATE` no MVP.

---

# 27. Ausência Justificada

Um administrador deverá poder justificar a ausência de uma pessoa.

Exemplos:

```text
férias
folga
atestado
viagem
treinamento
atividade externa
outro motivo
```

O status deverá ser:

```text
EXCUSED
```

Visualmente:

```text
🏖️ Carlos — Ausência justificada
```

---

# 28. Efeito da Ausência nas Métricas

Ausências justificadas não deverão ser contabilizadas como ausência de resposta.

Exemplo:

```text
5 pessoas

4 responderam
1 ausência justificada
```

A taxa de resposta deverá considerar:

```text
esperadas efetivamente = 4

respondidas = 4

taxa = 100%
```

e não:

```text
4 / 5 = 80%
```

O relatório deverá, entretanto, informar que houve uma ausência justificada.

---

# 29. Relatório Diário Automático

Às 12:10 deverá ser gerado um relatório consolidado.

O destino inicial será:

```text
#geral-gerencia
```

Porém deverão existir zero, um ou vários canais configurados para receber o relatório automaticamente.

---

# 30. Canais de Relatório

Conceitualmente:

```text
ReportChannel

id
guild_id
discord_channel_id
daily_enabled
weekly_enabled
monthly_enabled
```

Isso possibilita, por exemplo:

```text
#geral-gerencia

diário  ✅
semanal ✅
mensal  ✅
```

e:

```text
#coordenacao

diário  ❌
semanal ✅
mensal  ✅
```

---

# 31. Estrutura do Relatório Diário

O relatório geral deverá priorizar a visão por pessoa.

Exemplo:

```text
📊 RELATÓRIO DE DAILY
19/08/2026

RESUMO

Projetos: 4
Participantes únicos: 14
Dailies esperadas: 18

✅ Respondidas: 16
❌ Não respondidas: 2
🏖️ Justificadas: 1

Taxa de resposta: 94,1%

━━━━━━━━━━━━━━━━━━━━

👤 Marcelle

Projetos:

✅ AmazHealth
✅ Campanhas Barbearia

AMAZHEALTH

Feito:
• Implementação do endpoint X

Hoje:
• Integração frontend/backend

Impedimentos:
Nenhum

Observações:
Nenhuma


CAMPANHAS BARBEARIA

Feito:
• Ajustes da campanha

Hoje:
• Implementação do módulo de custos

Impedimentos:
• Aguardando regra de negócio

━━━━━━━━━━━━━━━━━━━━

👤 Carlos

Projetos:

✅ TCM
❌ Campanhas Barbearia

TCM

Feito:
...

Hoje:
...

Impedimentos:
...

CAMPANHAS BARBEARIA

❌ Daily não respondida
```

---

# 32. Participantes x Dailies

Os relatórios deverão diferenciar:

```text
Participantes únicos
```

de:

```text
Dailies esperadas
```

Exemplo:

```text
Marcelle participa de:

AmazHealth
Campanhas
```

Logo:

```text
Participantes únicos: +1

Dailies esperadas: +2
```

---

# 33. Relatórios por Projeto

Também deverá ser possível gerar visão específica.

Exemplo:

```text
📊 AMAZHEALTH
19/08/2026

Participantes: 5

✅ Amanda
✅ Carlos
❌ Lira
✅ Marcelle
🏖️ Matheus

Respondidas: 3
Não respondidas: 1
Justificadas: 1

Taxa válida de resposta: 75%
```

Seguido das respectivas respostas autorizadas.

---

# 34. Relatório Sob Demanda

Administradores deverão possuir um comando de geração manual.

Exemplo conceitual:

```text
/relatorio gerar
```

Parâmetros:

```text
tipo

diario
semanal
mensal
```

```text
projeto

todos
ou projeto específico
```

```text
data/período
```

Quando executado, o relatório deverá ser publicado no mesmo canal em que o comando foi solicitado.

---

# 35. Regra de Canal para Relatório Manual

Um relatório manual poderá ser gerado em qualquer canal desde que:

1. o bot consiga visualizar o canal;
2. o bot tenha permissão para enviar mensagens;
3. o usuário solicitante seja administrador do Daily Bot.

O canal não precisa estar cadastrado como destino automático.

---

# 36. Relatório Semanal

Inicialmente:

```text
sexta-feira
12:20
```

O agendamento deverá ser configurável.

O relatório deverá consolidar as dailies da semana.

---

# 37. Conteúdo Semanal

Exemplo:

```text
📊 RELATÓRIO SEMANAL

Período:
17/08 → 21/08

Projetos: 4

Dailies esperadas: 80
Respondidas: 75
Não respondidas: 5
Justificadas: 3

Taxa de resposta: 93,75%
```

Depois, por projeto:

```text
AMAZHEALTH

Amanda       5/5
Carlos       4/5
Lira         5/5
Marcelle     5/5
Matheus      4/4 + 1 justificada
```

Deverão também ser agrupados:

```text
atividades realizadas
atividades planejadas
impedimentos
observações
```

---

# 38. Relatório Mensal

Inicialmente deverá ser executado:

```text
último dia útil do mês
12:20
```

O horário e comportamento deverão ser configuráveis.

Exemplo:

```text
📊 RELATÓRIO MENSAL
Agosto/2026

Projetos acompanhados: 4

Dailies esperadas: 320
Dailies respondidas: 304
Não respondidas: 16
Ausências justificadas: 12

Taxa geral: 95%
```

O relatório deverá permitir análise:

```text
por projeto
por participante
por período
```

---

# 39. Administração

A administração ocorrerá através de Slash Commands do Discord.

Exemplos:

```text
/projeto
/membro
/daily
/relatorio
/config
```

---

# 40. Cargos Administrativos

Inicialmente existem cargos administrativos no servidor como:

```text
Professor
Ditador
Gerencia
```

Nenhum desses nomes deverá ser codificado na aplicação.

O bot deverá armazenar:

```text
Discord Role ID
```

de cada cargo autorizado.

---

# 41. Múltiplos Cargos Administrativos

Deverá ser possível:

```text
adicionar cargo
remover cargo
listar cargos
```

sem reiniciar ou alterar o código do bot.

Exemplo conceitual:

```text
/config admin role-adicionar @Gerencia

/config admin role-remover @Gerencia

/config admin roles
```

---

# 42. Níveis de Acesso

## MEMBER

Poderá:

* responder própria daily;
* visualizar status da daily;
* editar própria resposta enquanto a daily estiver aberta.

## ADMIN

Além das permissões de membro, poderá:

* criar projetos;
* editar projetos;
* arquivar projetos;
* adicionar participantes;
* remover participantes;
* configurar perguntas;
* configurar horários;
* configurar canais;
* configurar cargos;
* justificar ausência;
* gerar relatórios;
* consultar histórico;
* administrar a daily.

---

# 43. Comandos de Projeto

Previstos:

```text
/projeto criar
/projeto editar
/projeto listar
/projeto detalhes
/projeto arquivar
```

Exemplo:

```text
/projeto criar

nome: AmazHealth
canal: #amazhealth
```

---

# 44. Gerenciamento de Participantes

Previstos:

```text
/projeto membro adicionar
/projeto membro remover
/projeto membros
```

Exemplo:

```text
/projeto membro adicionar

projeto: AmazHealth
usuario: @Amanda
```

---

# 45. Consulta por Pessoa

Previsto:

```text
/membro projetos
```

Exemplo:

```text
/membro projetos @Marcelle
```

Resultado:

```text
Marcelle

Projetos ativos:

• AmazHealth
• Campanhas Barbearia
```

---

# 46. Comandos da Daily

Previstos:

```text
/daily status
/daily abrir
/daily fechar
/daily justificar
```

Abertura e fechamento manuais deverão ser restritos a administradores.

---

# 47. Comandos de Relatório

Previstos:

```text
/relatorio gerar
/relatorio diario
/relatorio semanal
/relatorio mensal
```

A implementação final poderá consolidar esses comandos em um único:

```text
/relatorio gerar
```

com parâmetros.

---

# 48. Configurações

Previstos:

```text
/config horarios
/config perguntas
/config dias
/config admin
/config relatorios
/config timezone
```

---

# 49. Edição da Resposta

Enquanto a daily estiver:

```text
OPEN
```

o usuário poderá editar sua resposta.

Depois de:

```text
12:00
```

ou do fechamento manual:

```text
CLOSED
```

nenhuma alteração de membro será permitida.

Alterações administrativas deverão possuir tratamento separado caso futuramente seja necessário corrigir registros.

---

# 50. Modelo Conceitual de Dados

```text
Guild
 │
 ├── GuildSettings
 │
 ├── AdminRole
 │
 ├── ReportChannel
 │
 ├── DailyQuestion
 │
 ├── Project
 │     │
 │     └── ProjectMembership
 │
 └── DailySession
       │
       └── DailyAssignment
             │
             └── DailyAnswer
```

---

# 51. Guild

Representa um servidor Discord.

Campos conceituais:

```text
id
discord_guild_id
name
created_at
updated_at
```

---

# 52. GuildSettings

```text
id
guild_id

timezone

daily_enabled

daily_open_time
first_reminder_time
last_reminder_time
daily_close_time
daily_report_time

weekly_report_enabled
weekly_report_day
weekly_report_time

monthly_report_enabled
monthly_report_time

created_at
updated_at
```

---

# 53. AdminRole

```text
id
guild_id
discord_role_id
created_at
```

---

# 54. ReportChannel

```text
id
guild_id
discord_channel_id

receive_daily
receive_weekly
receive_monthly

created_at
```

---

# 55. Project

```text
id
guild_id

name
slug

discord_channel_id

status
daily_enabled

created_at
updated_at
archived_at
```

---

# 56. ProjectMembership

```text
id
project_id
discord_user_id

joined_at
left_at

created_at
updated_at
```

O histórico de participação não deverá ser destruído.

---

# 57. DailyQuestion

```text
id
guild_id

question_text
position

required
active

created_at
updated_at
```

---

# 58. DailySession

Representa:

```text
uma daily
de um projeto
em uma determinada data
```

Campos conceituais:

```text
id
project_id
daily_date

status

opened_at
closed_at

discord_message_id

created_at
```

Status:

```text
OPEN
CLOSED
```

---

# 59. DailyAssignment

Representa:

> um participante que deveria responder determinada daily.

Campos:

```text
id
daily_session_id
discord_user_id

status

answered_at
excused_at
excused_by
excuse_reason

created_at
updated_at
```

Status:

```text
PENDING
ANSWERED
NOT_ANSWERED
EXCUSED
```

---

# 60. DailyAnswer

Representa uma resposta individual.

```text
id
daily_assignment_id

question_snapshot
answer

created_at
updated_at
```

---

# 61. Integridade Histórica

O sistema deverá seguir a seguinte regra:

> Relatórios históricos devem ser construídos com os dados históricos da daily e nunca exclusivamente com o estado atual dos projetos.

Portanto, para descobrir quem deveria ter respondido em determinada data:

Errado:

```text
consultar membros atuais do projeto
```

Correto:

```text
consultar DailyAssignments daquela sessão
```

---

# 62. Requisitos Funcionais

## RF-01 — Cadastro de projetos

O sistema deverá permitir cadastro de novos projetos.

## RF-02 — Edição de projetos

Administradores deverão poder alterar informações de projetos existentes.

## RF-03 — Arquivamento

Projetos poderão ser arquivados sem exclusão de histórico.

## RF-04 — Associação de canal

Cada projeto deverá possuir um canal Discord para sua daily.

## RF-05 — Gerenciamento de membros

Administradores poderão adicionar e remover membros de projetos.

## RF-06 — Associação múltipla

Um usuário poderá participar de múltiplos projetos simultaneamente.

## RF-07 — Histórico de associação

Entradas e saídas de projetos deverão possuir histórico.

## RF-08 — Abertura automática

As dailies deverão abrir automaticamente conforme calendário configurado.

## RF-09 — Snapshot

A abertura deverá criar o snapshot dos participantes esperados.

## RF-10 — Formulário

A resposta deverá ser realizada através de interação/formulário Discord.

## RF-11 — Perguntas configuráveis

As perguntas deverão poder ser alteradas administrativamente.

## RF-12 — Snapshot de perguntas

Cada daily deverá preservar as perguntas utilizadas naquele momento.

## RF-13 — Status visual

A mensagem principal deverá mostrar o status dos participantes.

## RF-14 — Primeiro lembrete

O sistema deverá gerar lembrete no primeiro horário configurado.

## RF-15 — Último lembrete

O sistema deverá gerar segundo lembrete no horário configurado.

## RF-16 — Pendentes somente

Lembretes deverão mencionar somente usuários que ainda precisam responder.

## RF-17 — Fechamento automático

A daily deverá fechar automaticamente no horário configurado.

## RF-18 — Bloqueio após prazo

Não deverão ser aceitas respostas após o fechamento.

## RF-19 — Não respondentes

Pendências deverão tornar-se `NOT_ANSWERED`.

## RF-20 — Ausência justificada

Administradores poderão justificar a ausência de participantes.

## RF-21 — Relatório diário

O sistema deverá gerar relatório diário automaticamente.

## RF-22 — Relatório semanal

O sistema deverá gerar relatório semanal automaticamente.

## RF-23 — Relatório mensal

O sistema deverá gerar relatório mensal automaticamente.

## RF-24 — Múltiplos destinos

Relatórios poderão ser enviados para múltiplos canais.

## RF-25 — Relatório manual

Administradores poderão gerar relatórios sob demanda.

## RF-26 — Canal atual

Relatórios manuais deverão poder ser enviados ao canal onde o comando for executado.

## RF-27 — Consulta histórica

O sistema deverá permitir geração de relatórios de períodos anteriores.

## RF-28 — Administração por role

A autorização administrativa deverá utilizar roles configuráveis.

## RF-29 — Múltiplas roles

O sistema deverá aceitar múltiplas roles administrativas.

## RF-30 — Horários configuráveis

Todos os horários operacionais deverão ser configuráveis.

## RF-31 — Dias configuráveis

Os dias de execução deverão ser configuráveis.

## RF-32 — Canais configuráveis

Canais de projeto e relatório deverão ser configuráveis.

## RF-33 — Timezone configurável

O timezone utilizado pelo scheduler deverá ser configurável.

## RF-34 — Edição antes do fechamento

O participante poderá alterar sua resposta enquanto a daily permanecer aberta.

---

# 63. Regras de Negócio

## RN-01

Cada daily pertence a exatamente um projeto e uma data.

## RN-02

Cada resposta pertence a:

```text
usuário + projeto + sessão de daily
```

## RN-03

Responder uma daily não responde outra daily do mesmo usuário.

## RN-04

Somente participantes existentes no snapshot poderão responder.

## RN-05

Mudanças posteriores na equipe não alteram sessões abertas ou históricas.

## RN-06

Projetos arquivados não deverão gerar novas dailies.

## RN-07

Arquivamento não poderá apagar histórico.

## RN-08

Somente administradores poderão alterar configurações.

## RN-09

Somente pendentes deverão receber lembretes.

## RN-10

Respostas não deverão ser publicadas automaticamente no canal do projeto.

## RN-11

O status da mensagem principal deverá ser atualizado após uma resposta.

## RN-12

Após o fechamento, novas respostas serão rejeitadas.

## RN-13

Ausências justificadas não contam como falta de resposta.

## RN-14

Uma pessoa pode possuir múltiplas dailies na mesma data.

## RN-15

Relatórios históricos deverão utilizar snapshots históricos.

## RN-16

Nomes de usuários, canais e cargos nunca deverão ser utilizados como identificadores permanentes quando existir um Discord ID equivalente.

---

# 64. Requisitos Não Funcionais

## RNF-01 — Persistência

Os dados deverão ser armazenados em banco PostgreSQL.

## RNF-02 — Disponibilidade

O bot deverá permanecer disponível durante os horários configurados para execução das dailies.

## RNF-03 — Recuperação

Uma reinicialização do bot não poderá apagar o estado das dailies existentes.

## RNF-04 — Idempotência

A execução repetida acidental de um job não deverá criar duas dailies do mesmo projeto para a mesma data.

## RNF-05 — Segurança

Tokens, senhas e credenciais deverão ser fornecidos através de variáveis de ambiente.

## RNF-06 — Privilégio mínimo

O bot deverá possuir somente as permissões Discord necessárias para suas funcionalidades.

## RNF-07 — Auditabilidade

Ações administrativas relevantes deverão possuir informações suficientes para identificar quem realizou a ação e quando.

## RNF-08 — Manutenibilidade

O código deverá possuir separação clara entre:

```text
Discord
regras de negócio
persistência
scheduler
relatórios
```

## RNF-09 — Extensibilidade

Novos tipos de relatório e integrações futuras não deverão exigir reestruturação completa do domínio.

## RNF-10 — Containerização

A aplicação deverá ser preparada para execução via Docker.

---

# 65. Stack Inicial Recomendada

```text
Python

discord.py

PostgreSQL

SQLAlchemy

APScheduler

Docker

Docker Compose
```

---

# 66. Arquitetura Recomendada

O projeto deverá começar como **monólito modular**.

```text
┌──────────────────────────┐
│ Discord Presentation     │
│                          │
│ Commands                 │
│ Views                    │
│ Buttons                  │
│ Modals                   │
│ Events                   │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Application              │
│                          │
│ ProjectService           │
│ MemberService            │
│ DailyService             │
│ ReportService            │
│ ConfigurationService     │
│ AbsenceService           │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Domain                   │
│                          │
│ Projects                 │
│ Memberships              │
│ Dailies                  │
│ Reports                  │
│ Configuration            │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Infrastructure           │
│                          │
│ Discord                  │
│ PostgreSQL               │
│ Scheduler                │
└──────────────────────────┘
```

Não há necessidade de microserviços no MVP.

---

# 67. Scheduler

Jobs iniciais:

```text
DailyOpenJob
09:00

FirstReminderJob
10:30

LastReminderJob
11:30

DailyCloseJob
12:00

DailyReportJob
12:10

WeeklyReportJob
sexta-feira 12:20

MonthlyReportJob
último dia útil do mês 12:20
```

Os valores exibidos são configuração inicial e não constantes de código.

---

# 68. Idempotência dos Jobs

O scheduler deverá evitar situações como:

```text
bot reiniciou às 09:01

↓

criou uma segunda Daily AmazHealth
```

Deverá existir uma restrição lógica equivalente a:

```text
project_id + daily_date
```

única para `DailySession`.

Assim:

```text
AmazHealth + 19/08/2026

= somente uma sessão
```

---

# 69. Reinicialização

Exemplo:

```text
09:00 daily aberta

09:45 servidor reinicia

09:46 bot volta
```

O sistema deverá recuperar do banco:

```text
Daily está OPEN
mensagem Discord existente
participantes
quem respondeu
quem ainda está pendente
próximos jobs
```

e continuar normalmente.

---

# 70. Estrutura Inicial do Projeto

Sugestão:

```text
lacis-daily-bot/
│
├── app/
│   │
│   ├── bot/
│   │   ├── commands/
│   │   ├── events/
│   │   ├── modals/
│   │   ├── views/
│   │   └── embeds/
│   │
│   ├── modules/
│   │   ├── projects/
│   │   ├── members/
│   │   ├── daily/
│   │   ├── reports/
│   │   ├── absences/
│   │   └── configuration/
│   │
│   ├── infrastructure/
│   │   ├── database/
│   │   ├── discord/
│   │   └── scheduler/
│   │
│   └── main.py
│
├── tests/
│
├── Docker/
│   └── Dockerfile
│
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

# 71. Variáveis de Ambiente

Configurações sensíveis deverão ficar fora do código.

Exemplo:

```env
DISCORD_TOKEN=

DATABASE_HOST=
DATABASE_PORT=
DATABASE_NAME=
DATABASE_USER=
DATABASE_PASSWORD=
```

Configurações funcionais como:

```text
09:00
12:00
canais
roles
perguntas
```

não deverão depender de `.env`.

Essas configurações pertencem ao banco e deverão ser alteráveis através do Discord.

---

# 72. Inteligência Artificial

IA não será requisito obrigatório para funcionamento da V1.

O fluxo principal será determinístico:

```text
Discord
   ↓
Daily Bot
   ↓
PostgreSQL
   ↓
Report Generator
```

Futuramente poderá ser adicionada:

```text
                     ┌─ Relatório estruturado
PostgreSQL ──────────┤
                     │
                     └─ LLM
                          ↓
                     Resumo executivo
```

Possibilidades futuras:

* resumir atividades da semana;
* identificar assuntos recorrentes;
* agrupar impedimentos;
* gerar resumo executivo;
* identificar riscos;
* destacar dependências;
* comparar progresso entre períodos.

A IA não deverá ser responsável por determinar:

```text
quem respondeu
quem não respondeu
quem está ausente
taxas de participação
associação entre projetos
```

Esses dados deverão sempre vir diretamente do sistema.

---

# 73. Fora do Escopo Inicial

Não fazem parte obrigatória da V1:

* dashboard web;
* aplicativo mobile;
* integração com GitHub;
* integração com Linear;
* integração com Jira;
* IA para análise;
* avaliação de produtividade individual;
* pontuação/ranking;
* microserviços;
* notificações por e-mail;
* análise automática de commits.

Essas funcionalidades poderão entrar em versões futuras.

---

# 74. Fluxo Completo do Dia

```text
09:00
│
├── identificar projetos ativos
├── identificar membros
├── criar DailySessions
├── criar snapshots
├── criar assignments
└── publicar mensagens
        │
        ▼
Usuário clica
[Responder Daily]
        │
        ▼
Bot valida participação
        │
        ▼
Modal
        │
        ▼
Respostas salvas
        │
        ▼
Mensagem principal atualizada
        │
        ▼
10:30
Primeiro lembrete aos pendentes
        │
        ▼
11:30
Último lembrete aos pendentes
        │
        ▼
12:00
Daily fecha
        │
        ├── PENDING → NOT_ANSWERED
        │
        └── bloqueia formulário
        │
        ▼
12:10
Relatório diário
        │
        ▼
Canais configurados
```

---

# 75. Fluxo Semanal

```text
Segunda
   │
Terça
   │
Quarta
   │
Quinta
   │
Sexta
   │
   ▼
Daily de sexta encerra
   │
   ▼
12:20
   │
   ▼
Consolidação semanal
   │
   ▼
Relatório semanal
```

---

# 76. Fluxo Mensal

```text
Dailies do mês
       │
       ▼
Último dia útil
       │
       ▼
Daily encerra
       │
       ▼
12:20
       │
       ▼
Consolidação mensal
       │
       ▼
Relatório mensal
```

---

# 77. Critérios Gerais de Aceitação da V1

A versão poderá ser considerada funcional quando for possível:

1. cadastrar projetos através do Discord;
2. associar projetos aos canais;
3. adicionar e remover participantes;
4. permitir uma pessoa em vários projetos;
5. configurar cargos administrativos;
6. abrir automaticamente uma daily;
7. publicar uma única mensagem principal por projeto;
8. responder através de formulário;
9. atualizar o check do participante;
10. não publicar o conteúdo da resposta no canal;
11. gerar lembrete público aos pendentes;
12. realizar segundo lembrete;
13. bloquear resposta após fechamento;
14. registrar quem não respondeu;
15. justificar ausência;
16. gerar relatório diário;
17. publicar relatório em múltiplos canais;
18. gerar relatório manual no canal atual;
19. gerar relatório semanal;
20. gerar relatório mensal;
21. consultar relatórios anteriores;
22. manter histórico quando membros mudarem de projetos;
23. manter histórico quando um projeto for arquivado;
24. sobreviver a reinicializações sem perder o estado da daily;
25. permitir alteração das configurações sem mudança no código.

---

# 78. Definição da V1

A **V1 do Zorysa Daily Bot** terá como núcleo:

```text
Gestão de projetos
        +
Gestão de participantes
        +
Configuração
        +
Daily automática
        +
Formulário Discord
        +
Lembretes
        +
Ausências
        +
Relatório diário
        +
Relatório semanal
        +
Relatório mensal
        +
Histórico
```

O Discord será simultaneamente:

```text
interface do usuário
+
interface administrativa
+
canal de notificações
+
canal de relatórios
```

eliminando a necessidade de um frontend web no MVP.

---

# 79. Princípio Central da Solução

O sistema não deve pensar em:

```text
"Quem está atualmente no AmazHealth?"
```

quando estiver analisando uma daily histórica.

Deve pensar em:

```text
"Quem deveria responder a Daily AmazHealth de 19/08/2026?"
```

Essa diferença deverá orientar a modelagem de toda a aplicação.

Por isso, `DailySession`, `DailyAssignment` e snapshots são elementos centrais da arquitetura.

---

# 80. Estado da Especificação

Com a versão 1.0 ficam definidos:

```text
✅ comportamento principal da daily

✅ forma de resposta

✅ horários iniciais

✅ lembretes

✅ fechamento

✅ resposta atrasada

✅ ausência justificada

✅ projetos dinâmicos

✅ participantes dinâmicos

✅ pessoas em múltiplos projetos

✅ roles administrativas configuráveis

✅ perguntas configuráveis

✅ canais de relatório configuráveis

✅ relatórios manuais

✅ relatório diário

✅ relatório semanal

✅ relatório mensal

✅ armazenamento histórico

✅ arquitetura inicial

✅ modelo conceitual de dados

✅ requisitos funcionais

✅ regras de negócio

✅ requisitos não funcionais
```

Esta especificação passa a ser a referência funcional inicial para decomposição do projeto em backlog de desenvolvimento.

