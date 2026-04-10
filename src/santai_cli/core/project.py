"""Project detection and data loading for Santai projects."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

SANTAI_DIRS = ["resources", "codebases", "history", "notes"]


@dataclass
class HistoryEntry:
    """A parsed history entry from the history/ directory."""

    date: date
    title: str
    content: str
    filename: str


@dataclass
class NoteEntry:
    """A note entry from the notes/ directory."""

    title: str
    content: str
    preview: str
    filename: str
    modified_at: datetime
    size_bytes: int


@dataclass
class FileInfo:
    """Information about a file in the project."""

    path: Path
    name: str
    size_bytes: int
    modified_at: datetime
    file_type: str


@dataclass
class GraphNode:
    """A node in the file graph representing a file."""

    id: str  # Relative path from project root
    name: str
    directory: str  # Which santai directory (resources, notes, etc.)
    file_type: str
    size_bytes: int


@dataclass
class GraphEdge:
    """An edge in the file graph representing a link between files."""

    source: str  # Source file id
    target: str  # Target file id
    link_text: str  # The text that was linked


@dataclass
class FileGraph:
    """Graph representation of files and their backlinks."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


@dataclass
class DirectoryStats:
    """Statistics for the project directories."""

    resources_count: int
    codebases_count: int
    history_count: int
    notes_count: int
    total_size_bytes: int
    file_types: dict[str, int]
    recent_files: list[FileInfo]


@dataclass
class SantaiProject:
    """Represents a Santai project."""

    root: Path
    name: str

    @property
    def resources_path(self) -> Path:
        return self.root / "resources"

    @property
    def codebases_path(self) -> Path:
        return self.root / "codebases"

    @property
    def history_path(self) -> Path:
        return self.root / "history"

    @property
    def notes_path(self) -> Path:
        return self.root / "notes"


def is_santai_project(path: Path) -> bool:
    """Check if the given path is a Santai project.

    A Santai project has resources/, codebases/, and history/ directories.
    """
    if not path.is_dir():
        return False

    for dir_name in SANTAI_DIRS:
        if not (path / dir_name).is_dir():
            return False

    return True


def get_project(path: Path | None = None) -> SantaiProject | None:
    """Get the Santai project from the given path or current directory.

    Returns None if the path is not a Santai project.
    """
    if path is None:
        path = Path.cwd()

    path = path.resolve()

    if not is_santai_project(path):
        return None

    return SantaiProject(root=path, name=path.name)


def _count_files_recursive(path: Path) -> int:
    """Count all files recursively in a directory."""
    if not path.is_dir():
        return 0
    return sum(1 for f in path.rglob("*") if f.is_file())


def _get_all_files(path: Path) -> list[FileInfo]:
    """Get all files recursively in a directory."""
    if not path.is_dir():
        return []

    files = []
    for f in path.rglob("*"):
        if f.is_file():
            stat = f.stat()
            files.append(
                FileInfo(
                    path=f,
                    name=f.name,
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                    file_type=f.suffix.lower() if f.suffix else "(no extension)",
                )
            )
    return files


def get_directory_stats(project: SantaiProject) -> DirectoryStats:
    """Get statistics for the project directories."""
    all_files: list[FileInfo] = []

    for dir_name in SANTAI_DIRS:
        dir_path = project.root / dir_name
        all_files.extend(_get_all_files(dir_path))

    # Count files per directory
    resources_count = _count_files_recursive(project.resources_path)
    codebases_count = _count_files_recursive(project.codebases_path)
    history_count = _count_files_recursive(project.history_path)
    notes_count = _count_files_recursive(project.notes_path)

    # Calculate total size
    total_size = sum(f.size_bytes for f in all_files)

    # Count file types
    file_types: dict[str, int] = {}
    for f in all_files:
        file_types[f.file_type] = file_types.get(f.file_type, 0) + 1

    # Get recent files (sorted by modified time, newest first)
    recent_files = sorted(all_files, key=lambda f: f.modified_at, reverse=True)[:10]

    return DirectoryStats(
        resources_count=resources_count,
        codebases_count=codebases_count,
        history_count=history_count,
        notes_count=notes_count,
        total_size_bytes=total_size,
        file_types=file_types,
        recent_files=recent_files,
    )


# Regex pattern for history filenames: YYYY-MM-DD-description.md
HISTORY_FILENAME_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(.+)\.md$")


def parse_history_filename(filename: str) -> tuple[date, str] | None:
    """Parse a history filename into date and title.

    Returns None if the filename doesn't match the expected pattern.
    Expected format: YYYY-MM-DD-description.md
    """
    match = HISTORY_FILENAME_PATTERN.match(filename)
    if not match:
        return None

    year, month, day, description = match.groups()

    try:
        entry_date = date(int(year), int(month), int(day))
    except ValueError:
        return None

    # Convert description to title (replace hyphens with spaces, title case)
    title = description.replace("-", " ").title()

    return entry_date, title


def get_history_entries(project: SantaiProject) -> list[HistoryEntry]:
    """Get all history entries from the project, sorted by date (newest first).

    Only files matching the YYYY-MM-DD-description.md pattern are included.
    """
    history_path = project.history_path
    if not history_path.is_dir():
        return []

    entries = []
    for file_path in history_path.glob("*.md"):
        parsed = parse_history_filename(file_path.name)
        if parsed is None:
            continue

        entry_date, title = parsed
        content = file_path.read_text(encoding="utf-8")

        entries.append(
            HistoryEntry(
                date=entry_date,
                title=title,
                content=content,
                filename=file_path.name,
            )
        )

    # Sort by date, newest first
    entries.sort(key=lambda e: e.date, reverse=True)

    return entries


def _generate_preview(content: str, max_length: int = 200) -> str:
    """Generate a preview from content, stripping markdown formatting."""
    # Remove markdown headers
    lines = content.split("\n")
    text_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip empty lines and headers
        if not stripped or stripped.startswith("#"):
            continue
        # Remove markdown formatting
        stripped = stripped.lstrip("*-•> ")
        if stripped:
            text_lines.append(stripped)

    preview = " ".join(text_lines)
    if len(preview) > max_length:
        preview = preview[: max_length - 3] + "..."
    return preview


def get_notes(project: SantaiProject) -> list[NoteEntry]:
    """Get all notes from the project, sorted by modified time (newest first).

    Supports .md and .txt files in the notes/ directory.
    """
    notes_path = project.notes_path
    if not notes_path.is_dir():
        return []

    entries = []
    for file_path in notes_path.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in (".md", ".txt"):
            continue
        if file_path.name.startswith("."):
            continue

        try:
            stat = file_path.stat()
            content = file_path.read_text(encoding="utf-8")

            # Generate title from filename (remove extension, replace hyphens/underscores)
            title = file_path.stem.replace("-", " ").replace("_", " ").title()

            entries.append(
                NoteEntry(
                    title=title,
                    content=content,
                    preview=_generate_preview(content),
                    filename=str(file_path.relative_to(notes_path)),
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                    size_bytes=stat.st_size,
                )
            )
        except (OSError, UnicodeDecodeError):
            # Skip files that can't be read
            continue

    # Sort by modified time, newest first
    entries.sort(key=lambda e: e.modified_at, reverse=True)

    return entries


# Patterns for detecting links in markdown files
# Matches: [text](path) and [[wikilink]]
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
WIKILINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


def _get_directory_name(file_path: Path, project_root: Path) -> str:
    """Get the santai directory name for a file."""
    try:
        relative = file_path.relative_to(project_root)
        parts = relative.parts
        if parts and parts[0] in SANTAI_DIRS:
            return parts[0]
    except ValueError:
        pass
    return "other"


def _extract_links(content: str) -> list[tuple[str, str]]:
    """Extract all links from markdown content.

    Returns list of (link_text, link_target) tuples.
    """
    links = []

    # Find markdown links [text](path)
    for match in MARKDOWN_LINK_PATTERN.finditer(content):
        link_text = match.group(1)
        link_target = match.group(2)
        # Skip external URLs and anchors
        if not link_target.startswith(("http://", "https://", "mailto:", "#")):
            links.append((link_text, link_target))

    # Find wikilinks [[path]] or [[path|text]]
    for match in WIKILINK_PATTERN.finditer(content):
        link_target = match.group(1)
        links.append((link_target, link_target))

    return links


def _resolve_link(
    link_target: str, source_file: Path, project_root: Path, file_map: dict[str, Path]
) -> str | None:
    """Resolve a link target to a file id (relative path).

    Returns None if the link cannot be resolved to an existing file.
    """
    # Clean up the link target
    link_target = link_target.strip()

    # Remove any URL fragments
    if "#" in link_target:
        link_target = link_target.split("#")[0]

    if not link_target:
        return None

    # Try different resolution strategies
    candidates = []

    # 1. Relative to source file's directory
    source_dir = source_file.parent
    relative_path = source_dir / link_target
    candidates.append(relative_path)

    # 2. Relative to project root
    root_relative = project_root / link_target
    candidates.append(root_relative)

    # 3. Try adding common extensions if no extension
    if not Path(link_target).suffix:
        for ext in [".md", ".txt"]:
            candidates.append(source_dir / (link_target + ext))
            candidates.append(project_root / (link_target + ext))

    # 4. Try matching by filename only (for wikilinks)
    link_name = Path(link_target).name
    if not Path(link_name).suffix:
        link_name_md = link_name + ".md"
        link_name_txt = link_name + ".txt"
        for file_id, file_path in file_map.items():
            if (
                file_path.name == link_name
                or file_path.name == link_name_md
                or file_path.name == link_name_txt
            ):
                return file_id

    # Check candidates
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            if resolved.is_file():
                try:
                    rel_path = resolved.relative_to(project_root)
                    file_id = str(rel_path)
                    if file_id in file_map:
                        return file_id
                except ValueError:
                    pass
        except (OSError, ValueError):
            pass

    return None


def get_file_graph(project: SantaiProject) -> FileGraph:
    """Build a graph of files and their backlinks.

    Scans all markdown and text files in the project directories,
    extracts links, and builds a graph representation.
    """
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    file_map: dict[str, Path] = {}  # file_id -> Path
    file_contents: dict[str, str] = {}  # file_id -> content

    # Collect all text-based files
    text_extensions = {".md", ".txt", ".markdown"}

    for dir_name in SANTAI_DIRS:
        dir_path = project.root / dir_name
        if not dir_path.is_dir():
            continue

        for file_path in dir_path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.name.startswith("."):
                continue

            try:
                relative_path = file_path.relative_to(project.root)
                file_id = str(relative_path)
                stat = file_path.stat()

                # Create node for all files
                nodes.append(
                    GraphNode(
                        id=file_id,
                        name=file_path.name,
                        directory=dir_name,
                        file_type=file_path.suffix.lower()
                        if file_path.suffix
                        else "(no ext)",
                        size_bytes=stat.st_size,
                    )
                )

                file_map[file_id] = file_path

                # Read content for text files (for link extraction)
                if file_path.suffix.lower() in text_extensions:
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        file_contents[file_id] = content
                    except UnicodeDecodeError:
                        pass

            except (OSError, ValueError):
                continue

    # Extract links and create edges
    for source_id, content in file_contents.items():
        source_path = file_map[source_id]
        links = _extract_links(content)

        for link_text, link_target in links:
            target_id = _resolve_link(link_target, source_path, project.root, file_map)
            if target_id and target_id != source_id:  # Don't create self-loops
                edges.append(
                    GraphEdge(
                        source=source_id,
                        target=target_id,
                        link_text=link_text,
                    )
                )

    return FileGraph(nodes=nodes, edges=edges)
