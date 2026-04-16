# How to Use These Agent Definitions

These markdown files are agent definitions that can be used **directly** as subagents in Claude Code, OpenAI, and other AI tools. Each agent understands the santai project structure and is specialized for context management workflows.

## Using with Claude Code

When you want to spawn a specialized subagent, tell Claude to use one of these definitions:

```
"Use the agent definition from agents/wiki.md as a subagent to curate our project knowledge"

"Read agents/research.md and spawn a subagent with those instructions to investigate this topic"

"Create a subagent using agents/summarizer.md to summarize our recent history entries"
```

Claude Code will:
1. Read the markdown file
2. Extract the system prompt and instructions
3. Spawn a subagent with that expertise
4. The subagent operates with the specialized knowledge defined in the file

## Using with OpenAI/ChatGPT

```
"Act as the agent defined in agents/documentation.md and help me write a history entry"

"Load the agent instructions from agents/linting.md and check our wiki for quality issues"
```

## Using with Other Tools

Any AI tool that supports custom instructions or system prompts can use these:

- **Custom GPTs**: Use the markdown content as custom instructions
- **Claude Projects**: Add as project knowledge
- **API calls**: Use as system prompt in API requests

## Example

```
You: "Use agents/wiki.md as a subagent to review our wiki and identify gaps"

Claude: [Reads wiki.md, spawns subagent with that expertise]

Wiki Subagent: "I'll scan the wiki/ directory and cross-reference with history/
and notes/ to identify knowledge that should be captured..."
```

## Why This Works

- **Direct use**: No code generation, just reference the markdown file
- **Santai-aware**: Each agent understands the 5-directory structure
- **Composable**: Chain agents together (research -> documentation -> wiki)
- **Consistent**: Same agent definitions work across tools

## Adding New Agents

1. Create a new `.md` file following the format
2. Include the santai directory structure context
3. Define the agent's specific role in the context management workflow
4. Reference it when spawning subagents

That's it!
