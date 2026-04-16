# Agent Registry

This directory contains agent definitions purpose-built for Santai project workflows. Each agent understands the santai directory structure and is specialized for a specific aspect of context management.

## Available Agents

### Context Management

- **[wiki.md](wiki.md)** - Curates the wiki/ directory as the authoritative source of project knowledge
- **[documentation.md](documentation.md)** - Creates and maintains documentation across all santai directories
- **[summarizer.md](summarizer.md)** - Condenses project context into clear, actionable summaries
- **[research.md](research.md)** - Investigates topics and gathers context for the project knowledge base

### Quality

- **[linting.md](linting.md)** - Enforces content quality and consistency across santai project files

## Usage

These agent definitions are designed to be used **directly** as subagents in Claude Code, OpenAI, and other AI tools.

### Quick Start

Tell your AI assistant to use an agent definition:

```
"Use agents/wiki.md as a subagent to organize our project knowledge"
"Spawn a subagent from agents/research.md to investigate this topic"
"Act as the agent defined in agents/summarizer.md to summarize recent history"
```

The AI tool will read the markdown file and operate as that specialized agent.

See [HOW_TO_USE.md](HOW_TO_USE.md) for detailed examples.

### Agent Definition Format

Each agent includes:

```markdown
---
description: Brief description of the agent's purpose
mode: subagent
permission:
  edit: allow/deny
  bash: allow/deny
  web: allow/deny
---

[Detailed system instructions and focus areas]
```

### Permission Levels

- **edit**: Whether the agent can modify files
- **bash**: Whether the agent can execute shell commands
- **web**: Whether the agent can access web resources

### Creating Custom Agents

Developers should create their own agents for context-specific needs in their own repositories. To create a new agent:

1. Create a new `.md` file in this directory
2. Add the required frontmatter (description, mode, permissions)
3. Write detailed system instructions grounded in the santai directory structure
4. Define focus areas and workflows
5. Include examples where helpful

## Agent Categories

### Read-Only Agents
Agents that analyze and provide information without making changes:
- Research, Summarizer

### Content-Modifying Agents
Agents that can create and edit project files:
- Wiki, Documentation, Linting

### Typical Workflows

1. **Knowledge capture**: Research -> Documentation -> Wiki
2. **Project onboarding**: Summarizer (produce overview from all directories)
3. **Content quality**: Linting (scan all directories for issues)
4. **Decision recording**: Research -> Documentation (write history entry)
5. **Context grounding**: Wiki (curate key knowledge for AI agents)

## Related Resources

- [Main Project README](../README.md)
- Issue Tracker: [GitHub Issues](https://github.com/santai-inc/santai-cli/issues)

## License

These agent definitions are part of the santai-cli project and follow the project's license terms.
