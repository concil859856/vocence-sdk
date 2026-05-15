"""Connect to a Vocence voice agent over WebSocket and stream events.

Create an agent on the website (or with this SDK) first, then:
    VOCENCE_API_KEY=voc_live_... python 04_voice_agent_ws.py <agent_id>
"""

import asyncio
import sys

from vocence import AsyncVocence


async def main(agent_id: str) -> None:
    async with AsyncVocence() as client:
        async with client.agents.session(agent_id) as sess:
            await sess.send_text("What is the capital of Japan?")
            async for event in sess:
                if hasattr(event, "type") and event.type == "token":
                    print(event.text, end="", flush=True)
                elif hasattr(event, "type") and event.type == "turn_end":
                    print()  # newline
                    break
                # AudioFrame instances are also yielded — see _streaming.py


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
