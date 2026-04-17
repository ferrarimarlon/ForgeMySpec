from __future__ import annotations

import os
import re
import shutil

from . import __app_name__, __version__

# ── ANSI palette ───────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

SLATE  = "\033[38;5;240m"    # dark gray
STEEL  = "\033[38;5;250m"    # light gray
SILVER = "\033[38;5;252m"    # near-white

SKY    = "\033[38;5;111m"    # soft blue
CYAN   = "\033[38;5;45m"     # bright cyan
MINT   = "\033[38;5;49m"     # mint green (OpenAI badge)

AMBER  = "\033[38;5;214m"    # bright amber
GOLD   = "\033[38;5;221m"    # warm gold
ORANGE = "\033[38;5;209m"    # coral-orange (Anthropic badge)
CORAL  = "\033[38;5;203m"    # coral-red
RED    = CORAL

# ── gem / logo mark ────────────────────────────────────────────────────────────
#
#   Three rows of ◆ forming a horizontal gem shape:
#
#     ◈  Row 0  "  ◆◆◆◆◆  "  outer ring  (ORANGE)
#     ◈  Row 1  "◆◆◆◆◆◆◆◆◆"  middle band  (AMBER)
#     ◈  Row 2  "  ◆◆◆◆◆  "  outer ring  (GOLD)
#
_MARK        = ["  ◆◆◆◆◆  ", "◆◆◆◆◆◆◆◆◆", "  ◆◆◆◆◆  "]
_MARK_COLORS = [ORANGE, AMBER, GOLD]
_MARK_W      = 9   # visible width of each mark row


# ── public render functions ────────────────────────────────────────────────────

def render_banner() -> str:
    iw = _iw()

    gap = 3
    titles = [
        f"{BOLD}{AMBER}{__app_name__}{RESET}",
        f"{DIM}{STEEL}Compile requirements into Claude artifacts{RESET}",
        f"{DIM}{SLATE}v{__version__}{RESET}",
    ]
    logo_rows = [
        _line(f" {color}{mark}{RESET}{' ' * gap}{title} ", iw)
        for mark, color, title in zip(_MARK, _MARK_COLORS, titles)
    ]

    plabel, pcolor = _provider_label()
    ws = _truncate_path(os.getcwd(), max(20, iw - 14))

    a = f"{DIM}{SLATE}→{RESET}"
    flow = f"{SILVER}task {a} spec {a} lint {a} package{RESET}"

    parts = [
        _hline("╭", "─", "╮", iw),
        _blank(iw),
        *logo_rows,
        _blank(iw),
        _hline("├", "─", "┤", iw),
        _blank(iw),
        _kv("Provider ", f"{pcolor}{plabel}{RESET}", iw),
        _kv("Workspace", f"{STEEL}{ws}{RESET}", iw),
        _blank(iw),
        _kv("Flow     ", flow, iw),
        _kv("Commands ", f"{STEEL}/help   /quit{RESET}", iw),
        _blank(iw),
        _hline("╰", "─", "╯", iw),
    ]
    return "\n".join(parts)


def render_footer() -> str:
    width = _terminal_width()
    left   = f"{DIM}{SLATE}/help{RESET}"
    center = f"{DIM}{SLATE}type a requirement{RESET}"
    right  = f"{DIM}{SLATE}/quit{RESET}"
    dot    = f"{DIM}{SLATE} · {RESET}"
    plain  = _visible_len("/help") + _visible_len(" · ") * 2 + _visible_len("type a requirement") + _visible_len("/quit")
    pad    = max(2, (width - plain) // 2)
    return " " * pad + left + dot + center + dot + right


def render_help() -> str:
    lines = [
        f"{BOLD}{AMBER}ForgeMySpec — help{RESET}",
        "",
        f"  {DIM}{SLATE}positional{RESET}   {STEEL}forgemyspec \"<task>\"{RESET}",
        f"  {DIM}{SLATE}named flag{RESET}   {STEEL}forgemyspec --prompt <text>{RESET}",
        f"  {DIM}{SLATE}from file {RESET}   {STEEL}forgemyspec --from-file <path>{RESET}",
        "",
        f"  {DIM}{SLATE}/quit{RESET}        {STEEL}exit the interactive shell{RESET}",
    ]
    return "\n".join(lines)


def render_shell_intro() -> str:
    return (
        f"  {STEEL}Describe the requirement you want to compile.{RESET}  "
        f"{DIM}{SLATE}ForgeMySpec will ask for an output folder next.{RESET}"
    )


def render_user_prompt() -> str:
    return f"{AMBER}❯{RESET} "


def render_assistant_line(text: str) -> str:
    return f"  {DIM}{SLATE}│{RESET}  {STEEL}{text}{RESET}"


def render_status(text: str) -> str:
    return f"  {AMBER}◆{RESET}  {SLATE}{text}{RESET}"


def render_success(text: str) -> str:
    return f"  {MINT}✓{RESET}  {STEEL}{text}{RESET}"


def render_error(text: str) -> str:
    return f"  {CORAL}✗{RESET}  {STEEL}{text}{RESET}"


def render_section_break() -> str:
    width = min(_terminal_width(), 108)
    return f"  {DIM}{SLATE}{'─' * max(24, width - 4)}{RESET}"


# ── private helpers ────────────────────────────────────────────────────────────

def _iw() -> int:
    """Inner width: space between │ chars (used by _line, _hline, _blank, _kv)."""
    return min(max(58, _terminal_width() - 4), 88)


def _terminal_width() -> int:
    return max(56, min(shutil.get_terminal_size((100, 28)).columns, 124))


def _line(content: str, iw: int) -> str:
    """Wrap *content* between │ chars, padding to fill inner_width + 2 chars."""
    vis     = _visible_len(content)
    padding = max(0, iw + 2 - vis)
    return f"{DIM}{SLATE}│{RESET}{content}{' ' * padding}{DIM}{SLATE}│{RESET}"


def _blank(iw: int) -> str:
    return f"{DIM}{SLATE}│{' ' * (iw + 2)}│{RESET}"


def _hline(left: str, fill: str, right: str, iw: int) -> str:
    return f"{DIM}{SLATE}{left}{fill * (iw + 2)}{right}{RESET}"


def _kv(key: str, value: str, iw: int) -> str:
    content = f"  {DIM}{SLATE}{key}  {RESET}{value} "
    return _line(content, iw)


def _provider_label() -> tuple[str, str]:
    if os.getenv("OPENAI_API_KEY"):
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        return f"{model}  OpenAI", MINT
    if os.getenv("ANTHROPIC_API_KEY"):
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        return f"{model}  Anthropic", ORANGE
    return "No provider configured", GOLD


def _provider_badge() -> str:
    label, color = _provider_label()
    return f"{color}●{RESET}{SKY} {label}{RESET}"


def _truncate_path(path: str, max_len: int) -> str:
    if len(path) <= max_len:
        return path
    home = os.path.expanduser("~")
    if path.startswith(home):
        path = "~" + path[len(home):]
    if len(path) <= max_len:
        return path
    return "…" + path[-(max_len - 1):]


def _visible_len(text: str) -> int:
    return len(re.sub(r"\x1b\[[0-9;]*m", "", text))


# ── legacy frame helpers (kept for any external callers) ──────────────────────

def _frame_content(text: str, inner_width: int) -> str:
    vis     = _visible_len(text)
    padding = max(0, inner_width - vis)
    return f"{DIM}{SLATE}│{RESET} {text}{' ' * padding} {DIM}{SLATE}│{RESET}"


def _frame_line(left: str, fill: str, right: str, inner_width: int) -> str:
    return f"{DIM}{SLATE}{left}{fill * (inner_width + 2)}{right}{RESET}"


def _center_text(text: str, inner_width: int) -> str:
    pad = max(0, (inner_width - _visible_len(text)) // 2)
    return (" " * pad) + text
