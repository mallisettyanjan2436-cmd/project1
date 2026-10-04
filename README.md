<<<<<<< HEAD
# JARVIS - Voice Assistant

A desktop voice assistant for Windows (also works on macOS/Linux). Jarvis listens to your
microphone, understands the command, and **replies in a way that matches what you asked** - both
on screen and out loud.

## Quick start (Windows PowerShell)

```powershell
python -m venv vir
.\vir\Scripts\Activate.ps1
pip install -r requirements.txt
python test_voice.py      # 1. confirm you can hear Jarvis
python GUI.py             # 2. start the assistant
```

Press **Start Listening** and speak, or type a command in the box and press Enter.

If `pip install PyAudio` fails, upgrade pip (`python -m pip install --upgrade pip`) and try again.
On Linux you may first need `sudo apt install portaudio19-dev python3-tk espeak`.

## What Jarvis says for each command

| You say | Jarvis replies |
|---|---|
| "Hello" / "Good morning" | Greets you back, matching what you said |
| "What is your name?" | "My name is Jarvis, sir. I'm your personal voice assistant." |
| "What is the time?" | "It's 3:45 PM, sir." |
| "What is the date?" / "What day is it?" | "Today is Sunday, 4 October 2026, sir." |
| "Weather in Delhi" | "Checking the weather in Delhi, sir." then the live temperature, conditions and humidity |
| "Weather" | Asks which city (or uses your default city when typed) |
| "What is 12 times 4?" / "20 percent of 150" | "12 times 4 is 48, sir." |
| "Search Google for python tutorials" | "Searching Google for python tutorials, sir." (opens the results) |
| "Search lo-fi beats on YouTube" | "Searching YouTube for lo-fi beats, sir." |
| "Play music" | "Playing music for you, sir. Opening YouTube Music." |
| "Play Believer" | "Finding Believer on YouTube, sir." |
| "Open YouTube / Gmail / GitHub / ChatGPT / Maps..." | "Opening YouTube, sir." |
| "Open Calculator / Notepad / Paint / File Explorer" | "Opening Calculator, sir." |
| "Who is the Prime Minister of India?" | Says it has no direct answer and searches Google for it |
| "Tell me a joke" | Tells a joke |
| "Help" | Lists everything Jarvis can do |
| "Stop" / "Goodbye" / "Exit" | "Shutting down Jarvis. Goodbye, sir." |

You can also begin with the name: "Jarvis, what is the time?" or "Hey Jarvis, open Google".
Anything Jarvis does not understand is repeated back to you so you can see what he heard.

## Settings

Edit **config.py** to change how Jarvis addresses you (`USER_TITLE`), your default weather city,
the recognition language, speaking speed and preferred voice.

**Weather** works with no setup. To use OpenWeatherMap instead, set the environment variable
`OPENWEATHER_API_KEY` before starting Jarvis.

## Files

| File | Purpose |
|---|---|
| `GUI.py` | Window, chat log, status indicator, typed commands |
| `action.py` | Understands commands and chooses the reply |
| `speech_to_text.py` | Microphone -> text, with clear error reporting |
| `text_to_speech.py` | Jarvis's voice (runs on its own safe thread) |
| `weather.py` | Weather lookup |
| `config.py` | Your personal settings |
| `test_voice.py` | Checks that the voice works |
| `test_commands.py` | Automated tests for all commands (`python test_commands.py`) |

## Troubleshooting

- **No sound:** run `python test_voice.py`; check your speaker volume and Windows default output device.
- **"I can't access the microphone":** check Windows Settings > Privacy > Microphone, and that PyAudio installed.
- **"I can't reach the speech recognition service":** speech recognition uses Google's online service, so an internet connection is required.
- **Jarvis mishears you:** set `SPEECH_LANGUAGE` in `config.py` (e.g. `en-US`) and speak after the status shows LISTENING.
=======
# project1
>>>>>>> 924fc6539086720e152e13171cc3192ea4aa0dee
