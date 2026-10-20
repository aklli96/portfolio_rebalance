import tkinter as tk
from tkinter import ttk
import pandas as pd


def _parse_ratio(ratio_str):
    """Parse a ratio string like '12.500%' into a float (0.125)."""
    try:
        return float(str(ratio_str).rstrip('%')) / 100
    except (ValueError, TypeError):
        return 0.0


class RatioManager:
    def __init__(self, ui, on_config_saved=None):
        self.ui = ui
        self.on_config_saved = on_config_saved
        self.edit_popup = None
        self.edit_entry = None
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
        self.edit_entry.insert(0, str(current_value).rstrip('%'))
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

    def _get_all_ratios(self):
        """Collect (ticker, ratio_float) pairs from the ratio tree."""
        items = []
        for item in self.ui.ratio_tree.get_children():
            values = self.ui.ratio_tree.item(item)['values']
            items.append((values[0], _parse_ratio(values[1])))
        return items

    def validate_ratios(self):
        ratios = self._get_all_ratios()
        total = sum(r for _, r in ratios)
        if abs(total - 1.0) > 0.001:
            self.ui.append_output(f"Warning: Ratios sum to {total:.3%}, should be 100%\n")
            return False
        return True

    def save_ratios(self):
        ratios = dict(self._get_all_ratios())
        try:
            # Preserve extra config columns (drawdown, rebal_ratio_if_hit_dd)
            new_df = pd.read_csv('portfolio_setting.csv')
            new_df['Ratio'] = new_df['Ticker'].map(lambda t: f"{ratios.get(t, 0.0):.2%}")
        except (OSError, KeyError):
            new_df = pd.DataFrame(ratios.items(), columns=['Ticker', 'Ratio'])
            new_df['Ratio'] = new_df['Ratio'].apply(lambda x: f"{x:.2%}")
        new_df.to_csv('portfolio_setting.csv', index=False)
        if self.on_config_saved:
            self.on_config_saved()
        self.ui.append_output("Portfolio ratios saved successfully!\n")