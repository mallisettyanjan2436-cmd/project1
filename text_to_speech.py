"""Jarvis's voice.

All speech runs on ONE dedicated worker thread that owns the pyttsx3 engine.
This avoids the classic "no sound / frozen" problem that happens when an engine
created on the GUI thread is used from another thread.
"""
import queue
import re
import threading

import config

_jobs = queue.Queue()
_worker = None
_worker_lock = threading.Lock()


class _Job:
    def __init__(self, text):
        self.text = text
        self.done = threading.Event()
        self.error = None


def _clean(text):
    """Remove characters that sound odd when read aloud."""
    text = re.sub(r"[*_`#<>|]", "", str(text))
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([,.!?;:])", r"\1", text)


def _select_voice(engine):
    try:
        voices = engine.getProperty("voices") or []
    except Exception:
        return
    for keyword in config.PREFERRED_VOICES:
        for voice in voices:
            if keyword in (getattr(voice, "name", "") or "").lower():
                engine.setProperty("voice", voice.id)
                return


def _speak_now(text):
    import pyttsx3  # imported lazily so the app can start without audio hardware

    engine = pyttsx3.init()
    try:
        engine.setProperty("rate", config.VOICE_RATE)
        engine.setProperty("volume", config.VOICE_VOLUME)
        _select_voice(engine)
        engine.say(text)
        engine.runAndWait()
    finally:
        try:
            engine.stop()
        except Exception:
            pass


def _run():
    while True:
        job = _jobs.get()
        if job is None:
            break
        try:
            _speak_now(job.text)
        except Exception as exc:  # keep the worker alive whatever happens
            job.error = exc
            print("Text-to-speech error:", exc)
        finally:
            job.done.set()


def _ensure_worker():
    global _worker
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_run, name="jarvis-tts", daemon=True)
            _worker.start()


def speak(text, wait=True):
    """Speak `text`. When wait=True this returns only after Jarvis finishes talking,
    so the microphone never hears Jarvis's own voice. Returns True on success."""
    text = _clean(text)
    if not text:
        return True
    _ensure_worker()
    job = _Job(text)
    _jobs.put(job)
    if wait:
        job.done.wait(timeout=30 + len(text) / 8)
        return job.error is None
    return True


def shutdown():
    """Stop the voice worker (called when the app closes)."""
    _jobs.put(None)


# Backwards-compatible name used by the old code.
text_to_speech = speak
