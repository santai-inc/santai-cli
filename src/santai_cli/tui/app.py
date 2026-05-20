"""Textual TUI application for Santai."""

from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

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
    RichLog,
    Static,
    TextArea,
)

from santai_cli.core.project import (
    NoteEntry,
    SantaiProject,
    get_directory_stats,
    get_file_graph,
    get_notes,
)
from santai_cli.tui.graph_render import search_nodes as graph_search_nodes
from santai_cli.tui.themes import ThemeManager, get_theme_css


def format_size(size_bytes: int | float) -> str:
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

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter to only show santai dirs at root level."""
        return [
            p
            for p in paths
            if not p.name.startswith(".")  # Hide hidden files
        ]


class StatsPanel(Static):
    """Panel showing directory statistics (compact, placed under graph)."""

    def __init__(self, project: SantaiProject) -> None:
        super().__init__()
        self.project = project

    def compose(self) -> ComposeResult:
        yield Label("[bold]Directory Statistics[/bold]", id="stats-title")
        yield DataTable(id="dir-stats-table")
        yield Label("")
        yield Label("[bold]File Types[/bold]", id="types-title")
        yield DataTable(id="types-table")

    def on_mount(self) -> None:
        """Populate tables with data."""
        self.refresh_stats()

    def refresh_stats(self) -> None:
        """Refresh statistics data."""
        stats = get_directory_stats(self.project)

        # Directory stats table
        dir_table = self.query_one("#dir-stats-table", DataTable)
        dir_table.clear(columns=True)
        dir_table.add_columns("Directory", "Files")
        dir_table.add_row("resources", str(stats.resources_count))
        dir_table.add_row("codebases", str(stats.codebases_count))
        dir_table.add_row("history", str(stats.history_count))
        dir_table.add_row("notes", str(stats.notes_count))
        dir_table.add_row("wiki", str(stats.wiki_count))
        dir_table.add_row(
            "[bold]Total[/bold]",
            f"[bold]{
                stats.resources_count
                + stats.codebases_count
                + stats.history_count
                + stats.notes_count
                + stats.wiki_count
            }[/bold]",
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


class RecentFilesPanel(Static):
    """Panel showing recent files with clickable rows."""

    def __init__(self, project: SantaiProject) -> None:
        super().__init__()
        self.project = project
        self._recent_files: list = []

    def compose(self) -> ComposeResult:
        yield Label(
            "[bold]Recent Files[/bold] [dim](click to open)[/dim]", id="recent-title"
        )
        yield DataTable(id="recent-table", cursor_type="row")

    def on_mount(self) -> None:
        """Populate recent files."""
        self.refresh_recent()

    def refresh_recent(self) -> None:
        """Refresh recent files data."""
        stats = get_directory_stats(self.project)
        self._recent_files = stats.recent_files[:8]

        recent_table = self.query_one("#recent-table", DataTable)
        recent_table.clear(columns=True)
        recent_table.add_columns("File", "Directory", "Modified")
        for file_info in self._recent_files:
            # Derive directory from file path relative to project root
            try:
                rel = file_info.path.relative_to(self.project.root)
                directory = rel.parts[0] if rel.parts else "unknown"
            except ValueError:
                directory = "unknown"
            recent_table.add_row(
                file_info.name,
                directory,
                format_time_ago(file_info.modified_at),
            )
        if not self._recent_files:
            recent_table.add_row("[dim]No files yet[/dim]", "", "")


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
        "wiki": "#f5c542",  # gold
        "unassigned": "#9b9ba8",  # muted blue-gray for root-level files
        "other": "#6b6560",  # warm gray fallback
    }

    # Matches the web UI _extraDirPalette — same order so the same dir gets
    # the same color in both surfaces.
    _EXTRA_PALETTE = [
        "#f97316",  # orange
        "#22d3ee",  # cyan
        "#d946ef",  # fuchsia
        "#84cc16",  # lime
        "#0f766e",  # dark teal
        "#fb923c",  # peach-orange
        "#a21caf",  # deep magenta
        "#0e7490",  # dark cyan
    ]

    @classmethod
    def get_dir_color(cls, dir_name: str) -> str:
        """Return a stable color for any directory name."""
        if dir_name in cls.DIR_COLORS:
            return cls.DIR_COLORS[dir_name]
        # Replicate the web UI's Math.imul(31, h) polynomial hash so the same
        # directory gets the same palette index (and therefore the same color)
        # on both surfaces.
        h = 0
        for c in dir_name:
            h_u32 = int(h) & 0xFFFFFFFF
            prod = (31 * h_u32) & 0xFFFFFFFF
            imul = prod if prod < 0x80000000 else prod - 0x100000000
            h = imul + ord(c)
        idx = abs(int(h)) % len(cls._EXTRA_PALETTE)
        return cls._EXTRA_PALETTE[idx]

    def __init__(self, project: SantaiProject, fullscreen: bool = False) -> None:
        super().__init__()
        self.project = project
        self.fullscreen = fullscreen
        self._selected_id: str | None = None
        self._highlight_ids: set[str] | None = None
        self._search_query: str = ""
        self._filter_dirs: set[str] | None = None  # None = show all

    def compose(self) -> ComposeResult:
        title = (
            "[bold]File Graph[/bold] [dim](g=exit  /=search  f=filter)[/dim]"
            if self.fullscreen
            else "[bold]File Graph[/bold]"
        )
        yield Label(title, id="graph-title")
        yield Static(id="graph-content")

    def on_mount(self) -> None:
        """Populate graph view."""
        self.refresh_graph()

    def set_search(
        self,
        query: str,
        selected_id: str | None = None,
        highlight_ids: set[str] | None = None,
    ) -> None:
        """Set search state and re-render."""
        self._search_query = query
        self._selected_id = selected_id
        self._highlight_ids = highlight_ids
        self.refresh_graph()

    def set_filter(self, filter_dirs: set[str] | None) -> None:
        """Set directory filter and re-render. None = show all."""
        self._filter_dirs = filter_dirs
        self.refresh_graph()

    def clear_filter(self) -> None:
        """Clear directory filter."""
        self._filter_dirs = None
        self.refresh_graph()

    def clear_search(self) -> None:
        """Clear search highlighting."""
        self._search_query = ""
        self._selected_id = None
        self._highlight_ids = None
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
            self._node_positions = {}
            self._render_width = 0
            self._render_height = 0
            self._graph_line_offset = 0
            return

        nodes, edges = build_graph_from_project_data(graph_data)

        # Apply directory filter
        if self._filter_dirs is not None:
            filtered_node_ids = {
                n.id for n in nodes if n.directory in self._filter_dirs
            }
            nodes = [n for n in nodes if n.id in filtered_node_ids]
            edges = [
                e
                for e in edges
                if e.source in filtered_node_ids and e.target in filtered_node_ids
            ]

        if not nodes:
            content_widget.update("[dim]No files match the current filter.[/dim]")
            self._node_positions = {}
            self._render_width = 0
            self._render_height = 0
            self._graph_line_offset = 0
            return

        # Determine render dimensions based on mode
        if self.fullscreen:
            render_width = 100
            render_height = 36
        else:
            render_width = 44
            render_height = 18

        self._render_width = render_width
        self._render_height = render_height

        # Build a complete color map for every directory present in the graph
        all_dirs = {n.directory for n in nodes}
        dynamic_dir_colors = {d: self.get_dir_color(d) for d in all_dirs}
        dynamic_dir_colors["other"] = self.DIR_COLORS["other"]

        # Render the force-directed graph
        result = render_graph(
            nodes=nodes,
            edges=edges,
            width=render_width,
            height=render_height,
            dir_colors=dynamic_dir_colors,
            selected_id=self._selected_id,
            highlight_ids=self._highlight_ids,
            show_labels=True,
            fullscreen=self.fullscreen,
        )

        # Store node positions for click detection
        self._node_positions = result.node_positions
        self._node_map = result.node_map

        # Build output — legend and stats come FIRST so they are never clipped
        # by the container height in the non-scrollable panel view.
        lines = []

        # Legend: reflect exactly what is rendered (uses `nodes`, not graph_data)
        dirs_present = {n.directory for n in nodes}
        known_order = ["resources", "codebases", "history", "notes", "wiki"]
        legend_parts = []
        for dir_name in known_order:
            if dir_name in dirs_present:
                color = self.get_dir_color(dir_name)
                label = dir_name[:12] + "…" if len(dir_name) > 13 else dir_name
                legend_parts.append(f"[{color}]●[/{color}] {label}")
        for dir_name in sorted(
            dirs_present - set(known_order) - {"unassigned", "other"}
        ):
            color = self.get_dir_color(dir_name)
            label = dir_name[:12] + "…" if len(dir_name) > 13 else dir_name
            legend_parts.append(f"[{color}]●[/{color}] {label}")
        if "unassigned" in dirs_present:
            color = self.get_dir_color("unassigned")
            legend_parts.append(f"[{color}]●[/{color}] unassigned")
        lines.append(" ".join(legend_parts))

        # Stats header with search/filter indicators
        total_nodes = len(graph_data.nodes)
        shown_nodes = len(nodes)
        total_edges = len(graph_data.edges)
        shown_edges = len(edges)

        if self._filter_dirs is not None and shown_nodes != total_nodes:
            stats_line = (
                f"[bold]Nodes:[/bold] {shown_nodes}/{total_nodes}  "
                f"[bold]Edges:[/bold] {shown_edges}/{total_edges}"
            )
            filter_names = ", ".join(sorted(self._filter_dirs))
            stats_line += f"  [bold cyan]Filter:[/bold cyan] {filter_names}"
        else:
            stats_line = (
                f"[bold]Nodes:[/bold] {total_nodes}  [bold]Edges:[/bold] {total_edges}"
            )
        if self._search_query:
            match_count = len(self._highlight_ids) if self._highlight_ids else 0
            suffix = "es" if match_count != 1 else ""
            stats_line += (
                f"  [bold yellow]Search:[/bold yellow]"
                f' "{self._search_query}"'
                f" ({match_count} match{suffix})"
            )
        lines.append(stats_line)
        lines.append("")

        # Track where the graph visualization starts (line offset for click mapping)
        self._graph_line_offset = len(lines)

        # The graph visualization
        lines.append(result.markup)

        if graph_data.edges:
            lines.append(
                "\n[dim]⬢ hub (5+)  ◆ connected (3+)  ● node"
                "  ◈ match  ◉ selected  c=clear[/dim]"
            )

        content_widget.update("\n".join(lines))

    def on_click(self, event) -> None:
        """Handle click on graph — find nearest node and open file."""
        if not hasattr(self, "_node_positions") or not self._node_positions:
            return

        # Get click position relative to the graph content widget
        content_widget = self.query_one("#graph-content", Static)
        # Calculate offset: the content widget's position within the panel
        try:
            content_region = content_widget.region
            # Click coordinates relative to the content widget
            click_x = event.x - content_region.x
            click_y = event.y - content_region.y
        except Exception:
            return

        # Adjust for the graph line offset (stats header lines above the graph)
        graph_y = click_y - self._graph_line_offset
        graph_x = click_x

        if graph_y < 0 or graph_y >= self._render_height:
            return

        # Find the nearest node within a reasonable click radius
        best_node_id = None
        best_dist = float("inf")
        click_radius = 3.0  # max distance in character cells to register a click

        for node_id, (nx, ny) in self._node_positions.items():
            dx = graph_x - nx
            dy = graph_y - ny
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < best_dist and dist <= click_radius:
                best_dist = dist
                best_node_id = node_id

        if best_node_id is None:
            return

        # node_id is the file path relative to project root (e.g., "notes/my-note.md")
        file_path = self.project.root / best_node_id
        if not file_path.is_file():
            return

        # Determine if it's a note
        node = self._node_map.get(best_node_id)
        is_note = (
            node and node.directory == "notes" and file_path.suffix in (".md", ".txt")
        )

        if is_note:
            from santai_cli.core.project import NoteEntry

            try:
                content = file_path.read_text(encoding="utf-8")
                title = file_path.stem.replace("-", " ").replace("_", " ").title()
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                preview = content[:200].replace("\n", " ").strip()
                stat = file_path.stat()
                note_entry = NoteEntry(
                    title=title,
                    content=content,
                    preview=preview,
                    filename=file_path.name,
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                    size_bytes=stat.st_size,
                )
                self.app.push_screen(NoteDetailScreen(note_entry, project=self.project))
            except (OSError, UnicodeDecodeError):
                self.app.push_screen(FilePreviewScreen(file_path, project=self.project))
        else:
            self.app.push_screen(FilePreviewScreen(file_path, project=self.project))


# === Modal Screens ===


class ConfirmScreen(ModalScreen):
    """Generic confirmation dialog."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
        Binding("y", "confirm", "Yes"),
        Binding("n", "dismiss", "No"),
    ]

    def __init__(self, message: str, on_confirm: Callable[[], Any]) -> None:
        super().__init__()
        self._message = message
        self._on_confirm = on_confirm

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-modal"), Vertical(id="theme-modal-content"):
            yield Label("[bold]Confirm[/bold]", id="theme-modal-title")
            yield Static(id="confirm-body")

    def on_mount(self) -> None:
        body = self.query_one("#confirm-body", Static)
        body.update(
            f"{self._message}\n\n[bold]y[/bold] = Yes  |  [bold]n[/bold] / Esc = Cancel"
        )

    def action_confirm(self) -> None:
        self._on_confirm()
        self.dismiss()


def _reload_all_panels(app: App) -> None:
    """Reload all panels and directory tree in the app."""
    for panel in app.query(StatsPanel):
        panel.refresh_stats()
    for panel in app.query(RecentFilesPanel):
        panel.refresh_recent()
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
        Binding("5", "move_5", "wiki"),
    ]

    DIRS = ["resources", "codebases", "history", "notes", "wiki"]

    def __init__(self, file_path: Path, project: SantaiProject) -> None:
        super().__init__()
        self._file_path = file_path
        self._project = project

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-modal"), Vertical(id="theme-modal-content"):
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
        lines.append("[dim]Press 1-5 to move, Esc to cancel[/dim]")
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

    def action_move_5(self) -> None:
        self._move_to("wiki")


class NoteDetailScreen(ModalScreen):
    """Modal showing a single note's full content."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("e", "edit_note", "Edit"),
        Binding("d", "delete_note", "Delete"),
        Binding("m", "move_note", "Move"),
    ]

    def __init__(self, note, project: SantaiProject | None = None) -> None:
        super().__init__()
        self._note = note
        self._project = project

    def compose(self) -> ComposeResult:
        with Vertical(id="notes-modal"), VerticalScroll(id="notes-modal-content"):
            yield Label(
                f"[bold]📄 {self._note.title}[/bold]",
                id="notes-modal-title",
            )
            yield Static(id="notes-modal-body")

    def on_click(self, event) -> None:
        """Dismiss when clicking the dimmed area outside the modal panel."""
        if event.widget is self:
            self.dismiss()

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
        content = (
            self._note.content[:5000]
            if len(self._note.content) > 5000
            else self._note.content
        )
        lines.append(content)
        if len(self._note.content) > 5000:
            lines.append("")
            lines.append("[dim]... (truncated)[/dim]")
        lines.append("")
        lines.append("[dim]e = edit · d = delete · m = move · Esc = close[/dim]")

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

    def action_edit_note(self) -> None:
        """Open note in edit mode."""
        note_path = self._find_note_path()
        if not note_path:
            self.app.notify("Cannot find note file", severity="error")
            return
        project = self._project or self._get_project()
        if not project:
            self.app.notify("Cannot determine project", severity="error")
            return
        edit_screen = EditNoteScreen(note_path, self._note, project)
        self.dismiss()
        self.app.call_later(lambda: self.app.push_screen(edit_screen))

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
            project = self.app.project  # type: ignore[attr-defined]
            if isinstance(project, SantaiProject):
                return project
        return None


class EditNoteScreen(ModalScreen):
    """Modal for editing an existing note's content."""

    BINDINGS = [
        Binding("escape", "dismiss_edit", "Close"),
    ]

    def __init__(self, file_path: Path, note, project: SantaiProject) -> None:
        super().__init__()
        self._file_path = file_path
        self._note = note
        self._project = project
        self._original_content: str = ""
        self._has_changes: bool = False

    def compose(self) -> ComposeResult:
        with Vertical(id="edit-note-modal"), Vertical(id="edit-note-content"):
            yield Label(
                f"[bold]✏️  Editing: {self._note.title}[/bold]",
                id="edit-note-title",
            )
            yield Static(
                f"[dim]{self._file_path.name}[/dim]",
                id="edit-note-path",
            )
            yield TextArea(id="edit-note-textarea")
            yield Static(
                "[dim]Ctrl+S = save · Esc = close (unsaved changes will prompt)[/dim]",
                id="edit-note-help",
            )

    def on_mount(self) -> None:
        """Load file content into the editor."""
        textarea = self.query_one("#edit-note-textarea", TextArea)
        try:
            content = self._file_path.read_text(encoding="utf-8")
            self._original_content = content
            textarea.load_text(content)
        except (OSError, UnicodeDecodeError) as e:
            self.app.notify(f"Error reading file: {e}", severity="error")
            self.dismiss()
            return
        textarea.focus()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Track whether content has been modified."""
        if event.text_area.id == "edit-note-textarea":
            self._has_changes = event.text_area.text != self._original_content

    def key_ctrl_s(self) -> None:
        """Save the note."""
        self._save()

    def _save(self) -> None:
        """Write content back to file."""
        textarea = self.query_one("#edit-note-textarea", TextArea)
        content = textarea.text

        try:
            self._file_path.write_text(content, encoding="utf-8")
            self._original_content = content
            self._has_changes = False
            self.app.notify(f"Saved: {self._file_path.name}")
            _reload_all_panels(self.app)
        except OSError as e:
            self.app.notify(f"Error saving: {e}", severity="error")

    def action_dismiss_edit(self) -> None:
        """Dismiss with unsaved changes check."""
        if self._has_changes:
            self.app.push_screen(
                ConfirmScreen(
                    "You have unsaved changes.\n\nDiscard changes?",
                    lambda: self.dismiss(),
                )
            )
        else:
            self.dismiss()


class AddNoteScreen(ModalScreen):
    """Modal for creating a new note."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    def __init__(self, project: SantaiProject) -> None:
        super().__init__()
        self.project = project

    def compose(self) -> ComposeResult:
        with Vertical(id="notes-modal"), Vertical(id="notes-modal-content"):
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


class EditFileScreen(ModalScreen):
    """Modal for editing any text file's content."""

    BINDINGS = [
        Binding("escape", "dismiss_edit", "Close"),
    ]

    def __init__(self, file_path: Path, project: SantaiProject) -> None:
        super().__init__()
        self._file_path = file_path
        self._project = project
        self._original_content: str = ""
        self._has_changes: bool = False

    def compose(self) -> ComposeResult:
        with Vertical(id="edit-note-modal"), Vertical(id="edit-note-content"):
            yield Label(
                f"[bold]✏️  Editing: {self._file_path.name}[/bold]",
                id="edit-note-title",
            )
            yield Static(
                f"[dim]{self._file_path}[/dim]",
                id="edit-note-path",
            )
            yield TextArea(id="edit-file-textarea")
            yield Static(
                "[dim]Ctrl+S = save · Esc = close (unsaved changes will prompt)[/dim]",
                id="edit-note-help",
            )

    def on_mount(self) -> None:
        """Load file content into the editor."""
        textarea = self.query_one("#edit-file-textarea", TextArea)
        try:
            content = self._file_path.read_text(encoding="utf-8")
            self._original_content = content
            textarea.load_text(content)
        except (OSError, UnicodeDecodeError) as e:
            self.app.notify(f"Error reading file: {e}", severity="error")
            self.dismiss()
            return
        textarea.focus()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Track whether content has been modified."""
        if event.text_area.id == "edit-file-textarea":
            self._has_changes = event.text_area.text != self._original_content

    def key_ctrl_s(self) -> None:
        """Save the file."""
        self._save()

    def _save(self) -> None:
        """Write content back to file."""
        textarea = self.query_one("#edit-file-textarea", TextArea)
        content = textarea.text

        try:
            self._file_path.write_text(content, encoding="utf-8")
            self._original_content = content
            self._has_changes = False
            self.app.notify(f"Saved: {self._file_path.name}")
            _reload_all_panels(self.app)
        except OSError as e:
            self.app.notify(f"Error saving: {e}", severity="error")

    def action_dismiss_edit(self) -> None:
        """Dismiss with unsaved changes check."""
        if self._has_changes:
            self.app.push_screen(
                ConfirmScreen(
                    "You have unsaved changes.\n\nDiscard changes?",
                    lambda: self.dismiss(),
                )
            )
        else:
            self.dismiss()


class FilePreviewScreen(ModalScreen):
    """File preview modal for viewing file contents."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("e", "edit_file", "Edit"),
        Binding("d", "delete_file", "Delete"),
        Binding("m", "move_file", "Move"),
    ]

    def __init__(self, file_path: Path, project: SantaiProject | None = None) -> None:
        super().__init__()
        self.file_path = file_path
        self._project = project
        self._is_text_file: bool = False

    def compose(self) -> ComposeResult:
        with (
            Vertical(id="file-preview-modal"),
            VerticalScroll(id="file-preview-content"),
        ):
            yield Label(
                f"[bold]{self.file_path.name}[/bold]",
                id="file-preview-title",
            )
            yield Static(id="file-preview-body")

    def on_click(self, event) -> None:
        """Dismiss when clicking the dimmed area outside the modal panel."""
        if event.widget is self:
            self.dismiss()

    def on_mount(self) -> None:
        """Load file content."""
        body = self.query_one("#file-preview-body", Static)
        try:
            content = self.file_path.read_text(encoding="utf-8")
            self._is_text_file = True
            if len(content) > 5000:
                content = content[:5000] + "\n\n[dim]... (truncated)[/dim]"
            content += "\n\n[dim]e = edit · d = delete · m = move · Esc = close[/dim]"
            body.update(content)
        except UnicodeDecodeError:
            self._is_text_file = False
            body.update(
                f"[dim]Binary file: "
                f"{format_size(self.file_path.stat().st_size)}"
                f"[/dim]\n\n"
                f"[dim]d = delete · m = move"
                f" · Esc = close[/dim]"
            )
        except OSError as e:
            body.update(f"[dim]Error reading file: {e}[/dim]")

    def _get_project(self) -> SantaiProject | None:
        if self._project:
            return self._project
        if hasattr(self.app, "project"):
            project = self.app.project  # type: ignore[attr-defined]
            if isinstance(project, SantaiProject):
                return project
        return None

    def action_edit_file(self) -> None:
        """Open file in edit mode."""
        if not self._is_text_file:
            self.app.notify("Cannot edit binary files", severity="warning")
            return
        if not self.file_path.is_file():
            self.app.notify("File not found", severity="error")
            return
        project = self._get_project()
        if not project:
            self.app.notify("Cannot determine project", severity="error")
            return
        edit_screen = EditFileScreen(self.file_path, project)
        self.dismiss()
        self.app.call_later(lambda: self.app.push_screen(edit_screen))

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
        ThemeManager.get_current_theme()
        with Vertical(id="theme-modal"), Vertical(id="theme-modal-content"):
            yield Label(
                "[bold]Theme Selector (press Esc to close)[/bold]",
                id="theme-modal-title",
            )
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
                    self.app.stylesheet.source[key] = css_source._replace(
                        content=new_css
                    )
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


# === Graph Search ===


class GraphSearchScreen(ModalScreen):
    """Modal for searching graph nodes with live results."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    def __init__(self, project: SantaiProject) -> None:
        super().__init__()
        self._project = project
        self._results: list = []
        self._selected_index: int = 0
        self._all_nodes: list = []

    def compose(self) -> ComposeResult:
        with Vertical(id="graph-search-modal"), Vertical(id="graph-search-content"):
            yield Label(
                "[bold]🔍 Graph Search[/bold]"
                " [dim](↑↓ select, Enter=open,"
                " Ctrl+H=highlight in graph, Esc=close)[/dim]",
                id="graph-search-title",
            )
            yield Input(
                placeholder="Search files...",
                id="graph-search-input",
            )
            yield Static(id="graph-search-results")

    def on_mount(self) -> None:
        """Focus the search input and load nodes."""
        from santai_cli.tui.graph_render import build_graph_from_project_data

        graph_data = get_file_graph(self._project)
        nodes, _ = build_graph_from_project_data(graph_data)
        self._all_nodes = nodes

        self.query_one("#graph-search-input", Input).focus()
        self._update_results("")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes — live filtering."""
        if event.input.id == "graph-search-input":
            self._selected_index = 0
            self._update_results(event.value)

    def key_down(self) -> None:
        """Move selection down."""
        if self._results:
            self._selected_index = min(self._selected_index + 1, len(self._results) - 1)
            self._render_results()

    def key_up(self) -> None:
        """Move selection up."""
        if self._results:
            self._selected_index = max(self._selected_index - 1, 0)
            self._render_results()

    def key_enter(self) -> None:
        """Open the selected file."""
        if not self._results:
            return

        selected = self._results[self._selected_index]
        file_path = self._project.root / selected.id

        if not file_path.is_file():
            self.app.notify(f"File not found: {selected.id}", severity="error")
            return

        self.dismiss()

        # Open note detail for notes, file preview for others
        is_note = selected.directory == "notes" and file_path.suffix in (".md", ".txt")
        if is_note:
            from santai_cli.core.project import NoteEntry

            try:
                content = file_path.read_text(encoding="utf-8")
                title = file_path.stem.replace("-", " ").replace("_", " ").title()
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                preview = content[:200].replace("\n", " ").strip()
                stat = file_path.stat()
                note_entry = NoteEntry(
                    title=title,
                    content=content,
                    preview=preview,
                    filename=file_path.name,
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                    size_bytes=stat.st_size,
                )
                self.app.push_screen(
                    NoteDetailScreen(note_entry, project=self._project)
                )
            except (OSError, UnicodeDecodeError):
                self.app.push_screen(
                    FilePreviewScreen(file_path, project=self._project)
                )
        else:
            self.app.push_screen(FilePreviewScreen(file_path, project=self._project))

    def key_ctrl_h(self) -> None:
        """Highlight the selected result in the graph (without opening)."""
        if not self._results:
            return

        selected = self._results[self._selected_index]
        query = self.query_one("#graph-search-input", Input).value.strip()

        # Build highlight set from all results
        highlight_ids = {node.id for node in self._results}

        # Apply search to all graph panels
        for panel in self.app.query(GraphPanel):
            panel.set_search(
                query=query,
                selected_id=selected.id,
                highlight_ids=highlight_ids,
            )

        self.app.notify(f"Highlighted: {selected.label} ({selected.directory}/)")
        self.dismiss()

    def _update_results(self, query: str) -> None:
        """Update search results based on query."""
        query = query.strip()
        if query:
            self._results = graph_search_nodes(self._all_nodes, query, max_results=15)
        else:
            # Show all nodes sorted by label when no query
            self._results = sorted(self._all_nodes, key=lambda n: n.label.lower())[:15]
        self._render_results()

    def _render_results(self) -> None:
        """Render the results list with selection highlight."""
        results_widget = self.query_one("#graph-search-results", Static)

        if not self._results:
            query = self.query_one("#graph-search-input", Input).value.strip()
            if query:
                results_widget.update("[dim]No matches found[/dim]")
            else:
                results_widget.update("[dim]No files in project[/dim]")
            return

        lines = []
        for i, node in enumerate(self._results):
            color = GraphPanel.get_dir_color(node.directory)
            is_selected = i == self._selected_index

            # Selection indicator
            if is_selected:
                prefix = "[bold white on #333333] ▸ [/bold white on #333333]"
                name_style = f"bold {color}"
                path_style = "white on #333333"
                line_end = ""
            else:
                prefix = "   "
                name_style = color
                path_style = "dim"
                line_end = ""

            # Degree info
            degree_str = f" ({node.degree} links)" if node.degree > 0 else ""

            line = (
                f"{prefix}"
                f"[{name_style}]{node.label}[/{name_style}]"
                f"[{path_style}]  {node.directory}/{degree_str}[/{path_style}]"
                f"{line_end}"
            )
            lines.append(line)

        # Footer info
        total = len(self._all_nodes)
        showing = len(self._results)
        lines.append("")
        lines.append(
            f"[dim]{showing} of {total} files"
            " · Enter=open · Ctrl+H=highlight"
            " · Esc=cancel[/dim]"
        )

        results_widget.update("\n".join(lines))


# === Graph Filter ===


class GraphFilterScreen(ModalScreen):
    """Modal for filtering graph nodes by directory type."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("1", "toggle_1", "resources"),
        Binding("2", "toggle_2", "codebases"),
        Binding("3", "toggle_3", "history"),
        Binding("4", "toggle_4", "notes"),
        Binding("5", "toggle_5", "wiki"),
        Binding("6", "toggle_6", "dir 6", show=False),
        Binding("7", "toggle_7", "dir 7", show=False),
        Binding("8", "toggle_8", "dir 8", show=False),
        Binding("9", "toggle_9", "dir 9", show=False),
        Binding("a", "select_all", "All"),
        Binding("x", "clear_all", "None"),
    ]

    DIRS = ["resources", "codebases", "history", "notes", "wiki"]

    def __init__(
        self, project: SantaiProject, current_filter: set[str] | None = None
    ) -> None:
        super().__init__()
        self._project = project
        self._no_initial_filter = current_filter is None
        # Temporary default; on_mount will expand to all available dirs if no filter
        self._selected: set[str] = (
            set(current_filter) if current_filter else set(self.DIRS)
        )
        self._available_dirs: set[str] = set()

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-modal"), Vertical(id="theme-modal-content"):
            yield Label(
                "[bold]🔍 Graph Filter[/bold]",
                id="theme-modal-title",
            )
            yield Static(id="filter-body")

    def on_mount(self) -> None:
        """Detect available directories and render."""
        from santai_cli.tui.graph_render import build_graph_from_project_data

        graph_data = get_file_graph(self._project)
        nodes, _ = build_graph_from_project_data(graph_data)
        self._available_dirs = {n.directory for n in nodes}
        # Count files per directory
        self._dir_counts: dict[str, int] = {}
        for n in nodes:
            self._dir_counts[n.directory] = self._dir_counts.get(n.directory, 0) + 1
        # When no filter was active, select everything (including dynamic dirs)
        if self._no_initial_filter:
            self._selected = set(self._available_dirs)
        self._update_display()

    def _update_display(self) -> None:
        body = self.query_one("#filter-body", Static)

        lines = []
        lines.append("")
        lines.append("Toggle directories to show/hide in the graph:")
        lines.append("")

        for i, d in enumerate(self.DIRS, 1):
            color = GraphPanel.get_dir_color(d)
            count = self._dir_counts.get(d, 0)
            is_on = d in self._selected
            available = d in self._available_dirs

            if not available:
                checkbox = "[dim]  ○[/dim]"
                label = f"[dim]{d}/ (empty)[/dim]"
            elif is_on:
                checkbox = f"[{color}]  ●[/{color}]"
                label = f"[bold {color}]{d}/[/bold {color}] [dim]({count} files)[/dim]"
            else:
                checkbox = "  ○"
                label = f"[dim]{d}/ ({count} files)[/dim]"

            lines.append(f"  [{i}]{checkbox} {label}")

        # Dynamic dirs: alphabetically, with "unassigned" at the end
        # Keys 6-9 are assigned to the first 4 extra dirs in order
        extra_dirs = sorted(self._available_dirs - set(self.DIRS) - {"unassigned"})
        all_extra = extra_dirs + (
            ["unassigned"] if "unassigned" in self._available_dirs else []
        )
        for idx, d in enumerate(all_extra):
            key_hint = f"[{idx + 6}]" if idx < 4 else "   "
            color = GraphPanel.get_dir_color(d)
            count = self._dir_counts.get(d, 0)
            is_on = d in self._selected
            if is_on:
                checkbox = f"[{color}]  ●[/{color}]"
                label = f"[bold {color}]{d}/[/bold {color}] [dim]({count} files)[/dim]"
            else:
                checkbox = "  ○"
                label = f"[dim]{d}/ ({count} files)[/dim]"
            lines.append(f"  {key_hint}{checkbox} {label}")

        lines.append("")

        selected_count = sum(
            self._dir_counts.get(d, 0)
            for d in self._selected
            if d in self._available_dirs
        )
        total_count = sum(self._dir_counts.values())
        lines.append(f"  Showing: [bold]{selected_count}[/bold] of {total_count} files")
        lines.append("")
        extra_key_hint = " · 6-9 = extra dirs" if all_extra else ""
        lines.append(
            f"  [dim]1-5 = toggle directory{extra_key_hint} · a = all · x = none[/dim]"
        )
        lines.append("  [dim]Enter = apply · Esc = cancel[/dim]")

        body.update("\n".join(lines))

    def _toggle_dir(self, dir_name: str) -> None:
        if dir_name in self._selected:
            self._selected.discard(dir_name)
        else:
            self._selected.add(dir_name)
        self._update_display()

    def action_toggle_1(self) -> None:
        self._toggle_dir("resources")

    def action_toggle_2(self) -> None:
        self._toggle_dir("codebases")

    def action_toggle_3(self) -> None:
        self._toggle_dir("history")

    def action_toggle_4(self) -> None:
        self._toggle_dir("notes")

    def action_toggle_5(self) -> None:
        self._toggle_dir("wiki")

    def _toggle_extra_dir(self, idx: int) -> None:
        extra_dirs = sorted(self._available_dirs - set(self.DIRS) - {"unassigned"})
        all_extra = extra_dirs + (
            ["unassigned"] if "unassigned" in self._available_dirs else []
        )
        if 0 <= idx < len(all_extra):
            self._toggle_dir(all_extra[idx])

    def action_toggle_6(self) -> None:
        self._toggle_extra_dir(0)

    def action_toggle_7(self) -> None:
        self._toggle_extra_dir(1)

    def action_toggle_8(self) -> None:
        self._toggle_extra_dir(2)

    def action_toggle_9(self) -> None:
        self._toggle_extra_dir(3)

    def action_select_all(self) -> None:
        self._selected = set(self.DIRS) | self._available_dirs
        self._update_display()

    def action_clear_all(self) -> None:
        self._selected.clear()
        self._update_display()

    def key_enter(self) -> None:
        """Apply the filter."""
        # Compare against available dirs only — standard dirs with no files
        # are irrelevant and would prevent this check from ever being True.
        if not self._selected or self._selected >= self._available_dirs:
            filter_dirs = None
        else:
            filter_dirs = set(self._selected)

        for panel in self.app.query(GraphPanel):
            panel.set_filter(filter_dirs)

        if filter_dirs:
            names = ", ".join(sorted(filter_dirs))
            self.app.notify(f"Filter: {names}")
        else:
            self.app.notify("Filter cleared — showing all")

        self.dismiss()


# === Chat Screen ===


class ChatScreen(ModalScreen):
    """Modal screen for AI chat within the TUI dashboard."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    ChatScreen {
        align: center middle;
    }
    #chat-modal {
        width: 90%;
        height: 90%;
        border: thick $primary;
        background: $surface;
    }
    #chat-modal-header {
        dock: top;
        height: 3;
        padding: 0 2;
        background: $primary;
        color: $text;
    }
    #chat-log {
        height: 1fr;
        padding: 1 2;
        scrollbar-size-vertical: 1;
    }
    #chat-input-bar {
        dock: bottom;
        height: 3;
        padding: 0 1;
    }
    #chat-input {
        width: 1fr;
    }
    #chat-status {
        dock: bottom;
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    """

    def __init__(self, project: SantaiProject) -> None:
        super().__init__()
        self.project = project
        self._provider: str | None = None
        self._model: str | None = None
        self._agent: str | None = None
        self._session: Any = None
        self._config: Any = None
        self._streaming = False

    def compose(self) -> ComposeResult:
        with Vertical(id="chat-modal"):
            yield Label(
                "[bold]Santai Chat[/bold] — press Escape to close",
                id="chat-modal-header",
            )
            yield RichLog(id="chat-log", wrap=True, highlight=True, markup=True)
            yield Label("", id="chat-status")
            with Horizontal(id="chat-input-bar"):
                yield Input(
                    placeholder="Type a message... (/help for commands)",
                    id="chat-input",
                )

    def on_mount(self) -> None:
        """Initialize chat configuration."""
        from santai_cli.core.config import load_config

        log = self.query_one("#chat-log", RichLog)
        status = self.query_one("#chat-status", Label)

        self._config = load_config(self.project.root)

        if not self._config.has_any_provider:
            log.write(
                "[bold red]No API keys configured.[/]\n\n"
                "Create a .env file in your project root with at least one key:\n"
                "  ANTHROPIC_API_KEY=sk-ant-...\n"
                "  OPENAI_API_KEY=sk-...\n\n"
                "See .env.example for the full template."
            )
            status.update("No providers configured")
            return

        # Auto-select first available model
        choices = self._config.get_model_choices()
        if choices:
            _, self._provider, self._model = choices[0]
            provider_name = self._config.providers[self._provider].name
            status.update(
                f"Provider: {provider_name} | Model: {self._model} | /help for commands"
            )

            # Show model selection prompt
            log.write("[bold cyan]Welcome to Santai Chat![/]\n")
            log.write(f"[dim]Using {provider_name}: {self._model}[/]")
            if len(choices) > 1:
                log.write("[dim]Type /model to switch models.[/]")
            log.write("[dim]Type /help for all commands.[/]\n")

        # Initialize session
        from santai_cli.core.chat import ChatSession

        self._session = ChatSession()

        # Focus the input
        self.query_one("#chat-input", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        if event.input.id != "chat-input":
            return

        user_text = event.value.strip()
        if not user_text:
            return

        event.input.value = ""
        log = self.query_one("#chat-log", RichLog)

        if self._session is None or self._config is None:
            log.write("[red]Chat not initialized. Check your .env configuration.[/]")
            return

        # Handle slash commands
        if user_text.startswith("/"):
            self._handle_chat_command(user_text)
            return

        if self._provider is None or self._model is None:
            log.write("[red]No model selected. Type /model to select one.[/]")
            return

        if self._streaming:
            log.write("[dim]Please wait for the current response to finish.[/]")
            return

        # Show user message
        log.write(f"\n[bold green]You:[/] {user_text}")

        # Get streaming response
        self._session.add_user_message(user_text)
        self._streaming = True
        status = self.query_one("#chat-status", Label)
        status.update("Generating response...")

        try:
            from santai_cli.core.chat import stream_response

            provider_config = self._config.providers[self._provider]
            full_text = ""

            log.write("[bold cyan]Assistant:[/]")

            async for chunk in stream_response(
                self._session, self._provider, provider_config, self._model
            ):
                full_text += chunk
                # RichLog doesn't support in-place updates easily,
                # so we write chunks as they arrive
                log.write(chunk, scroll_end=True)

            log.write("")  # Blank line after response
            self._session.add_assistant_message(full_text)

            provider_name = self._config.providers[self._provider].name
            status.update(
                f"Provider: {provider_name} | Model: {self._model} | /help for commands"
            )

        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "authentication" in error_msg.lower():
                log.write("[red]Authentication failed. Check your API key.[/]")
            elif "429" in error_msg or "rate" in error_msg.lower():
                log.write("[red]Rate limited. Wait a moment and try again.[/]")
            else:
                log.write(f"[red]Error: {error_msg}[/]")
            # Remove the failed user message
            self._session.messages.pop()
            status.update("Error occurred")
        finally:
            self._streaming = False

    def _handle_chat_command(self, command: str) -> None:
        """Handle slash commands in the chat input."""
        from santai_cli.core.chat import ChatSession
        from santai_cli.core.config import load_agent_prompt

        log = self.query_one("#chat-log", RichLog)
        status = self.query_one("#chat-status", Label)

        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None

        if cmd in ("/quit", "/exit", "/q"):
            self.dismiss()

        elif cmd == "/clear":
            if self._session:
                self._session.clear()
            log.clear()
            log.write("[dim]Conversation cleared.[/]\n")

        elif cmd == "/help":
            log.write(
                "\n[bold]Commands:[/]\n"
                "  [cyan]/quit[/]          Close the chat\n"
                "  [cyan]/clear[/]         Clear conversation history\n"
                "  [cyan]/agent[/]         List agents, or /agent <name> to switch\n"
                "  [cyan]/model[/]         Switch model (shows numbered list)\n"
                "  [cyan]/help[/]          Show this help\n"
            )

        elif cmd == "/agent":
            if arg:
                prompt = load_agent_prompt(arg)
                if prompt is None:
                    log.write(f"[red]Agent '{arg}' not found.[/]")
                    self._show_agents(log)
                else:
                    self._session = ChatSession(system_prompt=prompt)
                    self._agent = arg
                    log.clear()
                    log.write(f"[dim]Switched to agent: {arg}. History cleared.[/]\n")
                    status.update(
                        f"Agent: {arg} | Model: {self._model} | /help for commands"
                    )
            else:
                self._show_agents(log)

        elif cmd == "/model":
            if self._config is None:
                return
            choices = self._config.get_model_choices()
            if not choices:
                log.write("[red]No models available.[/]")
                return

            log.write("\n[bold]Available models:[/]")
            for i, (label, _, _) in enumerate(choices, 1):
                log.write(f"  [cyan]{i}[/]) {label}")

            if arg:
                # Allow direct selection by number
                try:
                    idx = int(arg) - 1
                    if 0 <= idx < len(choices):
                        _, self._provider, self._model = choices[idx]
                        provider_name = self._config.providers[self._provider].name
                        log.write(
                            f"\n[dim]Switched to {provider_name}: {self._model}[/]\n"
                        )
                        status.update(
                            f"Provider: {provider_name} | Model: {self._model}"
                        )
                        return
                except ValueError:
                    pass

            log.write("[dim]Type /model <number> to switch.[/]\n")

        else:
            log.write(f"[red]Unknown command: {cmd}[/]. Type /help for options.")

    def _show_agents(self, log: RichLog) -> None:
        """Display available agent profiles."""
        from santai_cli.core.config import get_agent_profiles

        profiles = get_agent_profiles()
        if not profiles:
            log.write("[dim]No agent profiles found.[/]")
            return

        log.write("\n[bold]Available agents:[/]")
        for name, description in profiles:
            desc_text = f" — {description}" if description else ""
            log.write(f"  [cyan]{name}[/]{desc_text}")
        log.write("[dim]Type /agent <name> to switch.[/]\n")


# === Main App ===


class SantaiApp(App):
    """Santai TUI application."""

    TITLE = "Santai"
    CSS = get_theme_css()

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("g", "toggle_graph", "Graph"),
        Binding("slash", "graph_search", "Search", show=True),
        Binding("f", "graph_filter", "Filter", show=True),
        Binding("t", "select_theme", "Theme"),
        Binding("n", "add_note", "Add Note"),
        Binding("p", "cycle_palette", "Palette"),
        Binding("c", "clear_graph_search", "Clear Search", show=True),
        Binding("x", "open_chat", "Chat", show=True),
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
                with Vertical(id="recent-container"):
                    yield RecentFilesPanel(self.project)
                with Vertical(id="notes-container"):
                    yield NotesPanel(self.project)
            with Vertical(id="right-container"):
                with Vertical(id="graph-container"):
                    yield GraphPanel(self.project)
                with Vertical(id="stats-container"):
                    yield StatsPanel(self.project)
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
        for panel in self.query(RecentFilesPanel):
            panel.refresh_recent()
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
        self.notify(
            f"{theme.display_name}: {palette.display_name}"
            f" ({ThemeManager.get_palette_info()})"
        )

    def action_graph_search(self) -> None:
        """Open graph search modal (only in fullscreen graph mode)."""
        if self._graph_fullscreen:
            self.push_screen(GraphSearchScreen(self.project))
        else:
            # Auto-enter fullscreen graph mode, then open search
            self._graph_fullscreen = True
            main_layout = self.query_one("#main-layout")
            graph_fs = self.query_one("#graph-fullscreen")
            main_layout.display = False
            graph_fs.display = True
            for panel in graph_fs.query(GraphPanel):
                panel.refresh_graph()
            self.push_screen(GraphSearchScreen(self.project))

    def action_graph_filter(self) -> None:
        """Open graph filter modal."""
        # Get current filter from the active graph panel
        current_filter = None
        for panel in self.query(GraphPanel):
            if panel._filter_dirs is not None:
                current_filter = panel._filter_dirs
                break
        # Auto-enter fullscreen if not already
        if not self._graph_fullscreen:
            self._graph_fullscreen = True
            main_layout = self.query_one("#main-layout")
            graph_fs = self.query_one("#graph-fullscreen")
            main_layout.display = False
            graph_fs.display = True
            for panel in graph_fs.query(GraphPanel):
                panel.refresh_graph()
        self.push_screen(GraphFilterScreen(self.project, current_filter=current_filter))

    def action_clear_graph_search(self) -> None:
        """Clear graph search highlighting and filters on all graph panels."""
        cleared = False
        for panel in self.query(GraphPanel):
            if panel._search_query or panel._highlight_ids or panel._selected_id:
                panel.clear_search()
                cleared = True
            if panel._filter_dirs is not None:
                panel.clear_filter()
                cleared = True
        if cleared:
            self.notify("Search & filter cleared")

    def action_add_note(self) -> None:
        """Open add note modal."""
        self.push_screen(AddNoteScreen(self.project))

    def action_open_chat(self) -> None:
        """Open the AI chat modal."""
        self.push_screen(ChatScreen(self.project))

    def on_clickable_note_clicked(self, event: ClickableNote.Clicked) -> None:
        """Handle click on a note — open note detail modal."""
        self.push_screen(NoteDetailScreen(event.note, project=self.project))

    async def action_back(self) -> None:
        """Go back — exit fullscreen graph or do nothing on dashboard."""
        if self._graph_fullscreen:
            self.action_toggle_graph()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in data tables.

        Opens the appropriate screen for recent files.
        """
        # Check if this is the recent files table
        table = event.data_table
        if table.id == "recent-table":
            # Find the RecentFilesPanel that owns this table
            for panel in self.query(RecentFilesPanel):
                row_index = event.cursor_row
                if 0 <= row_index < len(panel._recent_files):
                    file_info = panel._recent_files[row_index]
                    if file_info.path.is_file():
                        self._open_file(file_info.path)

    def _open_file(self, file_path: Path) -> None:
        """Open a file in the appropriate screen.

        Uses NoteDetailScreen for notes, FilePreviewScreen for others.
        """
        # Check if this file is in the notes directory
        try:
            rel = file_path.relative_to(self.project.root)
            is_note = rel.parts[0] == "notes" if rel.parts else False
        except ValueError:
            is_note = False

        if is_note and file_path.suffix in (".md", ".txt"):
            from santai_cli.core.project import NoteEntry

            try:
                content = file_path.read_text(encoding="utf-8")
                title = file_path.stem.replace("-", " ").replace("_", " ").title()
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                preview = content[:200].replace("\n", " ").strip()
                stat = file_path.stat()
                note = NoteEntry(
                    title=title,
                    content=content,
                    preview=preview,
                    filename=file_path.name,
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                    size_bytes=stat.st_size,
                )
                self.push_screen(NoteDetailScreen(note, project=self.project))
            except (OSError, UnicodeDecodeError):
                self.push_screen(FilePreviewScreen(file_path, project=self.project))
        else:
            self.push_screen(FilePreviewScreen(file_path, project=self.project))

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Handle file selection in directory tree — open with appropriate screen."""
        file_path = event.path
        if not file_path.is_file():
            return
        self._open_file(file_path)
