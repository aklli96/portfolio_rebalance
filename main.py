import tkinter as tk
from interface import PortfolioApp

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("960x780")
    root.minsize(820, 640)
    app = PortfolioApp(root)
    root.mainloop()