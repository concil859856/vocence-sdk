"""High-level voice conversation — say() returns when the assistant's
turn ends, with text + audio aggregated.

Usage:
    VOCENCE_API_KEY=voc_live_... python 06_conversation.py <agent_id>
"""

import asyncio
import sys

from vocence import AsyncVocence


async def main(agent_id: str) -> None:
    async with AsyncVocence() as client:
        async with client.agents.conversation(agent_id) as conv:
            turn = await conv.say("What is the capital of France?")
            print("assistant:", turn.text)
            print(f"  · {len(turn.audio):,} bytes of audio  ({turn.audio_meta})")

            # Multi-turn — same session, second message
            turn2 = await conv.say("And of Japan?")
            print("assistant:", turn2.text)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
