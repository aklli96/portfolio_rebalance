from tkinter import ttk, font as tkfont
import tkinter as tk
import pandas as pd


# ── Dark theme palette ────────────────────────────────
COLORS = {
    'bg':           '#0f1117',
    'bg_card':      '#1a1b2e',
    'bg_input':     '#13141f',
    'border':       '#2d2e4a',
    'text':         '#e2e4f0',
    'text_muted':   '#7a7d9c',
    'accent':       '#6366f1',
    'success':      '#22c55e',
    'danger':       '#ef4444',
    'warning':      '#f59e0b',
    'header_bg':    '#1f2037',
    'row_even':     '#1a1b2e',
    'row_odd':      '#1f2037',
    'select':       '#3d3e6c',
}


class UIComponents:
    def __init__(self, root):
        self.root = root
        self._setup_theme()
        self._build_layout()

    # ── Theme setup ───────────────────────────────────────

    def _setup_theme(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')

        self.font_title   = tkfont.Font(family='Segoe UI', size=16, weight='bold')
        self.font_section = tkfont.Font(family='Segoe UI', size=10, weight='bold')
        self.font_body    = tkfont.Font(family='Segoe UI', size=9)
        self.font_mono    = tkfont.Font(family='Consolas', size=9)
        self.font_btn     = tkfont.Font(family='Segoe UI', size=9, weight='bold')

        self.root.configure(bg=COLORS['bg'])

        # Default ttk widget styles (used by RatioManager inline editor)
        self.style.configure('TFrame', background=COLORS['bg_card'])
        self.style.configure('TEntry',
            fieldbackground=COLORS['bg_input'], foreground=COLORS['text'],
            insertcolor=COLORS['text'], borderwidth=1)

        # Treeview
        self.style.configure('Pos.Treeview',
            background=COLORS['bg_card'], fieldbackground=COLORS['bg_card'],
            foreground=COLORS['text'], font=self.font_body,
            rowheight=28, borderwidth=0)
        self.style.configure('Pos.Treeview.Heading',
            background=COLORS['header_bg'], foreground=COLORS['text_muted'],
            font=self.font_section, borderwidth=0, padding=(8, 5))
        self.style.map('Pos.Treeview',
            background=[('selected', COLORS['select'])],
            foreground=[('selected', '#ffffff')])
        self.style.map('Pos.Treeview.Heading',
            background=[('active', COLORS['border'])])

        # Buttons — one style per colour role
        for name, bg in [
            ('Accent.TButton',  COLORS['accent']),
            ('Success.TButton', COLORS['success']),
            ('Danger.TButton',  COLORS['danger']),
            ('Warning.TButton', COLORS['warning']),
            ('Muted.TButton',   COLORS['border']),
        ]:
            fg = '#ffffff' if name != 'Warning.TButton' else '#1a1b2e'
            self.style.configure(name,
                background=bg, foreground=fg,
                font=self.font_btn, padding=(14, 7), borderwidth=0)
            self.style.map(name,
                background=[('active', bg), ('disabled', '#3a3a50')],
                foreground=[('disabled', '#6a6a80')])

        # Scrollbar
        self.style.configure('Dark.Vertical.TScrollbar',
            background=COLORS['border'], troughcolor=COLORS['bg_input'],
            borderwidth=0, arrowsize=12)
        self.style.map('Dark.Vertical.TScrollbar',
            background=[('active', COLORS['text_muted'])])

    # ── Layout ────────────────────────────────────────────

    def _build_layout(self):
        main = tk.Frame(self.root, bg=COLORS['bg'], padx=16, pady=12)
        main.pack(fill='both', expand=True)

        # Title
        tk.Label(main, text='Portfolio Rebalancer', font=self.font_title,
                 bg=COLORS['bg'], fg=COLORS['text']).pack(anchor='w', pady=(0, 8))

        # ── Positions card ──
        pos_body = self._card(main, 'Current Positions')
        self.position_tree = ttk.Treeview(pos_body, show='headings',
                                          height=7, style='Pos.Treeview')
        self.position_tree.pack(fill='x', padx=8, pady=(4, 8))

        # ── Ratios card ──
        ratio_body = self._card(main, 'Ratio Settings')
        self.ratio_tree = ttk.Treeview(ratio_body, show='headings',
                                       height=5, style='Pos.Treeview')
        self.ratio_tree.pack(fill='x', padx=8, pady=(4, 8))

        # ── Toolbar ──
        toolbar = tk.Frame(main, bg=COLORS['bg_card'],
                           highlightbackground=COLORS['border'],
                           highlightthickness=1)
        toolbar.pack(fill='x', pady=6)
        btn_row = tk.Frame(toolbar, bg=COLORS['bg_card'], padx=10, pady=10)
        btn_row.pack(fill='x')

        self.rebalance_btn = ttk.Button(btn_row, text='Rebalance',
                                        style='Accent.TButton')
        self.rebalance_btn.pack(side='left', padx=(0, 6))

        self.scan_btn = ttk.Button(btn_row, text='Start Scanning',
                                   style='Muted.TButton')
        self.scan_btn.pack(side='left', padx=6)

        self.report_btn = ttk.Button(btn_row, text='Gen Report',
                                     style='Success.TButton')
        self.report_btn.pack(side='left', padx=6)

        self.stop_btn = ttk.Button(btn_row, text='Stop',
                                   style='Warning.TButton')
        self.stop_btn.pack(side='left', padx=6)
        self.stop_btn.pack_forget()           # hidden until scanning starts

        self.place_orders_btn = ttk.Button(btn_row, text='Place Orders',
                                              style='Success.TButton')
        self.place_orders_btn.pack(side='left', padx=6)

        self.withdraw_btn = ttk.Button(btn_row, text='Withdraw Money',
                                       style='Warning.TButton')
        self.withdraw_btn.pack(side='left', padx=6)

        self.disconnect_btn = ttk.Button(btn_row, text='Disconnect IBKR',
                                         style='Danger.TButton')
        self.disconnect_btn.pack(side='left', padx=6)

        # ── Output console card ──
        out_body = self._card(main, 'Output Console', expand=True)
        out_inner = tk.Frame(out_body, bg=COLORS['bg_input'])
        out_inner.pack(fill='both', expand=True, padx=8, pady=(4, 8))

        self.output_box = tk.Text(
            out_inner, wrap='word', state='disabled',
            bg=COLORS['bg_input'], fg=COLORS['text'],
            insertbackground=COLORS['text'], font=self.font_mono,
            bd=0, padx=10, pady=8,
            selectbackground=COLORS['accent'], selectforeground='#ffffff')
        vsb = ttk.Scrollbar(out_inner, orient='vertical',
                            command=self.output_box.yview,
                            style='Dark.Vertical.TScrollbar')
        self.output_box.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.output_box.pack(side='left', fill='both', expand=True)

    # ── Card builder ──────────────────────────────────────

    def _card(self, parent, title, expand=False):
        wrapper = tk.Frame(parent, bg=COLORS['bg'])
        wrapper.pack(fill='both' if expand else 'x', expand=expand, pady=4)

        card = tk.Frame(wrapper, bg=COLORS['bg_card'],
                        highlightbackground=COLORS['border'],
                        highlightthickness=1)
        card.pack(fill='both', expand=True)

        hdr = tk.Frame(card, bg=COLORS['header_bg'])
        hdr.pack(fill='x')
        tk.Label(hdr, text=title, font=self.font_section,
                 bg=COLORS['header_bg'], fg=COLORS['text_muted'],
                 anchor='w', padx=12, pady=5).pack(fill='x')

        body = tk.Frame(card, bg=COLORS['bg_card'])
        body.pack(fill='both', expand=True)
        return body

    # ── Public helpers ────────────────────────────────────

    def refresh_position(self, df):
        """Update the position table with new data."""
        for item in self.position_tree.get_children():
            self.position_tree.delete(item)

        pos_df = df.fillna(0)
        if 'MarketPrice' in pos_df.columns:
            pos_df = pos_df.drop(columns=['MarketPrice'])

        cols = list(pos_df.columns)
        if list(self.position_tree['columns']) != cols:
            self.position_tree['columns'] = cols
            for col in cols:
                self.position_tree.heading(col, text=col)
                self.position_tree.column(col, width=130, anchor='center')

        for i, (_, row) in enumerate(pos_df.iterrows()):
            values = [f"{x:.2f}" if isinstance(x, float) else x for x in row]
            tag = 'odd' if i % 2 else 'even'
            self.position_tree.insert('', 'end', values=values, tags=(tag,))
        self.position_tree.tag_configure('even', background=COLORS['row_even'])
        self.position_tree.tag_configure('odd',  background=COLORS['row_odd'])

    def refresh_ratio_table(self, cfg):
        """Rebuild the ratio treeview from a config DataFrame."""
        if cfg is None or cfg.empty:
            df = pd.DataFrame(columns=['Ticker', 'Ratio'])
        else:
            df = cfg.copy()
            if 'Ratio' in df.columns:
                df['Ratio'] = df['Ratio'].apply(lambda x: f"{x:.3%}")

        cols = list(df.columns)
        for item in self.ratio_tree.get_children():
            self.ratio_tree.delete(item)

        if list(self.ratio_tree['columns']) != cols:
            self.ratio_tree.config(columns=cols)
            for col in cols:
                self.ratio_tree.heading(col, text=col)
                self.ratio_tree.column(col, width=130, anchor='center')

        for i, (_, row) in enumerate(df.iterrows()):
            tag = 'odd' if i % 2 else 'even'
            self.ratio_tree.insert('', 'end', values=list(row), tags=(tag,))
        self.ratio_tree.tag_configure('even', background=COLORS['row_even'])
        self.ratio_tree.tag_configure('odd',  background=COLORS['row_odd'])

    def append_output(self, msg: str):
        self.output_box.config(state='normal')
        self.output_box.insert(tk.END, msg)
        self.output_box.see(tk.END)
        self.output_box.config(state='disabled')

    def show_output_lines(self, lines):
        self.output_box.config(state='normal')
        self.output_box.delete('1.0', tk.END)
        self.output_box.insert(tk.END, '\n'.join(lines))
        self.output_box.config(state='disabled')

    def show_stop_button(self):
        self.stop_btn.pack(side='left', padx=6)
        self.stop_btn.config(state='normal')

    def hide_stop_button(self):
        self.stop_btn.config(state='disabled')
        self.stop_btn.pack_forget()