<!-- forgemyspec:start -->
## ForgeMySpec (strict mode)

This repository uses ForgeMySpec. The guards are deterministic hooks: they deny edits outside the flow.

1. `/forgemyspec`: write the spec (with the `formal` section) and run the lint.
2. `/forgemyspec-formalize`: write the contract, tests and planted errors; the **user** approves by running `lock`.
3. `/forgemyspec-implement`: implement and run the gate until it passes.
4. `/forgemyspec-amend`: amendments always with the user's approval.

Harness commands (Claude may run `lint`, `package`, `gate`, `risk`, `lock --check` and `request-approval`;
`lock`, `approve`, `unlock` and `init` need the user's approval: the code from `request-approval`, typed by the
user in the chat, or the user running the command in their own terminal):

```bash
PYTHONPATH=.forgemyspec/harness python3 -m forgemyspec lint <spec.yaml> --formal
PYTHONPATH=.forgemyspec/harness python3 -m forgemyspec gate <bundle>
PYTHONPATH=.forgemyspec/harness python3 -m forgemyspec risk
```

### Requirements board

Every user request becomes a requirement in `forgemyspec-board.yaml` (status, the user's words, checkable steps).
The reply is the board: `PYTHONPATH=.forgemyspec/harness python3 -m forgemyspec board`, in a code block, plus at
most one line. Explain only when the user asks for a requirement (`board R<n>`). See `/forgemyspec-board`.
<!-- forgemyspec:end -->
