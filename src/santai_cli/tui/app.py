"""Textual TUI application for Santai."""

from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    DirectoryTree,
    Footer,
    Header,
    Label,
    Static,
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

    def compose(self) -> ComposeResult:
        yield Label("[bold]Directory Statistics[/bold]", id="stats-title")
        yield DataTable(id="dir-stats-table")
        yield Label("")
        yield Label("[bold]File Types[/bold]", id="types-title")
        yield DataTable(id="types-table")
        yield Label("")
        yield Label("[bold]Recent Files[/bold]", id="recent-title")
        yield DataTable(id="recent-table")

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

        # Recent files table
        recent_table = self.query_one("#recent-table", DataTable)
        recent_table.clear(columns=True)
        recent_table.add_columns("File", "Modified")
        for file_info in stats.recent_files[:5]:
            recent_table.add_row(
                file_info.name,
                format_time_ago(file_info.modified_at),
            )
        if not stats.recent_files:
            recent_table.add_row("[dim]No files[/dim]", "")


class NotesPanel(Static):
    """Panel showing notes preview."""

    def __init__(self, project: SantaiProject) -> None:
        super().__init__()
        self.project = project

    def compose(self) -> ComposeResult:
        yield Label("[bold]Notes Preview[/bold]", id="notes-title")
        yield Static(id="notes-content")

    def on_mount(self) -> None:
        """Populate notes preview."""
        self.refresh_notes()

    def refresh_notes(self) -> None:
        """Refresh notes data."""
        theme = ThemeManager.get_current_theme()
        notes = get_notes(self.project)
        content_widget = self.query_one("#notes-content", Static)

        if not notes:
            content_widget.update(
                "[dim]No notes yet. Add .md or .txt files to notes/[/dim]"
            )
            return

        # Build notes preview content
        lines = []
        accent = theme.colors.success
        muted = theme.colors.muted
        for note in notes[:5]:  # Show up to 5 notes
            lines.append(f"[bold {accent}]{note.title}[/bold {accent}]")
            lines.append(f"[dim]{format_time_ago(note.modified_at)}[/dim]")
            # Truncate preview for display
            preview = (
                note.preview[:100] + "..." if len(note.preview) > 100 else note.preview
            )
            lines.append(f"[{muted}]{preview}[/{muted}]")
            lines.append("")

        content_widget.update("\n".join(lines))


class GraphPanel(Static):
    """Panel showing file graph with backlinks."""

    # Directory color codes - harmonized with glass aesthetic
    DIR_COLORS = {
        "resources": "#10B981",  # green (accent)
        "codebases": "#06B6D4",  # cyan
        "history": "#8B5CF6",  # purple
        "notes": "#F59E0B",  # amber
        "other": "#78716C",  # gray
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
        """Refresh graph data."""
        graph = get_file_graph(self.project)
        content_widget = self.query_one("#graph-content", Static)

        if not graph.nodes:
            content_widget.update("[dim]No files found[/dim]")
            return

        lines = []

        # Show stats
        lines.append(
            f"[bold]Nodes:[/bold] {len(graph.nodes)}  [bold]Links:[/bold] {len(graph.edges)}"
        )
        lines.append("")

        max_links = 30 if self.fullscreen else 15

        if graph.edges:
            # Group edges by source
            edges_by_source: dict[str, list[tuple[str, str]]] = {}
            for edge in graph.edges:
                if edge.source not in edges_by_source:
                    edges_by_source[edge.source] = []
                edges_by_source[edge.source].append((edge.target, edge.link_text))

            # Create node lookup for directory info
            node_dirs = {node.id: node.directory for node in graph.nodes}

            lines.append("[bold]Links:[/bold]")
            lines.append("")

            # Show links
            shown = 0
            for source, targets in sorted(edges_by_source.items()):
                if shown >= max_links:
                    remaining = sum(
                        len(t) for s, t in list(edges_by_source.items())[shown:]
                    )
                    lines.append(f"[dim]... and {remaining} more links[/dim]")
                    break

                source_name = Path(source).name
                source_dir = node_dirs.get(source, "other")
                source_color = self.DIR_COLORS.get(source_dir, self.DIR_COLORS["other"])

                for target, link_text in targets:
                    if shown >= max_links:
                        break
                    target_name = Path(target).name
                    target_dir = node_dirs.get(target, "other")
                    target_color = self.DIR_COLORS.get(
                        target_dir, self.DIR_COLORS["other"]
                    )

                    # Truncate link text
                    max_text = 40 if self.fullscreen else 20
                    display_text = (
                        link_text[:max_text] + "..."
                        if len(link_text) > max_text
                        else link_text
                    )

                    lines.append(
                        f"[{source_color}]{source_name}[/{source_color}] "
                        f"[dim]──>[/dim] "
                        f"[{target_color}]{target_name}[/{target_color}] "
                        f"[dim]({display_text})[/dim]"
                    )
                    shown += 1
        else:
            lines.append("[dim]No links between files[/dim]")
            lines.append("")
            lines.append("[dim]Add links in markdown files:[/dim]")
            lines.append("[dim]  [text](path/to/file.md)[/dim]")
            lines.append("[dim]  [[wikilink]][/dim]")

        # Show all nodes grouped by directory in fullscreen
        if self.fullscreen:
            lines.append("")
            lines.append("[bold]All Files:[/bold]")
            nodes_by_dir: dict[str, list] = {}
            for node in graph.nodes:
                if node.directory not in nodes_by_dir:
                    nodes_by_dir[node.directory] = []
                nodes_by_dir[node.directory].append(node)

            for dir_name in sorted(nodes_by_dir.keys()):
                color = self.DIR_COLORS.get(dir_name, self.DIR_COLORS["other"])
                nodes = nodes_by_dir[dir_name]
                lines.append(f"  [{color}]● {dir_name}/ ({len(nodes)} files)[/{color}]")
                for node in sorted(nodes, key=lambda n: n.name)[:20]:
                    size = format_size(node.size_bytes)
                    lines.append(f"    [{color}]├[/{color}] {node.name} [dim]({size})[/dim]")
                if len(nodes) > 20:
                    lines.append(f"    [dim]... and {len(nodes) - 20} more[/dim]")

        # Show legend
        lines.append("")
        lines.append("[bold]Legend:[/bold]")
        for dir_name, color in self.DIR_COLORS.items():
            if dir_name != "other":
                lines.append(f"  [{color}]●[/{color}] {dir_name}")

        content_widget.update("\n".join(lines))


# === Modal Screens ===


class NotesModalScreen(ModalScreen):
    """Full-screen notes viewer modal."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("n", "dismiss", "Close"),
    ]

    def __init__(self, project: SantaiProject) -> None:
        super().__init__()
        self.project = project

    def compose(self) -> ComposeResult:
        theme = ThemeManager.get_current_theme()
        c = theme.colors
        with Vertical(id="notes-modal"):
            with VerticalScroll(id="notes-modal-content"):
                yield Label("[bold]Notes (press Esc to close)[/bold]", id="notes-modal-title")
                yield Static(id="notes-modal-body")

    def on_mount(self) -> None:
        """Populate notes."""
        theme = ThemeManager.get_current_theme()
        notes = get_notes(self.project)
        body = self.query_one("#notes-modal-body", Static)

        if not notes:
            body.update("[dim]No notes found. Add .md or .txt files to notes/[/dim]")
            return

        lines = []
        accent = theme.colors.primary
        for note in notes:
            lines.append(f"[bold {accent}]{'─' * 40}[/bold {accent}]")
            lines.append(f"[bold {accent}]{note.title}[/bold {accent}]")
            lines.append(f"[dim]{format_time_ago(note.modified_at)} · {format_size(note.size_bytes)}[/dim]")
            lines.append("")
            # Show full content (truncated to reasonable length)
            content = note.content[:2000] if len(note.content) > 2000 else note.content
            lines.append(content)
            lines.append("")

        body.update("\n".join(lines))


class FilePreviewScreen(ModalScreen):
    """File preview modal for viewing file contents."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    def __init__(self, file_path: Path) -> None:
        super().__init__()
        self.file_path = file_path

    def compose(self) -> ComposeResult:
        with Vertical(id="file-preview-modal"):
            with VerticalScroll(id="file-preview-content"):
                yield Label(
                    f"[bold]{self.file_path.name} (press Esc to close)[/bold]",
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
            body.update(content)
        except UnicodeDecodeError:
            body.update(f"[dim]Binary file: {format_size(self.file_path.stat().st_size)}[/dim]")
        except OSError as e:
            body.update(f"[dim]Error reading file: {e}[/dim]")


class ThemeSelectScreen(ModalScreen):
    """Theme selection modal with live switching."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("t", "dismiss", "Close"),
        Binding("1", "select_theme_1", "Claude"),
        Binding("2", "select_theme_2", "Catppuccin"),
        Binding("3", "select_theme_3", "btop"),
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
        """Refresh the theme options display."""
        current = ThemeManager.get_current_theme()
        options = self.query_one("#theme-options", Static)

        lines = []
        lines.append("")
        themes_info = [
            ("1", "claude", "Claude Code", "Warm terracotta, hot pink tools, playful"),
            ("2", "catppuccin", "Catppuccin", "Soothing pastels, mauve primary, cozy"),
            ("3", "btop", "btop", "Dense dashboard, green/red gradients, dark"),
        ]

        for key, name, display, desc in themes_info:
            marker = "▸" if current.name == name else " "
            active = " [bold](active)[/bold]" if current.name == name else ""
            lines.append(f"  {marker} [{key}] {display}{active}")
            lines.append(f"      [dim]{desc}[/dim]")
            lines.append("")

        lines.append("  [dim]Press 1/2/3 to switch theme, Esc to close[/dim]")
        lines.append("  [dim]Theme applies immediately.[/dim]")

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
        self.app.notify(f"Theme: {theme.display_name}")

    def action_select_theme_1(self) -> None:
        self._apply_theme("claude")

    def action_select_theme_2(self) -> None:
        self._apply_theme("catppuccin")

    def action_select_theme_3(self) -> None:
        self._apply_theme("btop")


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
        Binding("n", "show_notes", "Notes"),
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
        # Fullscreen graph - hidden by default
        with Vertical(id="graph-fullscreen"):
            yield GraphPanel(self.project, fullscreen=True)
        yield Footer()

    def on_mount(self) -> None:
        """Set initial visibility."""
        # Hide fullscreen graph on startup
        self.query_one("#graph-fullscreen").display = False
        # Ensure graph panel is visible
        self.query_one("#graph-container").display = True

    def action_refresh(self) -> None:
        """Refresh all panels."""
        for panel in self.query(StatsPanel):
            panel.refresh_stats()
        for panel in self.query(NotesPanel):
            panel.refresh_notes()
        for panel in self.query(GraphPanel):
            panel.refresh_graph()
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

    def action_show_notes(self) -> None:
        """Open notes viewer modal."""
        self.push_screen(NotesModalScreen(self.project))

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Handle file selection in directory tree — show file preview."""
        file_path = event.path
        if file_path.is_file():
            self.push_screen(FilePreviewScreen(file_path))