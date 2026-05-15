"""Pydantic response models for every endpoint.

Models are kept permissive (``extra='allow'``) so the SDK keeps working when
the server adds new fields. New optional fields can be promoted to typed
attributes in future SDK releases without breaking existing callers.
"""

from .account import Account, ApiKey, ApiKeyCreated, UsageEntry
from .agent import Agent, AgentBinding, AgentConfig, AgentSummary
from .response import AudioResponse, CloneResponse, SttResponse, TtsResponse
from .tool import CustomTool
from .voice import BuiltinVoice, SavedVoice, VoiceDesignPreview

__all__ = [
    "Account",
    "Agent",
    "AgentBinding",
    "AgentConfig",
    "AgentSummary",
    "ApiKey",
    "ApiKeyCreated",
    "AudioResponse",
    "BuiltinVoice",
    "CloneResponse",
    "CustomTool",
    "SavedVoice",
    "SttResponse",
    "TtsResponse",
    "UsageEntry",
    "VoiceDesignPreview",
]
