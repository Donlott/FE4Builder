"""Repair physical weapons repurposed from staff/magic item slots."""
import tkinter as tk
from tkinter import ttk, messagebox

from combat_art import CombatArtwork


class CombatArtWindow(tk.Toplevel):
    def __init__(self, app, item):
        model = CombatArtwork(app.rom)
        from item_expansion import enabled
        if item not in enabled(app.rom, 'items') or 125 <= item < 138:
            raise ValueError('This item has no supported held-weapon sprite assignment.')
        super().__init__(app)
        self.app, self.rom, self.model = app, app.rom, model
        self.title('FE4Builder — Combat animations');self.resizable(False, False)
        body = ttk.Frame(self, padding=18);body.pack(fill='both', expand=True)
        ttk.Label(body, text='Physical weapon combat animations', style='Title.TLabel').pack(anchor='w')
        ttk.Label(body, text='For weapons made from staff or magic slots: use compatible weapon attack\n'
                  'poses, map weapon graphics and effects. Your selected held-weapon sprite\n'
                  'and palette, inventory icon, name, stats and damage effects are preserved.', justify='left').pack(anchor='w', pady=12)
        self.items = [i for i in enabled(app.rom, 'items') if model.candidates(i)]
        if item not in self.items:self.items.insert(0, item)
        self.item = ttk.Combobox(body, state='readonly', width=54,
                                 values=[f'{i:02X} {model.art.name(i)}' for i in self.items])
        self.item.current(self.items.index(item));self.item.pack(fill='x')
        self.item.bind('<<ComboboxSelected>>', lambda _:self.refresh())
        ttk.Label(body, text='Use combat animations from').pack(anchor='w', pady=(12, 4))
        self.donor = ttk.Combobox(body, state='readonly', width=54);self.donor.pack(fill='x')
        self.status = tk.StringVar();ttk.Label(body, textvariable=self.status, wraplength=530, justify='left').pack(anchor='w', pady=12)
        buttons = ttk.Frame(body);buttons.pack(fill='x')
        self.write = ttk.Button(buttons, text='Write to ROM', command=self.save);self.write.pack(side='left')
        ttk.Button(buttons, text='Reload', command=self.reload).pack(side='left', padx=8)
        ttk.Button(buttons, text='Close', command=self.destroy).pack(side='right')
        self.refresh()

    def refresh(self):
        item = self.items[self.item.current()]
        self.donors = self.model.candidates(item)
        values = ['Original slot animations'] + [f'{i:02X} {self.model.art.name(i)}' for i in self.donors]
        self.donor.config(values=values)
        current = self.model.aliases[item]
        self.donor.current(self.donors.index(current) + 1 if current in self.donors else 1 if self.donors else 0)
        self.status.set(('Current: original slot animations.' if current == 255 else f'Current: combat animations from {current:02X} {self.model.art.name(current)}.') +
                        ('\nThe suggested base matches the weapon type and attack range. Write to ROM creates a backup and undo entry.' if self.donors else
                         '\nNo compatible physical animation base is available for this weapon type/range.'))
        self.write.config(state='normal' if self.donors or current != 255 else 'disabled')

    def reload(self):
        try:self.model = CombatArtwork(self.rom);self.refresh()
        except ValueError as error:messagebox.showerror('Cannot load combat animations', str(error), parent=self)

    def save(self):
        if self.app.rom is not self.rom:
            messagebox.showerror('ROM changed', 'Reopen combat animations for the current ROM.', parent=self);return False
        if not self.app.settle():return False
        item = self.items[self.item.current()];choice = self.donor.current()
        donor = self.donors[choice - 1] if choice > 0 else None
        try:changed = self.model.commit(item, donor)
        except (ValueError, OSError) as error:
            messagebox.showerror('Cannot save combat animations', str(error), parent=self);return False
        if changed:self.app.refresh_after_history()
        self.model = CombatArtwork(self.rom);self.refresh()
        self.status.set('Saved with an automatic backup. Restart the emulator with the written ROM.' if changed else 'No combat animation changes to write.')
        return True
