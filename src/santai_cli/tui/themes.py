"""TUI Theme System with palettes and runtime switching support."""

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
class Palette:
    """A named color palette variation within a theme."""

    name: str
    display_name: str
    colors: ThemeColors


@dataclass
class Theme:
    """Complete theme definition with multiple palettes."""

    name: str
    display_name: str
    palettes: list[Palette]
    border_chars: dict = field(default_factory=dict)
    icons: dict = field(default_factory=dict)

    @property
    def colors(self) -> ThemeColors:
        """Get colors from the active palette (first by default)."""
        return self.palettes[0].colors if self.palettes else ThemeColors()


# ─── Theme Definitions ───


def claude_theme() -> Theme:
    """Claude Code theme — warm, polished, graph-centric with terracotta accent."""
    palettes = [
        Palette(
            name="terracotta",
            display_name="Terracotta",
            colors=ThemeColors(
                bg="#1a1a1a",
                fg="#f0ece8",
                primary="#d77757",
                secondary="#fd5db1",
                accent="#b1b9f9",
                success="#4eba65",
                warning="#eb9f7f",
                error="#ff6b80",
                muted="#6b6560",
                surface="#2a2520",
            ),
        ),
        Palette(
            name="midnight",
            display_name="Midnight",
            colors=ThemeColors(
                bg="#0f0f1a",
                fg="#e8e4f0",
                primary="#8b7ec8",
                secondary="#c77dba",
                accent="#6ba5d7",
                success="#5cb87a",
                warning="#d4a76a",
                error="#e06070",
                muted="#5a5570",
                surface="#1a1a2e",
            ),
        ),
        Palette(
            name="forest",
            display_name="Forest",
            colors=ThemeColors(
                bg="#141a14",
                fg="#e0ece0",
                primary="#6aab6a",
                secondary="#d7a05a",
                accent="#7ab5c4",
                success="#5cb87a",
                warning="#c4a84d",
                error="#d06050",
                muted="#556055",
                surface="#1e281e",
            ),
        ),
    ]
    return Theme(
        name="claude",
        display_name="Claude Code",
        palettes=palettes,
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
            "warning": "⚠",
            "running": "▸",
            "bullet": "•",
            "spinner": ["·", "✢", "✳", "✶", "✻", "✽"],
        },
    )


def catppuccin_theme() -> Theme:
    """Catppuccin theme — soothing pastels in multiple flavors."""
    palettes = [
        Palette(
            name="mocha",
            display_name="Mocha",
            colors=ThemeColors(
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
            ),
        ),
        Palette(
            name="macchiato",
            display_name="Macchiato",
            colors=ThemeColors(
                bg="#24273a",
                fg="#cad3f5",
                primary="#c6a0f6",
                secondary="#8aadf4",
                accent="#f5bde6",
                success="#a6da95",
                warning="#eed49f",
                error="#ed8796",
                muted="#5b6078",
                surface="#363a4f",
            ),
        ),
        Palette(
            name="frappe",
            display_name="Frappé",
            colors=ThemeColors(
                bg="#303446",
                fg="#c6d0f5",
                primary="#ca9ee6",
                secondary="#8caaee",
                accent="#f4b8e4",
                success="#a6d189",
                warning="#e5c890",
                error="#e78284",
                muted="#626880",
                surface="#414559",
            ),
        ),
    ]
    return Theme(
        name="catppuccin",
        display_name="Catppuccin",
        palettes=palettes,
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
    palettes = [
        Palette(
            name="default",
            display_name="Default",
            colors=ThemeColors(
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
            ),
        ),
        Palette(
            name="green",
            display_name="Green",
            colors=ThemeColors(
                bg="#001100",
                fg="#c0d8c0",
                primary="#44dd44",
                secondary="#88cc88",
                accent="#dd6644",
                success="#44dd44",
                warning="#cccc44",
                error="#dd4444",
                muted="#446644",
                surface="#0a1a0a",
            ),
        ),
        Palette(
            name="blue",
            display_name="Blue",
            colors=ThemeColors(
                bg="#000011",
                fg="#c0c8d8",
                primary="#4488ee",
                secondary="#66aadd",
                accent="#dd5577",
                success="#55bb77",
                warning="#ccaa44",
                error="#dd4455",
                muted="#445566",
                surface="#0a0a1a",
            ),
        ),
    ]
    return Theme(
        name="btop",
        display_name="btop",
        palettes=palettes,
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


def light_theme() -> Theme:
    """Light theme — clean, minimal, paper-like with high contrast."""
    palettes = [
        Palette(
            name="paper",
            display_name="Paper",
            colors=ThemeColors(
                bg="#e4e2de",
                fg="#1a1a1a",
                primary="#2563eb",
                secondary="#7c3aed",
                accent="#db2777",
                success="#15803d",
                warning="#a16207",
                error="#b91c1c",
                muted="#4b5563",
                surface="#f0eeea",
            ),
        ),
        Palette(
            name="sand",
            display_name="Sand",
            colors=ThemeColors(
                bg="#ddd8ce",
                fg="#1c1917",
                primary="#b45309",
                secondary="#9a3412",
                accent="#a21caf",
                success="#166534",
                warning="#854d0e",
                error="#991b1b",
                muted="#57534e",
                surface="#ece7dd",
            ),
        ),
        Palette(
            name="ice",
            display_name="Ice",
            colors=ThemeColors(
                bg="#d8dee8",
                fg="#111827",
                primary="#1d4ed8",
                secondary="#4338ca",
                accent="#be185d",
                success="#15803d",
                warning="#92400e",
                error="#991b1b",
                muted="#475569",
                surface="#e8eef8",
            ),
        ),
    ]
    return Theme(
        name="light",
        display_name="Light",
        palettes=palettes,
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
            "warning": "⚠",
            "running": "▸",
            "bullet": "•",
            "spinner": ["◐", "◓", "◑", "◒"],
        },
    )


AVAILABLE_THEMES: dict[str, callable] = {
    "claude": claude_theme,
    "catppuccin": catppuccin_theme,
    "btop": btop_theme,
    "light": light_theme,
}


class ThemeManager:
    """Manages TUI themes with palette support and runtime switching."""

    _current_theme: Theme = btop_theme()
    _current_palette_idx: int = 0
    _theme_names = list(AVAILABLE_THEMES.keys())

    @classmethod
    def set_theme(cls, name: str, palette_idx: int = 0) -> bool:
        """Set the current theme by name, optionally with a palette index."""
        if name in AVAILABLE_THEMES:
            cls._current_theme = AVAILABLE_THEMES[name]()
            cls._current_palette_idx = min(palette_idx, len(cls._current_theme.palettes) - 1)
            return True
        return False

    @classmethod
    def get_current_theme(cls) -> Theme:
        """Get the current theme (with active palette's colors)."""
        return cls._current_theme

    @classmethod
    def get_current_palette(cls) -> Palette:
        """Get the currently active palette."""
        return cls._current_theme.palettes[cls._current_palette_idx]

    @classmethod
    def get_active_colors(cls) -> ThemeColors:
        """Get the active palette's colors."""
        return cls._current_theme.palettes[cls._current_palette_idx].colors

    @classmethod
    def cycle_theme(cls) -> Theme:
        """Cycle to the next theme and return it."""
        current_idx = cls._theme_names.index(cls._current_theme.name)
        next_idx = (current_idx + 1) % len(cls._theme_names)
        cls._current_theme = AVAILABLE_THEMES[cls._theme_names[next_idx]]()
        cls._current_palette_idx = 0
        return cls._current_theme

    @classmethod
    def cycle_palette(cls) -> Palette:
        """Cycle to the next palette within the current theme."""
        num_palettes = len(cls._current_theme.palettes)
        cls._current_palette_idx = (cls._current_palette_idx + 1) % num_palettes
        return cls._current_theme.palettes[cls._current_palette_idx]

    @classmethod
    def get_available_themes(cls) -> list[str]:
        """Get list of available theme names."""
        return cls._theme_names.copy()

    @classmethod
    def get_palette_info(cls) -> str:
        """Get info about current palette."""
        palette = cls.get_current_palette()
        theme = cls._current_theme
        idx = cls._current_palette_idx
        total = len(theme.palettes)
        return f"{palette.display_name} ({idx + 1}/{total})"


def get_theme_css(theme: Theme | None = None) -> str:
    """Generate CSS for a theme. Uses current theme if none specified.

    Uses the active palette's colors for CSS generation.
    """
    if theme is None:
        theme = ThemeManager.get_current_theme()
    c = ThemeManager.get_active_colors()
    return _generate_css(c)


def _generate_css(c: ThemeColors) -> str:
    """Generate the full CSS for a given color palette — dashboard style."""
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
        background: {c.bg};
        color: {c.fg};
    }}

    Footer > .footer--key {{
        background: {c.primary};
        color: {c.bg};
        text-style: bold;
    }}

    Footer > .footer--description {{
        color: {c.fg};
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

    NoteDetailScreen, AddNoteScreen, FilePreviewScreen, ThemeSelectScreen, ConfirmScreen, MoveFileScreen {{
        align: center middle;
        background: {c.bg} 80%;
    }}

    #confirm-body, #move-body {{
        color: {c.fg};
        padding: 1;
        height: auto;
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
        color: {c.fg};
    }}

    #theme-options {{
        color: {c.fg};
        height: auto;
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
