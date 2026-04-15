# How to Use These Agent Definitions

These markdown files are agent definitions that can be used **directly** as subagents in Claude Code, OpenAI, and other AI tools.

## Using with Claude Code

When you want to spawn a specialized subagent, tell Claude to use one of these definitions:

```
"Use the agent definition from agents/finance.md as a subagent to analyze my budget"

"Read agents/security.md and spawn a subagent with those instructions to review this code"

"Create a subagent using agents/research.md to investigate this topic"
```

Claude Code will:
1. Read the markdown file
2. Extract the system prompt and instructions
3. Spawn a subagent with that expertise
4. The subagent operates with the specialized knowledge defined in the file

## Using with OpenAI/ChatGPT

```
"Act as the agent defined in agents/travel.md and help me plan a trip"

"Load the agent instructions from agents/writing.md and help me write this article"
```

## Using with Other Tools

Any AI tool that supports custom instructions or system prompts can use these:

- **Custom GPTs**: Use the markdown content as custom instructions
- **Claude Projects**: Add as project knowledge
- **API calls**: Use as system prompt in API requests

## Example

```
You: "Use agents/finance.md as a subagent to analyze my investment portfolio"

Claude: [Reads finance.md, spawns subagent with that expertise]

Finance Subagent: "I'm a finance expert. Let me analyze your portfolio..."
```

## Why This Works

- ✅ **Direct use**: No code generation, just use as-is
- ✅ **Specialized**: Each agent has deep domain expertise
- ✅ **Consistent**: Same agent definitions work across tools
- ✅ **Simple**: Just reference the markdown file

## Adding New Agents

1. Create a new `.md` file following the format
2. Reference it when spawning subagents

That's it!
