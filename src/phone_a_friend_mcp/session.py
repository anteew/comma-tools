"""Session management for GPT-5 agent interactions."""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from agents import Agent, Runner
from agents.result import RunResult


@dataclass
class SessionMessage:
    """A message in a session conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    """
    A GPT-5 agent session with conversation history.

    Attributes:
        session_id: Unique session identifier
        agent: OpenAI agent instance
        messages: Conversation history
        created_at: Session creation timestamp
        last_active: Last activity timestamp
        metadata: Session metadata (user context, vehicle info, etc.)
        total_tokens: Total tokens used in this session
        total_cost: Estimated total cost in USD
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent: Optional[Agent] = None
    messages: List[SessionMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    total_tokens: int = 0
    total_cost: float = 0.0

    def add_message(
        self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a message to the conversation history."""
        self.messages.append(SessionMessage(role=role, content=content, metadata=metadata or {}))
        self.last_active = time.time()

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get conversation history in OpenAI format."""
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]

    def is_expired(self, timeout_seconds: int) -> bool:
        """Check if session has expired due to inactivity."""
        return time.time() - self.last_active > timeout_seconds

    def get_age_seconds(self) -> float:
        """Get session age in seconds."""
        return time.time() - self.created_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary representation."""
        return {
            "session_id": self.session_id,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "last_active": datetime.fromtimestamp(self.last_active).isoformat(),
            "age_seconds": self.get_age_seconds(),
            "message_count": len(self.messages),
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "metadata": self.metadata,
        }


class SessionManager:
    """
    Manages GPT-5 agent sessions with lifecycle and resource management.

    Provides session creation, retrieval, cleanup, and resource tracking.
    """

    def __init__(self, max_concurrent: int = 5, timeout_seconds: int = 1800):
        """
        Initialize session manager.

        Args:
            max_concurrent: Maximum number of concurrent sessions
            timeout_seconds: Session idle timeout in seconds
        """
        self.sessions: Dict[str, Session] = {}
        self.max_concurrent = max_concurrent
        self.timeout_seconds = timeout_seconds
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        instructions: str,
        metadata: Optional[Dict[str, Any]] = None,
        model: str = "gpt-4o",
        reasoning_effort: Optional[str] = None,
        enable_code_interpreter: bool = False,
        enable_file_search: bool = False,
    ) -> Session:
        """
        Create a new GPT-5 agent session.

        Args:
            instructions: System instructions for the agent
            metadata: Optional session metadata
            model: OpenAI model to use
            reasoning_effort: Reasoning effort for o1 models ("low", "medium", "high")
            enable_code_interpreter: Enable Python code execution
            enable_file_search: Enable file search capabilities

        Returns:
            Created session

        Raises:
            RuntimeError: If max concurrent sessions reached
        """
        async with self._lock:
            await self._cleanup_expired_sessions()

            if len(self.sessions) >= self.max_concurrent:
                raise RuntimeError(
                    f"Maximum concurrent sessions ({self.max_concurrent}) reached. "
                    f"End existing sessions before creating new ones."
                )

            tools = []
            if enable_code_interpreter:
                tools.append("code_interpreter")
            if enable_file_search:
                tools.append("file_search")

            agent_kwargs = {
                "name": "GPT5Expert",
                "instructions": instructions,
                "model": model,
            }

            if tools:
                agent_kwargs["tools"] = tools

            if reasoning_effort and model and ("o1" in model.lower()):
                agent_kwargs["model_settings"] = {"reasoning_effort": reasoning_effort}

            agent = Agent(**agent_kwargs)

            session = Session(
                agent=agent,
                metadata=metadata or {},
            )

            self.sessions[session.session_id] = session

            return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Retrieve a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session if found, None otherwise
        """
        async with self._lock:
            session = self.sessions.get(session_id)
            if session and session.is_expired(self.timeout_seconds):
                del self.sessions[session_id]
                return None
            return session

    async def end_session(self, session_id: str) -> bool:
        """
        End a session and clean up resources.

        Args:
            session_id: Session identifier

        Returns:
            True if session was ended, False if not found
        """
        async with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                return True
            return False

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all active sessions.

        Returns:
            List of session dictionaries
        """
        async with self._lock:
            await self._cleanup_expired_sessions()
            return [session.to_dict() for session in self.sessions.values()]

    async def send_message(
        self,
        session_id: str,
        message: str,
        stream: bool = False,
    ) -> RunResult:
        """
        Send a message to a session's agent and get response.

        Args:
            session_id: Session identifier
            message: User message
            stream: Whether to stream the response

        Returns:
            Agent result with response

        Raises:
            ValueError: If session not found
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found or expired")

        if session.agent is None:
            raise ValueError(f"Session {session_id} has no agent configured")

        session.add_message("user", message)

        result = await Runner.run(
            session.agent,
            message,
        )

        session.add_message("assistant", result.final_output)

        if hasattr(result, "usage") and result.usage:
            session.total_tokens += getattr(result.usage, "total_tokens", 0)

        session.last_active = time.time()

        return result

    async def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions."""
        expired = [
            sid
            for sid, session in self.sessions.items()
            if session.is_expired(self.timeout_seconds)
        ]
        for sid in expired:
            del self.sessions[sid]

    async def start_cleanup_task(self) -> None:
        """Start background task to periodically clean up expired sessions."""
        if self._cleanup_task is not None:
            return

        async def cleanup_loop():
            while True:
                await asyncio.sleep(300)  # Check every 5 minutes
                async with self._lock:
                    await self._cleanup_expired_sessions()

        self._cleanup_task = asyncio.create_task(cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
