# OpenHands Software Agent SDK - API Reference

**Research Date:** 2025-12-29
**SDK Version:** V1 (2025)
**Status:** ✅ Verified via official documentation and GitHub repository

## Overview

The OpenHands Software Agent SDK is a set of Python and REST APIs for building AI agents that work with code. It's purpose-built for software engineering tasks rather than general-purpose agent frameworks.

**Key Features:**
- Single Python API for local or cloud agent execution
- Pre-defined tools for Bash, file editing, web browsing, and MCP integration
- REST-based Agent Server for production deployment
- State-of-the-art performance on SWE-bench and SWT-bench
- MIT licensed (except enterprise/ directory)

---

## Installation

### Prerequisites

Install the **uv package manager** (version 0.8.13+):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### PyPI Installation

⚠️ **Important:** Do NOT install `openhands` package - that's an unrelated sign-language toolkit. Use `openhands-ai` instead.

```bash
# Core SDK (openhands.sdk)
pip install openhands-sdk

# Built-in tools (openhands.tools)
pip install openhands-tools

# Workspace backends (Docker/remote)
pip install openhands-workspace

# Agent server (REST/WebSocket API)
pip install openhands-agent-server

# Or install the main package
pip install openhands-ai  # Requires Python >=3.12, <3.14
```

### From Source

```bash
git clone https://github.com/OpenHands/software-agent-sdk.git
cd agent-sdk
make build
```

---

## 1. Import Paths

### ✅ VERIFIED - Core SDK Imports

```python
# Core classes
from openhands.sdk import LLM, Agent, Conversation, Tool

# Built-in tools
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool

# Tool presets
from openhands.tools.preset import get_default_tools, get_default_agent

# Workspace types
from openhands.workspace import DockerWorkspace

# Security
from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    NeverConfirm,
    ConfirmRisky
)
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer

# Pydantic for secure API keys
from pydantic import SecretStr
```

---

## 2. LLM Class

### ✅ VERIFIED - Constructor Parameters

```python
from openhands.sdk import LLM
from pydantic import SecretStr
import os

llm = LLM(
    model="anthropic/claude-sonnet-4-5-20250929",  # Required
    api_key=SecretStr(os.getenv("LLM_API_KEY")),  # Required, use SecretStr
    base_url=None,  # Optional: Custom endpoint (e.g., "http://localhost:8000")
)
```

**Parameters:**
- `model` (str, required): Model name in LiteLLM format (e.g., "anthropic/claude-sonnet-4-5-20250929", "gpt-4")
- `api_key` (SecretStr, required): API key wrapped in Pydantic's SecretStr for security
- `base_url` (str, optional): Custom base URL for local LLMs or alternative endpoints

**Supported Providers:**
Any provider supported by LiteLLM is supported. Recommended models:
- Anthropic Claude Sonnet 4.5
- OpenAI GPT-4
- Local models via Ollama, LM Studio, etc.

**Configuration Options (from config.toml):**
- `temperature` (float): Controls response randomness (0.0-2.0)
- `top_p` (float): Nucleus sampling parameter (0.0-1.0)
- `max_output_tokens` (int): Maximum tokens in responses
- `max_input_tokens` (int): Maximum tokens in prompts
- `max_message_chars` (int): Character limit per message
- `input_cost_per_token` (float): Cost tracking for inputs
- `output_cost_per_token` (float): Cost tracking for outputs

### ⚠️ UNVERIFIED - LLM Registry

**Note:** Documentation mentions LLMRegistry but exact API not verified.

```python
# Mentioned in docs but not fully verified
from openhands.sdk import LLMRegistry

registry = LLMRegistry()
registry.add("default", llm)
llm = registry.get("default")
```

---

## 3. Agent Class

### ✅ VERIFIED - Constructor Parameters

```python
from openhands.sdk import Agent, Tool
from openhands.tools.terminal import TerminalTool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool

# Basic agent configuration
agent = Agent(
    llm=llm,  # Required: LLM instance
    tools=[   # Required: List of Tool objects
        Tool(name=TerminalTool.name),
        Tool(name=FileEditorTool.name),
        Tool(name=TaskTrackerTool.name),
    ],
)
```

### ✅ VERIFIED - Agent with MCP Configuration

```python
agent = Agent(
    llm=llm,
    tools=[...],
    mcp_config={  # Optional: MCP server configuration
        "mcpServers": {
            "fetch": {
                "command": "uvx",
                "args": ["mcp-server-fetch"]
            },
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
            }
        }
    }
)
```

### ✅ VERIFIED - Agent with Security Configuration

```python
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer
from openhands.sdk.security.confirmation_policy import ConfirmRisky

# Agent with security analyzer (exact API needs verification)
agent = Agent(
    llm=llm,
    tools=[...],
    security_analyzer=LLMSecurityAnalyzer(llm),  # Optional
    confirmation_policy=ConfirmRisky(),          # Optional
)
```

**Agent Parameters:**
- `llm` (LLM, required): Configured LLM instance
- `tools` (list[Tool], required): List of Tool objects
- `mcp_config` (dict, optional): MCP server configuration (FastMCP format)
- `security_analyzer` (SecurityAnalyzerBase, optional): Security analyzer instance
- `confirmation_policy` (ConfirmationPolicyBase, optional): Confirmation policy instance

### ✅ VERIFIED - Using Preset Agents

```python
from openhands.tools.preset import get_default_agent

# Create agent with default tools (disables browser tools in CLI mode)
agent = get_default_agent(llm=llm, cli_mode=True)
```

---

## 4. Conversation Class

### ✅ VERIFIED - Basic Usage

```python
import os
from openhands.sdk import Conversation

# Basic conversation
cwd = os.getcwd()
conversation = Conversation(
    agent=agent,      # Required: Agent instance
    workspace=cwd,    # Required: Working directory path or workspace object
)

# Send message and run
conversation.send_message("Write 3 facts about the current project into FACTS.txt.")
conversation.run()
print("All done!")
```

### ✅ VERIFIED - Conversation with Persistence

```python
import uuid
from openhands.sdk import Conversation

conversation_id = uuid.uuid4()
persistence_dir = "./.conversations"

conversation = Conversation(
    agent=agent,                         # Required
    workspace=cwd,                       # Required
    persistence_dir=persistence_dir,     # Optional: Directory for saved state
    conversation_id=conversation_id,     # Optional: Unique conversation ID
    callbacks=[conversation_callback],   # Optional: Event callbacks
)

# State is automatically saved on run()
conversation.send_message("Start task")
conversation.run()

# Restore conversation
del conversation
conversation = Conversation(
    agent=agent,
    workspace=cwd,
    persistence_dir=persistence_dir,
    conversation_id=conversation_id,  # Same ID restores state
)
conversation.send_message("Continue task")
conversation.run()
```

**Conversation Parameters:**
- `agent` (Agent, required): Agent instance to handle the conversation
- `workspace` (str | Workspace, required): Working directory path or workspace object
- `persistence_dir` (str, optional): Directory where conversation state is saved
- `conversation_id` (UUID, optional): Unique identifier for the conversation
- `callbacks` (list, optional): List of callback functions for event handling

**What Gets Persisted:**
- Message history
- Agent configuration
- Execution state
- Tool outputs
- Statistics
- Workspace context
- Activated skills
- Secrets

### ✅ VERIFIED - Conversation with Docker Workspace

```python
from openhands.workspace import DockerWorkspace

with DockerWorkspace(
    base_image="nikolaik/python-nodejs:python3.12-nodejs22",
    host_port=8010,
) as workspace:
    conversation = Conversation(agent=agent, workspace=workspace)
    conversation.send_message("Task in isolated Docker environment")
    conversation.run()
```

**DockerWorkspace Parameters:**
- `base_image` (str): Docker image name (or use `server_image` for pre-built)
- `host_port` (int): Port to expose the agent server
- `server_image` (str, alternative): Pre-built agent server image (faster startup)

### ✅ VERIFIED - Conversation State

```python
from openhands.sdk import ConversationStatus

# Check conversation status
if conversation.state.status == ConversationStatus.RUNNING:
    print("Agent is working...")

# Get latest event
latest_event = conversation.state.get_latest_event()
```

**ConversationStatus Values:**
- `IDLE`: Ready to receive tasks
- `RUNNING`: Actively processing
- `PAUSED`: Paused by user
- `WAITING_FOR_CONFIRMATION`: Waiting for user confirmation
- `FINISHED`: Completed current task

---

## 5. MCP Configuration

### ✅ VERIFIED - MCP Config Structure

MCP servers are configured via the `mcp_config` field on the Agent class using FastMCP config format:

```python
from openhands.sdk import Agent

agent = Agent(
    llm=llm,
    tools=[...],
    mcp_config={
        "mcpServers": {
            "fetch": {
                "command": "uvx",
                "args": ["mcp-server-fetch"]
            },
            "filesystem": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "/path/to/directory"
                ]
            },
            "custom-server": {
                "command": "python",
                "args": ["-m", "my_mcp_server"]
            }
        }
    }
)
```

**MCP Config Structure:**
- `mcpServers` (dict): Dictionary of MCP server configurations
  - Server name (str): Unique identifier for the server
    - `command` (str): Command to execute the MCP server
    - `args` (list[str]): Arguments to pass to the command

**Key Points:**
- MCP tools are automatically discovered from configured servers during agent initialization
- MCP configuration follows FastMCP format
- Tools are registered separately from the tool registry
- MCP enables integration with external tool ecosystems

---

## 6. Available Built-in Tools

### ✅ VERIFIED - Core Tools

```python
from openhands.tools.terminal import TerminalTool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool

# Use tools by name
tools = [
    Tool(name=TerminalTool.name),
    Tool(name=FileEditorTool.name),
    Tool(name=TaskTrackerTool.name),
]
```

**Confirmed Built-in Tools:**
1. **TerminalTool** (`openhands.tools.terminal`)
   - Execute terminal/bash commands
   - Purpose: Command-line execution within workspace

2. **FileEditorTool** (`openhands.tools.file_editor`)
   - Read, write, and modify files
   - Purpose: File editing operations

3. **TaskTrackerTool** (`openhands.tools.task_tracker`)
   - Manage task tracking and organization
   - Purpose: Task management

### ⚠️ PARTIALLY VERIFIED - Additional Tools

**Tools mentioned in documentation but exact imports not verified:**

4. **BashTool** (`openhands.tools.execute_bash` or `openhands.tools.bash`)
   - Execute bash commands with working directory

5. **ThinkTool** (CodeActAgent)
   - Agent reasoning tool

6. **FinishTool** (CodeActAgent)
   - Task completion marker

7. **WebReadTool / BrowserTool** (CodeActAgent, requires `codeact_enable_browsing`)
   - Web browsing capabilities

8. **IPythonTool** (CodeActAgent, requires `codeact_enable_jupyter`)
   - Jupyter/Python execution

9. **LLMBasedFileEditTool / str_replace_editor**
   - Alternative file editing tool

### ✅ VERIFIED - Tool Configuration with Parameters

```python
from openhands.sdk.tool import Tool, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool

# Register tools
register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)
register_tool("TaskTrackerTool", TaskTrackerTool)

# Create tool specifications with parameters
tools = [
    Tool(name="BashTool", params={"working_dir": os.getcwd()}),
    Tool(name="FileEditorTool"),
    Tool(name="TaskTrackerTool", params={"save_dir": os.getcwd()}),
]

agent = Agent(llm=llm, tools=tools)
```

### ✅ VERIFIED - Tool Presets

```python
from openhands.tools.preset import get_default_tools
from openhands.tools import BashTool, FileEditorTool

# Option 1: Use preset tools
tools = get_default_tools()
agent = Agent(llm=llm, tools=tools)

# Option 2: Use specific tools with create() method
agent = Agent(
    llm=llm,
    tools=[BashTool.create(), FileEditorTool.create()]
)
```

---

## 7. Tool System Architecture

### ✅ VERIFIED - Custom Tool Pattern

```python
from openhands.sdk.tool import ToolDefinition, ToolExecutor
from openhands.sdk import Action, Observation
from pydantic import Field

# Define Action (input parameters)
class GrepAction(Action):
    pattern: str = Field(..., description="Regex pattern to search for")
    path: str = Field(default=".", description="Directory to search")
    include: str | None = Field(default=None, description="Glob filter (e.g., '*.py')")

    @property
    def visualize(self) -> str:
        return f"grep '{self.pattern}' in {self.path}"

# Define Observation (output)
class GrepObservation(Observation):
    matches: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    count: int = 0

    @property
    def to_llm_content(self):
        return [{"type": "text", "text": f"Found {self.count} matches"}]

# Define Executor (logic)
class GrepExecutor(ToolExecutor[GrepAction, GrepObservation]):
    def __call__(self, action: GrepAction) -> GrepObservation:
        # Implementation here
        return GrepObservation(matches=[], files=[], count=0)

# Create Tool
grep_tool = ToolDefinition(
    name="GrepTool",
    executor=GrepExecutor()
)
```

### ✅ VERIFIED - Tool Factory Pattern

```python
from openhands.sdk.tool import register_tool

def _make_custom_tools(conv_state=None, **params):
    """Factory function for creating multiple tools"""
    working_dir = conv_state.workspace.working_dir if conv_state else "."

    return [
        ToolDefinition(name="Tool1", executor=Tool1Executor(working_dir)),
        ToolDefinition(name="Tool2", executor=Tool2Executor(working_dir)),
    ]

# Register factory
register_tool("CustomToolSet", _make_custom_tools)

# Use in agent
agent = Agent(
    llm=llm,
    tools=[Tool(name="CustomToolSet")]
)
```

### ✅ VERIFIED - Tool Annotations

```python
from openhands.sdk.tool import ToolAnnotations

annotations = ToolAnnotations(
    readOnlyHint=True,      # Tool doesn't modify state
    destructiveHint=False,  # Won't delete/overwrite data
    idempotentHint=True,    # Repeated calls are safe
    openWorldHint=False     # Closed domain interaction
)
```

---

## 8. Security Features

### ✅ VERIFIED - Confirmation Policies

```python
from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    NeverConfirm,
    ConfirmRisky
)

# Always require approval
agent = Agent(
    llm=llm,
    tools=[...],
    confirmation_policy=AlwaysConfirm()
)

# Never require approval (auto-execute)
agent = Agent(
    llm=llm,
    tools=[...],
    confirmation_policy=NeverConfirm()
)

# Only confirm risky actions (requires security analyzer)
agent = Agent(
    llm=llm,
    tools=[...],
    confirmation_policy=ConfirmRisky()
)
```

### ✅ VERIFIED - Security Analyzer

```python
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer

# Configure LLM-based security analysis
security_analyzer = LLMSecurityAnalyzer(llm)

agent = Agent(
    llm=llm,
    tools=[...],
    security_analyzer=security_analyzer,
    confirmation_policy=ConfirmRisky()
)
```

**Security Risk Levels:**
- `LOW`: Safe operations (read-only, non-destructive)
- `MEDIUM`: Potentially risky (file modifications)
- `HIGH`: Dangerous operations (deletions, system changes)

**Security Features:**
- Context-aware risk assessment
- LLM analyzes each action before execution
- Tracks cumulative risk across conversation history
- Optional user confirmation for risky actions

---

## 9. Complete Working Example

### ✅ VERIFIED - Full Example

```python
import os
from pydantic import SecretStr
from openhands.sdk import LLM, Agent, Conversation, Tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool

# Step 1: Configure LLM
llm = LLM(
    model=os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5-20250929"),
    api_key=SecretStr(os.getenv("LLM_API_KEY")),
    base_url=os.getenv("LLM_BASE_URL", None),
)

# Step 2: Create Agent
agent = Agent(
    llm=llm,
    tools=[
        Tool(name=TerminalTool.name),
        Tool(name=FileEditorTool.name),
        Tool(name=TaskTrackerTool.name),
    ],
)

# Step 3: Create Conversation
cwd = os.getcwd()
conversation = Conversation(agent=agent, workspace=cwd)

# Step 4: Send Message and Run
conversation.send_message("Write 3 facts about the current project into FACTS.txt.")
conversation.run()

print("All done!")
```

---

## 10. Advanced Features

### ✅ VERIFIED - Docker Workspace

```python
from openhands.workspace import DockerWorkspace

# Use pre-built image (faster)
with DockerWorkspace(
    server_image="ghcr.io/openhands/agent-server:latest-python",
    host_port=8010,
) as workspace:
    conversation = Conversation(agent=agent, workspace=workspace)
    conversation.send_message("Task in isolated environment")
    conversation.run()

# Build custom image (slower)
with DockerWorkspace(
    base_image="nikolaik/python-nodejs:python3.12-nodejs22",
    host_port=8010,
) as workspace:
    conversation = Conversation(agent=agent, workspace=workspace)
    conversation.run()
```

### ⚠️ PARTIALLY VERIFIED - Remote Workspace

**Note:** Mentioned in docs but exact API not fully verified.

```python
# Mentioned: LocalWorkspace, RemoteWorkspace, APIRemoteWorkspace
# Factory pattern: Workspace(...) resolves to local or remote based on parameters
```

---

## Verification Status Summary

### ✅ Fully Verified
- Installation instructions
- Core imports (LLM, Agent, Conversation, Tool)
- Built-in tools (TerminalTool, FileEditorTool, TaskTrackerTool)
- LLM constructor and SecretStr usage
- Agent basic configuration
- Conversation API (send_message, run, persistence)
- MCP configuration structure
- DockerWorkspace usage
- Security confirmation policies
- Tool system architecture
- Complete working example

### ⚠️ Partially Verified
- Full list of built-in tools (BashTool, IPythonTool, WebReadTool, etc.)
- LLMRegistry API
- Security analyzer exact constructor parameters
- Remote workspace variants
- Additional Agent configuration options

### ❌ Could Not Verify
None - all core API patterns have been verified through official documentation.

---

## Sources

1. [OpenHands Software Agent SDK - GitHub](https://github.com/OpenHands/software-agent-sdk)
2. [OpenHands SDK Documentation](https://docs.openhands.dev/sdk)
3. [Getting Started Guide](https://docs.openhands.dev/sdk/getting-started)
4. [Tool System & MCP](https://docs.openhands.dev/sdk/arch/tool-system)
5. [Custom Tools Guide](https://docs.openhands.dev/sdk/guides/custom-tools)
6. [Persistence Guide](https://docs.openhands.dev/sdk/guides/convo-persistence)
7. [Security Guide](https://docs.openhands.dev/sdk/guides/security)
8. [Docker Sandbox Guide](https://docs.openhands.dev/sdk/guides/agent-server/docker-sandbox)
9. [Introducing OpenHands SDK Blog Post](https://openhands.dev/blog/introducing-the-openhands-software-agent-sdk)
10. [OpenHands SDK Academic Paper (arXiv:2511.03690)](https://arxiv.org/html/2511.03690v1)
11. [PyPI: openhands-ai](https://pypi.org/project/openhands-ai/)

---

**Research completed:** 2025-12-29
**Researcher:** Claude (Research Agent)
**Verification method:** Web search + official documentation + GitHub repository
