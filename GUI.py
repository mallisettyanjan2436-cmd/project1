"""JARVIS desktop interface.  Run with:  python GUI.py"""
import datetime
import queue
import threading
import tkinter as tk

import config
import text_to_speech
from action import Jarvis

BG = "#0b1118"
PANEL = "#111c27"
BORDER = "#26384a"
TEXT = "#e2e8f0"
MUTED = "#8b9bad"

STATES = {
    "idle": ("READY", "#94a3b8"),
    "listening": ("LISTENING - speak now", "#22c55e"),
    "thinking": ("THINKING", "#eab308"),
    "speaking": ("SPEAKING", "#38bdf8"),
    "stopped": ("STOPPED", "#ef4444"),
}
ROLES = {
    "user": ("You", "#67e8f9"),
    "jarvis": ("Jarvis", "#86efac"),
    "system": ("System", "#94a3b8"),
    "error": ("Error", "#fca5a5"),
}


class JarvisApp:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()          # worker threads -> GUI thread
        self.stop_event = threading.Event()
        self.voice_thread = None
        self.jarvis = Jarvis(
            on_message=lambda role, text: self.events.put(("message", role, text)),
            on_state=lambda state: self.events.put(("state", state)),
        )
        self._build_window()
        self._build_widgets()
        self._welcome()
        self.root.after(50, self._drain_events)

    # ------------------------------------------------------------------ layout
    def _build_window(self):
        self.root.title(f"{config.ASSISTANT_NAME.upper()} - Voice Assistant")
        self.root.configure(bg=BG)
        self.root.minsize(760, 560)
        w, h = 900, 680
        x = max((self.root.winfo_screenwidth() - w) // 2, 0)
        y = max((self.root.winfo_screenheight() - h) // 2, 0)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_widgets(self):
        header = tk.Frame(self.root, bg=BG)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 6))
        tk.Label(header, text=" ".join(config.ASSISTANT_NAME.upper()), font=("Segoe UI", 28, "bold"),
                 bg=BG, fg="white").pack()
        tk.Label(header, text="Personal Voice Assistant", font=("Segoe UI", 12),
                 bg=BG, fg=MUTED).pack()

        self.status = tk.Label(self.root, font=("Segoe UI", 11, "bold"), bg=PANEL, pady=9)
        self.status.grid(row=1, column=0, sticky="ew", padx=24, pady=(10, 10))
        self._show_state("idle")

        chat = tk.Frame(self.root, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        chat.grid(row=2, column=0, sticky="nsew", padx=24)
        chat.grid_rowconfigure(0, weight=1)
        chat.grid_columnconfigure(0, weight=1)
        scroll = tk.Scrollbar(chat)
        scroll.grid(row=0, column=1, sticky="ns")
        self.chat = tk.Text(chat, font=("Consolas", 12), bg=PANEL, fg=TEXT, wrap=tk.WORD,
                            relief=tk.FLAT, padx=14, pady=12, state=tk.DISABLED,
                            spacing1=3, spacing3=3, yscrollcommand=scroll.set,
                            selectbackground="#334155")
        self.chat.grid(row=0, column=0, sticky="nsew")
        scroll.config(command=self.chat.yview)
        self.chat.tag_configure("time", foreground="#5b6b7d", font=("Consolas", 9))
        for role, (_, colour) in ROLES.items():
            self.chat.tag_configure(role, foreground=colour, font=("Consolas", 12, "bold"))
        self.chat.tag_configure("body", foreground=TEXT)

        entry_row = tk.Frame(self.root, bg=BG)
        entry_row.grid(row=3, column=0, sticky="ew", padx=24, pady=(12, 0))
        entry_row.grid_columnconfigure(0, weight=1)
        self.entry = tk.Entry(entry_row, font=("Segoe UI", 12), bg="#16212b", fg=TEXT,
                              insertbackground="white", relief=tk.FLAT,
                              highlightthickness=1, highlightbackground=BORDER,
                              highlightcolor="#38bdf8")
        self.entry.grid(row=0, column=0, sticky="ew", ipady=8, padx=(0, 8))
        self.entry.bind("<Return>", lambda _e: self.send_typed())
        self.entry.focus_set()
        tk.Button(entry_row, text="Send", font=("Segoe UI", 11, "bold"), width=9,
                  command=self.send_typed, cursor="hand2").grid(row=0, column=1)

        buttons = tk.Frame(self.root, bg=BG)
        buttons.grid(row=4, column=0, sticky="ew", padx=24, pady=(12, 4))
        for col in range(3):
            buttons.grid_columnconfigure(col, weight=1)
        self.toggle_btn = tk.Button(buttons, text="Start Listening", font=("Segoe UI", 11, "bold"),
                                    height=2, command=self.toggle_listening, cursor="hand2")
        self.toggle_btn.grid(row=0, column=0, sticky="ew", padx=4)
        tk.Button(buttons, text="Clear Chat", font=("Segoe UI", 11, "bold"), height=2,
                  command=self.clear_chat, cursor="hand2").grid(row=0, column=1, sticky="ew", padx=4)
        tk.Button(buttons, text="Exit", font=("Segoe UI", 11, "bold"), height=2,
                  command=self.close, cursor="hand2").grid(row=0, column=2, sticky="ew", padx=4)

        tk.Label(self.root, text='Speak or type a command. Say "stop" to shut Jarvis down.',
                 font=("Segoe UI", 9), bg=BG, fg=MUTED).grid(row=5, column=0, pady=(4, 12))

    def _welcome(self):
        self._append("system", "Jarvis is ready.")
        self._append("system", 'Press "Start Listening" to use your voice, or type a command below.')
        self._append("system", 'Try: "what is the time", "weather in Delhi", "search Google for python", "open YouTube".')

    # ------------------------------------------------------------------ events
    def _drain_events(self):
        try:
            while True:
                kind, *data = self.events.get_nowait()
                if kind == "message":
                    self._append(*data)
                elif kind == "state":
                    self._show_state(data[0])
                elif kind == "voice_finished":
                    self._voice_finished()
        except queue.Empty:
            pass
        self.root.after(50, self._drain_events)

    def _show_state(self, state):
        text, colour = STATES.get(state, STATES["idle"])
        self.status.config(text=f"●  {text}", fg=colour)

    def _append(self, role, text):
        label = ROLES.get(role, ROLES["system"])[0]
        stamp = datetime.datetime.now().strftime("%H:%M")
        self.chat.config(state=tk.NORMAL)
        self.chat.insert(tk.END, f"{stamp}  ", "time")
        self.chat.insert(tk.END, f"{label}: ", role if role in ROLES else "system")
        self.chat.insert(tk.END, text + "\n", "body")
        self.chat.see(tk.END)
        self.chat.config(state=tk.DISABLED)

    # ------------------------------------------------------------------ actions
    def toggle_listening(self):
        if self.voice_thread and self.voice_thread.is_alive():
            self.stop_event.set()
            self.toggle_btn.config(text="Stopping...", state=tk.DISABLED)
            return
        self.stop_event.clear()
        self.toggle_btn.config(text="Stop Listening")
        self.voice_thread = threading.Thread(target=self._voice_worker, name="jarvis-voice", daemon=True)
        self.voice_thread.start()

    def _voice_worker(self):
        try:
            self.jarvis.run_voice_loop(self.stop_event)
        except Exception as exc:
            self.events.put(("message", "error", f"{type(exc).__name__}: {exc}"))
        finally:
            self.events.put(("voice_finished",))

    def _voice_finished(self):
        self.toggle_btn.config(text="Start Listening", state=tk.NORMAL)
        self._show_state("stopped")

    def send_typed(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, tk.END)
        threading.Thread(target=self._run_typed, args=(text,), daemon=True).start()

    def _run_typed(self, text):
        try:
            keep_running = self.jarvis.handle(text, interactive=False)
        except Exception as exc:
            self.events.put(("message", "error", f"{type(exc).__name__}: {exc}"))
            return
        if not keep_running:
            self.stop_event.set()
            if not (self.voice_thread and self.voice_thread.is_alive()):
                self.events.put(("state", "stopped"))

    def clear_chat(self):
        self.chat.config(state=tk.NORMAL)
        self.chat.delete("1.0", tk.END)
        self.chat.config(state=tk.DISABLED)
        self._append("system", "Chat cleared.")

    def close(self):
        self.stop_event.set()
        text_to_speech.shutdown()
        self.root.destroy()


def main():
    root = tk.Tk()
    JarvisApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
