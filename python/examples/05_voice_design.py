"""Design a brand-new voice from a written prompt and reuse it.

Usage:
    VOCENCE_API_KEY=voc_live_... python 05_voice_design.py
"""

from vocence import Vocence

client = Vocence()

# 1. Generate two preview variants
preview = client.voice_design.preview(
    voice_description="warm middle-aged female narrator with a slight British accent",
)
print("variant A (original):", preview.audio_a_url)
print("variant B (revised) :", preview.audio_b_url)
print("sample script       :", preview.sample_script)

# 2. Save the chosen variant
saved = client.voice_design.save(
    preview_token=preview.preview_token,
    chosen_variant="revised",
    display_name="Narrator",
)
voice_id = saved["voice_id"]
print("saved voice id:", voice_id)

# 3. Synthesize with the new voice
audio = client.voices.speak(voice_id, text="This narrator was designed in seconds.")
print("audio URL:", audio.audio_url)
