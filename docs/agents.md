# Agent Profiles

Agent profiles are specialized system prompts that shape how the AI assistant behaves during `santai chat` sessions. Each agent is tuned for a specific workflow within your Santai project.

## Using Agents

Load an agent when starting a chat:

```bash
santai chat --agent research
```

Or switch agents mid-session with the `/agent` command:

```
You: /agent wiki
Switched to agent: wiki
Conversation history cleared.
```

List available agents:

```
You: /agent
```

## Built-in Agents

### documentation

Creates and maintains structured documentation across Santai project directories.

- **Permissions**: Can edit files and run commands
- **Use for**: Writing history entries, wiki pages, resource documentation, and project-level docs
- **Example**: "Write a history entry summarizing today's architecture discussion"

### linting

Enforces content quality and consistency across project files.

- **Permissions**: Can edit files and run commands
- **Use for**: Checking markdown quality, history file naming conventions, notes formatting, wiki consistency, and cross-directory coherence
- **Reports issues as**: Error, Warning, or Info severity levels
- **Example**: "Review all my history entries for formatting issues"

### research

Investigates topics and gathers context for project knowledge bases.

- **Permissions**: Read-only (cannot edit files), can run commands and access the web
- **Use for**: Technology evaluation, domain investigation, codebase analysis, context recovery, and external research
- **Example**: "What are the tradeoffs between REST and GraphQL for our use case?"

### summarizer

Condenses project context into clear, actionable summaries.

- **Permissions**: Read-only (cannot edit files), can run commands
- **Use for**: Project overviews, history summaries, notes triage, resource digests, wiki summaries, and cross-directory synthesis
- **Example**: "Summarize the last month of history entries"

### wiki

Curates and maintains the `wiki/` directory as the single source of truth for AI agent context.

- **Permissions**: Can edit files and run commands
- **Use for**: Managing architecture docs, conventions, domain knowledge, and operational context in the wiki
- **Example**: "Create a wiki page documenting our deployment process"

## Agent Categories

| Category | Agents | Can modify files? |
|----------|--------|-------------------|
| Content-modifying | documentation, linting, wiki | Yes |
| Read-only | research, summarizer | No |

## Recommended Workflows

### Knowledge Capture

```
research → documentation → wiki
```

1. Use `research` to investigate a topic
2. Use `documentation` to write up findings as a history entry or resource
3. Use `wiki` to distill key takeaways into the wiki

### Project Onboarding

Use `summarizer` to quickly understand an existing project:

```bash
santai chat --agent summarizer
```

Ask it to give you an overview of the project, summarize recent history, or triage notes.

### Content Quality Audit

Use `linting` to review your project's content:

```bash
santai chat --agent linting
```

Ask it to check history entry formatting, note quality, or wiki completeness.

### Decision Documentation

```
research → documentation
```

1. Use `research` to analyze options
2. Use `documentation` to record the decision as a dated history entry

## Creating Custom Agents

Agent profiles are markdown files in the `agents/` directory of the Santai CLI package. Each file has YAML frontmatter:

```yaml
---
description: Brief description of what this agent does
mode: subagent
permission:
  edit: allow    # or deny
  bash: allow    # or deny
  web: allow     # or deny
---

Your system prompt content goes here.
Describe the agent's role, capabilities, and behavior.
```

The `description` field appears in the agent listing. The body of the markdown file becomes the system prompt sent to the AI model.
