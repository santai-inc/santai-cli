"""TUI Theme System."""

from dataclasses import dataclass
from typing import Callable

import rich.theme
from rich.style import Style
from rich.text import Text


@dataclass
class ThemeColors:
    """Theme color palette."""

    bg: str = "#000000"
    fg: str = "#cccccc"
    primary: str = "#eeeeee"
    secondary: str = "#77ca9b"
    accent: str = "#dc4c4c"
    success: str = "#77ca9b"
    warning: str = "#cbc06c"
    error: str = "#dc4c4c"
    muted: str = "#555555"
    surface: str = "#111111"


@dataclass
class Theme:
    """Complete theme definition."""

    name: str
    display_name: str
    colors: ThemeColors
    border_chars: dict
    icons: dict
    css: str


def claude_theme() -> Theme:
    """Claude Code theme."""
    colors = ThemeColors(
        bg="#1a1a1a",
        fg="#ffffff",
        primary="#d77757",
        secondary="#fd5db1",
        accent="#b1b9f9",
        success="#4eba65",
        warning="#ffc107",
        error="#ff6b80",
        muted="#888888",
        surface="#373737",
    )
    return Theme(
        name="claude",
        display_name="Claude Code",
        colors=colors,
        border_chars={
            "top_left": "┌",
            "top_right": "┐",
            "bottom_left": "└",
            "bottom_right": "┘",
            "horizontal": "─",
            "vertical": "│",
        },
        icons={
            "success": "✓",
            "error": "✗",
            "warning": "!",
            "running": "▸",
            "bullet": "•",
            "spinner": ["·", "✢", "✳", "✶", "✻", "✽"],
        },
        css=_claude_css(colors),
    )


def catppuccin_theme() -> Theme:
    """Catppuccin Mocha theme."""
    colors = ThemeColors(
        bg="#1e1e2e",
        fg="#cdd6f4",
        primary="#cba6f7",
        secondary="#89b4fa",
        accent="#f5c2e7",
        success="#a6e3a1",
        warning="#f9e2af",
        error="#f38ba8",
        muted="#585b70",
        surface="#313244",
    )
    return Theme(
        name="catppuccin",
        display_name="Catppuccin",
        colors=colors,
        border_chars={
            "top_left": "╭",
            "top_right": "╮",
            "bottom_left": "╰",
            "bottom_right": "╯",
            "horizontal": "─",
            "vertical": "│",
        },
        icons={
            "success": "✓",
            "error": "✗",
            "warning": "!",
            "running": "▸",
            "bullet": "◦",
            "spinner": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
        },
        css=_catppuccin_css(colors),
    )


def btop_theme() -> Theme:
    """btop theme."""
    colors = ThemeColors(
        bg="#000000",
        fg="#cccccc",
        primary="#eeeeee",
        secondary="#77ca9b",
        accent="#dc4c4c",
        success="#77ca9b",
        warning="#cbc06c",
        error="#dc4c4c",
        muted="#555555",
        surface="#111111",
    )
    return Theme(
        name="btop",
        display_name="btop",
        colors=colors,
        border_chars={
            "top_left": "╭",
            "top_right": "╮",
            "bottom_left": "╰",
            "bottom_right": "╯",
            "horizontal": "─",
            "vertical": "│",
        },
        icons={
            "success": "✓",
            "error": "✗",
            "warning": "!",
            "running": "R",
            "bullet": "│",
            "spinner": ["│", "/", "─", "\\"],
        },
        css=_btop_css(colors),
    )


def _claude_css(colors: ThemeColors) -> str:
    """Generate Claude Code CSS."""
    return f"""
    Screen {{
        layout: horizontal;
        background: {colors.bg};
    }}

    Header {{
        background: {colors.surface};
        color: {colors.primary};
        text-style: bold;
    }}

    Header > HeaderTitle {{
        color: {colors.primary};
        text-style: bold;
    }}

    Header > HeaderIcon {{
        color: {colors.primary};
    }}

    Footer {{
        background: {colors.surface};
        color: {colors.muted};
    }}

    Footer > .footer--key {{
        background: {colors.surface};
        color: {colors.fg};
    }}

    Footer > .footer--description {{
        color: {colors.muted};
    }}

    #tree-container {{
        width: 1fr;
        height: 100%;
        border: solid {colors.muted};
        padding: 1 2;
        background: {colors.surface};
        margin: 1;
    }}

    #tree-title {{
        text-style: bold;
        color: {colors.primary};
        margin-bottom: 1;
        text-align: center;
        width: 100%;
    }}

    DirectoryTree {{
        background: transparent;
        padding: 0 1;
    }}

    DirectoryTree > .directory-tree--folder {{
        color: {colors.fg};
        text-style: bold;
    }}

    DirectoryTree > .directory-tree--extension {{
        color: {colors.muted};
    }}

    DirectoryTree > .directory-tree--file {{
        color: {colors.fg};
    }}

    DirectoryTree:focus > .directory-tree--cursor {{
        background: {colors.primary};
        color: {colors.bg};
    }}

    DirectoryTree > .directory-tree--cursor {{
        background: {colors.secondary} 30%;
        color: {colors.fg};
    }}

    #middle-container, #right-container {{
        width: 2fr;
        height: 100%;
        layout: vertical;
    }}

    #stats-container, #notes-container, #graph-container {{
        height: 1fr;
        border: solid {colors.muted};
        padding: 1 2;
        background: {colors.surface};
        margin: 1;
    }}

    #stats-title, #types-title, #recent-title, #notes-title, #graph-title {{
        margin-bottom: 1;
        color: {colors.primary};
        text-style: bold;
        border-bottom: solid {colors.primary};
        padding-bottom: 1;
    }}

    #notes-content, #graph-content {{
        color: {colors.fg};
        padding: 1;
        height: auto;
    }}

    DataTable {{
        height: auto;
        max-height: 10;
        margin-bottom: 1;
        background: {colors.surface};
        padding: 0 1;
    }}

    DataTable > .datatable--header {{
        background: {colors.primary};
        color: {colors.bg};
        text-style: bold;
    }}

    DataTable > .datatable--cursor {{
        background: {colors.primary} 40%;
        color: {colors.bg};
    }}

    DataTable > .datatable--even-row, .datatable--odd-row {{
        background: {colors.surface};
    }}

    DataTable:focus > .datatable--cursor {{
        background: {colors.primary};
        color: {colors.bg};
    }}

    StatsPanel, NotesPanel, GraphPanel {{
        background: transparent;
    }}

    StatsPanel > Label, NotesPanel > Label, GraphPanel > Label {{
        color: {colors.fg};
    }}
    """


def _catppuccin_css(colors: ThemeColors) -> str:
    """Generate Catppuccin CSS."""
    return f"""
    Screen {{
        layout: horizontal;
        background: {colors.bg};
    }}

    Header {{
        background: {colors.surface};
        color: {colors.primary};
        text-style: bold;
    }}

    Header > HeaderTitle {{
        color: {colors.primary};
        text-style: bold;
    }}

    Header > HeaderIcon {{
        color: {colors.primary};
    }}

    Footer {{
        background: {colors.surface};
        color: {colors.muted};
    }}

    Footer > .footer--key {{
        background: {colors.surface};
        color: {colors.fg};
    }}

    Footer > .footer--description {{
        color: {colors.muted};
    }}

    #tree-container {{
        width: 1fr;
        height: 100%;
        border: solid {colors.muted};
        padding: 1 2;
        background: {colors.surface};
        margin: 1;
    }}

    #tree-title {{
        text-style: bold;
        color: {colors.primary};
        margin-bottom: 1;
        text-align: center;
        width: 100%;
    }}

    DirectoryTree {{
        background: transparent;
        padding: 0 1;
    }}

    DirectoryTree > .directory-tree--folder {{
        color: {colors.fg};
        text-style: bold;
    }}

    DirectoryTree > .directory-tree--extension {{
        color: {colors.muted};
    }}

    DirectoryTree > .directory-tree--file {{
        color: {colors.fg};
    }}

    DirectoryTree:focus > .directory-tree--cursor {{
        background: {colors.primary};
        color: {colors.bg};
    }}

    DirectoryTree > .directory-tree--cursor {{
        background: {colors.primary} 30%;
        color: {colors.fg};
    }}

    #middle-container, #right-container {{
        width: 2fr;
        height: 100%;
        layout: vertical;
    }}

    #stats-container, #notes-container, #graph-container {{
        height: 1fr;
        border: solid {colors.muted};
        padding: 1 2;
        background: {colors.surface};
        margin: 1;
    }}

    #stats-title, #types-title, #recent-title, #notes-title, #graph-title {{
        margin-bottom: 1;
        color: {colors.primary};
        text-style: bold;
        border-bottom: solid {colors.primary};
        padding-bottom: 1;
    }}

    #notes-content, #graph-content {{
        color: {colors.fg};
        padding: 1;
        height: auto;
    }}

    DataTable {{
        height: auto;
        max-height: 10;
        margin-bottom: 1;
        background: {colors.surface};
        padding: 0 1;
    }}

    DataTable > .datatable--header {{
        background: {colors.primary};
        color: {colors.bg};
        text-style: bold;
    }}

    DataTable > .datatable--cursor {{
        background: {colors.primary} 40%;
        color: {colors.bg};
    }}

    DataTable > .datatable--even-row, .datatable--odd-row {{
        background: {colors.surface};
    }}

    DataTable:focus > .datatable--cursor {{
        background: {colors.primary};
        color: {colors.bg};
    }}

    StatsPanel, NotesPanel, GraphPanel {{
        background: transparent;
    }}

    StatsPanel > Label, NotesPanel > Label, GraphPanel > Label {{
        color: {colors.fg};
    }}
    """


def _btop_css(colors: ThemeColors) -> str:
    """Generate btop CSS."""
    return f"""
    Screen {{
        layout: horizontal;
        background: {colors.bg};
    }}

    Header {{
        background: {colors.surface};
        color: {colors.primary};
        text-style: bold;
    }}

    Header > HeaderTitle {{
        color: {colors.primary};
        text-style: bold;
    }}

    Header > HeaderIcon {{
        color: {colors.secondary};
    }}

    Footer {{
        background: {colors.surface};
        color: {colors.muted};
    }}

    Footer > .footer--key {{
        background: {colors.surface};
        color: {colors.fg};
    }}

    Footer > .footer--description {{
        color: {colors.muted};
    }}

    #tree-container {{
        width: 1fr;
        height: 100%;
        border: solid {colors.muted};
        padding: 1 2;
        background: {colors.surface};
        margin: 1;
    }}

    #tree-title {{
        text-style: bold;
        color: {colors.primary};
        margin-bottom: 1;
        text-align: center;
        width: 100%;
    }}

    DirectoryTree {{
        background: transparent;
        padding: 0 1;
    }}

    DirectoryTree > .directory-tree--folder {{
        color: {colors.fg};
        text-style: bold;
    }}

    DirectoryTree > .directory-tree--extension {{
        color: {colors.muted};
    }}

    DirectoryTree > .directory-tree--file {{
        color: {colors.fg};
    }}

    DirectoryTree:focus > .directory-tree--cursor {{
        background: {colors.accent};
        color: {colors.fg};
    }}

    DirectoryTree > .directory-tree--cursor {{
        background: {colors.accent} 30%;
        color: {colors.fg};
    }}

    #middle-container, #right-container {{
        width: 2fr;
        height: 100%;
        layout: vertical;
    }}

    #stats-container, #notes-container, #graph-container {{
        height: 1fr;
        border: solid {colors.muted};
        padding: 1 2;
        background: {colors.surface};
        margin: 1;
    }}

    #stats-title, #types-title, #recent-title, #notes-title, #graph-title {{
        margin-bottom: 1;
        color: {colors.secondary};
        text-style: bold;
        border-bottom: solid {colors.secondary};
        padding-bottom: 1;
    }}

    #notes-content, #graph-content {{
        color: {colors.fg};
        padding: 1;
        height: auto;
    }}

    DataTable {{
        height: auto;
        max-height: 10;
        margin-bottom: 1;
        background: {colors.surface};
        padding: 0 1;
    }}

    DataTable > .datatable--header {{
        background: {colors.secondary};
        color: {colors.bg};
        text-style: bold;
    }}

    DataTable > .datatable--cursor {{
        background: {colors.accent} 40%;
        color: {colors.fg};
    }}

    DataTable > .datatable--even-row, .datatable--odd-row {{
        background: {colors.surface};
    }}

    DataTable:focus > .datatable--cursor {{
        background: {colors.accent};
        color: {colors.fg};
    }}

    StatsPanel, NotesPanel, GraphPanel {{
        background: transparent;
    }}

    StatsPanel > Label, NotesPanel > Label, GraphPanel > Label {{
        color: {colors.fg};
    }}
    """


AVAILABLE_THEMES = {
    "claude": claude_theme,
    "catppuccin": catppuccin_theme,
    "btop": btop_theme,
}


class ThemeManager:
    """Manages TUI themes."""

    _current: Theme = btop_theme()
    _theme_names = list(AVAILABLE_THEMES.keys())

    @classmethod
    def set_theme(cls, name: str) -> bool:
        """Set the current theme by name."""
        if name in AVAILABLE_THEMES:
            cls._current = AVAILABLE_THEMES[name]()
            return True
        return False

    @classmethod
    def get_current_theme(cls) -> Theme:
        """Get the current theme."""
        return cls._current

    @classmethod
    def cycle_theme(cls) -> str:
        """Cycle to the next theme."""
        current_idx = cls._theme_names.index(cls._current.name)
        next_idx = (current_idx + 1) % len(cls._theme_names)
        cls._current = AVAILABLE_THEMES[cls._theme_names[next_idx]]()
        return cls._current.display_name

    @classmethod
    def get_available_themes(cls) -> list[str]:
        """Get list of available theme names."""
        return cls._theme_names.copy()


def get_theme_css() -> str:
    """Get CSS for the current theme."""
    return ThemeManager.get_current_theme().css