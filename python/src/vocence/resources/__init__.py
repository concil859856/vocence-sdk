"""Resource modules grouped by tag on the public API.

Each module defines a sync ``X`` and async ``AsyncX`` resource class. They
are attached as attributes on the top-level client (``client.tts``,
``client.voices``, ``client.agents``, …).
"""

from .account import AccountResource, AsyncAccountResource
from .agent_tools import AgentToolsResource, AsyncAgentToolsResource
from .agents import AgentsResource, AsyncAgentsResource
from .embed_tokens import AsyncEmbedTokensResource, EmbedTokensResource
from .feedback import AsyncFeedbackResource, FeedbackResource
from .knowledge import AsyncKnowledgeResource, KnowledgeResource
from .stt import AsyncSttResource, SttResource
from .tts import AsyncTtsResource, TtsResource
from .voice_clone import AsyncVoiceCloneResource, VoiceCloneResource
from .voice_design import AsyncVoiceDesignResource, VoiceDesignResource
from .voices import AsyncVoicesResource, VoicesResource

__all__ = [
    "AccountResource",
    "AgentToolsResource",
    "AgentsResource",
    "AsyncAccountResource",
    "AsyncAgentToolsResource",
    "AsyncAgentsResource",
    "AsyncEmbedTokensResource",
    "AsyncFeedbackResource",
    "AsyncKnowledgeResource",
    "AsyncSttResource",
    "AsyncTtsResource",
    "AsyncVoiceCloneResource",
    "AsyncVoiceDesignResource",
    "AsyncVoicesResource",
    "EmbedTokensResource",
    "FeedbackResource",
    "KnowledgeResource",
    "SttResource",
    "TtsResource",
    "VoiceCloneResource",
    "VoiceDesignResource",
    "VoicesResource",
]
