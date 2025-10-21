import threading
import time
import asyncio

class Scanner:
    def __init__(self, ui, fetcher, interval=5.0):
        """
        ui: UIComponents instance (must expose root, refresh_position, append_output, hide_stop_button, show_stop_button)
        fetcher: callable(ib) -> DataFrame (e.g. fetch_ibkr_portfolio)
        interval: seconds between scans
        """
        self.ui = ui
        self.fetcher = fetcher
        self.interval = interval
        self._thread = None
        self._stop_event = threading.Event()
        self._ib = None

    def start(self, ib):
        if self._thread and self._thread.is_alive():
            return
        self._ib = ib
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        # show stop button on UI (must be called on main thread)
        try:
            self.ui.root.after(0, self.ui.show_stop_button)
        except Exception:
            self.ui.show_stop_button()

    def stop(self):
        self._stop_event.set()
        try:
            self.ui.root.after(0, self.ui.hide_stop_button)
        except Exception:
            self.ui.hide_stop_button()

    def _ensure_event_loop(self):
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
        except Exception:
            pass

    def _run(self):
        # create an event loop for this thread (required by ib_insync)
        self._ensure_event_loop()
        last_snapshot = None
        while not self._stop_event.is_set():
            try:
                new_df = self.fetcher(self._ib)
                # optional: avoid UI updates if nothing changed (compare key columns)
                try:
                    snapshot = tuple(zip(new_df['Ticker'].astype(str), 
                                         new_df.get('MarketPrice', new_df.get('CurrentValue')).round(2)))
                except Exception:
                    snapshot = None

                changed = (snapshot is None) or (snapshot != last_snapshot)
                if changed:
                    last_snapshot = snapshot
                    # schedule UI update on main thread
                    try:
                        self.ui.root.after(0, lambda df=new_df: self.ui.refresh_position(df))
                        self.ui.root.after(0, lambda: self.ui.append_output(
                            "scanning in progress...\nThe latest market price has been refreshed into the UI\n"))
                    except Exception:
                        # fallback: call directly (less safe)
                        self.ui.refresh_position(new_df)
                        self.ui.append_output("scanning in progress...\nThe latest market price has been refreshed into the UI\n")
            except Exception as e:
                try:
                    self.ui.root.after(0, lambda e=e: self.ui.append_output(f"Price scan error: {e}\n"))
                except Exception:
                    self.ui.append_output(f"Price scan error: {e}\n")
            # wait responsively
            if self._stop_event.wait(self.interval):
                break
        # ensure stop button hidden on exit
        try:
            self.ui.root.after(0, self.ui.hide_stop_button)
        except Exception:
            self.ui.hide_stop_button()