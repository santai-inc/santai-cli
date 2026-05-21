"""Chat command for Santai CLI.

Provides an interactive REPL-style chat with AI models (Anthropic, OpenAI)
using Rich for terminal formatting and streaming response display.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from santai_cli.core.chat import ChatSession, stream_response
from santai_cli.core.config import (
    ChatConfig,
    get_agent_profiles,
    load_agent_prompt,
    load_config,
    save_api_keys,
)
from santai_cli.core.project import SantaiProject, get_project
from santai_cli.core.repo_context import build_repo_context, inject_repo_context

console = Console()


@dataclass
class _ChatState:
    """Mutable state for the chat REPL loop."""

    session: ChatSession
    config: ChatConfig
    provider: str
    model: str
    agent: str | None
    project: SantaiProject | None = None


def chat(
    agent: Annotated[
        str | None,
        typer.Option(
            "--agent",
            "-a",
            help="Agent profile name to use as system prompt (e.g. 'code-review').",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help=(
                "Model to use (e.g. 'claude-sonnet-4-20250514', 'gpt-4o')."
                " Skips interactive selection."
            ),
        ),
    ] = None,
) -> None:
    """Start an interactive AI chat session.

    Chat with AI models from your terminal. Requires API keys to be
    configured in a .env file at your project root (see .env.example).

    Use --agent to load an agent profile as the system prompt.

    REPL commands:
      /quit     Exit the chat
      /clear    Clear conversation history
      /agent    List or switch agent profiles
      /model    Re-select the model
      /help     Show available commands
    """
    project = get_project()
    project_root = project.root if project else None

    # Load configuration
    config = load_config(project_root)

    if not config.has_any_provider:
        config = _prompt_api_keys(project_root)
        if config is None:
            raise typer.Exit(1)

    # Load agent system prompt if specified
    system_prompt = None
    active_agent = agent
    if active_agent:
        system_prompt = load_agent_prompt(active_agent)
        if system_prompt is None:
            console.print(f"[red]Agent profile '{active_agent}' not found.[/]")
            _print_available_agents()
            raise typer.Exit(1)

    # Inject repository context if in a Santai project
    if project:
        repo_context = build_repo_context(project)
        system_prompt = inject_repo_context(system_prompt, repo_context)
        console.print(f"[dim]Repository context loaded: {project.root.name}[/]")

    # Select model (interactive or from flag)
    provider, selected_model = _select_model(config, model)
    if provider is None or selected_model is None:
        raise typer.Exit(1)

    # Initialize session
    session = ChatSession(system_prompt=system_prompt)

    # Print welcome
    _print_welcome(config, provider, selected_model, active_agent)

    # Enter REPL loop
    try:
        _repl_loop(session, config, provider, selected_model, active_agent, project)
    except KeyboardInterrupt:
        console.print("\n[dim]Chat ended.[/]")


def _select_model(
    config: ChatConfig, model_flag: str | None
) -> tuple[str | None, str | None]:
    """Select a provider and model, either from flag or interactively.

    Returns (provider, model) tuple, or (None, None) on cancellation.
    """
    if model_flag:
        # Try to auto-detect provider from model name
        return _resolve_model_provider(config, model_flag)

    # Interactive selection
    choices = config.get_model_choices()
    if not choices:
        console.print("[red]No models available.[/]")
        return None, None

    if len(choices) == 1:
        label, provider, model_name = choices[0]
        console.print(f"[dim]Auto-selected: {label}[/]")
        return provider, model_name

    console.print("\n[bold]Select a model:[/]\n")
    for i, (label, _, _) in enumerate(choices, 1):
        console.print(f"  [cyan]{i}[/]) {label}")
    console.print()

    while True:
        selection = Prompt.ask(
            "Enter number",
            default="1",
        )
        try:
            idx = int(selection) - 1
            if 0 <= idx < len(choices):
                _, provider, model_name = choices[idx]
                return provider, model_name
        except ValueError:
            pass
        console.print(f"[red]Please enter a number between 1 and {len(choices)}.[/]")


def _prompt_api_keys(project_root: Path | None) -> ChatConfig | None:
    """Interactively prompt the user for API keys and save them to .env.

    Asks for Anthropic and OpenAI keys one at a time, writes them to the
    project's .env file, reloads config, and returns it. Returns None if
    the user skips both providers.
    """
    console.print(
        Panel(
            "[bold]No API keys configured.[/]\n\n"
            "Let's set one up. Enter your API key(s) below.\n"
            "Press [cyan]Enter[/] to skip a provider.",
            title="Chat Setup",
            border_style="cyan",
        )
    )
    console.print()

    anthropic_key = Prompt.ask(
        "  [bold]Anthropic[/] API key",
        password=True,
        default="",
    ).strip()

    openai_key = Prompt.ask(
        "  [bold]OpenAI[/] API key",
        password=True,
        default="",
    ).strip()

    if not anthropic_key and not openai_key:
        console.print(
            "\n[red]No keys provided.[/] At least one API key is required.\n"
            "See [cyan].env.example[/] for the full template."
        )
        return None

    env_path = save_api_keys(
        project_root,
        anthropic_key=anthropic_key,
        openai_key=openai_key,
    )
    console.print(f"\n[green]API key(s) saved to {env_path}[/]\n")

    # Reload config so the rest of the chat flow picks up the new keys
    return load_config(project_root)


def _resolve_model_provider(
    config: ChatConfig, model_name: str
) -> tuple[str | None, str | None]:
    """Resolve which provider a model belongs to."""
    # Check if it matches a known model in any configured provider
    for provider_name, provider_config in config.providers.items():
        if model_name in provider_config.available_models:
            return provider_name, model_name

    # Heuristic: claude -> anthropic, gpt/o3 -> openai
    model_lower = model_name.lower()
    if "claude" in model_lower and "anthropic" in config.providers:
        return "anthropic", model_name
    if (
        any(prefix in model_lower for prefix in ("gpt", "o3", "o1"))
        and "openai" in config.providers
    ):
        return "openai", model_name

    # If only one provider is configured, use it
    if len(config.providers) == 1:
        provider_name = next(iter(config.providers))
        return provider_name, model_name

    console.print(
        f"[red]Cannot determine provider for model '{model_name}'.[/]\n"
        "[dim]Use interactive selection or specify a recognized model name.[/]"
    )
    return None, None


def _print_welcome(
    config: ChatConfig,
    provider: str,
    model: str,
    agent: str | None,
) -> None:
    """Print the welcome banner when chat starts."""
    provider_display = config.providers[provider].name
    info_lines = [
        f"[bold]Provider:[/] {provider_display}",
        f"[bold]Model:[/]    {model}",
    ]
    if agent:
        info_lines.append(f"[bold]Agent:[/]    {agent}")

    info_lines.append("")
    info_lines.append("[dim]Type /help for commands, /quit to exit.[/]")

    console.print(
        Panel(
            "\n".join(info_lines),
            title="[bold cyan]Santai Chat[/]",
            border_style="cyan",
        )
    )
    console.print()


def _print_available_agents() -> None:
    """Print a list of available agent profiles."""
    profiles = get_agent_profiles()
    if not profiles:
        console.print("[dim]No agent profiles found.[/]")
        return

    console.print("\n[bold]Available agents:[/]\n")
    for name, description in profiles:
        desc_text = f" — {description}" if description else ""
        console.print(f"  [cyan]{name}[/]{desc_text}")
    console.print()


def _repl_loop(
    session: ChatSession,
    config: ChatConfig,
    provider: str,
    model: str,
    agent: str | None,
    project: SantaiProject | None = None,
) -> None:
    """Main REPL loop for the chat."""
    state = _ChatState(
        session=session,
        config=config,
        provider=provider,
        model=model,
        agent=agent,
        project=project,
    )

    while True:
        try:
            user_input = Prompt.ask("[bold green]You[/]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Chat ended.[/]")
            return

        user_input = user_input.strip()
        if not user_input:
            continue

        # Handle REPL commands
        if user_input.startswith("/"):
            if _handle_command(user_input, state) == "quit":
                return
            continue

        # Add user message and get streaming response
        state.session.add_user_message(user_input)

        console.print()
        full_response = _stream_assistant_response(state)

        if full_response is not None:
            state.session.add_assistant_message(full_response)
        else:
            # Remove the user message if the response failed
            state.session.messages.pop()

        console.print()


def _handle_command(command: str, state: _ChatState) -> str:
    """Handle a REPL slash command. Mutates state in place.

    Returns 'quit' to exit the REPL, or 'continue' to keep going.
    """
    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else None

    if cmd in ("/quit", "/exit", "/q"):
        console.print("[dim]Goodbye![/]")
        return "quit"

    elif cmd == "/clear":
        state.session.clear()
        console.print("[dim]Conversation cleared.[/]\n")

    elif cmd == "/help":
        console.print(
            Panel(
                "[cyan]/quit[/]          Exit the chat\n"
                "[cyan]/clear[/]         Clear conversation history\n"
                "[cyan]/agent[/]         List agents, or /agent <name> to switch\n"
                "[cyan]/model[/]         Re-select the model\n"
                "[cyan]/help[/]          Show this help message",
                title="Commands",
                border_style="dim",
            )
        )

    elif cmd == "/agent":
        if arg:
            new_prompt = load_agent_prompt(arg)
            if new_prompt is None:
                console.print(f"[red]Agent '{arg}' not found.[/]")
                _print_available_agents()
            else:
                if state.project:
                    repo_context = build_repo_context(state.project)
                    new_prompt = inject_repo_context(new_prompt, repo_context)
                state.session = ChatSession(system_prompt=new_prompt)
                state.agent = arg
                console.print(f"[dim]Switched to agent: {arg}. History cleared.[/]\n")
        else:
            _print_available_agents()

    elif cmd == "/model":
        new_provider, new_model = _select_model(state.config, None)
        if new_provider and new_model:
            state.provider = new_provider
            state.model = new_model
            provider_name = state.config.providers[new_provider].name
            console.print(f"[dim]Switched to {provider_name}: {new_model}[/]\n")

    else:
        console.print(f"[red]Unknown command: {cmd}[/]. Type /help for options.\n")

    return "continue"


def _stream_assistant_response(state: _ChatState) -> str | None:
    """Stream the assistant response to the terminal with Rich formatting.

    Returns the full response text, or None on error.
    """
    provider_config = state.config.providers[state.provider]
    full_text = ""

    try:
        label = Text.assemble(("Assistant", "bold cyan"))
        console.print(label)

        # Use Live display with markdown rendering for streaming
        with Live(
            Markdown(" "),
            console=console,
            refresh_per_second=12,
            vertical_overflow="visible",
        ) as live:

            async def _run_stream() -> str:
                nonlocal full_text
                async for chunk in stream_response(
                    state.session,
                    state.provider,
                    provider_config,
                    state.model,
                ):
                    if not isinstance(chunk, str):
                        continue
                    full_text += chunk
                    live.update(Markdown(full_text))
                return full_text

            full_text = asyncio.run(_run_stream())

        return full_text

    except KeyboardInterrupt:
        console.print("\n[dim]Response interrupted.[/]")
        return full_text if full_text else None

    except Exception as e:
        error_msg = str(e)
        # Provide friendlier messages for common errors
        if "401" in error_msg or "authentication" in error_msg.lower():
            console.print("[red]Authentication failed.[/] Check your API key in .env")
        elif "429" in error_msg or "rate" in error_msg.lower():
            console.print("[red]Rate limited.[/] Wait a moment and try again.")
        elif "model" in error_msg.lower() and "not found" in error_msg.lower():
            console.print(
                f"[red]Model '{state.model}' not found.[/]"
                " Use /model to select another."
            )
        else:
            console.print(f"[red]Error:[/] {error_msg}")
        return None
