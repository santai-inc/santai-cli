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
    """Panel showing file graph with backlinks."""

    # Directory color codes — warm palette inspired by Obsidian graph
    DIR_COLORS = {
        "resources": "#4eba65",  # green
        "codebases": "#06B6D4",  # cyan
        "history": "#b1b9f9",  # lavender
        "notes": "#d77757",  # terracotta
        "other": "#6b6560",  # warm gray
    }

    # Braille edge characters for smoother connections
    BRAILLE_DOTS = "⠁⠂⠃⠄⠅⠆⠇⡀⡁⡂⡃⡄⡅⡆⡇⠈⠉⠊⠋⠌⠍⠎⠏⡈⡉⡊⡋⡌⡍⡎⡏"
    EDGE_CHARS = ["⡀", "⠄", "⠂", "⠁", "⠈", "⠐", "⠠", "⡀"]

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

    def _node_shape(self, degree: int) -> str:
        """Get node shape based on connection degree."""
        if degree >= 5:
            return "⬢"  # hexagon — hub node
        elif degree >= 3:
            return "◆"  # diamond — well-connected
        elif degree >= 1:
            return "●"  # circle — has links
        else:
            return "○"  # empty circle — isolated

    def _braille_edge(self, length: int = 6) -> str:
        """Generate a Braille-character edge line."""
        chars = ["⠤", "⠤", "⠤", "⠶", "⠤", "⠤"]
        return "".join(chars[:length])

    def _render_panel_graph(self, lines, active_dirs, nodes_by_dir, adjacency, node_lookup, max_per_dir):
        """Render compact graph for side panel — polished Obsidian-style."""
        theme = ThemeManager.get_current_theme()

        for i, dir_name in enumerate(active_dirs):
            color = self.DIR_COLORS.get(dir_name, self.DIR_COLORS["other"])
            nodes = sorted(nodes_by_dir[dir_name], key=lambda n: n.name)
            count = len(nodes)
            display_nodes = nodes[:max_per_dir]

            # Cluster box with rounded corners
            max_name_len = max((len(n.name) for n in display_nodes), default=8)
            box_width = max(max_name_len + 6, len(dir_name) + 8)

            lines.append(f"[{color}]╭{'─' * box_width}╮[/{color}]")
            header = f" ● {dir_name}/ ({count})"
            lines.append(f"[{color}]│[/{color}][bold {color}]{header:<{box_width}}[/bold {color}][{color}]│[/{color}]")
            lines.append(f"[{color}]├{'─' * box_width}┤[/{color}]")

            for node in display_nodes:
                degree = len(adjacency.get(node.id, set()))
                marker = self._node_shape(degree)
                name = node.name[:box_width - 6]
                deg_str = f" [{degree}]" if degree > 0 else ""
                padding = max(0, box_width - len(name) - len(deg_str) - 4)
                lines.append(
                    f"[{color}]│[/{color}] {marker} {name}[dim]{deg_str}[/dim]{' ' * padding}[{color}]│[/{color}]"
                )

            if count > max_per_dir:
                more_text = f"  ⠶ +{count - max_per_dir} more"
                padding = max(0, box_width - len(more_text))
                lines.append(
                    f"[{color}]│[/{color}][dim]{more_text}{' ' * padding}[/dim][{color}]│[/{color}]"
                )

            lines.append(f"[{color}]╰{'─' * box_width}╯[/{color}]")

            # Braille-style connections between clusters
            if i < len(active_dirs) - 1:
                connections = self._get_cross_dir_connections(
                    dir_name, active_dirs[i + 1:], nodes_by_dir, adjacency
                )
                if connections:
                    for src_name, tgt_name, tgt_dir in connections[:3]:
                        tgt_color = self.DIR_COLORS.get(tgt_dir, self.DIR_COLORS["other"])
                        lines.append(
                            f"  [{color}]●[/{color}] {src_name} "
                            f"[dim]⠤⠤⠶⠤⠤[/dim] "
                            f"[{tgt_color}]●[/{tgt_color}] {tgt_name}"
                        )
                else:
                    lines.append(f"[dim]  ⠇[/dim]")

    def _render_fullscreen_graph(self, lines, active_dirs, nodes_by_dir, adjacency, node_lookup, max_per_dir):
        """Render expanded graph for fullscreen — Obsidian-inspired with Braille edges."""
        max_per_dir = 15
        theme = ThemeManager.get_current_theme()

        # === Cluster visualization ===
        for i, dir_name in enumerate(active_dirs):
            color = self.DIR_COLORS.get(dir_name, self.DIR_COLORS["other"])
            nodes = sorted(nodes_by_dir[dir_name], key=lambda n: n.name)
            count = len(nodes)
            display_nodes = nodes[:max_per_dir]

            max_name_len = max((len(n.name) for n in display_nodes), default=8)
            box_width = max(max_name_len + 22, len(dir_name) + 12, 44)

            # Double-line box for clusters
            lines.append(f"[{color}]╔{'═' * box_width}╗[/{color}]")
            header = f" ⬢ {dir_name}/ ({count} files)"
            lines.append(f"[{color}]║[/{color}][bold {color}]{header:<{box_width}}[/bold {color}][{color}]║[/{color}]")
            lines.append(f"[{color}]╠{'═' * box_width}╣[/{color}]")

            for node in display_nodes:
                degree = len(adjacency.get(node.id, set()))
                marker = self._node_shape(degree)
                size = format_size(node.size_bytes)
                name_part = node.name[:box_width - 22]

                # Degree bar visualization
                bar = "█" * min(degree, 8) + "░" * max(0, 8 - degree) if degree > 0 else "░" * 8
                detail = f"{name_part}  [dim]{size}[/dim] [{color}]{bar}[/{color}]"
                visible_len = len(name_part) + 2 + len(size) + 1 + 8
                padding = max(0, box_width - visible_len - 3)
                lines.append(
                    f"[{color}]║[/{color}] {marker} {detail}{' ' * padding}[{color}]║[/{color}]"
                )

            if count > max_per_dir:
                more_text = f"  ⠶ +{count - max_per_dir} more files"
                padding = max(0, box_width - len(more_text))
                lines.append(
                    f"[{color}]║[/{color}][dim]{more_text}{' ' * padding}[/dim][{color}]║[/{color}]"
                )

            lines.append(f"[{color}]╚{'═' * box_width}╝[/{color}]")

            # Braille-style connections between clusters
            if i < len(active_dirs) - 1:
                connections = self._get_cross_dir_connections(
                    dir_name, active_dirs[i + 1:], nodes_by_dir, adjacency
                )
                if connections:
                    lines.append("")
                    for src_name, tgt_name, tgt_dir in connections[:5]:
                        tgt_color = self.DIR_COLORS.get(tgt_dir, self.DIR_COLORS["other"])
                        lines.append(
                            f"    [{color}]●[/{color}] {src_name} "
                            f"[dim]⠤⠤⠤⠶⠤⠤⠤⠶⠤⠤⠤[/dim] "
                            f"[{tgt_color}]●[/{tgt_color}] {tgt_name} "
                            f"[dim]({tgt_dir}/)[/dim]"
                        )
                    lines.append("")
                else:
                    lines.append(f"[dim]    ⠇[/dim]")
                    lines.append("")

        # === Connection Matrix ===
        if adjacency:
            lines.append("")
            lines.append(f"[bold]⬡ Connection Graph[/bold]")
            lines.append(f"[dim]{'─' * 56}[/dim]")

            # Sort by degree (most connected first)
            sorted_nodes = sorted(
                [(nid, len(conns)) for nid, conns in adjacency.items() if nid in node_lookup],
                key=lambda x: x[1],
                reverse=True,
            )

            edge_shown = 0
            seen_edges: set[tuple[str, str]] = set()
            for node_id, degree in sorted_nodes:
                src_node = node_lookup[node_id]
                src_color = self.DIR_COLORS.get(src_node.directory, self.DIR_COLORS["other"])

                for target_id in sorted(adjacency[node_id]):
                    edge_key = tuple(sorted([node_id, target_id]))
                    if edge_key in seen_edges or target_id not in node_lookup:
                        continue
                    seen_edges.add(edge_key)
                    tgt_node = node_lookup[target_id]
                    tgt_color = self.DIR_COLORS.get(tgt_node.directory, self.DIR_COLORS["other"])

                    src_shape = self._node_shape(degree)
                    tgt_degree = len(adjacency.get(target_id, set()))
                    tgt_shape = self._node_shape(tgt_degree)

                    lines.append(
                        f"  [{src_color}]{src_shape} {src_node.name}[/{src_color}] "
                        f"[dim]⠤⠶⠤[/dim] "
                        f"[{tgt_color}]{tgt_shape} {tgt_node.name}[/{tgt_color}]"
                    )
                    edge_shown += 1
                    if edge_shown >= 25:
                        lines.append(f"  [dim]⠶ ... and more connections[/dim]")
                        break
                if edge_shown >= 25:
                    break

            # Node info summary
            lines.append("")
            lines.append(f"[bold]Node Info[/bold]")
            lines.append(f"[dim]{'─' * 56}[/dim]")
            lines.append(f"  ⬢ = hub (5+ links)  ◆ = connected (3+)  ● = linked  ○ = isolated")
            lines.append(f"  [dim]█ = connection strength  ⠤⠶⠤ = edge[/dim]")

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
            self._refresh_panels()
        except OSError as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.dismiss()

    def _refresh_panels(self) -> None:
        for panel in self.app.query(StatsPanel):
            panel.refresh_stats()
        for panel in self.app.query(NotesPanel):
            panel.refresh_notes()
        for panel in self.app.query(GraphPanel):
            panel.refresh_graph()

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
                self._refresh_panels()
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
            self.app.push_screen(MoveFileScreen(note_path, project))
            self.dismiss()

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

    def _refresh_panels(self) -> None:
        for panel in self.app.query(StatsPanel):
            panel.refresh_stats()
        for panel in self.app.query(NotesPanel):
            panel.refresh_notes()
        for panel in self.app.query(GraphPanel):
            panel.refresh_graph()


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

        # Refresh notes panel
        for panel in self.app.query(NotesPanel):
            panel.refresh_notes()
        # Refresh stats
        for panel in self.app.query(StatsPanel):
            panel.refresh_stats()

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
                self._refresh_panels()
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
            self.app.push_screen(MoveFileScreen(self.file_path, project))
            self.dismiss()
        else:
            self.app.notify("Cannot determine project", severity="error")

    def _refresh_panels(self) -> None:
        for panel in self.app.query(StatsPanel):
            panel.refresh_stats()
        for panel in self.app.query(NotesPanel):
            panel.refresh_notes()
        for panel in self.app.query(GraphPanel):
            panel.refresh_graph()


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
        """Refresh the theme options display."""
        current = ThemeManager.get_current_theme()
        options = self.query_one("#theme-options", Static)

        lines = []
        lines.append("")
        themes_info = [
            ("1", "claude", "Claude Code", "Warm terracotta, hot pink tools, playful"),
            ("2", "catppuccin", "Catppuccin", "Soothing pastels, mauve primary, cozy"),
            ("3", "btop", "btop", "Dense dashboard, green/red gradients, dark"),
            ("4", "light", "Light", "Clean paper-like, blue accents, minimal"),
        ]

        for key, name, display, desc in themes_info:
            marker = "▸" if current.name == name else " "
            active = " [bold](active)[/bold]" if current.name == name else ""
            lines.append(f"  {marker} [{key}] {display}{active}")
            lines.append(f"      [dim]{desc}[/dim]")
            lines.append("")

        lines.append("  [dim]Press 1/2/3/4 to switch theme, Esc to close[/dim]")
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
