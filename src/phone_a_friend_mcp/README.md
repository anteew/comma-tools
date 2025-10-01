# Phone-A-Friend MCP Server

> **🤖 FOR AI ASSISTANTS** - This MCP server exposes GPT-5 (or other OpenAI models) to Claude, enabling collaborative problem-solving where Claude can delegate complex reasoning tasks to GPT-5 and orchestrate between GPT-5 and comma-tools analysis capabilities.

Model Context Protocol (MCP) server that wraps OpenAI's Agents SDK to provide GPT-5 agent capabilities to Claude through the MCP protocol.

## Architecture: Three-Way Collaboration

```
Human User
    ↓ Natural Language Request
Claude (Local AI Assistant)
    ↓ MCP Protocol                    ↓ MCP Protocol
Phone-A-Friend MCP (this)         comma-tools MCP
    ↓ Agents SDK                      ↓ HTTP/REST
OpenAI GPT-5 Agent                CTS-Lite API
                                      ↓
                                  Analysis Tools
```

**Workflow:**
1. Human asks Claude to debug a vehicle issue
2. Claude starts a GPT-5 session via phone-a-friend MCP
3. Claude sends problem context to GPT-5
4. GPT-5 provides reasoning and suggestions
5. Claude executes comma-tools analyses based on GPT-5's recommendations
6. Claude sends analysis results back to GPT-5
7. GPT-5 interprets results and provides insights
8. Claude presents final findings to human

## For AI Assistants: Self-Registration

**If you are Claude Code**, register this MCP server:

### Prerequisites

1. **OpenAI API key** must be configured:
   ```bash
   # Option 1: Environment variable
   export OPENAI_API_KEY=sk-...
   
   # Option 2: Config file (recommended for security)
   mkdir -p ~/.config/comma-tools
   echo "sk-..." > ~/.config/comma-tools/openai.key
   chmod 600 ~/.config/comma-tools/openai.key
   ```

2. **Install comma-tools with phone-a-friend support:**
   ```bash
   cd /path/to/comma-tools
   pip install -e ".[mcp,phone-a-friend]"
   ```

### Claude Code Registration

```bash
# Find the phone-a-friend-mcp command
find . -name phone-a-friend-mcp -path "*/venv/bin/*" | head -1

# Register the MCP server
claude mcp add phone-a-friend --scope user \
  -e PAF_MODEL_NAME=gpt-4o \
  -e PAF_COST_LIMIT_PER_DAY=50.0 \
  -- $(find . -name phone-a-friend-mcp -path "*/venv/bin/*" | head -1)

# Verify connection
claude mcp list
# Expected: phone-a-friend: /path/to/phone-a-friend-mcp - ✓ Connected
```

## Available Tools

### Session Management

- **start_gpt5_session(instructions, context?)** → Start GPT-5 collaboration session
  - `instructions`: System prompt for GPT-5 (describe problem domain)
  - `context`: Optional metadata (vehicle info, log paths, etc.)
  - Returns: `{session_id, status, usage}`

- **send_message_to_gpt5(session_id, message)** → Send message and get response
  - `session_id`: Session ID from start_gpt5_session()
  - `message`: Your message to GPT-5
  - Returns: `{response, status, usage}`

- **end_gpt5_session(session_id)** → End session and cleanup
  - Returns: `{status, final_usage}`

- **list_gpt5_sessions()** → List active sessions
  - Returns: `{sessions[], count}`

### Monitoring

- **get_usage_stats(session_id?)** → Get usage and cost metrics
- **check_health()** → Check server health and status

### Resources

- **paf://config** - Server configuration and status
- **paf://usage** - Detailed usage and cost information

## Example Workflows

### Workflow 1: Debugging Cruise Control Issue

```python
# Claude (you) orchestrating between human, GPT-5, and comma-tools

# Human: "My Subaru's cruise control set button isn't working. Can you help?"

# 1. Start GPT-5 session with domain expertise
session = start_gpt5_session(
    instructions="""You are an expert in automotive CAN bus analysis and Subaru 
    cruise control systems. Help debug issues by analyzing CAN message patterns 
    and suggesting diagnostic approaches.""",
    context={
        "vehicle": "2019 Subaru Outback",
        "issue": "cruise_control_set_button",
        "log_available": True
    }
)

# 2. Consult GPT-5 about the problem
response1 = send_message_to_gpt5(
    session_id=session["session_id"],
    message="""User reports cruise control set button not working on 2019 Subaru Outback. 
    I have an rlog.zst file. What analysis should I run first?"""
)
# GPT-5: "Start by converting the log to CSV and looking at CAN address 0x146 
#         which contains cruise button states..."

# 3. Run comma-tools analysis (via comma-tools MCP)
analysis_result = run_analysis("rlog-to-csv", {
    "rlog": "/path/to/log.zst",
    "out": "/tmp/analysis.csv"
})

# 4. Send results back to GPT-5
response2 = send_message_to_gpt5(
    session_id=session["session_id"],
    message=f"""I've analyzed the log. Here's what I found:
    - CAN address 0x146 shows activity
    - Byte 0 bit patterns suggest button press detection
    - However, the set button bit (bit 2) never transitions to 1
    
    What could cause this?"""
)
# GPT-5: "This pattern suggests either a hardware fault in the button itself,
#         a wiring issue, or a problem with the CCM (cruise control module)..."

# 5. End session when done
end_gpt5_session(session["session_id"])

# 6. Present findings to human
# "Based on GPT-5's analysis and the CAN data, it appears to be a hardware issue..."
```

### Workflow 2: CAN Bus Pattern Analysis

```python
# Human: "I'm trying to reverse-engineer the turn signal CAN message. 
#         Which bits indicate left vs right?"

# 1. Start GPT-5 session
session = start_gpt5_session(
    instructions="""You are an expert in CAN bus reverse engineering. 
    Help identify bit patterns that correlate with vehicle behaviors.""",
    context={"task": "bit_pattern_analysis", "signal": "turn_indicators"}
)

# 2. Get GPT-5's methodology
response = send_message_to_gpt5(
    session_id=session["session_id"],
    message="""User wants to identify turn signal bits in CAN messages. 
    What's the best approach for this analysis?"""
)
# GPT-5: "Use can-bitwatch to track bit changes during specific time windows.
#         Recommend using marker detection with blinkers..."

# 3. Execute comma-tools analysis with GPT-5's recommended approach
# ... run can-bitwatch with marker detection ...

# 4. Iterate with GPT-5 on findings
# ... back-and-forth analysis ...

# 5. End session
end_gpt5_session(session["session_id"])
```

## Configuration

Configure via environment variables (prefix with `PAF_`):

```bash
# OpenAI Settings
PAF_OPENAI_API_KEY=sk-...              # Or use OPENAI_API_KEY
PAF_OPENAI_API_KEY_PATH=~/.config/comma-tools/openai.key
PAF_MODEL_NAME=gpt-4o                  # Model to use

# Rate Limiting
PAF_MAX_CONCURRENT_SESSIONS=5          # Max simultaneous sessions
PAF_MAX_REQUESTS_PER_MINUTE=60         # API rate limit
PAF_MAX_TOKENS_PER_REQUEST=4096        # Max tokens per request

# Session Management
PAF_SESSION_TIMEOUT_SECONDS=1800       # 30 minutes idle timeout
PAF_SESSION_RETENTION_DAYS=30          # Transcript retention

# Cost Controls
PAF_COST_LIMIT_PER_SESSION=5.0         # Max $5 per session
PAF_COST_LIMIT_PER_DAY=50.0            # Max $50 per day
```

Or create `.env` file in project root:
```env
PAF_MODEL_NAME=gpt-4o
PAF_COST_LIMIT_PER_DAY=50.0
```

## Cost Estimation

Rough estimates for GPT-4o (actual costs vary):
- Input: ~$5 per 1M tokens
- Output: ~$15 per 1M tokens
- Average message: ~500 tokens = ~$0.01
- Typical debugging session (20 messages): ~$0.20
- Daily limit default ($50): ~2500 messages

Monitor usage with:
```python
get_usage_stats()  # Global stats
get_usage_stats(session_id="...")  # Session-specific
```

## Security

**API Key Security:**
- Never commit API keys to git
- Use file permissions: `chmod 600 ~/.config/comma-tools/openai.key`
- Keys are never logged or exposed in responses
- Environment variables are preferred over hardcoded values

**Rate Limiting:**
- Automatic throttling prevents runaway costs
- Per-session cost limits
- Daily cost caps with automatic reset
- Real-time usage monitoring

**Session Isolation:**
- Each session has independent conversation history
- Sessions timeout after inactivity
- Automatic cleanup of expired sessions

## Troubleshooting

**"Failed to initialize: OpenAI API key not found"**
```bash
# Verify key location
echo $OPENAI_API_KEY
cat ~/.config/comma-tools/openai.key

# Set key
export OPENAI_API_KEY=sk-...
```

**"Maximum concurrent sessions reached"**
```python
# List active sessions
sessions = list_gpt5_sessions()

# End unused sessions
for session in sessions["sessions"]:
    end_gpt5_session(session["session_id"])
```

**"Rate limit exceeded"**
```python
# Check current usage
stats = get_usage_stats()
print(stats["usage"]["requests_per_minute"])

# Wait before retrying
import time
time.sleep(60)
```

**"Daily cost limit reached"**
```python
# Check usage
stats = get_usage_stats()
print(f"Daily cost: ${stats['usage']['daily_cost']:.2f}")

# Increase limit in config (use responsibly!)
# PAF_COST_LIMIT_PER_DAY=100.0
```

## Development

### Testing the Server

```bash
# Start server manually for testing
export OPENAI_API_KEY=sk-...
python -m phone_a_friend_mcp.server

# Test with MCP inspector
pip install mcp-inspector
mcp dev src/phone_a_friend_mcp/server.py
```

### Adding New Tools

```python
@mcp.tool()
async def my_new_tool(param: str) -> Dict[str, Any]:
    """
    Description for AI assistants.
    
    Args:
        param: Parameter description
        
    Returns:
        Return value description
    """
    # Implementation
    return {"status": "success", "result": "..."}
```

## Comparison with cts-mcp

| Feature | cts-mcp | phone-a-friend-mcp |
|---------|---------|-------------------|
| Purpose | Expose comma-tools to AI | Expose GPT-5 to AI |
| Direction | AI → Tools | AI → GPT-5 |
| Backend | CTS-Lite HTTP API | OpenAI Agents SDK |
| Use Case | Run log analysis | Complex reasoning |
| Cost | Free (local) | Paid (OpenAI API) |

**When to use phone-a-friend:**
- Need deep domain expertise (automotive, CAN bus)
- Complex multi-step reasoning required
- Benefit from GPT-5's training on technical docs
- Want a second "AI opinion" on analysis

**When to use cts-mcp directly:**
- Standard log conversion and analysis
- Known analysis workflows
- Cost-sensitive operations
- No complex reasoning needed

## Future Enhancements

- [ ] Streaming responses for long GPT-5 outputs
- [ ] Session persistence across server restarts
- [ ] Multi-model support (GPT-4, Claude-3, etc.)
- [ ] Actual delegate tool for GPT-5 to call comma-tools directly
- [ ] Fine-tuned models for automotive analysis
- [ ] Cost optimization with caching
- [ ] Session export/import for collaboration

## References

- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [comma-tools MCP Server](../comma_tools_mcp/)
- [CTS-Lite API Documentation](../../docs/CTS_LITE_README.md)
