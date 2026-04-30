# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Create a simple local console-based Jogo da Velha (tic-tac-toe) game for exactly two human players, with no online or GUI features.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] The application starts in a console and displays a 3x3 game board in text form.
- [ ] Two human players can alternately enter moves from the keyboard on the same machine.
- [ ] The game prevents invalid moves such as selecting an occupied cell or an out-of-range position.
- [ ] The game detects and announces a win for either player when three matching markers align horizontally, vertically, or diagonally.
- [ ] The game detects and announces a draw when all board cells are filled without a winner.
- [ ] The implementation contains no online or networking functionality.
- [ ] The implementation contains no GUI components and runs entirely in the console.

## Required Evidence
- [ ] Source code for a console application implementing the game loop.
- [ ] Evidence in code that input is taken from local keyboard/console only.
- [ ] Evidence in code that the board is rendered as text in the console.
- [ ] Evidence in code that win and draw conditions are checked.
- [ ] Evidence in code that invalid moves are rejected.
- [ ] Evidence in code that no networking or GUI libraries/features are used.

## Decision Rules Compliance
- [ ] If a feature is not necessary for local two-player console gameplay, exclude it.
- [ ] If an implementation choice introduces GUI behavior, reject that choice.
- [ ] If an implementation choice introduces networking or online behavior, reject that choice.
- [ ] If the input format is unspecified, choose a simple console-friendly format such as numbered cell selection.
- [ ] If invalid input is entered, the game must not advance the turn until a valid move is provided.
- [ ] If no language is specified, prefer a straightforward language suitable for console programs without adding extra frameworks.
