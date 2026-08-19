# Zorysa Daily Bot — Product Backlog

**Versão:** 1.0
**Origem:** Spec funcional v1.0
**Objetivo:** Organizar a implementação do Zorysa Daily Bot em épicos e User Stories priorizadas.

---

# 1. Estratégia de Entrega

O desenvolvimento será dividido em três marcos:

### MVP Técnico

Bot conectado ao Discord, banco configurado e estrutura necessária para evolução.

### MVP Operacional

Bot capaz de executar uma daily completa de um projeto real:

```text
abrir
→ coletar respostas
→ atualizar status
→ lembrar pendentes
→ fechar
→ gerar relatório diário
```

### V1 Completa

Todos os recursos previstos na Spec v1.0, incluindo:

```text
configuração dinâmica
relatórios semanais
relatórios mensais
ausências
histórico
administração
recuperação após reinício
```

---

# 2. Prioridades

Será utilizada a seguinte classificação:

| Prioridade | Significado                                            |
| ---------- | ------------------------------------------------------ |
| **P0**     | Essencial para o MVP                                   |
| **P1**     | Necessário para fechar a V1                            |
| **P2**     | Melhoria importante, mas não bloqueia a V1 operacional |
| **Future** | Evolução posterior                                     |

---

# 3. Visão Geral dos Épicos

| ID    | Épico                              | Objetivo                                      | Prioridade |
| ----- | ---------------------------------- | --------------------------------------------- | ---------- |
| EP-01 | Fundação e Infraestrutura          | Criar a base técnica do bot                   | P0         |
| EP-02 | Configuração e Administração       | Permitir configuração sem alteração de código | P0         |
| EP-03 | Projetos e Participantes           | Gerenciar projetos e equipes                  | P0         |
| EP-04 | Engine de Daily                    | Executar o fluxo principal da daily           | P0         |
| EP-05 | Lembretes, Fechamento e Ausências  | Controlar prazos e exceções                   | P0/P1      |
| EP-06 | Relatórios                         | Produzir informações gerenciais               | P0/P1      |
| EP-07 | Histórico, Auditoria e Resiliência | Garantir confiabilidade operacional           | P1         |
| EP-08 | Qualidade e Deploy                 | Testes, documentação e operação               | P0/P1      |

---

# EP-01 — Fundação e Infraestrutura

## Objetivo

Criar a estrutura técnica necessária para execução e evolução do bot.

---

## US-001 — Criar estrutura inicial do projeto

**Como desenvolvedor, quero uma estrutura modular para o bot, para que novas funcionalidades possam ser adicionadas sem acoplamento excessivo.**

### Critérios de aceitação

* Projeto Python criado.
* Separação entre Discord, domínio, aplicação e infraestrutura.
* Dependências documentadas.
* Aplicação possui ponto de entrada único.
* Estrutura permite módulos independentes para projetos, daily, relatórios e configuração.

**Prioridade:** P0

---

## US-002 — Configurar aplicação Discord

**Como administrador, quero que o bot consiga conectar ao servidor Discord, para que possa receber comandos e enviar mensagens.**

### Critérios de aceitação

* Token carregado por variável de ambiente.
* Bot conecta corretamente.
* Bot registra Slash Commands.
* Bot identifica o servidor em que está executando.
* Falha de autenticação produz log compreensível.
* Token nunca aparece nos logs.

**Prioridade:** P0

**Dependência:** US-001

---

## US-003 — Configurar PostgreSQL

**Como sistema, quero persistir meus dados em PostgreSQL, para que as informações sobrevivam a reinicializações.**

### Critérios de aceitação

* PostgreSQL executa via Docker Compose.
* Conexão configurada através de `.env`.
* SQLAlchemy configurado.
* Banco inicial criado através de migrations.
* Aplicação falha de forma controlada caso o banco esteja indisponível.

**Prioridade:** P0

---

## US-004 — Criar mecanismo de migrations

**Como desenvolvedor, quero controlar versões do banco, para que mudanças no modelo possam ser aplicadas de forma segura.**

### Critérios de aceitação

* Existe mecanismo versionado de migrations.
* Banco vazio pode ser criado integralmente pelas migrations.
* Migration executada não é reaplicada.
* Histórico de migrations é persistido.

**Prioridade:** P0

---

## US-005 — Configurar Docker

**Como administrador, quero executar o bot utilizando containers, para facilitar deploy e manutenção.**

### Critérios de aceitação

* Existe Dockerfile da aplicação.
* Existe `docker-compose.yml`.
* Bot e PostgreSQL executam juntos.
* Configurações sensíveis utilizam `.env`.
* Reiniciar container não apaga banco.

**Prioridade:** P0

---

## US-006 — Logging básico

**Como administrador, quero registros da execução do bot, para conseguir identificar problemas.**

### Critérios de aceitação

* Inicialização registrada.
* Erros registrados.
* Execução de jobs registrada.
* Comandos administrativos relevantes registrados.
* Informações sensíveis não aparecem nos logs.

**Prioridade:** P1

---

# EP-02 — Configuração e Administração

## Objetivo

Eliminar configurações hardcoded e permitir administração através do próprio Discord.

---

## US-007 — Registrar configuração do servidor

**Como administrador, quero que o bot possua uma configuração por servidor Discord.**

### Critérios de aceitação

* Guild identificada por `discord_guild_id`.
* Configuração persistida.
* Guild pode ser inicializada automaticamente no primeiro uso.
* Configuração pode ser consultada.

**Prioridade:** P0

---

## US-008 — Configurar timezone

**Como administrador, quero definir o timezone do servidor, para que os horários sejam executados corretamente.**

### Critérios de aceitação

* Timezone armazenado no banco.
* Timezone pode ser alterado por comando.
* Scheduler respeita o timezone configurado.
* Valor inicial poderá ser `America/Belem`.

**Prioridade:** P0

---

## US-009 — Configurar horários da daily

**Como administrador, quero alterar os horários da daily sem alterar código.**

### Configuração inicial

```text
09:00 abertura
10:30 primeiro lembrete
11:30 último lembrete
12:00 fechamento
12:10 relatório diário
```

### Critérios de aceitação

* Todos os horários ficam persistidos.
* Administrador consegue visualizar configuração atual.
* Administrador consegue alterá-los.
* Scheduler utiliza os novos valores.

**Prioridade:** P0

---

## US-010 — Configurar dias da daily

**Como administrador, quero definir em quais dias existem dailies.**

### Configuração inicial

```text
segunda
terça
quarta
quinta
sexta
```

### Critérios de aceitação

* Dias ficam persistidos.
* Administrador consegue adicionar/remover dias.
* Scheduler respeita a configuração.

**Prioridade:** P1

---

## US-011 — Configurar roles administrativas

**Como administrador, quero escolher quais cargos Discord podem administrar o bot.**

### Critérios de aceitação

* Configuração utiliza Discord Role ID.
* É possível cadastrar múltiplas roles.
* É possível remover uma role.
* É possível listar roles autorizadas.
* Usuário sem role autorizada não executa comandos administrativos.

**Prioridade:** P0

---

## US-012 — Configurar perguntas

**Como administrador, quero alterar as perguntas da daily sem alterar código.**

### Perguntas iniciais

```text
1. O que você fez desde a última daily?
2. O que pretende fazer hoje?
3. Possui algum impedimento?
4. Alguma observação importante?
```

### Critérios de aceitação

Cada pergunta poderá possuir:

```text
texto
ordem
obrigatória
ativa
```

* Administrador consegue visualizar perguntas.
* Administrador consegue adicionar pergunta.
* Administrador consegue editar pergunta.
* Administrador consegue ativar/desativar pergunta.
* Alterações não modificam dailies históricas.

**Prioridade:** P1

---

## US-013 — Configurar canais de relatório

**Como administrador, quero definir onde relatórios automáticos serão publicados.**

### Critérios de aceitação

* Um servidor pode possuir zero, um ou vários canais.
* Cada canal pode receber:

  * diário;
  * semanal;
  * mensal.
* Configuração utiliza Channel ID.
* Canal pode ser removido sem apagar relatórios históricos.

**Prioridade:** P0

---

# EP-03 — Projetos e Participantes

## Objetivo

Permitir que a estrutura organizacional seja completamente dinâmica.

---

## US-014 — Criar projeto

**Como administrador, quero cadastrar um projeto, para que ele passe a participar das dailies.**

### Entrada

```text
nome
canal
```

### Critérios de aceitação

* Projeto recebe ID interno.
* Projeto possui slug.
* Canal é armazenado através do Discord Channel ID.
* Projeto começa ativo.
* Projeto pode ter daily habilitada ou desabilitada.

**Prioridade:** P0

---

## US-015 — Listar projetos

**Como administrador, quero consultar os projetos cadastrados.**

### Critérios de aceitação

O resultado deverá mostrar:

```text
nome
canal
status
daily habilitada/desabilitada
quantidade de participantes
```

**Prioridade:** P0

---

## US-016 — Editar projeto

**Como administrador, quero alterar informações de um projeto.**

### Critérios de aceitação

* Nome pode ser alterado.
* Canal pode ser alterado.
* Daily pode ser habilitada/desabilitada.
* Histórico anterior não é alterado.

**Prioridade:** P1

---

## US-017 — Arquivar projeto

**Como administrador, quero arquivar um projeto encerrado.**

### Critérios de aceitação

* Projeto passa para `ARCHIVED`.
* Projeto deixa de gerar novas dailies.
* Histórico permanece disponível.
* Projeto não é fisicamente excluído.

**Prioridade:** P1

---

## US-018 — Adicionar membro ao projeto

**Como administrador, quero associar um membro Discord a um projeto.**

### Critérios de aceitação

* Usuário identificado por Discord User ID.
* Participação recebe `joined_at`.
* Usuário pode pertencer a múltiplos projetos.
* Associação duplicada ativa é impedida.

**Prioridade:** P0

---

## US-019 — Remover membro do projeto

**Como administrador, quero remover um membro sem apagar sua participação histórica.**

### Critérios de aceitação

* Registro recebe `left_at`.
* Histórico permanece.
* Usuário deixa de participar das próximas dailies.
* Dailies já abertas não são alteradas.

**Prioridade:** P0

---

## US-020 — Listar membros de um projeto

**Como administrador, quero visualizar quem participa atualmente de determinado projeto.**

### Critérios de aceitação

* Apenas memberships atuais são exibidas por padrão.
* Histórico pode ser consultado separadamente.

**Prioridade:** P1

---

## US-021 — Consultar projetos de uma pessoa

**Como administrador, quero saber em quais projetos determinada pessoa participa.**

### Critérios de aceitação

Exemplo:

```text
Marcelle

• AmazHealth
• Campanhas Barbearia
```

* Deve considerar apenas associações ativas por padrão.

**Prioridade:** P1

---

# EP-04 — Engine de Daily

## Objetivo

Implementar o principal fluxo funcional do sistema.

Este é o épico central do produto.

---

## US-022 — Criar sessão diária automaticamente

**Como sistema, quero criar uma sessão de daily para cada projeto ativo no horário configurado.**

### Critérios de aceitação

* Job executa inicialmente às 09:00.
* Apenas projetos ativos participam.
* Projeto com daily desabilitada é ignorado.
* Existe no máximo uma sessão por:

```text
projeto + data
```

* Execução repetida do job não duplica sessão.

**Prioridade:** P0

---

## US-023 — Criar snapshot de participantes

**Como sistema, quero registrar quem deveria responder cada daily.**

### Critérios de aceitação

* Ao abrir a daily, todos os membros ativos do projeto recebem um `DailyAssignment`.
* Mudanças posteriores nas memberships não alteram assignments existentes.
* Cada participante inicia como `PENDING`.

**Prioridade:** P0

**Dependência:** US-022

---

## US-024 — Criar snapshot das perguntas

**Como sistema, quero preservar as perguntas utilizadas naquela sessão.**

### Critérios de aceitação

* Perguntas ativas são copiadas para a sessão.
* Alteração posterior das perguntas globais não altera a sessão.
* Relatórios históricos usam o texto original.

**Prioridade:** P0

---

## US-025 — Publicar mensagem principal

**Como participante, quero visualizar a daily do projeto em seu canal.**

### Exemplo

```text
📋 DAILY — AMAZHEALTH

Prazo: 12:00

⏳ Amanda
⏳ Carlos
⏳ Marcelle

0/3 responderam

[Responder Daily]
```

### Critérios de aceitação

* Apenas uma mensagem principal é criada.
* Message ID é persistido.
* Bot consegue editar posteriormente a mesma mensagem.

**Prioridade:** P0

---

## US-026 — Responder daily através de botão

**Como participante, quero clicar em `Responder Daily` para preencher minhas informações.**

### Critérios de aceitação

* Bot identifica o usuário que clicou.
* Bot valida existência de assignment.
* Usuário de fora do snapshot recebe erro.
* Usuário autorizado recebe formulário.

**Prioridade:** P0

---

## US-027 — Exibir formulário da daily

**Como participante, quero preencher as perguntas através de um formulário Discord.**

### Critérios de aceitação

* Formulário utiliza perguntas configuradas.
* Campos obrigatórios são validados.
* Projeto e data são apresentados.
* Resposta pertence exclusivamente ao usuário autenticado pelo Discord.

**Prioridade:** P0

---

## US-028 — Registrar resposta

**Como participante, quero que minha daily seja persistida ao enviar o formulário.**

### Critérios de aceitação

* Respostas são armazenadas.
* Assignment passa para `ANSWERED`.
* `answered_at` é registrado.
* Resposta fica associada à sessão correta.
* Conteúdo não é publicado no canal.

**Prioridade:** P0

---

## US-029 — Atualizar mensagem principal

**Como equipe, quero visualizar rapidamente quem já respondeu.**

### Antes

```text
⏳ Amanda
⏳ Carlos
⏳ Marcelle
```

### Depois

```text
✅ Amanda
⏳ Carlos
⏳ Marcelle
```

### Critérios de aceitação

* Bot edita a mensagem original.
* Não cria mensagem adicional.
* Contador é atualizado.

**Prioridade:** P0

---

## US-030 — Permitir edição antes do fechamento

**Como participante, quero corrigir minha daily enquanto ela estiver aberta.**

### Critérios de aceitação

* Usuário que já respondeu pode abrir novamente o formulário.
* Valores anteriores são recuperados quando tecnicamente aplicável.
* Atualização substitui/atualiza sua resposta.
* `updated_at` é registrado.
* Status continua `ANSWERED`.

**Prioridade:** P1

---

## US-031 — Impedir resposta de usuário não associado

**Como sistema, quero impedir respostas indevidas.**

### Critérios de aceitação

Usuário sem assignment recebe resposta privada:

```text
Você não está registrado como participante desta daily.
```

Nenhum registro é criado.

**Prioridade:** P0

---

# EP-05 — Lembretes, Fechamento e Ausências

## US-032 — Primeiro lembrete público

**Como participante pendente, quero ser lembrado antes do prazo.**

### Horário inicial

```text
10:30
```

### Critérios de aceitação

* Somente `PENDING` são mencionados.
* Lembrete é publicado no canal do projeto.
* Se ninguém estiver pendente, nenhuma cobrança é publicada.

**Prioridade:** P0

---

## US-033 — Último lembrete público

### Horário inicial

```text
11:30
```

### Critérios de aceitação

* Somente pendentes são mencionados.
* Mensagem informa horário de fechamento.
* Quem respondeu após o primeiro lembrete não aparece novamente.

**Prioridade:** P0

---

## US-034 — Fechar daily automaticamente

**Como sistema, quero encerrar a daily no horário definido.**

### Horário inicial

```text
12:00
```

### Critérios de aceitação

* Session passa para `CLOSED`.
* `closed_at` é registrado.
* Assignments ainda `PENDING` tornam-se `NOT_ANSWERED`.
* Mensagem principal é atualizada.

**Prioridade:** P0

---

## US-035 — Bloquear respostas atrasadas

**Como sistema, quero rejeitar respostas após o fechamento.**

### Critérios de aceitação

Ao tentar responder após o fechamento:

```text
❌ Esta daily já foi encerrada.
```

* Nenhuma resposta tardia é salva.
* Resposta anterior não pode ser editada.

**Prioridade:** P0

---

## US-036 — Justificar ausência

**Como administrador, quero registrar uma ausência justificada.**

### Critérios de aceitação

Administrador informa:

```text
usuário
projeto/daily
motivo
```

Sistema registra:

```text
status = EXCUSED
excused_at
excused_by
excuse_reason
```

**Prioridade:** P1

---

## US-037 — Atualizar mensagem após justificativa

**Como equipe, quero visualizar que determinado participante está justificadamente ausente.**

Exemplo:

```text
🏖️ Carlos
```

**Prioridade:** P1

---

## US-038 — Excluir justificadas da taxa de resposta

**Como gestor, quero que ausências justificadas não reduzam artificialmente a taxa de participação.**

### Fórmula

```text
respondidas /
(respondidas + não respondidas)
```

`EXCUSED` não entra no denominador.

**Prioridade:** P1

---

## US-039 — Fechamento manual

**Como administrador, quero fechar excepcionalmente uma daily antes do horário.**

### Critérios de aceitação

* Apenas ADMIN executa.
* Mesmas regras do fechamento automático são aplicadas.
* Ação é auditada.

**Prioridade:** P2

---

# EP-06 — Relatórios

## US-040 — Gerar relatório diário consolidado

**Como gestor, quero receber uma visão consolidada da daily do dia.**

### Horário inicial

```text
12:10
```

### Critérios de aceitação

Relatório contém:

```text
projetos
participantes únicos
dailies esperadas
respondidas
não respondidas
justificadas
taxa de resposta
```

**Prioridade:** P0

---

## US-041 — Exibir relatório por participante

**Como gestor, quero visualizar os projetos e respostas de cada participante.**

### Exemplo

```text
Marcelle

✅ AmazHealth
✅ Campanhas

AmazHealth
- feito
- hoje
- impedimentos
- observações

Campanhas
...
```

**Prioridade:** P0

---

## US-042 — Identificar daily não respondida

**Como gestor, quero visualizar claramente quando uma pessoa não respondeu determinado projeto.**

Exemplo:

```text
Campanhas Barbearia
❌ Daily não respondida
```

**Prioridade:** P0

---

## US-043 — Enviar relatório aos canais configurados

**Como administrador, quero que o relatório seja enviado automaticamente a todos os canais habilitados.**

### Critérios de aceitação

* Um relatório pode possuir múltiplos destinos.
* Falha em um canal não deve impedir os demais.
* Erro de permissão fica registrado.

**Prioridade:** P0

---

## US-044 — Gerar relatório manual

**Como administrador, quero solicitar um relatório sob demanda.**

### Comando conceitual

```text
/relatorio gerar
```

Parâmetros:

```text
tipo
projeto
data/período
```

### Critérios de aceitação

* Relatório é enviado ao canal onde o comando foi executado.
* Canal não precisa estar nos destinos automáticos.
* Apenas ADMIN pode executar.

**Prioridade:** P1

---

## US-045 — Gerar relatório de projeto

**Como gestor, quero analisar apenas um projeto específico.**

### Critérios de aceitação

* Pode selecionar projeto.
* Pode selecionar data/período.
* Inclui status e respostas dos membros daquela sessão.

**Prioridade:** P1

---

## US-046 — Gerar relatório semanal

**Como gestor, quero receber um resumo consolidado da semana.**

### Configuração inicial

```text
sexta-feira
12:20
```

### Conteúdo mínimo

```text
dailies esperadas
respondidas
não respondidas
justificadas
taxa por projeto
participação por pessoa
atividades
impedimentos
observações
```

**Prioridade:** P1

---

## US-047 — Gerar relatório mensal

**Como gestor, quero acompanhar os resultados consolidados do mês.**

### Configuração inicial

```text
último dia útil
12:20
```

### Critérios de aceitação

* Consolida todas as sessões válidas do mês.
* Apresenta visão geral.
* Apresenta visão por projeto.
* Apresenta visão por participante.

**Prioridade:** P1

---

## US-048 — Consultar relatório histórico

**Como gestor, quero gerar relatórios de períodos anteriores.**

### Exemplos

```text
ontem
semana passada
agosto/2026
data específica
```

### Critérios de aceitação

* Dados vêm de snapshots históricos.
* Mudanças atuais de projeto não modificam resultados anteriores.

**Prioridade:** P1

---

# EP-07 — Histórico, Auditoria e Resiliência

## US-049 — Preservar histórico de memberships

**Como sistema, quero manter entrada e saída de participantes dos projetos.**

**Prioridade:** P1

---

## US-050 — Preservar histórico das perguntas

**Como sistema, quero que alterações nas perguntas não mudem respostas anteriores.**

**Prioridade:** P1

---

## US-051 — Registrar ações administrativas

**Como administrador, quero saber quem realizou alterações importantes.**

### Ações mínimas

```text
criação de projeto
arquivamento
adição/remoção de membro
alteração de configuração
justificativa
fechamento manual
```

### Informações

```text
quem
o quê
quando
alvo
```

**Prioridade:** P1

---

## US-052 — Recuperar sessões após reinício

**Como sistema, quero continuar uma daily após reinicialização do bot.**

### Cenário

```text
09:00 daily aberta
09:45 bot reinicia
09:46 bot retorna
```

### Critérios de aceitação

* Session continua `OPEN`.
* Assignments permanecem.
* Respostas permanecem.
* Message ID é recuperado.
* Próximas etapas do ciclo ainda são executadas.

**Prioridade:** P1

---

## US-053 — Garantir idempotência dos jobs

**Como sistema, quero impedir duplicação causada por execução repetida.**

### Exemplos

O sistema não pode criar duas:

```text
Daily AmazHealth
19/08/2026
```

### Critérios de aceitação

* Restrição única por projeto/data.
* Jobs podem ser executados novamente sem duplicar registros.

**Prioridade:** P0

---

## US-054 — Tratar canal removido ou inacessível

**Como sistema, quero falhar de forma controlada quando um canal configurado não estiver disponível.**

### Critérios de aceitação

* Bot não encerra sua execução.
* Problema é registrado.
* Demais projetos continuam funcionando.

**Prioridade:** P1

---

## US-055 — Tratar usuário que saiu do Discord

**Como sistema, quero preservar o histórico mesmo se um membro sair do servidor.**

### Critérios de aceitação

* Registros históricos permanecem pelo Discord User ID.
* Relatórios históricos continuam funcionando.
* Usuário não participa de novas sessões.

**Prioridade:** P1

---

# EP-08 — Qualidade, Deploy e Operação

## US-056 — Criar testes unitários das regras de negócio

Cobertura prioritária:

```text
membership
snapshot
status
fechamento
ausência
taxa de participação
autorização
```

**Prioridade:** P0

---

## US-057 — Criar testes de integração com banco

Cobertura mínima:

```text
projects
memberships
daily sessions
assignments
answers
reports
```

**Prioridade:** P0

---

## US-058 — Testar ciclo completo da daily

### Cenário

```text
criar projeto
→ adicionar usuários
→ abrir daily
→ responder
→ lembrar pendente
→ fechar
→ relatório
```

### Critérios de aceitação

O fluxo completo deverá funcionar em ambiente de teste sem manipulação manual do banco.

**Prioridade:** P0

---

## US-059 — Criar `.env.example`

Deverá documentar:

```text
DISCORD_TOKEN
DATABASE_HOST
DATABASE_PORT
DATABASE_NAME
DATABASE_USER
DATABASE_PASSWORD
```

Sem credenciais reais.

**Prioridade:** P0

---

## US-060 — Documentar setup local

README deverá explicar:

```text
pré-requisitos
configuração Discord
variáveis
Docker
migrations
execução
comandos
testes
```

**Prioridade:** P1

---

## US-061 — Documentar permissões Discord

Deverá existir documentação das permissões mínimas necessárias.

Exemplos:

```text
View Channels
Send Messages
Embed Links
Use Application Commands
Read Message History
Mention Everyone/roles conforme necessidade
```

A aplicação não deverá exigir `Administrator`.

**Prioridade:** P1

---

## US-062 — Preparar deploy permanente

**Como administrador, quero manter o bot online continuamente.**

### Critérios de aceitação

* Deploy executado através de Docker.
* Containers reiniciam automaticamente.
* Banco utiliza volume persistente.
* `.env` não está versionado.
* Logs podem ser consultados.

**Prioridade:** P1

---

# 4. Corte do MVP Operacional

Para não construirmos a V1 inteira antes de testar o bot na prática, considero **MVP operacional** o seguinte conjunto:

```text
EP-01 Fundação

US-001
US-002
US-003
US-004
US-005

EP-02 Configuração

US-007
US-008
US-009
US-011
US-013

EP-03 Projetos

US-014
US-015
US-018
US-019

EP-04 Daily

US-022
US-023
US-024
US-025
US-026
US-027
US-028
US-029
US-031

EP-05 Fluxo

US-032
US-033
US-034
US-035

EP-06 Relatório

US-040
US-041
US-042
US-043

EP-07 Resiliência

US-053

EP-08 Qualidade

US-056
US-057
US-058
US-059
```

Ao final desse corte será possível usar o bot em produção para uma daily real.

---

# 5. Fluxo de Entrega Sugerido

## Fase 1 — Fundação

```text
Discord conectado
PostgreSQL funcionando
Docker
migrations
estrutura
```

Resultado:

> Bot online, mas ainda sem regra de negócio.

---

## Fase 2 — Projetos e Pessoas

```text
criar projeto
adicionar membro
remover membro
listar projetos
```

Resultado:

> O bot já conhece a estrutura da equipe.

---

## Fase 3 — Primeira Daily Manual

```text
abrir sessão
snapshot
mensagem principal
botão
modal
resposta
check
```

Resultado:

> Primeira daily funcional, ainda sem automação temporal.

Esse é o primeiro grande milestone do projeto.

---

## Fase 4 — Automação

```text
09:00 abre

10:30 lembra

11:30 lembra

12:00 fecha
```

Resultado:

> Daily completamente automática.

---

## Fase 5 — Relatório Diário

```text
12:10
↓
consolidação
↓
#geral-gerencia
```

Resultado:

> **MVP operacional concluído.**

---

## Fase 6 — Administração Completa

```text
perguntas
dias
roles
horários
canais
ausências
edição
```

---

## Fase 7 — Relatórios Gerenciais

```text
manual
histórico
semanal
mensal
```

---

## Fase 8 — Hardening

```text
recuperação
auditoria
erros
permissões
testes
deploy
```

Resultado:

> **Zorysa Daily Bot V1.0.**

---

# 6. Ordem Inicial Recomendada de Desenvolvimento

```text
US-001 Estrutura
   ↓
US-003 PostgreSQL
   ↓
US-004 Migrations
   ↓
US-005 Docker
   ↓
US-002 Discord
   ↓
US-007 Guild
   ↓
US-011 Admin Roles
   ↓
US-014 Projeto
   ↓
US-018 Membership
   ↓
US-022 DailySession
   ↓
US-023 Assignments
   ↓
US-024 Questions Snapshot
   ↓
US-025 Mensagem
   ↓
US-026 Botão
   ↓
US-027 Modal
   ↓
US-028 Resposta
   ↓
US-029 Atualização da mensagem
   ↓
US-032/033 Lembretes
   ↓
US-034 Fechamento
   ↓
US-040 Relatório
```

---

# 7. Primeiro Milestone

## M1 — Daily manual completa

O primeiro objetivo funcional não deve ser implementar todos os comandos.

Deve ser conseguir executar:

```text
/admin cria AmazHealth
        ↓
adiciona Amanda
adiciona Carlos
adiciona Marcelle
        ↓
abre Daily manualmente
        ↓
#amazhealth

📋 Daily AmazHealth

⏳ Amanda
⏳ Carlos
⏳ Marcelle

[Responder Daily]
        ↓
Amanda responde
        ↓
✅ Amanda
⏳ Carlos
⏳ Marcelle
```

Uma vez que esse fluxo funcionar, teremos validado as partes tecnicamente mais críticas:

```text
Discord interactions
+
PostgreSQL
+
modelo de domínio
+
snapshots
+
modal
+
persistência
+
edição de mensagem
```

Só então adicionamos o scheduler.

---

# 8. Segundo Milestone

## M2 — Daily automática

Adicionar:

```text
09:00 abertura
10:30 reminder
11:30 reminder
12:00 fechamento
```

Resultado:

> nenhuma intervenção humana necessária para executar a daily.

---

# 9. Terceiro Milestone

## M3 — Gestão diária completa

Adicionar:

```text
12:10 relatório
ausência justificada
roles configuráveis
canais configuráveis
perguntas configuráveis
```

Resultado:

> fluxo diário completo da equipe.

---

# 10. Quarto Milestone

## M4 — Gestão histórica

Adicionar:

```text
relatório manual
relatório histórico
semanal
mensal
auditoria
recuperação pós-restart
```

Resultado:

> Zorysa Daily Bot V1.0.

---

# 11. Backlog Futuro

Funcionalidades que não deverão bloquear a V1:

### FUT-01 — Resumo por IA

Gerar resumo executivo das dailies.

### FUT-02 — Detecção de impedimentos recorrentes

Identificar bloqueios mencionados por vários dias.

### FUT-03 — Integração GitHub

Relacionar PRs, issues ou commits às informações da daily.

### FUT-04 — Integração Linear

Relacionar atividades reportadas aos cards dos projetos.

### FUT-05 — Dashboard Web

Dashboard gerencial independente do Discord.

### FUT-06 — Exportação

Exportar relatórios para:

```text
PDF
CSV
XLSX
```

### FUT-07 — Indicadores

Dashboard com:

```text
taxa de resposta
dailies por projeto
impedimentos
participação
histórico
```

### FUT-08 — Feriados

Calendário de feriados e exceções.

### FUT-09 — Pausa temporária

Permitir:

```text
/project pause
/member vacation
```

com intervalo de datas.

### FUT-10 — Resumo automático por projeto

Publicar uma versão curta e não sensível para a própria equipe do projeto.

---

# 12. Definition of Done Geral

Uma User Story poderá ser considerada concluída somente quando:

* implementação estiver finalizada;
* regras de autorização estiverem aplicadas;
* persistência estiver funcionando quando aplicável;
* erros relevantes estiverem tratados;
* testes correspondentes estiverem passando;
* comportamento estiver validado em ambiente Discord de teste;
* nenhuma credencial estiver hardcoded;
* documentação necessária estiver atualizada;
* funcionalidade não quebrar o histórico existente.

---

# 13. Resultado Esperado

A ordem de desenvolvimento deverá priorizar a obtenção rápida deste fluxo:

```text
Projeto
   ↓
Participantes
   ↓
Daily
   ↓
Formulário
   ↓
Resposta
   ↓
Status
   ↓
Lembretes
   ↓
Fechamento
   ↓
Relatório
```

Somente depois que esse fluxo estiver estável deverão ser priorizadas funcionalidades analíticas e integrações externas.

Dessa forma, a complexidade será adicionada progressivamente sem impedir que o bot comece a ser utilizado pela equipe ainda durante seu desenvolvimento.

