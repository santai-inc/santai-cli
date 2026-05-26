"""Project detection and data loading for Santai projects."""

import contextlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

# Canonical Santai directories. These are recommended (created by `santai init`)
# but not enforced — projects are free to add, rename, or omit them.
SANTAI_DIRS = ["media", "history", "notes"]

# Single source of truth for what each folder is for.
# Consumed by both the smart-place AI prompt (app.py) and the chat system
# prompt (repo_context.py) so they never drift.
SANTAI_FOLDER_DESCRIPTIONS: dict[str, str] = {
    "notes": (
        "personal notes, summaries, AI research, documentation, "
        "how-to guides, tutorials, reference pages"
    ),
    "media": (
        "media files, images, audio, video, PDFs, templates, archives, binary data"
    ),
    "history": "logs, changelogs, versioned records",
}


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
    directory: str  # Which santai directory (media, notes, etc.)
    file_type: str
    size_bytes: int


@dataclass
class GraphEdge:
    """An edge in the file graph representing a link between files."""

    source: str  # Source file id
    target: str  # Target file id
    link_text: str = ""  # The text that was linked
    edge_type: str = field(default="reference")  # "reference" or "semantic"


@dataclass
class FileGraph:
    """Graph representation of files and their backlinks."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


@dataclass
class DirectoryStats:
    """Statistics for the project directories."""

    media_count: int
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
    def media_path(self) -> Path:
        return self.root / "media"

    @property
    def history_path(self) -> Path:
        return self.root / "history"

    @property
    def notes_path(self) -> Path:
        return self.root / "notes"


def get_project(path: Path | None = None) -> SantaiProject | None:
    """Get the Santai project at the given path or current directory.

    Any existing directory is treated as a project — the canonical media/,
    history/, and notes/ layout is recommended but not enforced.
    """
    if path is None:
        path = Path.cwd()

    path = path.resolve()

    if not path.is_dir():
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
    media_count = _count_files_recursive(project.media_path)
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
        media_count=media_count,
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

            # Generate title from filename
            # (remove extension, replace hyphens/underscores)
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
WIKILINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


_SKIP_DIRS = frozenset({"__pycache__", "node_modules", ".venv", "venv", ".git"})

# Project meta-files that should never appear as graph nodes
_GRAPH_EXCLUDE_NAMES_LOWER = frozenset(
    {
        "agents.md",
        "claude.md",
        "readme.md",
        "readme.rst",
        "rumdl.toml",
    }
)


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


_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "by",
        "can",
        "did",
        "do",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "him",
        "his",
        "how",
        "if",
        "in",
        "is",
        "it",
        "its",
        "my",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "she",
        "so",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "up",
        "was",
        "we",
        "were",
        "what",
        "when",
        "which",
        "who",
        "will",
        "with",
        "would",
        "you",
        "your",
        "very",
        "also",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "one",
        "other",
        "same",
        "such",
        "about",
        "but",
        "into",
        "here",
        "just",
        "over",
        "only",
    }
)

_MARKDOWN_STRIP = re.compile(
    r"```.*?```|`[^`]+`|\[([^\]]+)\]\([^)]+\)"
    r"|\[\[([^\]|]+)(?:\|[^\]]+)?\]\]|#{1,6} |[*_~]",
    re.DOTALL,
)


def _tokenize(text: str) -> list[str]:
    """Strip markdown syntax and return meaningful lowercase words (min 3 chars)."""
    cleaned = _MARKDOWN_STRIP.sub(lambda m: m.group(1) or m.group(2) or " ", text)
    words = re.findall(r"[a-z]{3,}", cleaned.lower())
    return [w for w in words if w not in _STOP_WORDS]


def _tfidf_vectors(
    file_contents: dict[str, str],
) -> dict[str, dict[str, float]]:
    """Return a TF-IDF vector (sparse dict) per file id."""
    doc_terms: dict[str, Counter] = {}
    for file_id, content in file_contents.items():
        tokens = _tokenize(content)
        if len(tokens) >= 20:  # skip very short files
            doc_terms[file_id] = Counter(tokens)

    n = len(doc_terms)
    if n < 2:
        return {}

    df: Counter = Counter()
    for terms in doc_terms.values():
        df.update(terms.keys())

    # Smoothed IDF: log((1+n)/(1+df)) + 1  — keeps shared terms at reduced weight
    # instead of zeroing them out, which breaks small corpora (e.g. n=2).
    idf = {term: math.log((1 + n) / (1 + count)) + 1.0 for term, count in df.items()}

    vectors: dict[str, dict[str, float]] = {}
    for file_id, terms in doc_terms.items():
        total = sum(terms.values())
        vectors[file_id] = {
            term: (count / total) * idf[term] for term, count in terms.items()
        }
    return vectors


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    dot = sum(a.get(t, 0.0) * v for t, v in b.items())
    if dot == 0.0:
        return 0.0
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0


def _name_tokens(filename: str) -> set[str]:
    """Extract meaningful alpha tokens from a filename (no extension, no digits)."""
    stem = Path(filename).stem.lower()
    words = re.findall(r"[a-z]{3,}", stem)
    return {w for w in words if w not in _STOP_WORDS}


def _compute_name_edges(
    nodes: list[GraphNode],
    existing_pairs: set[tuple[str, str]],
) -> list[GraphEdge]:
    """Connect files that share significant filename tokens (e.g. assignment series)."""
    token_to_ids: dict[str, list[str]] = {}
    for node in nodes:
        for token in _name_tokens(node.name):
            token_to_ids.setdefault(token, []).append(node.id)

    edges: list[GraphEdge] = []
    # Normalize to sorted pairs so direction-sensitive existing_pairs don't miss dedup
    seen = {(min(a, b), max(a, b)) for a, b in existing_pairs}
    for node_ids in token_to_ids.values():
        if len(node_ids) < 2:
            continue
        for i, id_a in enumerate(node_ids):
            for id_b in node_ids[i + 1 :]:
                pair = (min(id_a, id_b), max(id_a, id_b))
                if pair in seen:
                    continue
                seen.add(pair)
                edges.append(GraphEdge(source=id_a, target=id_b, edge_type="name"))
    return edges


def _compute_semantic_edges(
    file_contents: dict[str, str],
    existing_pairs: set[tuple[str, str]],
    threshold: float = 0.15,
    max_per_node: int = 3,
) -> list[GraphEdge]:
    """Add semantic edges between topically related files that lack explicit links."""
    vectors = _tfidf_vectors(file_contents)
    ids = list(vectors.keys())

    # Score all candidate pairs
    scored: list[tuple[float, str, str]] = []
    for i, id_a in enumerate(ids):
        for id_b in ids[i + 1 :]:
            if (id_a, id_b) in existing_pairs or (id_b, id_a) in existing_pairs:
                continue
            sim = _cosine(vectors[id_a], vectors[id_b])
            if sim >= threshold:
                scored.append((sim, id_a, id_b))

    scored.sort(key=lambda x: x[0], reverse=True)

    budget: Counter = Counter()
    edges: list[GraphEdge] = []
    for sim, id_a, id_b in scored:
        if budget[id_a] >= max_per_node or budget[id_b] >= max_per_node:
            continue
        edges.append(
            GraphEdge(
                source=id_a,
                target=id_b,
                link_text=f"~{sim:.2f}",
                edge_type="semantic",
            )
        )
        budget[id_a] += 1
        budget[id_b] += 1

    return edges


def _add_file_to_graph(
    file_path: Path,
    directory: str,
    project_root: Path,
    nodes: list[GraphNode],
    file_map: dict[str, Path],
    file_contents: dict[str, str],
    text_extensions: set[str],
) -> None:
    """Add a single file to the graph data structures."""
    if file_path.name.lower() in _GRAPH_EXCLUDE_NAMES_LOWER:
        return
    try:
        relative_path = file_path.relative_to(project_root)
        file_id = str(relative_path)
        stat = file_path.stat()

        nodes.append(
            GraphNode(
                id=file_id,
                name=file_path.name,
                directory=directory,
                file_type=file_path.suffix.lower() if file_path.suffix else "(no ext)",
                size_bytes=stat.st_size,
            )
        )
        file_map[file_id] = file_path

        if file_path.suffix.lower() in text_extensions:
            with contextlib.suppress(UnicodeDecodeError):
                file_contents[file_id] = file_path.read_text(encoding="utf-8")

    except (OSError, ValueError):
        pass


def get_file_graph(project: SantaiProject) -> FileGraph:
    """Build a graph of files and their backlinks.

    Scans all files in the project: known santai dirs, root-level files
    (shown as "unassigned"), and any other root-level subdirectories.
    """
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    file_map: dict[str, Path] = {}  # file_id -> Path
    file_contents: dict[str, str] = {}  # file_id -> content

    text_extensions = {
        ".md",
        ".txt",
        ".markdown",
        # Code files — tokenizer extracts identifiers and comments
        ".py",
        ".cpp",
        ".cc",
        ".cxx",
        ".c",
        ".h",
        ".hpp",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".rb",
        ".go",
        ".rs",
        ".cs",
        ".swift",
        ".kt",
        ".scala",
        ".sql",
        ".sh",
        # Markup / config / data — often contain meaningful prose or keys
        ".html",
        ".htm",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".xml",
        ".csv",
    }

    # Known santai subdirectories
    for dir_name in SANTAI_DIRS:
        dir_path = project.root / dir_name
        if not dir_path.is_dir():
            continue

        for file_path in dir_path.rglob("*"):
            if not file_path.is_file() or file_path.name.startswith("."):
                continue
            _add_file_to_graph(
                file_path,
                dir_name,
                project.root,
                nodes,
                file_map,
                file_contents,
                text_extensions,
            )

    # Root-level files (directly in project root) → "unassigned"
    # Plus non-SANTAI, non-hidden root subdirectories
    santai_and_skip = set(SANTAI_DIRS) | _SKIP_DIRS
    for entry in project.root.iterdir():
        if entry.name.startswith("."):
            continue
        if entry.is_file():
            _add_file_to_graph(
                entry,
                "unassigned",
                project.root,
                nodes,
                file_map,
                file_contents,
                text_extensions,
            )
        elif entry.is_dir() and entry.name not in santai_and_skip:
            for file_path in entry.rglob("*"):
                if not file_path.is_file() or file_path.name.startswith("."):
                    continue
                _add_file_to_graph(
                    file_path,
                    entry.name,
                    project.root,
                    nodes,
                    file_map,
                    file_contents,
                    text_extensions,
                )

    # Extract links and create reference edges — only from prose/markdown files,
    # not code files (whose [text](url) in comments isn't meaningful graph structure)
    _prose_extensions = {".md", ".txt", ".markdown"}
    for source_id, content in file_contents.items():
        source_path = file_map[source_id]
        if source_path.suffix.lower() not in _prose_extensions:
            continue
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

    # Add semantic edges for topically related files with no explicit link
    existing_pairs = {(e.source, e.target) for e in edges}
    edges.extend(_compute_semantic_edges(file_contents, existing_pairs))

    # Add name-based edges for files sharing significant filename tokens
    existing_pairs = {(e.source, e.target) for e in edges}
    edges.extend(_compute_name_edges(nodes, existing_pairs))

    return FileGraph(nodes=nodes, edges=edges)
