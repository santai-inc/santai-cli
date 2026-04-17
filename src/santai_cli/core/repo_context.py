"""Repository context builder for chat sessions.

Provides functions to generate a comprehensive context about the project
that can be injected into chat system prompts, giving AI models awareness
of all files and content in the repository.
"""

from dataclasses import dataclass
from pathlib import Path

from santai_cli.core.project import (
    SantaiProject,
    get_history_entries,
    get_notes,
)


@dataclass
class RepoContext:
    """Complete repository context for a Santai project."""

    project: SantaiProject
    file_tree: str
    wiki_content: str
    notes_content: str
    history_content: str
    resources_summary: str


def _build_file_tree(root: Path, max_depth: int = 4) -> str:
    """Build a tree representation of the project directory.

    Args:
        root: The root directory to tree.
        max_depth: Maximum depth to traverse.

    Returns:
        A string representation of the directory tree.
    """
    lines = [f"{root.name}/"]

    def _walk(path: Path, prefix: str = "", depth: int = 0) -> list[str]:
        if depth >= max_depth:
            return []

        try:
            entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        except PermissionError:
            return []

        result = []
        entries = [e for e in entries if not e.name.startswith(".")]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            current_prefix = "└── " if is_last else "├── "
            result.append(f"{prefix}{current_prefix}{entry.name}")

            if entry.is_dir():
                extension = "    " if is_last else "│   "
                result.extend(_walk(entry, prefix + extension, depth + 1))

        return result

    lines.extend(_walk(root))
    return "\n".join(lines)


def _format_wiki_content(project: SantaiProject, max_entries: int = 10) -> str:
    """Format wiki entries for context.

    Args:
        project: The Santai project.
        max_entries: Maximum number of wiki entries to include.

    Returns:
        Formatted wiki content string.
    """
    wiki_path = project.wiki_path
    if not wiki_path.is_dir():
        return ""

    entries = []
    for file_path in sorted(wiki_path.glob("*.md"))[:max_entries]:
        try:
            content = file_path.read_text(encoding="utf-8")
            title = file_path.stem.replace("-", " ").replace("_", " ").title()
            preview = content[:500] + "..." if len(content) > 500 else content
            entries.append(f"## {title}\n{preview}\n")
        except (OSError, UnicodeDecodeError):
            continue

    if not entries:
        return ""

    return f"## Wiki Content\n\n{'=' * 40}\n\n" + "\n\n".join(entries)


def _format_notes_content(project: SantaiProject, max_entries: int = 10) -> str:
    """Format note entries for context.

    Args:
        project: The Santai project.
        max_entries: Maximum number of notes to include.

    Returns:
        Formatted notes content string.
    """
    notes = get_notes(project)
    if not notes:
        return ""

    entries = []
    for note in notes[:max_entries]:
        preview = note.preview if note.preview else note.content[:300]
        entries.append(f"## {note.title}\n{preview}\n")

    return f"## Notes\n\n{'=' * 40}\n\n" + "\n\n".join(entries)


def _format_history_content(project: SantaiProject, max_entries: int = 10) -> str:
    """Format history entries for context.

    Args:
        project: The Santai project.
        max_entries: Maximum number of history entries to include.

    Returns:
        Formatted history content string.
    """
    history = get_history_entries(project)
    if not history:
        return ""

    entries = []
    for entry in history[:max_entries]:
        content = entry.content
        preview = content[:500] + "..." if len(content) > 500 else content
        entries.append(f"## {entry.title} ({entry.date})\n{preview}\n")

    return f"## History\n\n{'=' * 40}\n\n" + "\n\n".join(entries)


def _get_resources_summary(project: SantaiProject) -> str:
    """Get a summary of resources in the project.

    Args:
        project: The Santai project.

    Returns:
        Summary string of resources.
    """
    resources_path = project.resources_path
    codebases_path = project.codebases_path

    summary_parts = []

    if resources_path.is_dir():
        files = [f for f in resources_path.rglob("*") if f.is_file()]
        if files:
            summary_parts.append(f"Resources ({len(files)} files):")
            for f in sorted(files)[:20]:
                rel = f.relative_to(resources_path)
                summary_parts.append(f"  - {rel}")

    if codebases_path.is_dir():
        repos = [d for d in codebases_path.iterdir() if d.is_dir()]
        if repos:
            summary_parts.append(f"\nCodebases ({len(repos)} repositories):")
            for repo in sorted(repos)[:10]:
                summary_parts.append(f"  - {repo.name}/")

    if not summary_parts:
        return ""

    return f"## Resources Summary\n\n{'=' * 40}\n\n" + "\n".join(summary_parts)


def build_repo_context(project: SantaiProject) -> RepoContext:
    """Build a comprehensive context for a Santai project.

    This function scans the project directory and generates structured
    context including:
    - File tree structure
    - Wiki content (most recent entries)
    - Notes content (most recent entries)
    - History content (most recent entries)
    - Resources summary

    Args:
        project: The Santai project to build context for.

    Returns:
        A RepoContext object containing all project context.
    """
    return RepoContext(
        project=project,
        file_tree=_build_file_tree(project.root),
        wiki_content=_format_wiki_content(project),
        notes_content=_format_notes_content(project),
        history_content=_format_history_content(project),
        resources_summary=_get_resources_summary(project),
    )


def build_repo_context_prompt(context: RepoContext) -> str:
    """Build a system prompt segment with repository context.

    This generates a formatted prompt that provides the AI model with
    awareness of the entire repository structure and key content.

    Args:
        context: The pre-built repository context.

    Returns:
        A formatted string suitable for inclusion in a system prompt.
    """
    sections = [
        "## Repository Context",
        "",
        (
            "You have access to this Santai project. "
            "Below is its structure and key content:"
        ),
        "",
        "### File Tree",
        f"```\n{context.file_tree}\n```",
    ]

    if context.wiki_content:
        sections.extend(["", context.wiki_content])

    if context.notes_content:
        sections.extend(["", context.notes_content])

    if context.history_content:
        sections.extend(["", context.history_content])

    if context.resources_summary:
        sections.extend(["", context.resources_summary])

    sections.extend(
        [
            "",
            "## Important Guidelines",
            "- You have full visibility into this project's structure and content.",
            "- When answering questions, reference relevant files and content from above.",
            "- Use [[wikilinks]] or markdown links when referencing project files.",
        ]
    )

    return "\n".join(sections)


def inject_repo_context(session_system_prompt: str | None, context: RepoContext) -> str:
    """Inject repository context into a system prompt.

    If an existing system prompt is provided, the repo context is appended
    to it. If no system prompt exists, only the repo context is returned.

    Args:
        session_system_prompt: Optional existing system prompt.
        context: The repository context to inject.

    Returns:
        The combined system prompt with repository context.
    """
    repo_prompt = build_repo_context_prompt(context)

    if not session_system_prompt:
        return repo_prompt

    return f"{session_system_prompt}\n\n{repo_prompt}"
