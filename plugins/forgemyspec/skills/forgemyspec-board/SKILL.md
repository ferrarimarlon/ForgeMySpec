---
name: forgemyspec-board
description: Keeps the conversation as a requirements board. Every user request becomes a requirement with the user's words and checkable steps; each reply is the status-bar board printed by the harness. Use in every ForgeMySpec session, on every request.
---

# ForgeMySpec board

The reply is the board, not a running chat.

1. For each user request, add a requirement to the board file (`forgemyspec-board.yaml` in a project,
   `forgemyspec-bundle/board/requirements.yaml` in the ForgeMySpec repository):

   ```yaml
   - id: R7
     status: doing        # done | doing | open | blocked
     title: "Short name of the requirement"
     quote: "the user's own words"
     steps:
       - {do: "a step with proof", check: "test: test_x.Class.test_y"}   # or check: "cmd: <shell command>"
       - {do: "a step only the user can confirm", ok: true}            # shown as claimed (?)
     evidence: "test or command output that shows it"   # when there is some
     next: "what happens next"                           # optional
   ```

2. Break it down: the steps are the requirement's **contract**, each one checkable. Then mark it as the one
   being worked on, so every action counts toward it (harness runs vs model writes):

   ```bash
   PYTHONPATH=<harness> python3 -m forgemyspec board start R7
   ```

   Work on it. Give every step a check whenever one exists, then run the checks: a step is verified (✔) only
   when its check ran and passed, and it turns stale (↻) when the code changes afterwards:

   ```bash
   PYTHONPATH=<harness> python3 -m forgemyspec board verify      # or: board verify R7
   ```

   After each step, show the board again, so the user sees it change. Mark a step `ok: true` only when there is evidence (a test run, a command output).
   A requirement's percent is its done steps over all steps; never estimate it.
3. Answer with the board, in a code block, plus at most one line of text:

   ```bash
   PYTHONPATH=<harness> python3 -m forgemyspec board
   ```

4. When the user asks for detail ("abre R7", "open R7"), answer with `forgemyspec board R7`.
