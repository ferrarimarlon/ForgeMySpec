# MCP and additional context

Inside Claude Code, ForgeMySpec benefits from **grounding** the requirement before locking a spec. MCP servers expose repositories, trackers, wikis, or internal APIs—use them **before** fixing constraints and success criteria.

## Principles

1. **Read before you write**: Pull relevant files, tickets, or schemas so `constraints` and `success_criteria` reflect reality, not guesses.
2. **Cite implicitly**: The spec text should state invariants (“must match API v2 error shape”) without pasting secrets or huge logs into `spec.yaml`.
3. **Scope contract**: If MCPs reveal required capabilities, encode them as short phrases under `metadata.scope_contract.must_include`. Out-of-scope items belong in `constraints`, not in `scope_contract`.
4. **Assumptions**: Anything inferred but not verified belongs in `context.assumptions`, not in `constraints`.

## Typical MCP patterns

- **Codebase / filesystem**: Confirm module boundaries, test locations, existing CLI patterns.
- **Issue / project trackers**: Align objective with ticket acceptance language.
- **Documentation MCPs**: External API contracts, SLA, auth flows.
- **Custom internal MCPs**: Service catalogs, compliance rules—fold into `constraints` and `decision_rules`.

## When MCPs are unavailable

Fall back to user interview: ask for repo paths, “must not” items, and evidence expectations, then record assumptions explicitly.
