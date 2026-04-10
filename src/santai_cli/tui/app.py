"""Textual TUI application for Santai."""

from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
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
        notes = get_notes(self.project)
        content_widget = self.query_one("#notes-content", Static)

        if not notes:
            content_widget.update(
                "[dim]No notes yet. Add .md or .txt files to notes/[/dim]"
            )
            return

        # Build notes preview content
        lines = []
        for note in notes[:5]:  # Show up to 5 notes
            lines.append(f"[bold #10B981]{note.title}[/bold #10B981]")
            lines.append(f"[dim]{format_time_ago(note.modified_at)}[/dim]")
            # Truncate preview for display
            preview = (
                note.preview[:100] + "..." if len(note.preview) > 100 else note.preview
            )
            lines.append(f"[#AEAEB2]{preview}[/#AEAEB2]")
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

    def __init__(self, project: SantaiProject) -> None:
        super().__init__()
        self.project = project

    def compose(self) -> ComposeResult:
        yield Label("[bold]File Graph[/bold]", id="graph-title")
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

            # Show links (limit to avoid overflow)
            shown = 0
            max_links = 15
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
                    display_text = (
                        link_text[:20] + "..." if len(link_text) > 20 else link_text
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

        # Show legend
        lines.append("")
        lines.append("[bold]Legend:[/bold]")
        for dir_name, color in self.DIR_COLORS.items():
            if dir_name != "other":
                lines.append(f"  [{color}]●[/{color}] {dir_name}")

        content_widget.update("\n".join(lines))


class SantaiApp(App):
    """Santai TUI application."""

    TITLE = "Santai"
    CSS = """
    Screen {
        layout: horizontal;
        background: #0C0A09;
    }

    Header {
        background: rgba(255, 255, 255, 0.08);
        color: #F5F5F7;
        text-style: bold;
    }

    Header > HeaderTitle {
        color: #F5F5F7;
        text-style: bold;
    }

    Header > HeaderIcon {
        color: #10B981;
    }

    Footer {
        background: rgba(255, 255, 255, 0.08);
        color: #F5F5F7;
    }

    Footer > .footer--key {
        background: rgba(255, 255, 255, 0.12);
        color: #F5F5F7;
    }

    Footer > .footer--description {
        color: #AEAEB2;
    }

    #tree-container {
        width: 1fr;
        height: 100%;
        border: solid rgba(255, 255, 255, 0.18);
        padding: 1 2;
        background: rgba(255, 255, 255, 0.08);
        margin: 1;
        border-radius: 12;
    }

    #tree-title {
        text-style: bold;
        color: #10B981;
        margin-bottom: 1;
        text-align: center;
        width: 100%;
    }

    DirectoryTree {
        background: transparent;
        padding: 0 1;
    }

    DirectoryTree > .directory-tree--folder {
        color: #F5F5F7;
        text-style: bold;
    }

    DirectoryTree > .directory-tree--extension {
        color: #AEAEB2;
    }

    DirectoryTree > .directory-tree--file {
        color: #D6D3D1;
    }

    DirectoryTree:focus > .directory-tree--cursor {
        background: #10B981;
        color: #0C0A09;
        text-style: bold;
    }

    DirectoryTree > .directory-tree--cursor {
        background: rgba(16, 185, 129, 0.3);
        color: #F5F5F7;
    }

    #middle-container {
        width: 2fr;
        height: 100%;
        layout: vertical;
    }

    #stats-container {
        height: 1fr;
        border: solid rgba(255, 255, 255, 0.18);
        padding: 1 2;
        background: rgba(255, 255, 255, 0.08);
        margin: 1;
        border-radius: 12;
    }

    #notes-container {
        height: 1fr;
        border: solid rgba(255, 255, 255, 0.18);
        padding: 1 2;
        background: rgba(255, 255, 255, 0.08);
        margin: 1;
        border-radius: 12;
    }

    #right-container {
        width: 1fr;
        height: 100%;
        layout: vertical;
    }

    #graph-container {
        height: 100%;
        border: solid rgba(255, 255, 255, 0.18);
        padding: 1 2;
        background: rgba(255, 255, 255, 0.08);
        margin: 1;
        border-radius: 12;
        overflow-y: auto;
    }

    #stats-title, #types-title, #recent-title, #notes-title, #graph-title {
        margin-bottom: 1;
        color: #10B981;
        text-style: bold;
        border-bottom: solid #10B981;
        padding-bottom: 1;
    }

    #notes-content, #graph-content {
        color: #F5F5F7;
        padding: 1;
        height: auto;
    }

    DataTable {
        height: auto;
        max-height: 10;
        margin-bottom: 1;
        background: rgba(255, 255, 255, 0.12);
        padding: 0 1;
        border-radius: 8;
    }

    DataTable > .datatable--header {
        background: #10B981;
        color: #0C0A09;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: rgba(16, 185, 129, 0.4);
        color: #F5F5F7;
        text-style: bold;
    }

    DataTable > .datatable--even-row {
        background: rgba(255, 255, 255, 0.12);
    }

    DataTable > .datatable--odd-row {
        background: rgba(255, 255, 255, 0.06);
    }

    DataTable:focus > .datatable--cursor {
        background: #10B981;
        color: #0C0A09;
    }

    #dir-stats-table {
        max-height: 8;
    }

    #types-table {
        max-height: 6;
    }

    #recent-table {
        max-height: 6;
    }

    StatsPanel {
        background: transparent;
    }

    StatsPanel > Label {
        color: #F5F5F7;
    }

    NotesPanel {
        background: transparent;
    }

    NotesPanel > Label {
        color: #F5F5F7;
    }

    GraphPanel {
        background: transparent;
    }

    GraphPanel > Label {
        color: #F5F5F7;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("g", "toggle_graph", "Graph"),
    ]

    def __init__(self, project: SantaiProject) -> None:
        super().__init__()
        self.project = project
        self.sub_title = project.name

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
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
        yield Footer()

    def action_refresh(self) -> None:
        """Refresh all panels."""
        stats_panel = self.query_one(StatsPanel)
        stats_panel.refresh_stats()
        notes_panel = self.query_one(NotesPanel)
        notes_panel.refresh_notes()
        graph_panel = self.query_one(GraphPanel)
        graph_panel.refresh_graph()
        self.notify("Refreshed all panels")

    def action_toggle_graph(self) -> None:
        """Toggle graph panel visibility."""
        graph_container = self.query_one("#right-container")
        graph_container.display = not graph_container.display
        if graph_container.display:
            self.notify("Graph panel shown")
        else:
            self.notify("Graph panel hidden")