"""Repository context builder for chat sessions.

Provides functions to generate a comprehensive context about the project
that can be injected into chat system prompts, giving AI models awareness
of all files and content in the repository.
"""

from dataclasses import dataclass
from pathlib import Path

from santai_cli.core.project import SantaiProject


@dataclass
class RepoContext:
    """Complete repository context for a Santai project."""

    project: SantaiProject
    file_tree: str
    media_summary: str


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


def _get_resources_summary(project: SantaiProject) -> str:
    """Get a summary of media files and recent notes in the project."""
    summary_parts = []

    media_path = project.root / "media"
    if media_path.is_dir():
        files = [f for f in media_path.rglob("*") if f.is_file()]
        if files:
            summary_parts.append(f"Media ({len(files)} files):")
            for f in sorted(files)[:20]:
                summary_parts.append(f"  - {f.relative_to(media_path)}")

    # Legacy resources/ support while migration is in progress
    resources_path = project.resources_path
    if resources_path.is_dir():
        files = [f for f in resources_path.rglob("*") if f.is_file()]
        if files:
            summary_parts.append(f"Media ({len(files)} files):")
            for f in sorted(files)[:20]:
                summary_parts.append(f"  - {f.relative_to(resources_path)}")

    if not summary_parts:
        return ""

    return f"## Media & Resources\n\n{'=' * 40}\n\n" + "\n".join(summary_parts)


def build_repo_context(project: SantaiProject) -> RepoContext:
    """Build a comprehensive context for a Santai project.

    This function scans the project directory and generates structured
    context including:
    - File tree structure
    - Media summary

    Args:
        project: The Santai project to build context for.

    Returns:
        A RepoContext object containing all project context.
    """
    return RepoContext(
        project=project,
        file_tree=_build_file_tree(project.root),
        media_summary=_get_resources_summary(project),
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
            "Below is its structure — use read_file to get the contents of any file."
        ),
        "",
        "### File Tree",
        f"```\n{context.file_tree}\n```",
    ]

    if context.media_summary:
        sections.extend(["", context.media_summary])

    sections.extend(
        [
            "",
            "## File Organization",
            "This project organizes files into three knowledge-base folders:",
            "- **notes/** — personal notes, summaries, AI research, documentation, how-to guides, tutorials, reference pages",
            "- **media/** — media files, images, audio, video, PDFs, templates, archives, binary data",
            "- **history/** — logs, changelogs, versioned records (use `YYYY-MM-DD-brief-description.md` format)",
            "",
            "**When writing files:**",
            "- Always place files under one of these three folders (e.g. `notes/my-summary.md`, not just `my-summary.md`)",
            "- Choose descriptive, lowercase, hyphenated filenames that reflect the content",
            "- **Proactively expand context**: when a conversation produces knowledge worth preserving — a summary, a research finding, meeting notes, a decision — write it to `notes/` without waiting to be asked",
            "- Keep the original extension when moving or referencing existing files",
            "",
            "## Important Guidelines",
            "- You can see the file tree above, but you do NOT have the file contents in context.",
            "- IMPORTANT: Whenever a user asks a question that could be answered by a file in this project (notes/, media/, history/, or any other file), you MUST call read_file to read the relevant file(s) before answering. Never answer knowledge-base questions from memory — always fetch fresh content with the tool.",
            "- If multiple files might be relevant, read each one before responding.",
            "- Use [[wikilinks]] or markdown links when referencing project files.",
            "- IMPORTANT: If a read_file result includes 'truncated: true', the file was cut off. Acknowledge this to the user rather than treating the partial content as complete.",
        ]
    )

    sections.extend(
        [
            "",
            "## Available Tools",
            "You have access to the following tools. WHEN THE USER ASKS YOU TO CREATE OR WRITE A FILE, YOU MUST USE THE write_file TOOL - DO NOT JUST TELL THEM HOW TO DO IT:",
            "",
            "- **write_file**: Write content to a file. Creates directories as needed.",
            "  Arguments: filepath (string), content (string)",
            "  Example use: write_file(filepath='notes/test.md', content='Hi')",
            "",
            "- **read_file**: Read the contents of a file.",
            "  Arguments: filepath (string)",
            "",
            "- **list_dir**: List files in a directory.",
            "  Arguments: directory (optional, defaults to project root)",
            "",
            "- **mkdir**: Create a directory. Creates parent directories as needed.",
            "  Arguments: path (string)",
            "",
            "- **move**: Move a file or directory to a new location. Prefer this over manually copying and deleting.",
            "  Arguments: source (string), destination (string)",
            "",
            "- **remove_file**: Remove a file.",
            "  Arguments: filepath (string)",
            "",
            "- **remove_dir**: Remove a directory. If empty, deletes immediately. If non-empty, the tool returns a CONFIRM_REQUIRED message — show only that message to the user (do not add any preamble or narration), then wait for confirmation before calling again with confirmed=true.",
            "  Arguments: path (string), confirmed (boolean, optional)",
            "",
            "IMPORTANT: When the user asks you to create, write, or edit a file, use the write_file tool - do not describe how to do it or suggest commands.",
            "IMPORTANT: For remove_dir, call the tool first without narrating — do not say you are about to delete anything. Let the tool result determine what to say.",
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
