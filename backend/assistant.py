"""Web-facing access to the existing Ollama tool-calling agent."""

from assistant import MODEL, ToolCallError, handle_request

__all__ = ["MODEL", "ToolCallError", "handle_request"]
