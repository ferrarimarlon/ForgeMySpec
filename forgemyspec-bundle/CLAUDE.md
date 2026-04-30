# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Console Jogo da Velha for Two Local Human Players
- Objective: Create a simple local console-based Jogo da Velha (tic-tac-toe) game for exactly two human players, with no online or GUI features.

## Non-Negotiable Guardrails
- Must be a console application only.
- Must support exactly two human local players.
- Must not include online, networked, or remote play features.
- Must not include a GUI or graphical window.
- Must keep the implementation simple and local.
- Must follow standard turn-based Jogo da Velha gameplay on a 3x3 board.

## Decision Rules
- If a feature is not necessary for local two-player console gameplay, exclude it.
- If an implementation choice introduces GUI behavior, reject that choice.
- If an implementation choice introduces networking or online behavior, reject that choice.
- If the input format is unspecified, choose a simple console-friendly format such as numbered cell selection.
- If invalid input is entered, the game must not advance the turn until a valid move is provided.
- If no language is specified, prefer a straightforward language suitable for console programs without adding extra frameworks.

## Success Criteria
- The application starts in a console and displays a 3x3 game board in text form.
- Two human players can alternately enter moves from the keyboard on the same machine.
- The game prevents invalid moves such as selecting an occupied cell or an out-of-range position.
- The game detects and announces a win for either player when three matching markers align horizontally, vertically, or diagonally.
- The game detects and announces a draw when all board cells are filled without a winner.
- The implementation contains no online or networking functionality.
- The implementation contains no GUI components and runs entirely in the console.

## Assumptions
- The game runs entirely in a text-based console or terminal.
- Both players take turns on the same device using keyboard input.
- The standard 3x3 Jogo da Velha rules apply.
- Players are represented by two distinct markers, assumed to be X and O.
- No networking, matchmaking, accounts, or remote multiplayer is needed.
- No graphical interface is allowed.
- If the programming language is not specified, any suitable language for console applications may be used.

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
