# Use Cases

Practical workflows and recipes for getting the most out of Santai CLI.

## Starting a New Research Project

Set up a structured workspace for a research effort:

```bash
# Create the project
santai init api-migration-research
cd api-migration-research

# Add reference materials
cp ~/specs/current-api.md media/
cp ~/specs/target-api.md media/

# Set up AI chat for research
cp .env.example .env
# Edit .env with your API keys

# Start researching with the research agent
santai chat --agent research
```

## Documenting Architecture Decisions

Use the history directory and AI agents to create a decision log:

```bash
# Start a chat session with the documentation agent
santai chat --agent documentation --model claude-sonnet-4-6
```

In the chat, ask it to write a history entry:

```
You: Write a history entry for today about our decision to use PostgreSQL 
     over MongoDB. Key reasons: ACID compliance, existing team expertise, 
     and better support for relational data in our domain model.
```

The agent will create a properly formatted `history/YYYY-MM-DD-description.md` file.

## Building a Project Knowledge Base

Incrementally capture knowledge that serves as ground truth for AI agents:

```bash
# Research a topic
santai chat --agent research
# "What are our deployment environments and how do they differ?"

# Capture findings in media/
santai chat --agent documentation
# "Create a media/ entry documenting our deployment environments"

# Review quality
santai chat --agent linting
# "Check the project for completeness and consistency"
```

## Onboarding to an Existing Project

When joining a project that already has Santai structure:

```bash
cd existing-project

# Get a quick overview
santai chat --agent summarizer
# "Give me a complete overview of this project"
# "Summarize the last 10 history entries"
# "What's in media/?"

# Browse visually
santai ui

# Or in the browser
santai web
```

## Cherry-Picking Between Knowledge Bases

When you need specific files from one project in another without merging everything:

```bash
# Preview what you'd get
santai cherry-pick ./large-kb ./focused-kb media/architecture.md notes/ --dry-run

# Copy the files
santai cherry-pick ./large-kb ./focused-kb media/architecture.md notes/

# Copy an entire directory, overwriting conflicts
santai cherry-pick ./research ./writing media/ --overwrite
```

This is particularly useful when:

- Splitting a large KB into focused sub-projects
- Sharing specific reference materials across projects
- Pulling in shared context from a team KB into a personal one

## Merging Two Research Streams

When separate research efforts need to be combined:

```bash
# Both must be valid Santai projects
santai merge frontend-research backend-research combined-research
```

After merging, review what was combined:

```bash
cd combined-research
santai ui
```

!!! note
    The merge command reports which files were skipped due to conflicts. Check the output and manually reconcile any important files that were in both projects.

## Forking a Project for a New Phase

Create a clean copy when starting a new phase of work:

```bash
santai copy current-project phase-2-project
cd phase-2-project

# Add a history entry marking the fork
echo "# Phase 2 Kickoff\nForked from phase 1 project to begin implementation." \
  > history/2025-04-17-phase-2-kickoff.md
```

## Cloud Sync Workflow

Push your project to Santai Hub for backup or sharing, and pull it on another machine:

```bash
# Authenticate (one-time setup)
santai login

# Push your project
cd my-project
santai push

# On another machine, pull it down
santai login
santai pull my-project
```

## Quick Notes Workflow

Use the notes directory as scratch space during research:

```bash
cd my-project

# Quick note from the command line
echo "# Idea: Use webhooks instead of polling\nCould reduce API calls by 90%" \
  > notes/webhook-idea.md

# Add notes interactively in the TUI
santai ui
# Press 'n' to add a new note

# Review all notes
santai ui  # Check the notes panel
```

## Exploring File Relationships

The file graph visualization tracks links between your documents:

1. Add cross-references in your markdown files using standard links:
    ```markdown
    See [Architecture Overview](../media/architecture.md) for context.
    Related: [[deployment-process]]
    ```

2. View the graph:
    ```bash
    santai ui  # Press 'g' for fullscreen graph
    # or
    santai web  # Graph panel in the dashboard
    ```

3. Search and filter the graph:
    - Press `/` to search for specific files
    - Press `f` to filter by directory (e.g., show only media/ links)

The graph detects both standard markdown links and wikilinks (`[[page]]` and `[[page|display text]]`).

## Multi-Model Comparison

Compare responses from different AI models on the same question:

```bash
# Ask Anthropic
santai chat --model claude-sonnet-4-6
# Ask your question, note the response, then /quit

# Ask OpenAI
santai chat --model gpt-4o
# Ask the same question, compare responses
```

## Content Quality Audit

Run a quality check across your entire project:

```bash
santai chat --agent linting
```

In the chat:

```
You: Audit the entire project. Check:
     - History entry filename conventions
     - Markdown formatting quality
     - Cross-references between documents
     - Notes that should be promoted to history
```

The linting agent will report issues with Error, Warning, and Info severity levels.
