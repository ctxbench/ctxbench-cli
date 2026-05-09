# C4 — Dynamic Diagrams

## Purpose

Dynamic diagrams document runtime behavior: how components interact during a scenario.

This is the best C4 view for explaining MCP operation loops, tool calls, and strategy-specific flows.

## Inline execution

```mermaid
sequenceDiagram
    participant B as CTXBench
    participant F as Local Filesystem
    participant L as LLM Provider

    B->>F: read context artifact
    F-->>B: context
    B->>L: task + inline context
    L-->>B: response
    B->>F: write response and trace
```

## Local function execution

```mermaid
sequenceDiagram
    participant B as CTXBench
    participant L as LLM Provider
    participant T as Local Python Functions
    participant F as Local Filesystem

    B->>L: task + function declarations
    L-->>B: function call request
    B->>T: execute function
    T->>F: read context artifact
    F-->>T: context data
    T-->>B: function result
    B->>L: function result
    L-->>B: final response
    B->>F: write response and trace
```

## Local MCP execution

```mermaid
sequenceDiagram
    participant B as CTXBench
    participant L as LLM Provider
    participant C as MCP Client
    participant S as Local MCP Server
    participant F as Local Filesystem

    B->>L: task + MCP tool declarations
    L-->>B: tool call request
    B->>C: invoke MCP tool
    C->>S: MCP tool call
    S->>F: read context artifact
    F-->>S: context data
    S-->>C: tool result
    C-->>B: normalized tool result
    B->>L: tool result
    L-->>B: final response
    B->>F: write response and trace
```

## Remote MCP execution

```mermaid
sequenceDiagram
    participant B as CTXBench
    participant L as LLM Provider
    participant S as Remote MCP Server
    participant D as Context Store
    participant F as Local Filesystem

    B->>L: task + remote MCP configuration
    L->>S: provider-managed MCP tool call
    S->>D: read context
    D-->>S: context data
    S-->>L: tool result
    L-->>B: final response + available evidence
    B->>F: write response and trace
```

## What MCP does in these flows

MCP introduces a client/server protocol boundary for context access.

The MCP server exposes tools with:

```text
name
description
input schema
output structure
error behavior
```

The MCP client invokes those tools. In `local_mcp`, CTXBench controls the MCP client. In `remote_mcp`, the provider may control or mediate MCP calls.

## Runtime implications

| Concern | Local MCP | Remote MCP |
|---|---|---|
| Loop control | CTXBench | Provider/remote integration may control |
| Tool observability | High | Lower |
| Network boundary | Local only | Remote |
| Context service reuse | Medium | High |
| Latency risk | Lower | Higher |
| Token/call accounting | More direct | Provider-specific / partial |

## MCP failure modes

```text
tool not called
wrong tool selected
invalid arguments
tool timeout
remote server unavailable
provider hides intermediate calls
tool output too large
tool output too unstructured
model stops before collecting enough evidence
```
