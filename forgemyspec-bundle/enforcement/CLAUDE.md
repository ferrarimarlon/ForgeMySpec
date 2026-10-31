# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Enforcement estrito e caixa de risco por prompt, instalados por `forgemyspec init`
- Objective: Tornar o fluxo ForgeMySpec impossível de pular dentro do Claude Code e visível a cada prompt. O comando `forgemyspec init` instala em qualquer repositório uma cópia do harness, as skills e o agente, hooks estritos determinísticos, um gate no pre-commit do git e um gate no CI. A cada prompt aparece uma caixa de risco, em português, mostrando quais requisitos estão provados, só testados ou furando, onde o projeto está furando e quanto do código ainda deixa espaço para o LLM alucinar.

## Non-Negotiable Guardrails
- Somente hooks `type: command`. Os tipos `prompt` e `agent` chamam um LLM e são proibidos.
- As decisões dos hooks são funções puras do stdin, dos arquivos do repositório e do estado do harness; sem rede e sem chaves de API.
- Toda entrada de hook PreToolUse usa onFailure block, para que uma trava que quebre bloqueie a ação em vez de liberá-la.
- Os hooks PreToolUse e UserPromptSubmit terminam em até 2 segundos num repositório de 10 mil arquivos; o hook de Stop lê o resultado do gate em cache e nunca roda o gate.
- O init mescla com .claude/settings.json, CLAUDE.md, .gitignore e hooks do git existentes sem apagar entradas do usuário, grava um backup com data e hora de cada arquivo que altera e é idempotente: uma segunda execução não muda nada.
- O init nunca altera estado remoto (sem push, sem chamadas à API do GitHub); a proteção de branch é documentada como passo manual.
- Todo texto que o harness mostra ao usuário ou ao Claude (caixa de risco, motivos de bloqueio, relatório do gate, mensagens de lint, saída do init) é em português do Brasil e fica centralizado em um único módulo de mensagens.
- Dependências de execução continuam sendo Python >=3.9 com biblioteca padrão mais PyYAML, e Dafny 4.x como única ferramenta externa.
- Os dados de auditoria (ledger, cache do gate, marcas de turno) ficam em `.forgemyspec/state/`, que o init adiciona ao .gitignore.
- Commits ficam locais; nada vai para o remoto sem ordem explícita do usuário naquele momento.

## Decision Rules
- Se uma trava não consegue decidir (entrada ilegível, ferramenta desconhecida), negar em modo estrito e dizer a causa; nunca liberar por padrão.
- Se o uso de tokens da transcrição não puder ser lido, mostrar 'tokens indisponíveis' na caixa; nunca estimar tokens.
- Se o limite de repetições do Stop for atingido com o gate falhando, liberar o turno com um systemMessage dizendo que o trabalho não está verificado; nunca apresentá-lo como pronto.
- Se uma trava bloquear trabalho legítimo, ampliar a regra pelo config.yaml ou pelo scope.paths de um bundle com aprovação do usuário; nunca criar uma flag de desvio que o Claude possa ligar.
- Se um hook passar do tempo limite, guardar a parte cara (descoberta de bundles, hashes) em cache em .forgemyspec/state em vez de remover a checagem.
- Se um texto de mensagem não tiver tradução no módulo de mensagens, o teste falha; nunca deixar texto em inglês escapar para o usuário.

## Success Criteria
- `forgemyspec init <repo-git-temporário>` cria .forgemyspec/harness, .forgemyspec/config.yaml, .claude/skills, .claude/agents, um .claude/settings.json mesclado com `agent: forgemyspec-default` e os hooks, um bloco marcado no CLAUDE.md, .githooks/pre-commit com core.hooksPath configurado e .github/workflows/forgemyspec.yml; uma segunda execução informa que nada mudou; `init --check` sai com 0 numa instalação nova e com 1 depois que uma entrada de hook é removida.
- Testes de pipe da trava PreToolUse retornam deny, com um motivo que diz o próximo passo, para: edição fora de qualquer bundle aprovado e da lista de permitidos; contract.dfy, tests.dfy ou a seção formal depois do lock; contract.lock; generated/; .forgemyspec/state; .claude/settings*.json; .forgemyspec/config.yaml. Retornam allow para impl.dfy e shell/ num bundle travado e para caminhos permitidos.
- Testes de pipe da trava de Bash negam `forgemyspec lock`, `unlock` e `approve`, `git commit --no-verify` e redirecionamentos, sed -i, tee, cp, mv ou rm que atinjam um caminho protegido, e permitem comandos só de leitura.
- Uma trava que lança exceção resulta em chamada de ferramenta bloqueada (onFailure block conferido na entrada do hook e num teste de pipe que sai com 2).
- O hook de Stop retorna decision block nomeando o bundle e as etapas que falharam quando um bundle travado não tem gate PASS para o conteúdo atual, permite encerrar quando tem, e depois das continuações com stop_hook_active permite encerrar com um systemMessage dizendo que o trabalho não está verificado.
- O gate registra evidência por obrigação: erros de verificação atribuídos às obrigações pela cláusula do contrato que citam, testes Dafny e Python atribuídos pelas suas tags, e mutantes sobreviventes atribuídos às obrigações do método que os contém.
- Depois de cada turno o hook de Stop mostra uma caixa de risco em várias linhas, nenhuma com mais de 60 caracteres, com: requisitos atendidos sobre o total; uma linha por requisito de must_include com PROVADO, FRÁGIL ou FURANDO e o motivo; a divisão do espaço para alucinar (provado, só exemplos, livre) em linhas e porcentagem com a variação desde o turno anterior; cada furo com arquivo:linha; os itens que só o usuário garante (contrato e premissas, e quando ele os aprovou); e uma nota com os tokens do LLM no turno ou 'tokens indisponíveis'.
- SessionStart e UserPromptSubmit injetam um resumo de estado listando cada bundle com sua fase (spec, aprovado, travado, gate PASS ou FAIL) e o próximo passo obrigatório.
- Todas as mensagens do harness saem em português do Brasil, e o lint detecta negação em hipóteses escritas em português (não, nunca, sem, exceto, evitar e variações) além das palavras em inglês.
- README.md, CLAUDE.md, as skills e as referências em plugins/forgemyspec e o agente padrão estão em português do Brasil.
- O hook de pre-commit roda o gate nos bundles com mudanças em stage e rejeita o commit quando algum falha; o workflow de CI roda a mesma checagem.
- Este repositório é inicializado com o próprio `init` em modo estrito, e todo o trabalho da v0.2 a partir desse ponto passa pelas travas.
- A caixa de risco aparece na sessão do Claude Code no VS Code do usuário depois de um turno real, confirmado pelo usuário.

## Assumptions
- O modelo de ameaça é um agente que deriva sob pressão de contexto, não um adversário: as travas cobrem todas as ferramentas de arquivo e os caminhos comuns de escrita pelo shell, e o pre-commit e o CI pegam o que escapar por comando de shell.
- A distribuição é um comando, não um plugin: `forgemyspec init <repo>` copia o harness para `<repo>/.forgemyspec/harness/`, de modo que hooks, pre-commit e CI rodam sem pip, sem rede e sem plugin.
- Aprovação é ato humano: `lock`, `unlock` e `approve` são recusados quando o Claude os executa, e o usuário os roda no próprio terminal.
- Nem todo código cabe em Dafny. Um bundle pode ser só de spec: declara os caminhos que cobre em `scope.paths`, é aprovado com `approve` (lock da spec) e seu gate é o lint da spec mais um `verify_command` declarado.
- A caixa mede risco, não atividade. Cada cor sai de regras fixas sobre as evidências do gate, nunca do LLM: PROVADO = obrigação Dafny verificada, testes com a tag dela passando, nenhum mutante sobrevivente atribuído a ela e lock válido; FRÁGIL = provado com mutante sobrevivente atribuído a ela, ou obrigação de fronteira coberta só por testes de exemplo; FURANDO = sem cobertura, falhando em alguma etapa ou alterado depois da última rodada do gate.
- O espaço para alucinar é medido em linhas de código do projeto inteiro: provado (corpos atrás de obrigações PROVADAS), só exemplos (código de fronteira e corpos FRÁGEIS) e livre (código fora de bundle aprovado, ou em bundle FURANDO). Documentação e configuração aparecem à parte, como texto não verificado.
- Não existe divisão de tokens entre harness e LLM, porque o harness gasta zero tokens; os tokens do LLM aparecem só como nota de custo no fim da caixa.
- O uso de tokens por turno é lido do JSONL da transcrição da sessão (campos de usage das mensagens do assistente). O formato não é contrato documentado, então o leitor falha de forma suave e mostra 'tokens indisponíveis' em vez de estimar.
- Os elementos de interface do próprio Claude Code (indicador de raciocínio, cronômetro) não podem ser alterados; a caixa de risco é o systemMessage do hook de Stop.
- Specs são escritas no idioma do usuário; as frases de must_include aparecem na caixa exatamente como estão na spec.

## Implementation Protocol
1. Read `spec.yaml` first and implement only traceable scope.
2. If details are missing, document explicit assumptions before coding.
3. Do not add features, frameworks, or layers outside the spec objective.
4. Verify all success criteria with concrete evidence (tests, commands, outputs).
5. Report residual risks and unresolved assumptions in the final summary.

## Decision Log
- (record stable architecture or policy decisions here)

## Known Pitfalls
- (record recurring implementation failure modes here)
