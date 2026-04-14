# How to Use These Agent Definitions

These agent markdown files are **source of truth** specifications that you can give to Claude Code, OpenAI, or any AI assistant to generate actual implementations.

## The Simple Way

Just ask your AI assistant to read an agent definition and create what you need.

### Examples

#### Create a Claude Agent SDK implementation
```
"Read agents/finance.md and create a Python class using the Anthropic SDK that implements this agent"
```

#### Create an MCP tool
```
"Read agents/research.md and create an MCP tool definition for this agent"
```

#### Create a CLI command
```
"Read agents/security.md and create a Typer CLI command that uses this agent"
```

#### Create a LangChain tool
```
"Read agents/writing.md and create a LangChain tool implementation"
```

## That's It!

The agent definitions have everything needed:
- **Frontmatter**: Description and permissions
- **System prompt**: All the instructions and expertise
- **Focus areas**: What the agent does
- **Best practices**: How it should behave

Just point your AI assistant to the file and tell it what platform/format you want.

## Example Workflows

### Building a CLI Tool
```
User: "Read agents/finance.md, agents/travel.md, and agents/health.md. 
       Create a CLI tool with subcommands for each agent using Typer."

Claude: [Reads the files and generates complete CLI implementation]
```

### Creating an MCP Server
```
User: "Read all the agent files in the agents/ directory. 
       Create an MCP server that exposes each as a tool."

Claude: [Generates MCP server with all agents as tools]
```

### Custom Integration
```
User: "Read agents/data-analysis.md and create a FastAPI endpoint 
       that accepts tasks and returns results."

Claude: [Generates FastAPI code with the agent integrated]
```

## Why This Works

- ✅ **Simple**: No scripts, no complex build processes
- ✅ **Flexible**: Generate for any platform or framework
- ✅ **Up-to-date**: Your AI assistant uses current best practices
- ✅ **Customizable**: Easily modify the generated code
- ✅ **Universal**: Works with Claude, OpenAI, or any AI tool

## Adding New Agents

1. Create a new `.md` file in this directory
2. Follow the format (see existing agents)
3. Ask your AI to generate implementations

That's it!
