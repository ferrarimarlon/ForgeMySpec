from __future__ import annotations

import os
import re
import shutil

from . import __app_name__, __version__


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

SLATE = "\033[38;5;240m"
STEEL = "\033[38;5;250m"
SILVER = "\033[38;5;252m"
SKY = "\033[38;5;111m"
CYAN = "\033[38;5;45m"
MINT = "\033[38;5;49m"
GOLD = "\033[38;5;221m"
CORAL = "\033[38;5;209m"
RED = "\033[38;5;203m"
ORANGE = "\033[38;5;216m"

WORDMARK = (
    r"  ____                  ______                     ",
    r" / ___| _ __   ___  ___|  ___|__  _ __ __ _  ___  ",
    r" \___ \| '_ \ / _ \/ __| |_ / _ \| '__/ _` |/ _ \ ",
    r"  ___) | |_) |  __/ (__|  _| (_) | | | (_| |  __/ ",
    r" |____/| .__/ \___|\___|_|  \___/|_|  \__, |\___| ",
    r"       |_|                            |___/       ",
)


def render_banner() -> str:
    width = _terminal_width()
    inner_width = min(max(68, width - 6), 96)
    wordmark = _render_wordmark(inner_width)
    left_width = max(26, min(38, inner_width // 2 - 2))
    right_width = max(24, inner_width - left_width - 3)
    provider_label, provider_color = _provider_label()
    workspace = os.getcwd()
    body = [
        _frame_line("+", "-", "+", inner_width),
        *_frame_multiline(wordmark, inner_width),
        _frame_content("", inner_width),
        _frame_content(f"{BOLD}{ORANGE}Spec Forge{RESET}  {DIM}{SLATE}v{__version__}{RESET}", inner_width),
        _frame_content(f"{STEEL}Compile requirements into Claude execution artifacts{RESET}", inner_width),
        _frame_content("", inner_width),
        _frame_split(
            [
                f"{DIM}{SLATE}Provider{RESET}",
                f"{provider_color}{provider_label}{RESET}",
                "",
                f"{DIM}{SLATE}Workspace{RESET}",
                f"{STEEL}{workspace}{RESET}",
            ],
            [
                f"{DIM}{SLATE}Flow{RESET}",
                f"{SILVER}task -> spec -> lint -> package{RESET}",
                "",
                f"{DIM}{SLATE}Commands{RESET}",
                f"{STEEL}/help   /quit{RESET}",
            ],
            left_width,
            right_width,
        ),
        _frame_line("+", "-", "+", inner_width),
    ]
    return "\n".join(body)


def render_footer() -> str:
    width = _terminal_width()
    left = f"{DIM}{SLATE}/help{RESET}"
    center = f"{DIM}{SLATE}type a requirement{RESET}"
    right = f"{DIM}{SLATE}/quit{RESET}"
    plain_total = _visible_len("/help") + _visible_len("type a requirement") + _visible_len("/quit")
    spaces = max(4, width - plain_total)
    left_gap = spaces // 2
    right_gap = spaces - left_gap
    return left + (" " * left_gap) + center + (" " * right_gap) + right


def render_help() -> str:
    lines = [
        f"{BOLD}{ORANGE}Spec Forge help{RESET}",
        f"{STEEL}specforge \"<task text>\"{RESET}",
        f"{DIM}{SLATE}Run directly from the shell with a positional requirement.{RESET}",
        f"{STEEL}specforge --prompt <text>{RESET}",
        f"{DIM}{SLATE}Provide the requirement as a named argument.{RESET}",
        f"{STEEL}specforge --from-file <prompt.txt>{RESET}",
        f"{DIM}{SLATE}Load the requirement from a file.{RESET}",
        f"{STEEL}/quit{RESET}",
        f"{DIM}{SLATE}Exit the interactive client.{RESET}",
    ]
    return "\n".join(lines)


def render_shell_intro() -> str:
    return (
        f"{BOLD}{STEEL}Describe the requirement you want to compile.{RESET} "
        f"{DIM}{SLATE}Spec Forge will ask for the output folder next.{RESET}"
    )


def render_user_prompt() -> str:
    return f"{ORANGE}>{RESET} "


def render_assistant_line(text: str) -> str:
    return f"{DIM}{SLATE}|{RESET} {STEEL}{text}{RESET}"


def render_status(text: str) -> str:
    return f"{GOLD}●{RESET} {SLATE}{text}{RESET}"


def render_section_break() -> str:
    width = min(_terminal_width(), 108)
    return f"{DIM}{SLATE}{'─' * max(24, width - 2)}{RESET}"


def _provider_badge() -> str:
    if os.getenv("OPENAI_API_KEY"):
        return f"{MINT}●{RESET}{SKY} {_env_or_default('OPENAI_MODEL', 'gpt-codex')} · OpenAI{RESET}"
    if os.getenv("ANTHROPIC_API_KEY"):
        return f"{CORAL}●{RESET}{SKY} {_env_or_default('ANTHROPIC_MODEL', 'claude-3-5-sonnet-latest')} · Anthropic{RESET}"
    return f"{GOLD}●{RESET}{SLATE} No provider configured{RESET}"


def _env_or_default(key: str, default: str) -> str:
    value = os.getenv(key)
    return value if value else default


def _terminal_width() -> int:
    return max(56, min(shutil.get_terminal_size((100, 28)).columns, 124))


def _provider_label() -> tuple[str, str]:
    if os.getenv("OPENAI_API_KEY"):
        return f"{_env_or_default('OPENAI_MODEL', 'gpt-codex')}  OpenAI", MINT
    if os.getenv("ANTHROPIC_API_KEY"):
        return f"{_env_or_default('ANTHROPIC_MODEL', 'claude-3-5-sonnet-latest')}  Anthropic", CORAL
    return "No provider configured", GOLD


def _render_wordmark(inner_width: int) -> str:
    lines = []
    for raw_line in WORDMARK:
        pad = max(0, (inner_width - _visible_len(raw_line)) // 2)
        lines.append((" " * pad) + f"{ORANGE}{raw_line}{RESET}")
    return "\n".join(lines)


def _frame_multiline(text: str, inner_width: int) -> list[str]:
    return [_frame_content(line, inner_width) for line in text.splitlines()]


def _frame_content(text: str, inner_width: int) -> str:
    visible = _visible_len(text)
    padding = max(0, inner_width - visible)
    return f"{DIM}{SLATE}|{RESET} {text}{' ' * padding} {DIM}{SLATE}|{RESET}"


def _frame_line(left: str, fill: str, right: str, inner_width: int) -> str:
    return f"{DIM}{SLATE}{left}{fill * (inner_width + 2)}{right}{RESET}"


def _frame_split(left_lines: list[str], right_lines: list[str], left_width: int, right_width: int) -> str:
    rows = []
    height = max(len(left_lines), len(right_lines))
    left = left_lines + [""] * (height - len(left_lines))
    right = right_lines + [""] * (height - len(right_lines))
    for left_text, right_text in zip(left, right):
        left_visible = _visible_len(left_text)
        right_visible = _visible_len(right_text)
        left_padding = max(0, left_width - left_visible)
        right_padding = max(0, right_width - right_visible)
        rows.append(
            f"{DIM}{SLATE}|{RESET} "
            f"{left_text}{' ' * left_padding} "
            f"{DIM}{SLATE}|{RESET} "
            f"{right_text}{' ' * right_padding} "
            f"{DIM}{SLATE}|{RESET}"
        )
    return "\n".join(rows)


def _visible_len(text: str) -> int:
    return len(re.sub(r"\x1b\[[0-9;]*m", "", text))
