from pathlib import Path

from bootstrap_env import ensure_environment

ensure_environment(entry_script=Path(__file__).resolve())

import tkinter as tk
from interface import PortfolioApp


def run():
    root = tk.Tk()
    root.geometry("960x780")
    root.minsize(820, 640)
    app = PortfolioApp(root)
    root.mainloop()


if __name__ == "__main__":
    run()