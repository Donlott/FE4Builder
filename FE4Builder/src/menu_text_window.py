"""Names, descriptions and menu labels, with native-font previews."""
import tkinter as tk
from tkinter import ttk, messagebox

from menu_text import MenuText, MenuFont, catalogue, check_profile
from ui_common import ask_unsaved


class MenuTextWindow(tk.Toplevel):
    def __init__(self, app, category='Item names', index=0):
        super().__init__(app)
        self.app, self.rom = app, app.rom
        self.entries = catalogue()['entries']
        self.categories = list(dict.fromkeys(e['category'] for e in self.entries))
        self.font = MenuFont(self.rom)
        self.model, self.current, self.initial = None, None, ''
        self.labels = {}
        self.title('FE4Builder — Menu Text Editor')
        self.geometry('1100x760')
        self.minsize(850, 600)
        self.transient(app)
        top = ttk.Frame(self, padding=12)
        top.pack(fill='x')
        ttk.Label(top, text='Menu Text Editor', style='Title.TLabel').pack(side='left')
        self.write_button = ttk.Button(top, text='Write to ROM', command=self.save)
        self.write_button.pack(side='right')
        ttk.Button(top, text='Save & Launch (F5)', command=self.launch).pack(side='right', padx=8)
        body = ttk.Panedwindow(self, orient='horizontal')
        body.pack(fill='both', expand=True, padx=12)
        left = ttk.Frame(body)
        body.add(left, weight=1)
        ttk.Label(left, text='Text category').pack(anchor='w')
        self.group = ttk.Combobox(left, state='readonly', values=self.categories, width=29)
        self.group.set(category if category in self.categories else self.categories[0])
        self.previous_group = self.group.get()
        self.group.pack(fill='x', pady=(3, 10))
        self.group.bind('<<ComboboxSelected>>', self.change_category)
        ttk.Label(left, text='Search names, text or hexadecimal ID').pack(anchor='w')
        self.search = tk.StringVar()
        ttk.Entry(left, textvariable=self.search).pack(fill='x', pady=(3, 8))
        listing = ttk.Frame(left)
        listing.pack(fill='both', expand=True)
        self.list = tk.Listbox(listing, exportselection=False, width=34)
        self.list.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(listing, command=self.list.yview)
        scroll.pack(side='right', fill='y')
        self.list.config(yscrollcommand=scroll.set)
        self.list.bind('<<ListboxSelect>>', self.select)
        self.count = tk.StringVar()
        ttk.Label(left, textvariable=self.count, padding=(0, 8)).pack(anchor='w')
        right = ttk.Frame(body, padding=(14, 0, 0, 0))
        body.add(right, weight=3)
        self.heading = tk.StringVar()
        ttk.Label(right, textvariable=self.heading, font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        self.instructions = tk.StringVar()
        ttk.Label(right, textvariable=self.instructions, wraplength=700, justify='left').pack(anchor='w', pady=8)
        self.editor = tk.Text(right, height=6, wrap='none', undo=True, font=('Segoe UI', 13))
        self.editor.pack(fill='x')
        self.editor.bind('<<Modified>>', self.changed)
        self.info = tk.StringVar()
        ttk.Label(right, textvariable=self.info, wraplength=700, justify='left').pack(anchor='w', pady=8)
        previews = ttk.Frame(right)
        previews.pack(fill='both', expand=True)
        previews.columnconfigure(0, weight=1)
        previews.columnconfigure(1, weight=1)
        previews.rowconfigure(1, weight=1)
        ttk.Label(previews, text='Current ROM').grid(row=0, column=0, sticky='w')
        ttk.Label(previews, text='Replacement preview').grid(row=0, column=1, sticky='w')
        self.old_preview = tk.Canvas(previews, background='#202832', highlightthickness=0, width=310, height=250)
        self.new_preview = tk.Canvas(previews, background='#202832', highlightthickness=0, width=310, height=250)
        self.old_preview.grid(row=1, column=0, sticky='nsew', padx=(0, 6))
        self.new_preview.grid(row=1, column=1, sticky='nsew', padx=(6, 0))
        self.notes = tk.StringVar()
        ttk.Label(right, textvariable=self.notes, wraplength=700, justify='left').pack(anchor='w', pady=10)
        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill='x')
        ttk.Button(bottom, text='Reload text', command=self.reload).pack(side='left')
        ttk.Button(bottom, text='Undo ROM', command=lambda: self.history(False)).pack(side='left', padx=8)
        ttk.Button(bottom, text='Redo ROM', command=lambda: self.history(True)).pack(side='left')
        ttk.Button(bottom, text='Close', command=self.close).pack(side='right')
        self.status = tk.StringVar(value='Loaded from ROM. Changes remain unwritten until Write to ROM.')
        ttk.Label(self, textvariable=self.status, padding=8, relief='sunken', wraplength=1000).pack(fill='x')
        self.search.trace_add('write', lambda *_: self.populate())
        self.populate()
        target = next((e['key'] for e in self.entries if e['category'] == self.group.get() and e['id'] == index), self.visible[0])
        self.load(target)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<F5>', lambda _: (self.launch(), 'break')[1])

    def text(self):
        return self.editor.get('1.0', 'end-1c')

    def pending(self):
        return self.model is not None and self.text() != self.initial

    def settle(self):
        if not self.pending():
            return True
        answer = ask_unsaved(self, 'Write this menu text to the opened ROM?')
        return False if answer is None else self.save() if answer else True

    def label(self, entry):
        key = entry['key']
        if key not in self.labels:
            try:
                model = MenuText(self.rom, entry, self.font)
                text = model.text
                self.labels[key] = (entry['label'] + ' (not written)' if model.unassigned else
                                    (text or '(blank)') if text is not None else '(unrecognized artwork)')
            except ValueError:
                self.labels[key] = '(unsupported layout)'
        return self.labels[key]

    def populate(self):
        query = self.search.get().casefold().strip()
        self.visible = [e['key'] for e in self.entries if e['category'] == self.group.get()
                        and query in f'{e["id"]:02X} {self.label(e)}'.casefold()]
        self.list.delete(0, 'end')
        for key in self.visible:
            entry = self.entries[key]
            text = self.label(entry).split('\n', 1)[0]
            self.list.insert('end', f'{entry["id"]:02X}  {text}')
        self.count.set(f'{len(self.visible)} entries')
        self.select_current()

    def select_current(self):
        self.list.selection_clear(0, 'end')
        if self.current in self.visible:
            i = self.visible.index(self.current)
            self.list.selection_set(i)
            self.list.see(i)

    def change_category(self, _=None):
        if not self.settle():
            self.group.set(self.previous_group)
            return
        self.previous_group = self.group.get()
        self.search.set('')
        self.populate()
        if self.visible:
            self.load(self.visible[0])

    def select(self, _=None):
        selected = self.list.curselection()
        if not selected:
            return
        key = self.visible[selected[0]]
        if key == self.current:
            return
        if not self.settle():
            self.select_current()
            return
        self.load(key)

    def load(self, key):
        self.current = key
        entry = self.entries[key]
        self.heading.set(f'{entry["category"]} · ID {entry["id"]:02X}')
        try:
            self.model = MenuText(self.rom, entry, self.font)
        except ValueError as error:
            self.model = None
            self.instructions.set(str(error))
            self.editor.delete('1.0', 'end')
            self.write_button.config(state='disabled')
            self.old_preview.delete('all')
            self.new_preview.delete('all')
            self.info.set('This entry is unavailable. Other recognized entries can still be edited.')
            self.notes.set('')
            self.select_current()
            return
        self.initial = self.model.text or ''
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', entry['default_text'] if self.model.unassigned else self.initial)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        if entry['kind'] == 'skill':
            instruction = 'First line: skill name (up to 56 pixels). Next three lines: help text (96 pixels each).'
        else:
            width = 64 if entry['kind'] == 'name' else 128
            instruction = f'Up to {self.model.capacity} line(s), {width} pixels per line.'
            if entry['kind'] == 'encoded':
                instruction += ' Maximum 15 stored characters.'
        if self.model.text is None:
            instruction += ' This artwork could not be read as text. Enter a replacement and review its preview.'
        if self.model.unassigned:
            instruction += " Suggested text is shown; Write to ROM adds it to this skill's help panel."
        self.instructions.set(instruction)
        self.draw(self.old_preview, self.model.original_rows)
        if entry['kind'] == 'effect':
            note = 'Shared effect label: this changes every item still using this effect artwork. It changes the description only, not the item’s behavior.'
        elif 'messages' in entry['category']:
            note = 'Battle/castle message names use their own IDs. They are separate from the inventory/class-name lists; edit the matching menu entry separately when renaming both.'
        else:
            note = 'Only this text entry is changed. Shared originals stay intact. Text changes do not change item or skill behavior.'
            if entry['category'] in ('Item names', 'Class names'):
                note += ' Matching message names are in the separate “… — messages” category.'
            if entry['category'].startswith('Locations'):
                note += ' Map/menu location lists and names written into story dialogue are separate contexts.'
        self.notes.set(note)
        self.select_current()
        self.preview()

    def draw(self, canvas, rows):
        canvas.delete('all')
        if not rows or not rows[0]:
            canvas.create_text(12, 12, anchor='nw', text='(blank)', fill='#c8d0dd')
            return
        colors = ('#202832', '#ffffff', '#a8ceff', '#080c14')
        image = tk.PhotoImage(master=self, width=len(rows[0]), height=len(rows))
        image.put(' '.join('{' + ' '.join(colors[p] for p in row) + '}' for row in rows))
        canvas.image = image.zoom(2)
        canvas.create_image(12, 12, image=canvas.image, anchor='nw')
        canvas.config(scrollregion=canvas.bbox('all'))

    def changed(self, _=None):
        if self.editor.edit_modified():
            self.editor.edit_modified(False)
            self.preview()

    def preview(self):
        if self.model is None:
            return
        try:
            if not self.pending():
                rows = self.model.original_rows
                self.info.set('Current ROM text · No pending changes.' if self.model.text is not None else
                              'Current artwork shown below. Enter text to preview a replacement.')
            else:
                _, rows, widths = self.model.render(self.text())
                self.info.set('Line widths: ' + ', '.join(f'{w} px' for w in widths) + '. Review before writing.')
            self.draw(self.new_preview, rows)
            self.write_button.config(state='normal' if self.pending() else 'disabled')
        except ValueError as error:
            self.info.set(str(error))
            self.new_preview.delete('all')
            self.write_button.config(state='disabled')

    def save(self):
        if self.app.rom is not self.rom:
            messagebox.showerror('ROM changed', 'Reopen Menu Text Editor for the current ROM.', parent=self)
            return False
        if not self.pending():
            return True
        if not self.app.settle():
            return False
        before = bytes(self.rom.data)
        try:
            self.model.write(self.text())
            entry = self.model.entry
            self.rom.save_original(f'Menu text: {entry["category"]} {entry["id"]:02X}',
                                   [f'Before: {self.initial}', f'After: {self.text()}'])
        except (ValueError, OSError) as error:
            self.rom.data[:] = before
            messagebox.showerror('Cannot write menu text', str(error), parent=self)
            return False
        self.font = MenuFont(self.rom)
        self.labels.clear()
        self.app.refresh_after_history()
        self.app.update_history_controls()
        self.load(self.current)
        self.populate()
        self.status.set('Saved to the opened ROM with automatic backup and undo history.')
        return True

    def reload(self):
        if self.pending() and not messagebox.askyesno('Reload text', 'Discard this unwritten text?', parent=self):
            return
        self.font = MenuFont(self.rom)
        self.labels.clear()
        self.load(self.current)
        self.populate()

    def history(self, redo):
        if not self.settle() or not self.app.settle():
            return
        try:
            self.rom.redo() if redo else self.rom.undo()
        except (ValueError, OSError) as error:
            messagebox.showerror('History unavailable', str(error), parent=self)
            return
        self.app.refresh_after_history()
        self.app.update_history_controls()
        self.font = MenuFont(self.rom)
        self.labels.clear()
        self.load(self.current)
        self.populate()

    def launch(self):
        return self.app.save_and_launch(save_callback=self.save, parent=self)

    def close(self):
        if self.settle():
            self.destroy()


def open_menu_text_window(app, category='Item names', index=0):
    if not app.rom:
        messagebox.showinfo('Open a ROM', 'Open a Project Naga beta 7 ROM first.', parent=app)
        return
    if not app.settle():
        return
    try:
        check_profile(app.rom)
        MenuFont(app.rom)
    except ValueError as error:
        messagebox.showerror('Menu text unavailable', str(error), parent=app)
        return
    return MenuTextWindow(app, category, index)
