"""Terminal rendering with rich: markdown lessons, syntax-highlighted code, check reports."""

from __future__ import annotations

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text

from azurath.checks import Report

LEXERS = {
    ".py": "python",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".go": "go",
    ".c": "c",
    ".h": "c",
    ".md": "markdown",
    ".ps1": "powershell",
    ".sh": "bash",
    ".txt": "text",
    ".cfg": "ini",
    ".ini": "ini",
    ".mod": "text",
}


def lexer_for(name: str) -> str:
    if name.endswith(".gitignore") or name.endswith(".funcignore"):
        return "text"
    for suffix, lexer in LEXERS.items():
        if name.endswith(suffix):
            return lexer
    return "text"


class Renderer:
    def __init__(self, console: Console, code_theme: str = "monokai") -> None:
        self.console = console
        self.code_theme = code_theme

    def md(self, text: str) -> None:
        self.console.print(Markdown(text.strip(), code_theme=self.code_theme, hyperlinks=True))

    def panel(self, body: str, title: str, style: str = "cyan") -> None:
        self.console.print(
            Panel(
                Markdown(body.strip(), code_theme=self.code_theme),
                title=f"[bold]{title}[/bold]",
                border_style=style,
                title_align="left",
            )
        )

    def code(self, source: str, filename: str, title: str | None = None) -> None:
        syntax = Syntax(
            source.rstrip("\n"),
            lexer_for(filename),
            theme=self.code_theme,
            line_numbers=True,
            word_wrap=False,
        )
        self.console.print(
            Panel(syntax, title=title or filename, border_style="blue", title_align="left")
        )

    def rule(self, title: str = "") -> None:
        self.console.print(Rule(title, style="dim"))

    def info(self, text: str) -> None:
        self.console.print(Text(text, style="cyan"))

    def ok(self, text: str) -> None:
        self.console.print(Text("✔ " + text, style="bold green"))

    def warn(self, text: str) -> None:
        self.console.print(Text("! " + text, style="yellow"))

    def error(self, text: str) -> None:
        self.console.print(Text("✘ " + text, style="bold red"))

    def say(self, markup: str) -> None:
        self.console.print(markup)

    def report(self, report: Report, title: str) -> None:
        lines: list = []
        for item in report.items:
            if item.ok:
                mark, style = "✔", "green"
            elif item.optional:
                mark, style = "○", "yellow"
            else:
                mark, style = "✘", "red"
            label = item.description + ("  (optional)" if item.optional else "")
            lines.append(
                Text.assemble((f" {mark} ", f"bold {style}"), Text.from_markup(_inline(label)))
            )
            if item.detail and not item.ok:
                for detail_line in item.detail.strip().splitlines()[:25]:
                    lines.append(Text("     " + detail_line, style="dim"))
        verdict = (
            Text(" QUEST COMPLETE ", style="bold black on green")
            if report.passed
            else Text(" Not yet. Fix the ✘ items and `check` again. ", style="bold white on red")
        )
        self.console.print(
            Panel(
                Group(*lines, Text(""), verdict),
                title=f"[bold]{title}[/bold]",
                title_align="left",
                border_style="green" if report.passed else "red",
            )
        )


def _inline(text: str) -> str:
    """Turn `backticks` into bold cyan markup, escaping anything else rich would eat."""
    from rich.markup import escape

    parts = escape(text).split("`")
    return "".join(f"[bold cyan]{p}[/bold cyan]" if i % 2 else p for i, p in enumerate(parts))
