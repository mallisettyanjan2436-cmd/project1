"""Automated checks: run `python test_commands.py` (no microphone or speakers needed)."""
import unittest
from unittest import mock

import weather
from action import Jarvis


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.log = []
        self.jarvis = Jarvis(on_message=lambda role, text: self.log.append((role, text)), speak_aloud=False)
        patcher = mock.patch("webbrowser.open", return_value=True)
        self.browser = patcher.start()
        self.addCleanup(patcher.stop)

    def ask(self, text):
        self.log.clear()
        keep = self.jarvis.handle(text)
        replies = [t for role, t in self.log if role == "jarvis"]
        return keep, " ".join(replies)

    def assertReply(self, command, *fragments):
        keep, reply = self.ask(command)
        for fragment in fragments:
            self.assertIn(fragment.lower(), reply.lower(), f"{command!r} -> {reply!r}")
        return keep, reply

    # ---- conversation
    def test_greetings(self):
        _, reply = self.ask("hello")
        self.assertTrue("how can i help" in reply.lower() or "what can i do" in reply.lower(), reply)
        self.assertReply("Good morning", "good morning")
        self.assertReply("good night", "good night")
        _, reply = self.ask("hello jarvis")
        self.assertTrue("how can i help" in reply.lower() or "what can i do" in reply.lower(), reply)
        self.assertReply("how are you", "running smoothly")
        self.assertReply("what is your name", "my name is jarvis")
        self.assertReply("who are you", "voice assistant")
        _, reply = self.ask("thank you")
        self.assertTrue("welcome" in reply.lower() or "pleasure" in reply.lower(), reply)
        self.assertReply("jarvis", "listening")

    def test_help_does_not_match_inside_other_words(self):
        self.assertReply("help", "time and date")
        _, reply = self.ask("whelp that was odd")
        self.assertNotIn("time and date", reply)

    # ---- stopping
    def test_stop_commands(self):
        for phrase in ("stop", "stop jarvis", "jarvis stop", "exit", "goodbye", "quit", "turn off"):
            keep, reply = self.ask(phrase)
            self.assertFalse(keep, phrase)
            self.assertIn("goodbye", reply.lower())

    def test_stop_word_inside_sentence_does_not_quit(self):
        keep, _ = self.ask("where is the nearest bus stop")
        self.assertTrue(keep)

    # ---- time / date
    def test_time_and_date(self):
        self.assertReply("what is the time", "it's")
        self.assertReply("can you please tell me the time", "it's")
        self.assertReply("what is the date", "today is")
        self.assertReply("what day is it", "today is")

    # ---- maths
    def test_math(self):
        self.assertReply("what is 12 times 4", "48")
        self.assertReply("calculate 100 divided by 8", "12.5")
        self.assertReply("what is 20 percent of 150", "30")
        self.assertReply("what is 5 plus 3", "is 8")
        self.assertReply("what is 5 divided by 0", "divide by zero")

    # ---- web actions use the topic you asked for
    def test_google_search_mentions_topic(self):
        self.assertReply("search google for python tutorials", "python tutorials")
        self.assertIn("python%20tutorials", self.browser.call_args[0][0])
        self.assertReply("google search machine learning", "machine learning")
        self.assertReply("search best laptops on google", "best laptops")
        self.assertNotIn("on%20google", self.browser.call_args[0][0])

    def test_youtube(self):
        self.assertReply("search lo-fi beats on youtube", "lo-fi beats", "youtube")
        self.assertIn("youtube.com/results", self.browser.call_args[0][0])
        self.assertReply("play believer", "believer")
        self.assertReply("play music", "youtube music")

    def test_open_websites_and_unknown(self):
        self.assertReply("open youtube", "opening youtube")
        self.browser.assert_called_with("https://www.youtube.com")
        self.assertReply("open github", "opening github")
        self.assertReply("open chat gpt", "opening chatgpt")
        self.assertReply("open example.com", "example.com")
        self.assertReply("open zorblax", "zorblax", "searching google")

    def test_browser_failure_is_reported(self):
        self.browser.return_value = False
        self.assertReply("open google", "couldn't open the web browser")

    def test_questions_fall_back_to_google(self):
        self.assertReply("who is the prime minister of india", "searching google")

    def test_unknown_command_is_echoed(self):
        self.assertReply("blorple wumble", "blorple wumble", "help")

    # ---- weather
    def test_weather_uses_city_from_command(self):
        with mock.patch("weather.get_weather", return_value="Sunny in Delhi.") as gw:
            self.assertReply("what is the weather in delhi today", "delhi", "sunny")
            gw.assert_called_with("Delhi")
            self.assertReply("weather in new york", "new york")
            gw.assert_called_with("New York")

    def test_weather_default_city_and_errors(self):
        with mock.patch("weather.get_weather", return_value="Hot."):
            self.assertReply("weather", "nellore")
        with mock.patch("weather.get_weather", side_effect=weather.WeatherError("City not found.")):
            self.assertReply("weather in xyz", "city not found")

    def test_jokes(self):
        keep, reply = self.ask("tell me a joke")
        self.assertTrue(keep)
        self.assertTrue(reply)

    def test_wake_word_variants(self):
        self.assertReply("hey jarvis what is the time", "it's")
        self.assertReply("jarvis open google", "opening google")


if __name__ == "__main__":
    unittest.main(verbosity=2)
