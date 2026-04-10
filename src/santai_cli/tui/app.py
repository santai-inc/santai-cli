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
        """Refresh graph data with visual ASCII graph rendering."""
        graph = get_file_graph(self.project)
        content_widget = self.query_one("#graph-content", Static)

        if not graph.nodes:
            content_widget.update("[dim]No files found. Add files to resources/, notes/, etc.[/dim]")
            return

        lines = []

        # Stats header
        lines.append(
            f"[bold]Nodes:[/bold] {len(graph.nodes)}  "
            f"[bold]Edges:[/bold] {len(graph.edges)}"
        )
        lines.append("")

        # Group nodes by directory
        nodes_by_dir: dict[str, list] = {}
        for node in graph.nodes:
            if node.directory not in nodes_by_dir:
                nodes_by_dir[node.directory] = []
            nodes_by_dir[node.directory].append(node)

        # Build node lookup
        node_lookup = {node.id: node for node in graph.nodes}

        # Build adjacency: node_id -> set of connected node_ids
        adjacency: dict[str, set[str]] = {}
        for edge in graph.edges:
            adjacency.setdefault(edge.source, set()).add(edge.target)
            adjacency.setdefault(edge.target, set()).add(edge.source)

        # Determine max nodes to show per directory
        max_per_dir = 8 if self.fullscreen else 4

        # === VISUAL GRAPH ===
        # Render directory clusters as visual boxes with nodes inside
        # Connected nodes get lines drawn between clusters

        dir_order = ["resources", "codebases", "history", "notes"]
        active_dirs = [d for d in dir_order if d in nodes_by_dir]
        # Add any dirs not in the standard order
        for d in nodes_by_dir:
            if d not in active_dirs:
                active_dirs.append(d)

        if self.fullscreen:
            # Fullscreen: render side-by-side cluster boxes
            self._render_fullscreen_graph(lines, active_dirs, nodes_by_dir, adjacency, node_lookup, max_per_dir)
        else:
            # Panel: compact vertical cluster view
            self._render_panel_graph(lines, active_dirs, nodes_by_dir, adjacency, node_lookup, max_per_dir)

        # Legend
        lines.append("")
        legend_parts = []
        for dir_name in active_dirs:
            color = self.DIR_COLORS.get(dir_name, self.DIR_COLORS["other"])
            legend_parts.append(f"[{color}]●[/{color}] {dir_name}")
        lines.append(" ".join(legend_parts))

        if graph.edges:
            lines.append("[dim]─── = link between files[/dim]")

        content_widget.update("\n".join(lines))

    def _render_panel_graph(self, lines, active_dirs, nodes_by_dir, adjacency, node_lookup, max_per_dir):
        """Render compact graph for side panel."""
        for i, dir_name in enumerate(active_dirs):
            color = self.DIR_COLORS.get(dir_name, self.DIR_COLORS["other"])
            nodes = sorted(nodes_by_dir[dir_name], key=lambda n: n.name)
            count = len(nodes)
            display_nodes = nodes[:max_per_dir]

            # Cluster box
            max_name_len = max((len(n.name) for n in display_nodes), default=8)
            box_width = max(max_name_len + 4, len(dir_name) + 6)

            lines.append(f"[{color}]╭{'─' * box_width}╮[/{color}]")
            header = f" {dir_name}/ ({count})"
            lines.append(f"[{color}]│[/{color}][bold {color}]{header:<{box_width}}[/bold {color}][{color}]│[/{color}]")
            lines.append(f"[{color}]├{'─' * box_width}┤[/{color}]")

            for node in display_nodes:
                # Check if this node has connections
                has_links = node.id in adjacency
                marker = "◆" if has_links else "○"
                name = node.name[:box_width - 4]
                padding = box_width - len(name) - 3
                lines.append(
                    f"[{color}]│[/{color}] {marker} {name}{' ' * padding}[{color}]│[/{color}]"
                )

            if count > max_per_dir:
                more_text = f"  +{count - max_per_dir} more"
                padding = box_width - len(more_text)
                lines.append(
                    f"[{color}]│[/{color}][dim]{more_text}{' ' * padding}[/dim][{color}]│[/{color}]"
                )

            lines.append(f"[{color}]╰{'─' * box_width}╯[/{color}]")

            # Draw connections from this cluster to others
            if i < len(active_dirs) - 1:
                connections = self._get_cross_dir_connections(
                    dir_name, active_dirs[i + 1:], nodes_by_dir, adjacency
                )
                if connections:
                    for src_name, tgt_name, tgt_dir in connections[:3]:
                        tgt_color = self.DIR_COLORS.get(tgt_dir, self.DIR_COLORS["other"])
                        lines.append(
                            f"  [{color}]{src_name}[/{color}] "
                            f"[dim]───────>[/dim] "
                            f"[{tgt_color}]{tgt_name}[/{tgt_color}]"
                        )
                else:
                    lines.append(f"[dim]  │[/dim]")

    def _render_fullscreen_graph(self, lines, active_dirs, nodes_by_dir, adjacency, node_lookup, max_per_dir):
        """Render expanded graph for fullscreen view."""
        max_per_dir = 15  # Show more in fullscreen

        # Render each cluster as a larger box
        for i, dir_name in enumerate(active_dirs):
            color = self.DIR_COLORS.get(dir_name, self.DIR_COLORS["other"])
            nodes = sorted(nodes_by_dir[dir_name], key=lambda n: n.name)
            count = len(nodes)
            display_nodes = nodes[:max_per_dir]

            # Wider box for fullscreen
            max_name_len = max((len(n.name) for n in display_nodes), default=8)
            box_width = max(max_name_len + 20, len(dir_name) + 10, 40)

            lines.append(f"[{color}]╔{'═' * box_width}╗[/{color}]")
            header = f" ● {dir_name}/ ({count} files)"
            lines.append(f"[{color}]║[/{color}][bold {color}]{header:<{box_width}}[/bold {color}][{color}]║[/{color}]")
            lines.append(f"[{color}]╠{'═' * box_width}╣[/{color}]")

            for node in display_nodes:
                has_links = node.id in adjacency
                link_count = len(adjacency.get(node.id, set()))
                marker = "◆" if has_links else "○"
                size = format_size(node.size_bytes)
                name_part = node.name[:box_width - 20]
                link_info = f"({link_count} links)" if link_count > 0 else ""
                detail = f"{name_part}  [dim]{size} {link_info}[/dim]"
                # Calculate visible length (without Rich markup)
                visible_len = len(name_part) + 2 + len(size) + 1 + len(link_info)
                padding = max(0, box_width - visible_len - 3)
                lines.append(
                    f"[{color}]║[/{color}] {marker} {detail}{' ' * padding}[{color}]║[/{color}]"
                )

            if count > max_per_dir:
                more_text = f"  ... +{count - max_per_dir} more files"
                padding = box_width - len(more_text)
                lines.append(
                    f"[{color}]║[/{color}][dim]{more_text}{' ' * padding}[/dim][{color}]║[/{color}]"
                )

            lines.append(f"[{color}]╚{'═' * box_width}╝[/{color}]")

            # Draw connections between this cluster and others
            if i < len(active_dirs) - 1:
                connections = self._get_cross_dir_connections(
                    dir_name, active_dirs[i + 1:], nodes_by_dir, adjacency
                )
                if connections:
                    lines.append("")
                    for src_name, tgt_name, tgt_dir in connections[:5]:
                        tgt_color = self.DIR_COLORS.get(tgt_dir, self.DIR_COLORS["other"])
                        lines.append(
                            f"    [{color}]{src_name}[/{color}] "
                            f"[dim]════════════>[/dim] "
                            f"[{tgt_color}]{tgt_name}[/{tgt_color}] "
                            f"[dim]({tgt_dir}/)[/dim]"
                        )
                    lines.append("")
                else:
                    lines.append(f"[dim]    ║[/dim]")
                    lines.append("")

        # Show all edges in a summary section
        if adjacency:
            lines.append("")
            lines.append("[bold]All Connections:[/bold]")
            lines.append(f"[dim]{'─' * 50}[/dim]")
            edge_shown = 0
            seen_edges: set[tuple[str, str]] = set()
            for node_id, connected in sorted(adjacency.items()):
                if node_id not in node_lookup:
                    continue
                src_node = node_lookup[node_id]
                src_color = self.DIR_COLORS.get(src_node.directory, self.DIR_COLORS["other"])
                for target_id in sorted(connected):
                    edge_key = tuple(sorted([node_id, target_id]))
                    if edge_key in seen_edges:
                        continue
                    seen_edges.add(edge_key)
                    if target_id not in node_lookup:
                        continue
                    tgt_node = node_lookup[target_id]
                    tgt_color = self.DIR_COLORS.get(tgt_node.directory, self.DIR_COLORS["other"])
                    lines.append(
                        f"  [{src_color}]◆ {src_node.name}[/{src_color}] "
                        f"[dim]⟷[/dim] "
                        f"[{tgt_color}]◆ {tgt_node.name}[/{tgt_color}]"
                    )
                    edge_shown += 1
                    if edge_shown >= 20:
                        remaining = len(seen_edges)
                        lines.append(f"  [dim]... and more connections[/dim]")
                        break
                if edge_shown >= 20:
                    break

    def _get_cross_dir_connections(self, source_dir, target_dirs, nodes_by_dir, adjacency):
        """Get connections between nodes in source_dir and target_dirs."""
        connections = []
        source_nodes = nodes_by_dir.get(source_dir, [])
        for src_node in source_nodes:
            if src_node.id not in adjacency:
                continue
            for target_id in adjacency[src_node.id]:
                for tgt_dir in target_dirs:
                    for tgt_node in nodes_by_dir.get(tgt_dir, []):
                        if tgt_node.id == target_id:
                            connections.append((src_node.name, tgt_node.name, tgt_dir))
        return connections


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