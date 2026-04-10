"""TUI Theme System with runtime switching support."""

from dataclasses import dataclass, field


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
    border_chars: dict = field(default_factory=dict)
    icons: dict = field(default_factory=dict)


def claude_theme() -> Theme:
    """Claude Code theme — warm, playful, terracotta accent."""
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
    )


def catppuccin_theme() -> Theme:
    """Catppuccin Mocha theme — soothing pastels, mauve primary."""
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
    )


def btop_theme() -> Theme:
    """btop theme — dense, gradient-rich, dashboard style."""
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
    )


AVAILABLE_THEMES: dict[str, callable] = {
    "claude": claude_theme,
    "catppuccin": catppuccin_theme,
    "btop": btop_theme,
}


class ThemeManager:
    """Manages TUI themes with runtime switching support."""

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
    def cycle_theme(cls) -> Theme:
        """Cycle to the next theme and return it."""
        current_idx = cls._theme_names.index(cls._current.name)
        next_idx = (current_idx + 1) % len(cls._theme_names)
        cls._current = AVAILABLE_THEMES[cls._theme_names[next_idx]]()
        return cls._current

    @classmethod
    def get_available_themes(cls) -> list[str]:
        """Get list of available theme names."""
        return cls._theme_names.copy()


def get_theme_css(theme: Theme | None = None) -> str:
    """Generate CSS for a theme. Uses current theme if none specified.

    Uses CSS variables pattern so the app can override get_css_variables()
    for runtime theme switching.
    """
    if theme is None:
        theme = ThemeManager.get_current_theme()
    c = theme.colors
    return _generate_css(c)


def _generate_css(c: ThemeColors) -> str:
    """Generate the full CSS for a given color palette."""
    return f"""
    Screen {{
        layout: horizontal;
        background: {c.bg};
    }}

    Header {{
        background: {c.surface};
        color: {c.primary};
        text-style: bold;
    }}

    Header > HeaderTitle {{
        color: {c.primary};
        text-style: bold;
    }}

    Header > HeaderIcon {{
        color: {c.primary};
    }}

    Footer {{
        background: {c.surface};
        color: {c.muted};
    }}

    Footer > .footer--key {{
        background: {c.surface};
        color: {c.fg};
    }}

    Footer > .footer--description {{
        color: {c.muted};
    }}

    /* === Main Layout Containers === */

    #main-layout {{
        width: 100%;
        height: 100%;
    }}

    #tree-container {{
        width: 1fr;
        height: 100%;
        border: solid {c.muted};
        padding: 1 2;
        background: {c.surface};
        margin: 1;
    }}

    #tree-title {{
        text-style: bold;
        color: {c.primary};
        margin-bottom: 1;
        text-align: center;
        width: 100%;
    }}

    DirectoryTree {{
        background: transparent;
        padding: 0 1;
    }}

    DirectoryTree > .directory-tree--folder {{
        color: {c.fg};
        text-style: bold;
    }}

    DirectoryTree > .directory-tree--extension {{
        color: {c.muted};
    }}

    DirectoryTree > .directory-tree--file {{
        color: {c.fg};
    }}

    DirectoryTree:focus > .directory-tree--cursor {{
        background: {c.primary};
        color: {c.bg};
    }}

    DirectoryTree > .directory-tree--cursor {{
        background: {c.primary} 30%;
        color: {c.fg};
    }}

    #middle-container, #right-container {{
        width: 2fr;
        height: 100%;
        layout: vertical;
    }}

    #stats-container, #notes-container, #graph-container {{
        height: 1fr;
        border: solid {c.muted};
        padding: 1 2;
        background: {c.surface};
        margin: 1;
    }}

    #stats-title, #types-title, #recent-title, #notes-title, #graph-title {{
        margin-bottom: 1;
        color: {c.primary};
        text-style: bold;
        border-bottom: solid {c.primary};
        padding-bottom: 1;
    }}

    #notes-list, #graph-content {{
        color: {c.fg};
        padding: 1;
        height: auto;
    }}

    ClickableNote {{
        padding: 1 2;
        margin-bottom: 1;
        background: {c.surface};
        border: solid {c.muted};
        height: auto;
    }}

    ClickableNote:hover {{
        background: {c.bg};
        border: solid {c.primary};
    }}

    DataTable {{
        height: auto;
        max-height: 10;
        margin-bottom: 1;
        background: {c.surface};
        padding: 0 1;
    }}

    DataTable > .datatable--header {{
        background: {c.primary};
        color: {c.bg};
        text-style: bold;
    }}

    DataTable > .datatable--cursor {{
        background: {c.primary} 40%;
        color: {c.bg};
    }}

    DataTable > .datatable--even-row, .datatable--odd-row {{
        background: {c.surface};
    }}

    DataTable:focus > .datatable--cursor {{
        background: {c.primary};
        color: {c.bg};
    }}

    StatsPanel, NotesPanel, GraphPanel {{
        background: transparent;
        height: auto;
    }}

    StatsPanel > Label, NotesPanel > Label, GraphPanel > Label {{
        color: {c.fg};
    }}

    /* === Graph Fullscreen === */

    #graph-fullscreen {{
        width: 100%;
        height: 100%;
        border: solid {c.primary};
        padding: 1 2;
        background: {c.surface};
        margin: 1;
    }}

    #graph-fullscreen GraphPanel {{
        height: auto;
    }}

    #graph-fullscreen #graph-title {{
        text-align: center;
        padding: 1 2;
        color: {c.primary};
    }}

    #graph-fullscreen #graph-content {{
        color: {c.fg};
        padding: 1 2;
        height: auto;
    }}

    /* === Modal Screens (centered overlay) === */

    NoteDetailScreen, AddNoteScreen, FilePreviewScreen, ThemeSelectScreen {{
        align: center middle;
        background: {c.bg} 80%;
    }}

    /* === Notes Modal === */

    #notes-modal {{
        width: 80%;
        height: 80%;
    }}

    #notes-modal-content {{
        width: 100%;
        height: 100%;
        border: solid {c.primary};
        background: {c.surface};
        padding: 2 4;
        overflow-y: auto;
    }}

    #notes-modal-title {{
        text-style: bold;
        color: {c.primary};
        text-align: center;
        margin-bottom: 1;
        border-bottom: solid {c.primary};
        padding-bottom: 1;
    }}

    #notes-modal-body {{
        color: {c.fg};
        padding: 1;
        height: auto;
    }}

    #note-title-input {{
        margin: 1 0;
        background: {c.bg};
        color: {c.fg};
        border: solid {c.muted};
    }}

    #note-title-input:focus {{
        border: solid {c.primary};
    }}

    #note-content-input {{
        margin: 1 0;
        min-height: 10;
        height: 1fr;
        background: {c.bg};
        color: {c.fg};
        border: solid {c.muted};
    }}

    #note-content-input:focus {{
        border: solid {c.primary};
    }}

    #note-help {{
        color: {c.muted};
        text-align: center;
        margin-top: 1;
    }}

    /* === File Preview Modal === */

    #file-preview-modal {{
        width: 80%;
        height: 80%;
    }}

    #file-preview-content {{
        width: 100%;
        height: 100%;
        border: solid {c.secondary};
        background: {c.surface};
        padding: 2 4;
        overflow-y: auto;
    }}

    #file-preview-title {{
        text-style: bold;
        color: {c.secondary};
        text-align: center;
        margin-bottom: 1;
        border-bottom: solid {c.secondary};
        padding-bottom: 1;
    }}

    #file-preview-body {{
        color: {c.fg};
        padding: 1;
        height: auto;
    }}

    /* === Theme Selector Modal === */

    #theme-modal {{
        width: 60%;
        height: auto;
        max-height: 70%;
    }}

    #theme-modal-content {{
        width: 100%;
        height: auto;
        border: solid {c.primary};
        background: {c.surface};
        padding: 2 4;
    }}

    #theme-modal-title {{
        text-style: bold;
        color: {c.primary};
        text-align: center;
        margin-bottom: 1;
        border-bottom: solid {c.primary};
        padding-bottom: 1;
    }}

    .theme-option {{
        padding: 1 2;
        margin: 0 1;
        color: {c.fg};
    }}

    .theme-option:hover {{
        background: {c.primary} 30%;
    }}

    .theme-option-active {{
        color: {c.primary};
        text-style: bold;
    }}
    """