"""Push-to-talk mic ↔ agent conversation.

Requires:  pip install "vocence[audio]"

Usage:
    VOCENCE_API_KEY=voc_live_... python 07_live_chat.py <agent_id>

Each turn:
    1. Press Enter to start recording.
    2. Speak.
    3. Press Enter to stop — the audio is sent, transcript + reply text
       print, and the reply plays back through your speakers.
"""

import asyncio
import sys

from vocence import AsyncVocence


async def main(agent_id: str) -> None:
    async with AsyncVocence() as client:
        async with client.agents.live_chat(agent_id) as live:
            while True:
                input("\npress enter to start speaking…")
                live.record()
                input("recording — press enter to stop…")
                turn = await live.stop_and_send()
                print(f"you   > {turn['transcript']}")
                print(f"agent > {turn['text']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    try:
        asyncio.run(main(sys.argv[1]))
    except KeyboardInterrupt:
        pass
