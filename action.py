"""JARVIS command engine.

Every command is understood with word-boundary patterns (no accidental substring
matches) and Jarvis answers with a reply that is specific to what you asked.
"""
import ast
import datetime
import operator
import os
import platform
import random
import re
import shutil
import subprocess
import threading
import urllib.parse
import webbrowser

import config
import speech_to_text
import text_to_speech
import weather

PASS = object()  # a handler returns this to say "not mine, try the next rule"

SITES = {
    "google": ("Google", "https://www.google.com"),
    "youtube": ("YouTube", "https://www.youtube.com"),
    "gmail": ("Gmail", "https://mail.google.com"),
    "github": ("GitHub", "https://github.com"),
    "chatgpt": ("ChatGPT", "https://chatgpt.com"),
    "claude": ("Claude", "https://claude.ai"),
    "facebook": ("Facebook", "https://www.facebook.com"),
    "instagram": ("Instagram", "https://www.instagram.com"),
    "whatsapp": ("WhatsApp Web", "https://web.whatsapp.com"),
    "linkedin": ("LinkedIn", "https://www.linkedin.com"),
    "x": ("X", "https://x.com"),
    "maps": ("Google Maps", "https://maps.google.com"),
    "wikipedia": ("Wikipedia", "https://www.wikipedia.org"),
    "netflix": ("Netflix", "https://www.netflix.com"),
    "amazon": ("Amazon", "https://www.amazon.in"),
    "flipkart": ("Flipkart", "https://www.flipkart.com"),
    "stack overflow": ("Stack Overflow", "https://stackoverflow.com"),
}
SITE_ALIASES = {
    "you tube": "youtube", "g mail": "gmail", "email": "gmail", "mail": "gmail",
    "git hub": "github", "chat gpt": "chatgpt", "twitter": "x",
    "google maps": "maps", "map": "maps", "whats app": "whatsapp", "whatsapp web": "whatsapp",
    "stackoverflow": "stack overflow", "wiki": "wikipedia",
}

APPS = {
    "calculator": ("Calculator", {"Windows": ["calc.exe"], "Darwin": ["open", "-a", "Calculator"], "Linux": ["gnome-calculator"]}),
    "notepad": ("Notepad", {"Windows": ["notepad.exe"], "Darwin": ["open", "-a", "TextEdit"], "Linux": ["gedit"]}),
    "paint": ("Paint", {"Windows": ["mspaint.exe"]}),
    "file explorer": ("File Explorer", {"Windows": ["explorer.exe"], "Darwin": ["open", "."], "Linux": ["xdg-open", "."]}),
    "task manager": ("Task Manager", {"Windows": ["taskmgr.exe"]}),
    "command prompt": ("Command Prompt", {"Windows": ["cmd.exe"]}),
    "settings": ("Settings", {"Windows": ["ms-settings:"]}),
}
APP_ALIASES = {
    "calc": "calculator", "text editor": "notepad", "explorer": "file explorer",
    "files": "file explorer", "cmd": "command prompt", "terminal": "command prompt",
    "windows settings": "settings", "ms paint": "paint",
}

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I would tell you a UDP joke, but you might not get it.",
    "There are only 10 kinds of people in the world: those who understand binary and those who don't.",
    "Why did the developer go broke? Because he used up all his cache.",
    "A SQL query walks into a bar, walks up to two tables and asks: can I join you?",
]

_MATH_WORDS = [
    (r"\bmultiplied by\b", " * "), (r"\bdivided by\b", " / "), (r"\bto the power of\b", " ** "),
    (r"\braised to\b", " ** "), (r"\btimes\b", " * "), (r"\bplus\b", " + "),
    (r"\bminus\b", " - "), (r"\bover\b", " / "), (r"\bmodulo\b", " % "), (r"\bmod\b", " % "),
]
_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
}


# --------------------------------------------------------------------------- helpers

def _day_period(now=None):
    hour = (now or datetime.datetime.now()).hour
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    return "evening"


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _safe_eval(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left, right = _safe_eval(node.left), _safe_eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 100 or abs(left) > 1_000_000):
            raise ValueError("number too large")
        result = _BIN_OPS[type(node.op)](left, right)
        if isinstance(result, complex):
            raise ValueError("complex result")
        return result
    raise ValueError("unsupported expression")


def _to_expression(text):
    """Turn spoken maths ('12 times 4', '20 percent of 150') into a Python expression."""
    expr = text.lower()
    expr = re.sub(r"(\d+(?:\.\d+)?)\s*(?:percent|%)\s*of\s*(\d+(?:\.\d+)?)", r"(\1 / 100 * \2)", expr)
    for pattern, symbol in _MATH_WORDS:
        expr = re.sub(pattern, symbol, expr)
    expr = re.sub(r"(?<=\d)\s*x\s*(?=\d)", " * ", expr)
    expr = expr.replace("^", "**").replace("×", "*").replace("÷", "/")
    if not re.fullmatch(r"[\d\s+\-*/%().]+", expr):
        return None
    if not re.search(r"\d", expr) or not re.search(r"[+\-*/%]", expr.strip().lstrip("+-")):
        return None
    return expr.strip()


def _format_number(value):
    if isinstance(value, float):
        value = round(value, 4)
        if value.is_integer():
            value = int(value)
    return str(value)


# --------------------------------------------------------------------------- assistant

class Jarvis:
    """The assistant. Independent of the GUI: it only reports through two callbacks.

    on_message(role, text)  role is "user", "jarvis", "system" or "error"
    on_state(state)         state is "idle", "listening", "thinking", "speaking" or "stopped"
    """

    def __init__(self, on_message=None, on_state=None, speak_aloud=True):
        self.on_message = on_message or (lambda role, text: print(f"{role.capitalize()}: {text}"))
        self.on_state = on_state or (lambda state: None)
        self.speak_aloud = speak_aloud
        self.title = config.USER_TITLE
        self.name = config.ASSISTANT_NAME
        self.listen_fn = None
        self._interactive = False
        self._state = "idle"
        self._lock = threading.RLock()
        self._rules = self._build_rules()

    # ---- output ------------------------------------------------------------
    def message(self, role, text):
        try:
            self.on_message(role, text)
        except Exception as exc:  # a broken GUI must never crash the assistant
            print("Display error:", exc)

    def set_state(self, state):
        self._state = state
        try:
            self.on_state(state)
        except Exception as exc:
            print("State error:", exc)

    def say(self, text):
        """Show the reply, then speak it (returns once Jarvis has finished talking)."""
        self.message("jarvis", text)
        if not self.speak_aloud:
            return
        previous = self._state
        self.set_state("speaking")
        text_to_speech.speak(text)
        self.set_state(previous)

    # ---- understanding -----------------------------------------------------
    @staticmethod
    def normalize(text):
        t = text.lower().strip()
        t = re.sub(r"[?!,;:\"“”]", " ", t)
        t = re.sub(r"\s+", " ", t).strip(" .")
        if t in ("jarvis", "hey jarvis", "ok jarvis", "okay jarvis"):
            return ""
        t = re.sub(r"^(?:(?:hey|ok|okay)\s+)?jarvis\s+(?=\S)", "", t)
        t = re.sub(r"(?<=\S)\s+jarvis$", "", t)
        for _ in range(3):
            t = re.sub(r"^(?:please|can you|could you|will you|would you)\s+", "", t)
        t = re.sub(r"\s+please$", "", t)
        return t.strip()

    def _build_rules(self):
        r = re.compile
        return [
            (r(r"^(?:stop|exit|quit|shut ?down|turn off|terminate|close|go to sleep|good ?bye|bye|bye bye)(?: jarvis| yourself| listening| assistant)?$"), self._exit),
            (r(r"^(?:hello|hi|hey)(?: there)?$"), self._greet),
            (r(r"^good (morning|afternoon|evening|night)$"), self._timed_greet),
            (r(r"\bhow are you\b"), self._how_are_you),
            (r(r"\bwhat(?:'s|s| is)? your name\b"), self._your_name),
            (r(r"\bwho are you\b"), self._who_are_you),
            (r(r"\bwho (?:created|made|built|developed) you\b"), self._creator),
            (r(r"\bhow old are you\b"), self._age),
            (r(r"\b(?:thank you|thanks|thank u)\b"), self._thanks),
            (r(r"^(?:help|commands|show commands)$|\bwhat can you do\b|\bwhat are your commands\b"), self._help),
            (r(r"\b(?:what(?:'s|s| is)? the (?:current )?time|what time|current time|time now|tell me the time)\b|^time$"), self._time),
            (r(r"\b(?:what(?:'s|s| is)? (?:the |today's |todays )?(?:current )?date|today(?:'s|s)? date|today date|current date|tell me the date)\b"), self._date),
            (r(r"\bwhat day (?:is it|is today)\b|\bwhich day\b"), self._day),
            (r(r"\b(?:weather|temperature)\b(?:.*?\b(?:in|at|for|of)\s+(?P<city>[a-z][a-z .'-]*))?"), self._weather),
            (r(r"^(?:calculate|compute|solve|evaluate|what(?:'s|s| is)|how much is)\s+(?P<expr>.+)$"), self._math),
            (r(r"^(?:search|find|look up|look for)(?: for)? (?P<q>.+?) (?:on|in) youtube$"), self._youtube),
            (r(r"^(?:youtube search|search youtube|youtube)(?: for)? (?P<q>.+)$"), self._youtube),
            (r(r"^play (?P<q>.+?) (?:on|in) youtube$"), self._youtube),
            (r(r"^(?:google search|search google|search on google|search|google|look up|look for)(?: for| about)? (?P<q>.+?)(?: (?:on|in) google)?$"), self._google),
            (r(r"^play (?:some )?(?:music|songs?)$|^music$"), self._music),
            (r(r"^play (?P<q>.+)$"), self._youtube),
            (r(r"^(?:open|launch|start|go to|take me to)\s+(?P<target>.+)$"), self._open),
            (r(r"\b(?:tell me a joke|joke|make me laugh)\b"), self._joke),
            (r(r"^(?:who|what|when|where|why|how|which|tell me about|explain)\b"), self._web_answer),
        ]

    def handle(self, text, interactive=False):
        """Process one command. Returns False when Jarvis should shut down."""
        with self._lock:
            raw = (text or "").strip()
            if not raw:
                return True
            self.message("user", raw)
            self._interactive = interactive
            self.set_state("thinking")
            command = self.normalize(raw)
            try:
                if not command:
                    self.say(f"Yes, {self.title}? I'm listening.")
                    return True
                for pattern, handler in self._rules:
                    match = pattern.search(command)
                    if not match:
                        continue
                    result = handler(match, command)
                    if result is PASS:
                        continue
                    return result is not False
                self.say(f"I'm sorry, {self.title}, I didn't understand \"{command}\". Say help to hear what I can do.")
                return True
            except Exception as exc:
                self.message("error", f"{type(exc).__name__}: {exc}")
                self.say(f"Sorry {self.title}, something went wrong while I was handling that.")
                return True

    # ---- voice loop --------------------------------------------------------
    def run_voice_loop(self, stop_event):
        """Listen -> understand -> answer, until stop_event is set or you say stop."""
        self.listen_fn = speech_to_text.listen
        self.say(f"Good {_day_period()}, {self.title}. {self.name} is online and ready. How can I help you?")
        service_failures = 0
        try:
            while not stop_event.is_set():
                self.set_state("listening")
                try:
                    heard = speech_to_text.listen()
                except speech_to_text.MicrophoneError as exc:
                    self.message("error", f"Microphone problem: {exc}")
                    self.say(f"I can't access the microphone, {self.title}. Please check that it is connected and allowed. You can still type commands.")
                    break
                except speech_to_text.SpeechServiceError as exc:
                    service_failures += 1
                    self.message("error", f"Speech service problem: {exc}")
                    if service_failures in (1, 5):
                        self.say(f"I can't reach the speech recognition service, {self.title}. Please check your internet connection.")
                    stop_event.wait(3)
                    continue
                service_failures = 0
                if not heard:
                    continue
                if not self.handle(heard, interactive=True):
                    break
        finally:
            self.listen_fn = None
            self.set_state("stopped")

    # ---- actions -----------------------------------------------------------
    def _open_url(self, url):
        try:
            return bool(webbrowser.open(url))
        except Exception:
            return False

    def _browser_failed(self):
        self.say(f"Sorry {self.title}, I couldn't open the web browser.")

    def _exit(self, m, cmd):
        self.say(f"Shutting down {self.name}. Goodbye, {self.title}.")
        return False

    def _greet(self, m, cmd):
        self.say(random.choice([
            f"Hello, {self.title}. How can I help you?",
            f"Good {_day_period()}, {self.title}. What can I do for you?",
        ]))

    def _timed_greet(self, m, cmd):
        replies = {
            "morning": f"Good morning, {self.title}. I hope you have a wonderful day. How can I help?",
            "afternoon": f"Good afternoon, {self.title}. How can I help you?",
            "evening": f"Good evening, {self.title}. How can I help you?",
            "night": f"Good night, {self.title}. Sleep well. I'll be here whenever you need me.",
        }
        self.say(replies[m.group(1)])

    def _how_are_you(self, m, cmd):
        self.say(f"I'm running smoothly, {self.title}, thank you for asking. How can I help you?")

    def _your_name(self, m, cmd):
        self.say(f"My name is {self.name}, {self.title}. I'm your personal voice assistant.")

    def _who_are_you(self, m, cmd):
        self.say(f"I'm {self.name}, a Python voice assistant. I can answer questions, open websites and apps, and search the web for you.")

    def _creator(self, m, cmd):
        self.say(f"I was built as a Python virtual assistant project, {self.title}.")

    def _age(self, m, cmd):
        self.say(f"I'm software, {self.title}, so I don't age like humans do.")

    def _thanks(self, m, cmd):
        self.say(random.choice([
            f"You're very welcome, {self.title}.",
            f"My pleasure, {self.title}. Anything else?",
        ]))

    def _help(self, m, cmd):
        self.say(
            "I can tell you the time and date, check the weather for any city, search Google and YouTube, "
            "play music, open websites and apps like Gmail, GitHub or Calculator, do quick calculations, "
            f"and tell jokes. Say stop to shut me down, {self.title}."
        )

    def _time(self, m, cmd):
        now = datetime.datetime.now().strftime("%I:%M %p").lstrip("0")
        self.say(f"It's {now}, {self.title}.")

    def _date(self, m, cmd):
        now = datetime.datetime.now()
        self.say(f"Today is {now.strftime('%A')}, {now.day} {now.strftime('%B %Y')}, {self.title}.")

    def _day(self, m, cmd):
        self.say(f"Today is {datetime.datetime.now().strftime('%A')}, {self.title}.")

    def _ask_city(self):
        if self._interactive and self.listen_fn:
            self.say(f"Which city should I check, {self.title}?")
            self.set_state("listening")
            try:
                heard = self.listen_fn()
            except Exception:
                heard = ""
            heard = re.sub(r"^(?:in|at|for|it's|its|the weather in)\s+", "", heard.strip())
            if heard:
                self.message("user", heard)
                return heard.title()
            self.say(f"I didn't catch a city, so I'll use {config.DEFAULT_CITY}.")
        return config.DEFAULT_CITY

    def _weather(self, m, cmd):
        city = (m.groupdict().get("city") or "").strip()
        city = re.sub(r"\b(?:today|tonight|now|right now|currently|outside|please|like)\b", " ", city)
        city = " ".join(city.split()).title()
        if not city:
            city = self._ask_city()
        self.say(f"Checking the weather in {city}, {self.title}.")
        try:
            self.say(weather.get_weather(city))
        except weather.WeatherError as exc:
            self.say(str(exc))

    def _math(self, m, cmd):
        spoken = m.group("expr")
        expression = _to_expression(spoken)
        if not expression:
            return PASS
        try:
            result = _safe_eval(ast.parse(expression, mode="eval"))
        except ZeroDivisionError:
            self.say(f"I can't divide by zero, {self.title}.")
            return None
        except (ValueError, SyntaxError, OverflowError):
            return PASS
        self.say(f"{spoken} is {_format_number(result)}, {self.title}.")

    def _youtube(self, m, cmd):
        query = m.group("q").strip()
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
        if self._open_url(url):
            verb = "Finding" if cmd.startswith("play") else "Searching YouTube for"
            suffix = " on YouTube" if cmd.startswith("play") else ""
            self.say(f"{verb} {query}{suffix}, {self.title}.")
        else:
            self._browser_failed()

    def _google(self, m, cmd):
        query = m.group("q").strip()
        self._search_google(query, f"Searching Google for {query}, {self.title}.")

    def _search_google(self, query, reply):
        url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
        if self._open_url(url):
            self.say(reply)
        else:
            self._browser_failed()

    def _music(self, m, cmd):
        if self._open_url("https://music.youtube.com/"):
            self.say(f"Playing music for you, {self.title}. Opening YouTube Music.")
        else:
            self._browser_failed()

    def _open(self, m, cmd):
        target = re.sub(r"^(?:the|my)\s+|\s+(?:app|application|website|site|page)$", "", m.group("target").strip())
        key = SITE_ALIASES.get(target, target)
        if key in SITES:
            label, url = SITES[key]
            if self._open_url(url):
                self.say(f"Opening {label}, {self.title}.")
            else:
                self._browser_failed()
            return
        app_key = APP_ALIASES.get(target, target)
        if app_key in APPS:
            label = APPS[app_key][0]
            if self._launch_app(app_key):
                self.say(f"Opening {label}, {self.title}.")
            else:
                self.say(f"Sorry {self.title}, I couldn't open {label} on this computer.")
            return
        if re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", target):
            if self._open_url("https://" + target):
                self.say(f"Opening {target}, {self.title}.")
            else:
                self._browser_failed()
            return
        self._search_google(
            target,
            f"I don't have {target} in my list, {self.title}, so I'm searching Google for it.",
        )

    def _launch_app(self, key):
        system = platform.system()
        command = APPS[key][1].get(system)
        if not command:
            return False
        try:
            if system == "Windows" and command[0].startswith("ms-settings"):
                os.startfile(command[0])  # noqa: only exists on Windows
            else:
                if system != "Windows" and shutil.which(command[0]) is None:
                    return False
                if system == "Windows" and command[0] == "cmd.exe":
                    subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(command)
            return True
        except Exception:
            return False

    def _joke(self, m, cmd):
        self.say(random.choice(JOKES))

    def _web_answer(self, m, cmd):
        self._search_google(
            cmd,
            f"I don't have a direct answer for that, {self.title}, so I'm searching Google for you.",
        )


# --------------------------------------------------------------------------- console mode

def Action():
    """Run Jarvis in the terminal (voice only). Press Ctrl+C to quit."""
    stop = threading.Event()
    try:
        Jarvis().run_voice_loop(stop)
    except KeyboardInterrupt:
        stop.set()
        print("\nJarvis stopped.")
    finally:
        text_to_speech.shutdown()


if __name__ == "__main__":
    Action()
