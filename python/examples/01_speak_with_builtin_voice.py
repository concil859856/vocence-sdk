"""Speak text in a pre-defined built-in voice.

Run with VOCENCE_API_KEY=voc_live_... python 01_speak_with_builtin_voice.py
"""

from vocence import Vocence

client = Vocence()  # picks up VOCENCE_API_KEY from the env

# Browse the catalog
for v in client.voices.builtin()[:5]:
    print(v.id, "·", v.name, "·", v.description)

# Synthesize in a specific speaker
audio = client.tts.speak(text="Hello from Vocence!", voice="design-aria")
print("\naudio URL:", audio.audio_url)
print("provider :", audio.provider)
