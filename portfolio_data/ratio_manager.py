import tkinter as tk
from tkinter import ttk
import pandas as pd

class RatioManager:
    def __init__(self, ui, on_config_saved=None):
        """
        ui: UIComponents instance exposing ratio_tree and append_output, refresh_ratio_table
        on_config_saved: optional callback to reload config in main app
        """
        self.ui = ui
        self.on_config_saved = on_config_saved
        self.edit_popup = None
        self.edit_entry = None

        # bind events
        self.ui.ratio_tree.bind('<Double-1>', self._on_edit)

    def _on_edit(self, event):
        item = self.ui.ratio_tree.identify_row(event.y)
        column = self.ui.ratio_tree.identify_column(event.x)
        if column != '#2' or not item:
            return
        current_value = self.ui.ratio_tree.item(item)['values'][1]
        x, y, w, h = self.ui.ratio_tree.bbox(item, column)
        self.cancel_edit()
        self.edit_popup = ttk.Frame(self.ui.ratio_tree)
        self.edit_entry = ttk.Entry(self.edit_popup, width=15)
        self.edit_entry.insert(0, current_value.rstrip('%'))
        self.edit_entry.select_range(0, tk.END)
        self.edit_entry.focus()
        self.edit_entry.bind('<Return>', lambda e: self.save_edit(item))
        self.edit_entry.bind('<Escape>', lambda e: self.cancel_edit())
        self.edit_popup.place(x=x, y=y, width=w, height=h)
        self.edit_entry.pack(fill='both', expand=True)

    def save_edit(self, item):
        if self.edit_entry:
            try:
                new_value = float(self.edit_entry.get().strip().rstrip('%')) / 100
                values = list(self.ui.ratio_tree.item(item)['values'])
                values[1] = f"{new_value:.3%}"
                self.ui.ratio_tree.item(item, values=values)
            except ValueError:
                pass
        self.cancel_edit()
        self.validate_ratios()

    def cancel_edit(self):
        if self.edit_popup:
            self.edit_popup.destroy()
            self.edit_popup = None
            self.edit_entry = None

    def validate_ratios(self):
        total = 0.0
        for item in self.ui.ratio_tree.get_children():
            ratio_str = self.ui.ratio_tree.item(item)['values'][1]
            try:
                ratio = float(ratio_str.rstrip('%')) / 100
            except Exception:
                ratio = 0.0
            total += ratio
        if abs(total - 1.0) > 0.001:
            self.ui.append_output(f"Warning: Ratios sum to {total:.3%}, should be 100%\n")
            return False
        return True

    def save_ratios(self):
        new_ratios = []
        for item in self.ui.ratio_tree.get_children():
            values = self.ui.ratio_tree.item(item)['values']
            ticker = values[0]
            ratio = float(values[1].rstrip('%')) / 100
            new_ratios.append({'Ticker': ticker, 'Ratio': ratio})
        new_df = pd.DataFrame(new_ratios)
        new_df['Ratio'] = new_df['Ratio'].apply(lambda x: f"{x:.2%}")
        new_df.to_csv('portfolio_setting.csv', index=False)
        if self.on_config_saved:
            self.on_config_saved()
        self.ui.append_output("Portfolio ratios saved successfully!\n")