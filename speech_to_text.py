"""Microphone -> text, with clear errors so Jarvis can tell you what is wrong."""
import config


class MicrophoneError(Exception):
    """The microphone (or PyAudio) is missing or not accessible."""


class SpeechServiceError(Exception):
    """The online recognition service could not be reached."""


_recognizer = None
_calibrated = False


def _get_recognizer():
    global _recognizer
    import speech_recognition as sr  # lazy import

    if _recognizer is None:
        _recognizer = sr.Recognizer()
        _recognizer.dynamic_energy_threshold = True
        _recognizer.pause_threshold = 0.8
    return sr, _recognizer


def listen():
    """Listen once. Returns the recognised text in lower case, or "" if nothing
    useful was heard. Raises MicrophoneError / SpeechServiceError for real faults."""
    global _calibrated
    try:
        sr, recognizer = _get_recognizer()
    except ImportError as exc:
        raise MicrophoneError("The SpeechRecognition package is not installed.") from exc

    try:
        with sr.Microphone() as source:
            if not _calibrated:
                recognizer.adjust_for_ambient_noise(source, duration=1.0)
                _calibrated = True
            audio = recognizer.listen(
                source,
                timeout=config.LISTEN_TIMEOUT,
                phrase_time_limit=config.PHRASE_TIME_LIMIT,
            )
    except sr.WaitTimeoutError:
        return ""
    except (OSError, AttributeError) as exc:
        raise MicrophoneError(str(exc)) from exc

    try:
        return recognizer.recognize_google(audio, language=config.SPEECH_LANGUAGE).lower().strip()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as exc:
        raise SpeechServiceError(str(exc)) from exc


# Backwards-compatible name used by the old code.
speech_to_text = listen
