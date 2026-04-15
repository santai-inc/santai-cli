# Agent Registry

This directory contains pre-built, reusable agent definitions for common use cases. Each agent is specialized in a specific domain and can be used as a subagent for focused tasks.

## Available Agents

### Development & Engineering

- **[linting.md](linting.md)** - Code quality checks, style enforcement, and best practices
- **[testing.md](testing.md)** - Test generation, validation, and quality assurance
- **[code-review.md](code-review.md)** - Code review with focus on quality, security, and best practices
- **[security.md](security.md)** - Vulnerability scanning and secure coding practices
- **[documentation.md](documentation.md)** - Technical documentation generation and maintenance
- **[database.md](database.md)** - Database design, queries, optimization, and administration
- **[api.md](api.md)** - API design, development, testing, and documentation
- **[devops.md](devops.md)** - CI/CD, deployment, infrastructure, and operational excellence

### Analysis & Data

- **[research.md](research.md)** - Deep research, analysis, and information gathering
- **[data-analysis.md](data-analysis.md)** - Data processing, statistical analysis, and visualization
- **[browser.md](browser.md)** - Web browsing, scraping, and online information gathering

### Content & Communication

- **[writing.md](writing.md)** - Content creation, editing, and various writing styles
- **[summarizer.md](summarizer.md)** - Condensing information and creating concise summaries

### Finance & Business

- **[finance.md](finance.md)** - Financial analysis, calculations, and money management

### Lifestyle & Personal

- **[travel.md](travel.md)** - Travel planning, destinations, and logistics
- **[activities-food.md](activities-food.md)** - Activity planning, dining, and entertainment recommendations
- **[health.md](health.md)** - Fitness, nutrition, mental health, and wellness
- **[learning.md](learning.md)** - Learning strategies, educational content, and skill development

### Productivity

- **[productivity.md](productivity.md)** - Task management, time optimization, and workflow improvement

## Usage

These agent definitions are designed to be used **directly** as subagents in Claude Code, OpenAI, and other AI tools.

### Quick Start

Tell your AI assistant to use an agent definition:

```
"Use agents/finance.md as a subagent to analyze this budget"
"Spawn a subagent from agents/security.md to review this code"
"Act as the agent defined in agents/research.md"
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

To create your own agent:

1. Create a new `.md` file in this directory
2. Add the required frontmatter (description, mode, permissions)
3. Write detailed system instructions
4. Define focus areas and best practices
5. Include examples where helpful

### Best Practices

- **Use specialized agents** for focused tasks rather than generic prompts
- **Read the agent definition** to understand its capabilities and limitations
- **Provide context** when invoking agents - they don't have conversation history
- **Combine agents** for multi-step workflows (e.g., research → write → review)
- **Update agents** as best practices evolve

## Agent Categories

### Read-Only Agents
Agents that analyze and provide information without making changes:
- Research, Summarizer, Browser, Finance, Health, Learning

### Code-Modifying Agents
Agents that can edit code and files:
- Linting, Testing, Code Review, Documentation, Database, API, DevOps, Writing, Data Analysis

### Development Workflow
Typical agent combinations:
1. **Feature Development**: Documentation → Testing → Code Review → Linting
2. **Bug Investigation**: Research → Browser → Database → Code Review
3. **Content Creation**: Research → Writing → Summarizer
4. **Infrastructure Setup**: DevOps → Security → Documentation
5. **API Development**: API → Documentation → Testing → Security

## Contributing

To contribute a new agent:

1. Identify a clear, focused domain
2. Research best practices in that domain
3. Write comprehensive but practical instructions
4. Include examples and common patterns
5. Define appropriate permissions
6. Test the agent with real tasks
7. Submit a pull request

## Related Resources

- [Main Project README](../README.md)
- [Project Documentation](../docs/)
- Issue Tracker: [GitHub Issues](https://github.com/santai-inc/santai-cli/issues)

## License

These agent definitions are part of the santai-cli project and follow the project's license terms.
