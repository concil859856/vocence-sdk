"""Upload a reference clip and reuse the cloned voice.

Usage:
    VOCENCE_API_KEY=voc_live_... python 02_clone_voice_from_clip.py ./my_voice.wav
"""

import sys

from vocence import Vocence

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

client = Vocence()
saved = client.voice_clone.save(audio_path=sys.argv[1], display_name="My Voice")
voice_id = saved["voice_id"]
print("Saved voice id:", voice_id)

audio = client.voices.speak(voice_id, text="This is my cloned voice speaking.")
print("audio URL:", audio.audio_url)
