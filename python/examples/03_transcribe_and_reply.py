"""STT → your LLM → TTS round-trip.

Usage:
    VOCENCE_API_KEY=voc_live_... python 03_transcribe_and_reply.py ./user_message.wav
"""

import sys

from vocence import Vocence

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

client = Vocence()

# 1. Transcribe what the user said
heard = client.stt.transcribe(audio_path=sys.argv[1], language="English").text
print("user said:", heard)

# 2. (your LLM call here)
reply = f"You said: {heard}. Here is my response..."

# 3. Speak the reply in a chosen voice
audio = client.tts.speak(text=reply, voice="design-aria")
print("reply audio URL:", audio.audio_url)
