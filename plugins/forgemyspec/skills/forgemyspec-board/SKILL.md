---
name: forgemyspec-board
description: Keeps the conversation as a requirements board. Every user request becomes a requirement with the user's words and checkable steps; each reply ends with the status-bar board printed by the harness, showing what is verified by checks (harness) and what is only claimed (model). Use in every ForgeMySpec session, on every request.
---

# ForgeMySpec board

The reply is the board, not a running chat.

1. For each user request, add a requirement to `forgemyspec-board.yaml` at the project root:

   ```yaml
   - id: R7
     status: doing        # done | doing | open | blocked
     title: "Short name of the requirement"
     quote: "the user's own words"
     steps:
       - {do: "a step with proof", check: "test: test_x.Class.test_y"}   # or check: "cmd: <shell command>"
       - {do: "a step only the user can confirm", ok: true}            # shown as claimed (?)
     evidence: "test or command output that shows it"
     next: "what happens next"
   ```

2. The steps are the requirement's **contract**. Mark the requirement being worked on, so every action counts
   toward it (harness runs against model writes, and output tokens):

   ```bash
   PYTHONPATH=src python3 -m forgemyspec.board start R7
   ```

   Give every step a check whenever one exists, then run the checks. A step is verified (✔) only when its check
   ran and passed, and it turns stale (↻) when the code changes afterwards:

   ```bash
   PYTHONPATH=src python3 -m forgemyspec.board verify      # or: verify R7
   ```

   Mark a step `ok: true` only when there is evidence. A requirement's percent is its done steps over all steps;
   never estimate it.

3. End every reply with the board, pasted whole in a code block, plus at most one line of text:

   ```bash
   PYTHONPATH=src python3 -m forgemyspec.board
   ```

   The Stop hook sends back, once, a reply that has no board.

4. When the user asks for detail ("abre R7", "open R7"), answer with `python3 -m forgemyspec.board R7`.
