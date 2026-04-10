"""Textual TUI application for Santai."""

from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    Static,
    TextArea,
)

from santai_cli.core.project import (
    SantaiProject,
    get_directory_stats,
    get_file_graph,
    get_notes,
)
from santai_cli.tui.themes import ThemeManager, get_theme_css


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_time_ago(dt: datetime) -> str:
    """Format datetime as relative time (e.g., '2 hours ago')."""
    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        return dt.strftime("%Y-%m-%d")


class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree that only shows santai directories."""

    def filter_paths(self, paths: list[Path]) -> list[Path]:
        """Filter to only show resources, codebases, history, notes dirs at root level."""
        return [
            p
            for p in paths
            if not p.name.startswith(".")  # Hide hidden files
        ]


class StatsPanel(Static):
    """Panel showing directory statistics."""

    def __init__(self, project: SantaiProject) -> None:
        super().__init__()
        self.project = project
        self._recent_files: list = []

    def compose(self) -> ComposeResult:
        yield Label("[bold]Directory Statistics[/bold]", id="stats-title")
        yield DataTable(id="dir-stats-table")
        yield Label("")
        yield Label("[bold]File Types[/bold]", id="types-title")
        yield DataTable(id="types-table")
        yield Label("")
        yield Label("[bold]Recent Files[/bold] [dim](click to open)[/dim]", id="recent-title")
        yield DataTable(id="recent-table", cursor_type="row")

    def on_mount(self) -> None:
        """Populate tables with data."""
        self.refresh_stats()

    def refresh_stats(self) -> None:
        """Refresh statistics data."""
        stats = get_directory_stats(self.project)
        self._recent_files = stats.recent_files[:5]

        # Directory stats table
        dir_table = self.query_one("#dir-stats-table", DataTable)
        dir_table.clear(columns=True)
        dir_table.add_columns("Directory", "Files")
        dir_table.add_row("resources", str(stats.resources_count))
        dir_table.add_row("codebases", str(stats.codebases_count))
        dir_table.add_row("history", str(stats.history_count))
        dir_table.add_row("notes", str(stats.notes_count))
        dir_table.add_row(
            "[bold]Total[/bold]",
            f"[bold]{stats.resources_count + stats.codebases_count + stats.history_count + stats.notes_count}[/bold]",
        )
        dir_table.add_row("Size", format_size(stats.total_size_bytes))

        # File types table
        types_table = self.query_one("#types-table", DataTable)
        types_table.clear(columns=True)
        types_table.add_columns("Type", "Count")
        for file_type, count in sorted(
            stats.file_types.items(), key=lambda x: x[1], reverse=True
        ):
            types_table.add_row(file_type, str(count))
        if not stats.file_types:
            types_table.add_row("[dim]No files[/dim]", "")

        # Recent files table (clickable rows)
        recent_table = self.query_one("#recent-table", DataTable)
        recent_table.clear(columns=True)
        recent_table.add_columns("File", "Modified")
        for file_info in self._recent_files:
            recent_table.add_row(
                file_info.name,
                format_time_ago(file_info.modified_at),
            )
        if not self._recent_files:
            recent_table.add_row("[dim]No files[/dim]", "")


class ClickableNote(Static):
    """A clickable note item in the notes panel."""

    class Clicked(Message):
        """Message sent when a note is clicked."""
        def __init__(self, note: "NoteEntry") -> None:
            super().__init__()
            self.note = note

    def __init__(self, note: "NoteEntry") -> None:
        super().__init__()
        self.note = note

    def on_click(self) -> None:
        """Handle click on this note."""
        self.post_message(self.Clicked(self.note))


class NotesPanel(Static):
    """Panel showing notes preview with clickable note items."""

    def __init__(self, project: SantaiProject) -> None:
        super().__init__()
        self.project = project
        self._notes: list = []

    def compose(self) -> ComposeResult:
        yield Label("[bold]Notes[/bold] [dim](click to open)[/dim]", id="notes-title")
        yield Vertical(id="notes-list")

    def on_mount(self) -> None:
        """Populate notes preview."""
        self.refresh_notes()

    def refresh_notes(self) -> None:
        """Refresh notes data."""
        from santai_cli.core.project import NoteEntry

        theme = ThemeManager.get_current_theme()
        self._notes = get_notes(self.project)
        notes_list = self.query_one("#notes-list", Vertical)

        # Remove old children
        notes_list.remove_children()

        if not self._notes:
            notes_list.mount(
                Static("[dim]No notes yet. Add .md or .txt files to notes/[/dim]")
            )
            return

        accent = theme.colors.success
        muted = theme.colors.muted
        for note in self._notes[:8]:  # Show up to 8 notes
            preview = (
                note.preview[:80] + "..." if len(note.preview) > 80 else note.preview
            )
            content = (
                f"[bold {accent}]📄 {note.title}[/bold {accent}]\n"
                f"[dim]{format_time_ago(note.modified_at)}[/dim]  "
                f"[{muted}]{preview}[/{muted}]"
            )
            widget = ClickableNote(note)
            widget.update(content)
            notes_list.mount(widget)


class GraphPanel(Static):
    """Panel showing file graph — Obsidian-style force-directed visualization."""

    # Directory color codes — warm palette inspired by Obsidian graph
    DIR_COLORS = {
        "resources": "#4eba65",  # green
        "codebases": "#06B6D4",  # cyan
        "history": "#b1b9f9",  # lavender
        "notes": "#d77757",  # terracotta
        "other": "#6b6560",  # warm gray
    }

    def __init__(self, project: SantaiProject, fullscreen: bool = False) -> None:
        super().__init__()
        self.project = project
        self.fullscreen = fullscreen

    def compose(self) -> ComposeResult:
        title = (
            "[bold]File Graph (Press g to exit)[/bold]"
            if self.fullscreen
            else "[bold]File Graph[/bold]"
        )
        yield Label(title, id="graph-title")
        yield Static(id="graph-content")

    def on_mount(self) -> None:
        """Populate graph view."""
        self.refresh_graph()

    def refresh_graph(self) -> None:
        """Refresh graph with Obsidian-style force-directed visualization."""
        from santai_cli.tui.graph_render import (
            build_graph_from_project_data,
            render_graph,
        )

        graph_data = get_file_graph(self.project)
        content_widget = self.query_one("#graph-content", Static)

        if not graph_data.nodes:
            content_widget.update(
                "[dim]No files found. Add files to resources/, notes/, etc.[/dim]"
            )
            return

        nodes, edges = build_graph_from_project_data(graph_data)

        # Determine render dimensions based on mode
        if self.fullscreen:
            render_width = 100
            render_height = 36
        else:
            render_width = 44
            render_height = 18

        # Render the force-directed graph
        graph_viz = render_graph(
            nodes=nodes,
            edges=edges,
            width=render_width,
            height=render_height,
            dir_colors=self.DIR_COLORS,
            show_labels=True,
            fullscreen=self.fullscreen,
        )

        # Build output
        lines = []

        # Stats header
        lines.append(
            f"[bold]Nodes:[/bold] {len(graph_data.nodes)}  "
            f"[bold]Edges:[/bold] {len(graph_data.edges)}"
        )
        lines.append("")

        # The graph visualization
        lines.append(graph_viz)

        # Legend
        lines.append("")
        dirs_present = {n.directory for n in graph_data.nodes}
        legend_parts = []
        for dir_name in ["resources", "codebases", "history", "notes"]:
            if dir_name in dirs_present:
                color = self.DIR_COLORS.get(dir_name, self.DIR_COLORS["other"])
                legend_parts.append(f"[{color}]●[/{color}] {dir_name}")
        for dir_name in dirs_present:
            if dir_name not in ["resources", "codebases", "history", "notes"]:
                color = self.DIR_COLORS.get(dir_name, self.DIR_COLORS["other"])
                legend_parts.append(f"[{color}]●[/{color}] {dir_name}")
        lines.append(" ".join(legend_parts))

        if graph_data.edges:
            lines.append(
                "[dim]⬢ hub (5+)  ◆ connected (3+)  ● linked  ○ isolated  ─ edge[/dim]"
            )

        content_widget.update("\n".join(lines))


# === Modal Screens ===


class ConfirmScreen(ModalScreen):
    """Generic confirmation dialog."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
        Binding("y", "confirm", "Yes"),
        Binding("n", "dismiss", "No"),
    ]

    def __init__(self, message: str, on_confirm: callable) -> None:
        super().__init__()
        self._message = message
        self._on_confirm = on_confirm

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-modal"):
            with Vertical(id="theme-modal-content"):
                yield Label("[bold]Confirm[/bold]", id="theme-modal-title")
                yield Static(id="confirm-body")

    def on_mount(self) -> None:
        body = self.query_one("#confirm-body", Static)
        body.update(
            f"{self._message}\n\n"
            f"[bold]y[/bold] = Yes  |  [bold]n[/bold] / Esc = Cancel"
        )

    def action_confirm(self) -> None:
        self._on_confirm()
        self.dismiss()


def _reload_all_panels(app: App) -> None:
    """Reload all panels and directory tree in the app."""
    for panel in app.query(StatsPanel):
        panel.refresh_stats()
    for panel in app.query(NotesPanel):
        panel.refresh_notes()
    for panel in app.query(GraphPanel):
        panel.refresh_graph()
    for tree in app.query(FilteredDirectoryTree):
        tree.reload()


class MoveFileScreen(ModalScreen):
    """Modal to move a file to another santai directory."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
        Binding("1", "move_1", "resources"),
        Binding("2", "move_2", "codebases"),
        Binding("3", "move_3", "history"),
        Binding("4", "move_4", "notes"),
    ]

    DIRS = ["resources", "codebases", "history", "notes"]

    def __init__(self, file_path: Path, project: SantaiProject) -> None:
        super().__init__()
        self._file_path = file_path
        self._project = project

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-modal"):
            with Vertical(id="theme-modal-content"):
                yield Label("[bold]Move File[/bold]", id="theme-modal-title")
                yield Static(id="move-body")

    def on_mount(self) -> None:
        body = self.query_one("#move-body", Static)
        # Determine current directory
        try:
            rel = self._file_path.relative_to(self._project.root)
            current_dir = rel.parts[0] if rel.parts else "unknown"
        except ValueError:
            current_dir = "unknown"

        lines = [
            f"File: [bold]{self._file_path.name}[/bold]",
            f"Current: [dim]{current_dir}/[/dim]",
            "",
            "Move to:",
        ]
        for i, d in enumerate(self.DIRS, 1):
            marker = " [dim](current)[/dim]" if d == current_dir else ""
            lines.append(f"  [{i}] {d}/{marker}")
        lines.append("")
        lines.append("[dim]Press 1-4 to move, Esc to cancel[/dim]")
        body.update("\n".join(lines))

    def _move_to(self, dest_dir: str) -> None:
        dest_path = self._project.root / dest_dir / self._file_path.name
        if dest_path.exists():
            # Add suffix to avoid overwrite
            stem = self._file_path.stem
            suffix = self._file_path.suffix
            counter = 1
            while dest_path.exists():
                dest_path = self._project.root / dest_dir / f"{stem}-{counter}{suffix}"
                counter += 1
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path.rename(dest_path)
            self.app.notify(f"Moved to {dest_dir}/{dest_path.name}")
            _reload_all_panels(self.app)
        except OSError as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.dismiss()

    def action_move_1(self) -> None:
        self._move_to("resources")

    def action_move_2(self) -> None:
        self._move_to("codebases")

    def action_move_3(self) -> None:
        self._move_to("history")

    def action_move_4(self) -> None:
        self._move_to("notes")


class NoteDetailScreen(ModalScreen):
    """Modal showing a single note's full content."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("d", "delete_note", "Delete"),
        Binding("m", "move_note", "Move"),
    ]

    def __init__(self, note, project: SantaiProject | None = None) -> None:
        super().__init__()
        self._note = note
        self._project = project

    def compose(self) -> ComposeResult:
        with Vertical(id="notes-modal"):
            with VerticalScroll(id="notes-modal-content"):
                yield Label(
                    f"[bold]📄 {self._note.title}[/bold]",
                    id="notes-modal-title",
                )
                yield Static(id="notes-modal-body")

    def on_mount(self) -> None:
        """Populate note content."""
        theme = ThemeManager.get_current_theme()
        body = self.query_one("#notes-modal-body", Static)
        accent = theme.colors.primary

        lines = []
        lines.append(f"[bold {accent}]{self._note.title}[/bold {accent}]")
        lines.append(
            f"[dim]{format_time_ago(self._note.modified_at)} · "
            f"{format_size(self._note.size_bytes)} · "
            f"{self._note.filename}[/dim]"
        )
        lines.append(f"[{accent}]{'─' * 50}[/{accent}]")
        lines.append("")
        # Show full content
        content = self._note.content[:5000] if len(self._note.content) > 5000 else self._note.content
        lines.append(content)
        if len(self._note.content) > 5000:
            lines.append("")
            lines.append("[dim]... (truncated)[/dim]")
        lines.append("")
        lines.append("[dim]d = delete · m = move · Esc = close[/dim]")

        body.update("\n".join(lines))

    def action_delete_note(self) -> None:
        """Delete this note with confirmation."""
        note_path = self._find_note_path()
        if not note_path:
            self.app.notify("Cannot find note file", severity="error")
            return

        def do_delete():
            try:
                note_path.unlink()
                self.app.notify(f"Deleted: {self._note.filename}")
                _reload_all_panels(self.app)
            except OSError as e:
                self.app.notify(f"Error: {e}", severity="error")
            self.dismiss()

        self.app.push_screen(
            ConfirmScreen(
                f"Delete [bold]{self._note.filename}[/bold]?\n\nThis cannot be undone.",
                do_delete,
            )
        )

    def action_move_note(self) -> None:
        """Move this note to another directory."""
        note_path = self._find_note_path()
        if not note_path:
            self.app.notify("Cannot find note file", severity="error")
            return
        project = self._project or self._get_project()
        if project:
            move_screen = MoveFileScreen(note_path, project)
            self.dismiss()
            self.app.call_later(lambda: self.app.push_screen(move_screen))

    def _find_note_path(self) -> Path | None:
        """Find the actual file path for this note."""
        project = self._project or self._get_project()
        if not project:
            return None
        note_path = project.notes_path / self._note.filename
        if note_path.exists():
            return note_path
        return None

    def _get_project(self) -> SantaiProject | None:
        """Get project from the app."""
        if hasattr(self.app, "project"):
            return self.app.project
        return None


class AddNoteScreen(ModalScreen):
    """Modal for creating a new note."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    def __init__(self, project: SantaiProject) -> None:
        super().__init__()
        self.project = project

    def compose(self) -> ComposeResult:
        with Vertical(id="notes-modal"):
            with Vertical(id="notes-modal-content"):
                yield Label(
                    "[bold]📝 Add Note (Esc to cancel)[/bold]",
                    id="notes-modal-title",
                )
                yield Label("Title:")
                yield Input(
                    placeholder="my-note (will be saved as my-note.md)",
                    id="note-title-input",
                )
                yield Label("Content:")
                yield TextArea(id="note-content-input")
                yield Static(
                    "[dim]Tab to switch fields · Ctrl+S to save · Esc to cancel[/dim]",
                    id="note-help",
                )

    def on_mount(self) -> None:
        """Focus the title input."""
        self.query_one("#note-title-input", Input).focus()

    def key_ctrl_s(self) -> None:
        """Save the note."""
        self._save_note()

    def _save_note(self) -> None:
        """Save the note to the notes/ directory."""
        title_input = self.query_one("#note-title-input", Input)
        content_input = self.query_one("#note-content-input", TextArea)

        title = title_input.value.strip()
        content = content_input.text.strip()

        if not title:
            self.app.notify("Title is required", severity="error")
            title_input.focus()
            return

        # Sanitize filename
        filename = title.lower().replace(" ", "-")
        # Remove non-alphanumeric chars except hyphens
        filename = "".join(c for c in filename if c.isalnum() or c == "-")
        if not filename:
            filename = "untitled"
        filename = filename + ".md"

        # Ensure notes directory exists
        notes_dir = self.project.notes_path
        notes_dir.mkdir(parents=True, exist_ok=True)

        file_path = notes_dir / filename

        # Don't overwrite existing files
        if file_path.exists():
            counter = 1
            while file_path.exists():
                file_path = notes_dir / f"{filename[:-3]}-{counter}.md"
                counter += 1

        # Write the note with a markdown header
        note_content = f"# {title}\n\n{content}\n"
        file_path.write_text(note_content, encoding="utf-8")

        self.app.notify(f"Saved: {file_path.name}")

        # Refresh all panels including directory tree
        _reload_all_panels(self.app)

        self.dismiss()


class FilePreviewScreen(ModalScreen):
    """File preview modal for viewing file contents."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("d", "delete_file", "Delete"),
        Binding("m", "move_file", "Move"),
    ]

    def __init__(self, file_path: Path, project: SantaiProject | None = None) -> None:
        super().__init__()
        self.file_path = file_path
        self._project = project

    def compose(self) -> ComposeResult:
        with Vertical(id="file-preview-modal"):
            with VerticalScroll(id="file-preview-content"):
                yield Label(
                    f"[bold]{self.file_path.name}[/bold]",
                    id="file-preview-title",
                )
                yield Static(id="file-preview-body")

    def on_mount(self) -> None:
        """Load file content."""
        body = self.query_one("#file-preview-body", Static)
        try:
            content = self.file_path.read_text(encoding="utf-8")
            if len(content) > 5000:
                content = content[:5000] + "\n\n[dim]... (truncated)[/dim]"
            content += "\n\n[dim]d = delete · m = move · Esc = close[/dim]"
            body.update(content)
        except UnicodeDecodeError:
            body.update(
                f"[dim]Binary file: {format_size(self.file_path.stat().st_size)}[/dim]\n\n"
                f"[dim]d = delete · m = move · Esc = close[/dim]"
            )
        except OSError as e:
            body.update(f"[dim]Error reading file: {e}[/dim]")

    def _get_project(self) -> SantaiProject | None:
        if self._project:
            return self._project
        if hasattr(self.app, "project"):
            return self.app.project
        return None

    def action_delete_file(self) -> None:
        """Delete this file with confirmation."""
        def do_delete():
            try:
                self.file_path.unlink()
                self.app.notify(f"Deleted: {self.file_path.name}")
                _reload_all_panels(self.app)
            except OSError as e:
                self.app.notify(f"Error: {e}", severity="error")
            self.dismiss()

        self.app.push_screen(
            ConfirmScreen(
                f"Delete [bold]{self.file_path.name}[/bold]?\n\nThis cannot be undone.",
                do_delete,
            )
        )

    def action_move_file(self) -> None:
        """Move this file to another directory."""
        project = self._get_project()
        if project:
            move_screen = MoveFileScreen(self.file_path, project)
            self.dismiss()
            self.app.call_later(lambda: self.app.push_screen(move_screen))
        else:
            self.app.notify("Cannot determine project", severity="error")

class ThemeSelectScreen(ModalScreen):
    """Theme selection modal with live switching."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("t", "dismiss", "Close"),
        Binding("1", "select_theme_1", "Claude"),
        Binding("2", "select_theme_2", "Catppuccin"),
        Binding("3", "select_theme_3", "btop"),
        Binding("4", "select_theme_4", "Light"),
    ]

    def compose(self) -> ComposeResult:
        theme = ThemeManager.get_current_theme()
        with Vertical(id="theme-modal"):
            with Vertical(id="theme-modal-content"):
                yield Label("[bold]Theme Selector (press Esc to close)[/bold]", id="theme-modal-title")
                yield Static(id="theme-options")

    def on_mount(self) -> None:
        """Show theme options."""
        self._refresh_options()

    def _refresh_options(self) -> None:
        """Refresh the theme options display with palette info."""
        current = ThemeManager.get_current_theme()
        current_palette = ThemeManager.get_current_palette()
        options = self.query_one("#theme-options", Static)

        lines = []
        lines.append("")
        themes_info = [
            ("1", "claude", "Claude Code", "Palettes: Terracotta · Midnight · Forest"),
            ("2", "catppuccin", "Catppuccin", "Palettes: Mocha · Macchiato · Frappé"),
            ("3", "btop", "btop", "Palettes: Default · Green · Blue"),
            ("4", "light", "Light", "Palettes: Paper · Sand · Ice"),
        ]

        for key, name, display, desc in themes_info:
            marker = "▸" if current.name == name else " "
            active = ""
            if current.name == name:
                active = f" [bold](active — {current_palette.display_name})[/bold]"
            lines.append(f"  {marker} [{key}] {display}{active}")
            lines.append(f"      [dim]{desc}[/dim]")
            lines.append("")

        lines.append("  [dim]Press 1/2/3/4 to switch theme[/dim]")
        lines.append("  [dim]Press p to cycle palettes within theme[/dim]")
        lines.append("  [dim]Esc to close[/dim]")

        options.update("\n".join(lines))

    def _apply_theme(self, name: str) -> None:
        """Apply a theme and refresh the app."""
        ThemeManager.set_theme(name)
        theme = ThemeManager.get_current_theme()
        new_css = get_theme_css(theme)

        # Find and replace the SantaiApp.CSS source in the stylesheet
        for key, css_source in self.app.stylesheet.source.items():
            if "SantaiApp" in str(key):
                self.app.stylesheet.source[key] = css_source._replace(content=new_css)
                break
        else:
            # Fallback: replace all non-default sources
            for key, css_source in self.app.stylesheet.source.items():
                if not css_source.is_defaults:
                    self.app.stylesheet.source[key] = css_source._replace(content=new_css)
                    break

        # Also update the class variable for consistency
        SantaiApp.CSS = new_css

        # Use Textual's built-in refresh_css which handles reparse + update + layout
        self.app.refresh_css()

        self._refresh_options()
        palette = ThemeManager.get_current_palette()
        self.app.notify(f"Theme: {theme.display_name} — {palette.display_name}")

    def action_select_theme_1(self) -> None:
        self._apply_theme("claude")

    def action_select_theme_2(self) -> None:
        self._apply_theme("catppuccin")

    def action_select_theme_3(self) -> None:
        self._apply_theme("btop")

    def action_select_theme_4(self) -> None:
        self._apply_theme("light")


# === Main App ===


class SantaiApp(App):
    """Santai TUI application."""

    TITLE = "Santai"
    CSS = get_theme_css()

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("g", "toggle_graph", "Graph"),
        Binding("t", "select_theme", "Theme"),
        Binding("n", "add_note", "Add Note"),
        Binding("p", "cycle_palette", "Palette"),
        Binding("escape", "back", "Back", show=True),
    ]

    def __init__(self, project: SantaiProject) -> None:
        # Set CSS class var to current theme before super().__init__
        SantaiApp.CSS = get_theme_css()
        super().__init__()
        self.project = project
        self.sub_title = project.name
        self._graph_fullscreen = False

    def compose(self) -> ComposeResult:
        yield Header()
        # Main dashboard layout - always present
        with Horizontal(id="main-layout"):
            with Vertical(id="tree-container"):
                yield Label(
                    f"[bold]Project: {self.project.name}[/bold]", id="tree-title"
                )
                yield FilteredDirectoryTree(self.project.root, id="tree")
            with Vertical(id="middle-container"):
                with Vertical(id="stats-container"):
                    yield StatsPanel(self.project)
                with Vertical(id="notes-container"):
                    yield NotesPanel(self.project)
            with Vertical(id="right-container"):
                with Vertical(id="graph-container"):
                    yield GraphPanel(self.project)
        # Fullscreen graph - hidden by default, scrollable
        with VerticalScroll(id="graph-fullscreen"):
            yield GraphPanel(self.project, fullscreen=True)
        yield Footer()

    def on_mount(self) -> None:
        """Set initial visibility."""
        # Hide fullscreen graph on startup
        self.query_one("#graph-fullscreen").display = False
        # Ensure graph panel is visible
        self.query_one("#graph-container").display = True

    def action_refresh(self) -> None:
        """Refresh all panels including directory tree."""
        for panel in self.query(StatsPanel):
            panel.refresh_stats()
        for panel in self.query(NotesPanel):
            panel.refresh_notes()
        for panel in self.query(GraphPanel):
            panel.refresh_graph()
        # Reload directory tree to reflect file changes
        for tree in self.query(FilteredDirectoryTree):
            tree.reload()
        self.notify("Refreshed all panels")

    def action_toggle_graph(self) -> None:
        """Toggle between panel view and fullscreen graph."""
        self._graph_fullscreen = not self._graph_fullscreen

        main_layout = self.query_one("#main-layout")
        graph_fs = self.query_one("#graph-fullscreen")

        if self._graph_fullscreen:
            main_layout.display = False
            graph_fs.display = True
            # Refresh the fullscreen graph panel
            for panel in graph_fs.query(GraphPanel):
                panel.refresh_graph()
            self.notify("Graph fullscreen — press g to exit")
        else:
            graph_fs.display = False
            main_layout.display = True
            self.notify("Dashboard view")

    def action_select_theme(self) -> None:
        """Open theme selector modal."""
        self.push_screen(ThemeSelectScreen())

    def action_cycle_palette(self) -> None:
        """Cycle to next palette within the current theme (p key)."""
        palette = ThemeManager.cycle_palette()
        new_css = get_theme_css()

        # Replace CSS in stylesheet
        for key, css_source in self.stylesheet.source.items():
            if "SantaiApp" in str(key):
                self.stylesheet.source[key] = css_source._replace(content=new_css)
                break
        else:
            for key, css_source in self.stylesheet.source.items():
                if not css_source.is_defaults:
                    self.stylesheet.source[key] = css_source._replace(content=new_css)
                    break

        SantaiApp.CSS = new_css
        self.refresh_css()
        theme = ThemeManager.get_current_theme()
        self.notify(f"{theme.display_name}: {palette.display_name} ({ThemeManager.get_palette_info()})")

    def action_add_note(self) -> None:
        """Open add note modal."""
        self.push_screen(AddNoteScreen(self.project))

    def on_clickable_note_clicked(self, event: ClickableNote.Clicked) -> None:
        """Handle click on a note — open note detail modal."""
        self.push_screen(NoteDetailScreen(event.note, project=self.project))

    def action_back(self) -> None:
        """Go back — exit fullscreen graph or do nothing on dashboard."""
        if self._graph_fullscreen:
            self.action_toggle_graph()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in data tables — open file preview for recent files."""
        # Check if this is the recent files table
        table = event.data_table
        if table.id == "recent-table":
            # Find the StatsPanel that owns this table
            for panel in self.query(StatsPanel):
                row_index = event.cursor_row
                if 0 <= row_index < len(panel._recent_files):
                    file_info = panel._recent_files[row_index]
                    if file_info.path.is_file():
                        self.push_screen(FilePreviewScreen(file_info.path, project=self.project))

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Handle file selection in directory tree — show file preview."""
        file_path = event.path
        if file_path.is_file():
            self.push_screen(FilePreviewScreen(file_path, project=self.project))
