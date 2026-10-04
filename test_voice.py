"""Run this first to confirm Jarvis's voice works:  python test_voice.py"""
import text_to_speech

try:
    import pyttsx3
    voices = pyttsx3.init().getProperty("voices")
    print("Installed voices:")
    for v in voices:
        print("  -", v.name)
except Exception as exc:
    print("Could not list voices:", exc)

print("\nSpeaking test sentence...")
ok = text_to_speech.speak("Hello sir. This is Jarvis. My voice is working correctly.")
print("Voice test passed." if ok else "Voice test FAILED - see the error above.")
text_to_speech.shutdown()
