# Phone-A-Friend MCP Server Plan

**Document Version**: 0.1  
**Date**: 2025-10-01  
**Author**: Droid (Factory AI)

## Executive Summary

This plan defines a new "phone-a-friend" Model Context Protocol (MCP) server that exposes OpenAI's GPT-5 (or compatible) agent through the official OpenAI Agents SDK. Claude—running locally with access to both the `comma-tools` MCP server and this new service—can orchestrate three-way collaboration between the human user, GPT-5, and the `comma-tools` analysis suite. The server emphasizes clear delegation, structured tool routing, and rate limiting to control costs while enabling GPT-5 to request analyses, receive results, and propose enhancements to `comma-tools` as needed.

## Goals & Non-Goals

### Goals
- Provide a reliable MCP interface that represents GPT-5 as a delegate capable of long-running conversations.
- Enable Claude to proxy GPT-5 tool requests into local `comma-tools` executions and return structured results.
- Support persistent conversation context using OpenAI Agents SDK memory/persistence features when available.
- Implement configurable rate limiting and safety guardrails to prevent runaway API usage.
- Document clear extension pathways for GPT-5 to request new `comma-tools` capabilities.

### Non-Goals
- Building new `comma-tools` analyzers (handled separately as feature follow-ups).
- Managing human authentication/authorization workflows beyond basic API key handling.
- Deploying GPT-5 itself; this plan assumes API access via OpenAI Agents SDK.

## Key Stakeholders
- **Human operator (Dan)**: Initiates troubleshooting sessions and reviews outputs.
- **Claude orchestrator**: Runs locally, brokers conversation, executes `comma-tools` commands.
- **GPT-5 expert**: Provides reasoning, requests tools, and suggests `comma-tools` enhancements.
- **comma-tools MCP server**: Supplies log analysis, artifact generation, and diagnostics capabilities.

## Architecture Overview

```
┌─────────────┐        ┌────────────────────────┐        ┌────────────────────────┐
│ Human User  │  ⇄   │ Claude Orchestrator    │  ⇄   │ comma-tools MCP Server │
└─────────────┘        │  (local MCP client)     │        └────────────────────────┘
        ⇅              │            ⇅             │
┌─────────────────────────────────────────────────────────┐
│        Phone-A-Friend MCP Server (OpenAI Agents SDK)     │
│    • Session manager  • Rate limiter  • Delegate bridge   │
└─────────────────────────────────────────────────────────┘
                             ⇅
                     ┌───────────────┐
                     │    GPT-5 API  │
                     └───────────────┘
```

### Component Responsibilities

| Component | Responsibilities |
| --- | --- |
| Phone-A-Friend MCP Server | Hosts GPT-5 via Agents SDK, enforces rate limits, translates MCP messages to agent API calls, exposes a delegate tool for Claude to fulfill GPT-5 requests. |
| Claude Orchestrator | Maintains conversation state with human, forwards transcripts to GPT-5, executes `comma-tools` tooling upon GPT-5 request, sends results back through the phone server. |
| `comma-tools` MCP Server | Delivers log analysis, run management, artifact retrieval, and diagnostics. |
| GPT-5 Agent | Provides reasoning, initiates delegate tool calls, requests new `comma-tools` features as needed. |

## Conversation Protocol

1. **Session bootstrap**: Claude initiates a GPT-5 session via `messages.create`, providing user goals, vehicle context, and any relevant logs or prior outputs.
2. **Dialogue loop**:
   - Claude forwards human inputs and log summaries to GPT-5.
   - GPT-5 replies with guidance or issues a delegate tool call (e.g., `run_comma_tool`).
   - Claude executes requested commands via the `comma-tools` MCP server and returns structured results.
3. **Iteration**: GPT-5 incorporates tool outputs, optionally requests additional analyses, or recommends feature enhancements.
4. **Closure**: Claude summarizes findings to the human, archives relevant artifacts, and ends the GPT-5 session.

## Delegate Tool Contract

- **Tool name**: `delegate_to_claude`
- **Input payload**:
  ```json
  {
    "action": "run_comma_tool" | "propose_feature" | "request_context",
    "parameters": { ... },
    "expect": "text" | "artifact" | "json"
  }
  ```
- **Response payload**:
  ```json
  {
    "status": "success" | "error",
    "output": "...",
    "artifacts": [
      {"type": "plot", "path": "...", "description": "..."}
    ],
    "metadata": {"elapsed_ms": 1234}
  }
  ```
- **Error handling**: Claude returns `status: "error"` with `error_code` and `message` when tool execution fails, allowing GPT-5 to adjust requests.

## Rate Limiting & Cost Controls

- Implement exponential backoff and configurable burst/steady-state quotas (e.g., `max_concurrent_sessions`, `max_requests_per_minute`).
- Surface quota usage to Claude after each request so it can alert the human when nearing limits.
- Provide kill switch endpoints for immediate session termination if runaway usage is detected.

## Persistence & Memory Considerations

- Evaluate Agents SDK conversation archival features to persist session transcripts and metadata.
- Store only non-sensitive context (log summaries, tool outputs) within GPT-5 memory; artifacts remain on local disk within `comma-tools` infrastructure.
- Define retention policy (default 30 days) and create CLI hooks for Claude to purge or export transcripts.

## API Key & Secret Management

- Require the human to place the OpenAI API key in a local path such as `~/.config/comma-tools/openai.key` with `0600` permissions.
- Phone-a-friend server reads the key at startup and never logs or stores it in git-tracked locations.
- Support environment variable override (`OPENAI_API_KEY_PATH`) for flexible deployments.

## Implementation Roadmap

1. **Bootstrap (Week 1)**
   - Scaffold server using TypeScript + official OpenAI Agents SDK.
   - Implement CLI entry point (e.g., `phone-mcp`) and basic MCP `messages.create` passthrough.
2. **Delegate Tooling (Week 2)**
   - Add `delegate_to_claude` tool implementation, define payload schemas, and integrate structured responses.
   - Implement rate limit middleware and logging.
3. **Claude Integration (Week 3)**
   - Update Claude orchestration scripts to route GPT-5 tool requests to `comma-tools`.
   - Exercise end-to-end flow with sample logs.
4. **Persistence & Observability (Week 4)**
   - Enable optional session persistence via Agents SDK features.
   - Add metrics endpoints (e.g., Prometheus or JSON stats) for request counts, latency, error rates.
5. **Handoff & Polish**
   - Document setup steps in `docs/AGENTS.md` or dedicated guide.
   - Prepare example Claude prompt templates and success playbooks for car log troubleshooting.

## Testing & Validation Strategy

- **Unit tests**: Mock Agents SDK client to validate session manager, rate limiter, and payload schemas.
- **Integration tests**: Spin up local `comma-tools` MCP server and exercise delegate flow end-to-end with synthetic logs.
- **Load tests**: Simulate high-frequency GPT-5 requests to verify rate limiting and graceful degradation.
- **Security checks**: Ensure no secrets leak, confirm TLS requirements when running remotely.

## Deployment & Operations

- Package as a Python or Node.js CLI executable (depending on final stack) registered as an MCP server.
- Provide systemd/service templates for long-running deployments if needed.
- Maintain structured logs (JSON) for session tracing; integrate with existing observability stack if available.
- Document upgrade path for Agents SDK changes and provide compatibility matrix.

## Open Questions

- Preferred persistence backend for Agents SDK (file-based, SQLite, or external store)?
- Should Claude surface human-readable cost estimates per session in real time?
- Do we require multi-tenant support, or is single-user operation sufficient for the foreseeable future?
