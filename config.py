"""Central settings for JARVIS. Edit this file to personalise the assistant."""

ASSISTANT_NAME = "Jarvis"
USER_TITLE = "sir"            # How Jarvis addresses you, e.g. "sir", "boss", "Ravi"
DEFAULT_CITY = "Nellore"      # Used when you ask for weather without naming a city

# ---- Speech recognition (microphone -> text) ----
SPEECH_LANGUAGE = "en-IN"     # e.g. "en-US", "en-GB", "en-IN"
LISTEN_TIMEOUT = 5            # Seconds to wait for you to start speaking
PHRASE_TIME_LIMIT = 10        # Maximum length of one spoken command (seconds)

# ---- Text to speech (Jarvis's voice) ----
VOICE_RATE = 170              # Words per minute
VOICE_VOLUME = 1.0            # 0.0 - 1.0
# Jarvis picks the first installed voice whose name contains one of these words.
PREFERRED_VOICES = ("ravi", "david", "mark", "george", "daniel", "alex")
