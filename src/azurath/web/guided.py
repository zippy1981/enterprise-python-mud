"""Find the STEPs in a guided room's practice file, and switch choices on and off.

Guided rooms give the player a file where each ``# STEP n:`` is followed by a few
commented-out choices. In the terminal you uncomment one by hand. In the browser
each choice is a card you click.

The *starter* file (the room's scaffold) says which lines are choices. After the
STEP line come a few lines of prose, then the choices: commented lines that look
like code. Wrong choices are often deliberately broken Python (``pet name = "Pip"``),
so "looks like code" is generous. A choice ending in ``:`` takes the more-indented
commented lines under it with it (a two-line test function is one choice). The
player's copy has the same lines, some uncommented, so choosing never adds or
removes lines.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

STEP_LINE = re.compile(r"^\s*#\s*STEP\s+(\d+)\b[^:]*:\s*(.*)$")
COMMENTED = re.compile(r"^(\s*)# ?(.*)$")
ASSIGNMENT = re.compile(r"""^[\w"'.\[\]() ,+\-*/%<>!]+=(?!=)""")
BLOCK_HEADER = re.compile(r"^(if|elif|else|def|for|while|class|with|try|except)\b.*:$")
CALL = re.compile(r"^[\w.]+\(.*\)$")
KEYWORD = re.compile(r"^(return|pass|import|from|assert|print|del|raise)\b")


@dataclass
class Choice:
    lines: list[int]  # 0-based line numbers in the file
    code: list[str]  # those lines as they read uncommented
    chosen: bool = False

    @property
    def text(self) -> str:
        return "\n".join(self.code)


@dataclass
class Step:
    label: str  # "3", or "3a" / "3b" when one STEP asks two questions
    prompt: str
    choices: list[Choice] = field(default_factory=list)


def _uncomment(line: str) -> str | None:
    m = COMMENTED.match(line)
    return None if not m else m.group(1) + m.group(2)


def _indent(text: str) -> int:
    return len(text) - len(text.lstrip(" "))


def looks_like_code(text: str) -> bool:
    s = text.strip()
    if not s or s.startswith("#"):
        return False
    if any(rx.match(s) for rx in (ASSIGNMENT, BLOCK_HEADER, CALL, KEYWORD)):
        return True
    try:
        ast.parse(s)
    except SyntaxError:
        return False
    return True


def _continues(choice: Choice, code: str) -> bool:
    """Is ``code`` the body of a multi-line choice (a ``def ...:`` and its lines)?"""
    return choice.code[0].rstrip().endswith(":") and _indent(code) > _indent(choice.code[0])


PROSE = re.compile(r"^(\.\.\.|[A-Z][a-z']*[ ,]|\()")
TOGETHER = re.compile(r"\b(both|all) of these\b", re.IGNORECASE)


def _text_col(line: str) -> int:
    """Where the words start after the ``#``: prose under a STEP lines up with its text."""
    hash_at = line.index("#")
    rest = line[hash_at + 1 :]
    return hash_at + 1 + len(rest) - len(rest.lstrip(" "))


def _is_prose(text: str) -> bool:
    s = text.strip()
    if s.startswith("..."):  # "...and the line that ADDS..." carries the question on
        return True
    return bool(PROSE.match(s)) and not looks_like_code(s)


def _finish(steps: list[Step], number: str, groups: list[Step]) -> None:
    groups = [g for g in groups if g.choices]
    for i, group in enumerate(groups):
        if TOGETHER.search(group.prompt) and len(group.choices) > 1:  # "Uncomment BOTH..."
            lines = [n for c in group.choices for n in c.lines]
            code = [line for c in group.choices for line in c.code]
            group.choices = [Choice(lines, code)]
        group.label = number if len(groups) == 1 else f"{number}{'abcdefgh'[i]}"
        steps.append(group)


def parse_steps(starter: str) -> list[Step]:
    """The STEPs and their choices, from the starter file."""
    steps: list[Step] = []
    number: str | None = None
    groups: list[Step] = []
    header_col = 0
    done = False
    for i, line in enumerate(starter.splitlines()):
        header = STEP_LINE.match(line)
        if header:
            if number is not None:
                _finish(steps, number, groups)
            number = header.group(1)
            groups = [Step(number, header.group(2).strip())]
            header_col = header.start(2)
            done = False
            continue
        if number is None or done or not line.strip():
            continue
        code = _uncomment(line)
        group = groups[-1]
        if code is None:  # live code
            if group.choices:
                done = True
            continue
        last = group.choices[-1] if group.choices else None
        if not group.choices and (_text_col(line) == header_col or _is_prose(code)):
            group.prompt += " " + code.strip()  # the question carries on
        elif last is not None and _continues(last, code):
            last.lines.append(i)
            last.code.append(code)
        elif group.choices and _is_prose(code):
            groups.append(Step(number, code.strip()))  # a second question in this STEP
        else:
            group.choices.append(Choice([i], [code]))
    if number is not None:
        _finish(steps, number, groups)
    return steps


def with_state(starter: str, current: str) -> list[Step]:
    """The STEPs, marking which choices are uncommented in the player's file."""
    steps = parse_steps(starter)
    lines = current.splitlines()
    for step in steps:
        for choice in step.choices:
            choice.chosen = all(
                n < len(lines) and lines[n] == code
                for n, code in zip(choice.lines, choice.code, strict=True)
            )
    return steps


class ChoiceError(ValueError):
    """The file can't be changed safely (it no longer lines up with the starter)."""


def choose(starter: str, current: str, step: str, index: int) -> str:
    """Uncomment one choice of a STEP and comment out the others. Returns the new text."""
    start_lines = starter.splitlines()
    lines = current.splitlines()
    if len(lines) != len(start_lines):
        raise ChoiceError(
            "Your file has had lines added or removed, so the cards can't find the STEPs "
            "any more. Finish it in the editor, or `scaffold` a fresh copy."
        )
    match = [s for s in parse_steps(starter) if s.label == step]
    if not match or not 0 <= index < len(match[0].choices):
        raise ChoiceError(f"There's no choice {index + 1} in STEP {step}.")
    for i, choice in enumerate(match[0].choices):
        for n, code in zip(choice.lines, choice.code, strict=True):
            lines[n] = code if i == index else start_lines[n]
    return "\n".join(lines) + ("\n" if current.endswith("\n") else "")
