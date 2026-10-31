# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Tornar o fluxo ForgeMySpec impossível de pular dentro do Claude Code e visível a cada prompt. O comando `forgemyspec init` instala em qualquer repositório uma cópia do harness, as skills e o agente, hooks estritos determinísticos, um gate no pre-commit do git e um gate no CI. A cada prompt aparece uma caixa de risco, em português, mostrando quais requisitos estão provados, só testados ou furando, onde o projeto está furando e quanto do código ainda deixa espaço para o LLM alucinar.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] `forgemyspec init <repo-git-temporário>` cria .forgemyspec/harness, .forgemyspec/config.yaml, .claude/skills, .claude/agents, um .claude/settings.json mesclado com `agent: forgemyspec-default` e os hooks, um bloco marcado no CLAUDE.md, .githooks/pre-commit com core.hooksPath configurado e .github/workflows/forgemyspec.yml; uma segunda execução informa que nada mudou; `init --check` sai com 0 numa instalação nova e com 1 depois que uma entrada de hook é removida.
- [ ] Testes de pipe da trava PreToolUse retornam deny, com um motivo que diz o próximo passo, para: edição fora de qualquer bundle aprovado e da lista de permitidos; contract.dfy, tests.dfy ou a seção formal depois do lock; contract.lock; generated/; .forgemyspec/state; .claude/settings*.json; .forgemyspec/config.yaml. Retornam allow para impl.dfy e shell/ num bundle travado e para caminhos permitidos.
- [ ] Testes de pipe da trava de Bash negam `forgemyspec lock`, `unlock` e `approve`, `git commit --no-verify` e redirecionamentos, sed -i, tee, cp, mv ou rm que atinjam um caminho protegido, e permitem comandos só de leitura.
- [ ] Uma trava que lança exceção resulta em chamada de ferramenta bloqueada (onFailure block conferido na entrada do hook e num teste de pipe que sai com 2).
- [ ] O hook de Stop retorna decision block nomeando o bundle e as etapas que falharam quando um bundle travado não tem gate PASS para o conteúdo atual, permite encerrar quando tem, e depois das continuações com stop_hook_active permite encerrar com um systemMessage dizendo que o trabalho não está verificado.
- [ ] O gate registra evidência por obrigação: erros de verificação atribuídos às obrigações pela cláusula do contrato que citam, testes Dafny e Python atribuídos pelas suas tags, e mutantes sobreviventes atribuídos às obrigações do método que os contém.
- [ ] Depois de cada turno o hook de Stop mostra uma caixa de risco em várias linhas, nenhuma com mais de 60 caracteres, com: requisitos atendidos sobre o total; uma linha por requisito de must_include com PROVADO, FRÁGIL ou FURANDO e o motivo; a divisão do espaço para alucinar (provado, só exemplos, livre) em linhas e porcentagem com a variação desde o turno anterior; cada furo com arquivo:linha; os itens que só o usuário garante (contrato e premissas, e quando ele os aprovou); e uma nota com os tokens do LLM no turno ou 'tokens indisponíveis'.
- [ ] SessionStart e UserPromptSubmit injetam um resumo de estado listando cada bundle com sua fase (spec, aprovado, travado, gate PASS ou FAIL) e o próximo passo obrigatório.
- [ ] Todas as mensagens do harness saem em português do Brasil, e o lint detecta negação em hipóteses escritas em português (não, nunca, sem, exceto, evitar e variações) além das palavras em inglês.
- [ ] README.md, CLAUDE.md, as skills e as referências em plugins/forgemyspec e o agente padrão estão em português do Brasil.
- [ ] O hook de pre-commit roda o gate nos bundles com mudanças em stage e rejeita o commit quando algum falha; o workflow de CI roda a mesma checagem.
- [ ] Este repositório é inicializado com o próprio `init` em modo estrito, e todo o trabalho da v0.2 a partir desse ponto passa pelas travas.
- [ ] A caixa de risco aparece na sessão do Claude Code no VS Code do usuário depois de um turno real, confirmado pelo usuário.

## Required Evidence
- [ ] Saída dos testes unitários do init (instalação nova, segunda execução idempotente, mescla com settings e CLAUDE.md já existentes, divergência no --check).
- [ ] Saída dos testes de pipe para cada decisão das travas listada nos critérios de sucesso, com o JSON que cada hook imprimiu.
- [ ] Saída dos testes de pipe do hook de Stop para os casos PASS, FAIL e stop_hook_active.
- [ ] Caixas de risco geradas para o budget-core em três estados: tudo provado, um mutante sobrevivente (FRÁGIL) e um verify falhando (FURANDO).
- [ ] Saída do gate e do lint em português, e o lint acusando uma hipótese com 'não'.
- [ ] Uma tentativa de commit rejeitada pelo pre-commit com um bundle falhando, e aceita depois da correção.
- [ ] Prova, dentro da sessão, de que um deny do PreToolUse disparou numa edição real neste repositório depois do init.
- [ ] Confirmação do usuário de que a caixa de risco aparece na sessão dele no VS Code.

## Decision Rules Compliance
- [ ] Se uma trava não consegue decidir (entrada ilegível, ferramenta desconhecida), negar em modo estrito e dizer a causa; nunca liberar por padrão.
- [ ] Se o uso de tokens da transcrição não puder ser lido, mostrar 'tokens indisponíveis' na caixa; nunca estimar tokens.
- [ ] Se o limite de repetições do Stop for atingido com o gate falhando, liberar o turno com um systemMessage dizendo que o trabalho não está verificado; nunca apresentá-lo como pronto.
- [ ] Se uma trava bloquear trabalho legítimo, ampliar a regra pelo config.yaml ou pelo scope.paths de um bundle com aprovação do usuário; nunca criar uma flag de desvio que o Claude possa ligar.
- [ ] Se um hook passar do tempo limite, guardar a parte cara (descoberta de bundles, hashes) em cache em .forgemyspec/state em vez de remover a checagem.
- [ ] Se um texto de mensagem não tiver tradução no módulo de mensagens, o teste falha; nunca deixar texto em inglês escapar para o usuário.
