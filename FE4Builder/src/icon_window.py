"""Staged icon artwork/assignments, with native-palette pixel painting."""
import base64
from copy import deepcopy
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from icons import IconDocument, SKILLS, CONTEXTS, COMPACT_BITS, MAGIC, ITEM_CAPACITY, tile, unpack, import_png
from icon_stats import IconSizeHistory, artwork_bytes, report
from ui_common import ask_unsaved, scrollable_frame


class IconWindow(tk.Toplevel):
    pixel_scale = 14
    def __init__(self, app, kind='items', record=0):
        document = IconDocument(app.rom)
        super().__init__(app)
        self.app, self.rom, self.document = app, app.rom, document
        self.size_history = IconSizeHistory(document)
        self.title('FE4Builder - Icon Editor');self.geometry('1160x850');self.minsize(920, 700)
        self.current = None;self.index = None;self.photos = [];self.pen = 1;self.busy = False
        top = ttk.Frame(self, padding=10);top.pack(fill='x')
        ttk.Label(top, text='Icon Editor', style='Title.TLabel').pack(side='left')
        ttk.Button(top, text='Save & Launch (F5)', command=self.launch).pack(side='right')
        self.write_button = ttk.Button(top, text='Write to ROM', command=self.save);self.write_button.pack(side='right', padx=6)
        ttk.Button(top, text='Redo', command=lambda:self.history(True)).pack(side='right')
        ttk.Button(top, text='Undo', command=lambda:self.history(False)).pack(side='right', padx=6)
        ttk.Button(top, text='Reload', command=self.reload).pack(side='right')
        body = ttk.Panedwindow(self, orient='horizontal', height=1);body.pack(fill='both', expand=True, padx=10)
        left = ttk.Frame(body, width=340);body.add(left, weight=0)
        self.kind = ttk.Combobox(left, state='readonly', values=['Item icons', 'Skill icons']);self.kind.current(kind == 'skills');self.kind.pack(fill='x')
        self.kind.bind('<<ComboboxSelected>>', lambda _:self.populate())
        self.view = ttk.Combobox(left, state='readonly', values=['Items / skills', 'Icon library']);self.view.current(0);self.view.pack(fill='x', pady=6)
        self.view.bind('<<ComboboxSelected>>', lambda _:self.populate())
        self.search = tk.StringVar();ttk.Entry(left, textvariable=self.search).pack(fill='x', pady=(0, 6));self.search.trace_add('write', lambda *_:self.populate())
        listing = ttk.Frame(left);listing.pack(fill='both', expand=True)
        self.list = ttk.Treeview(listing, show='tree', selectmode='browse', height=16)
        self.list.column('#0', width=310, minwidth=220)
        bar = ttk.Scrollbar(listing, command=self.list.yview);bar.pack(side='right', fill='y')
        self.list.config(yscrollcommand=bar.set);self.list.pack(fill='both', expand=True)
        self.list.bind('<<TreeviewSelect>>', self.select)
        right_shell = ttk.Frame(body, padding=(12, 0));body.add(right_shell, weight=1)
        right = scrollable_frame(right_shell)
        row = ttk.Frame(right);row.pack(fill='x')
        ttk.Label(row, text='Skill screen').pack(side='left')
        self.context = ttk.Combobox(row, state='readonly', values=CONTEXTS, width=23);self.context.current(0);self.context.pack(side='left', padx=6)
        self.context.bind('<<ComboboxSelected>>', lambda _:self.populate(self.current))
        self.linked = tk.BooleanVar(value=True)
        self.link_button = ttk.Checkbutton(row, text='Link skill screens', variable=self.linked);self.link_button.pack(side='left')
        row = ttk.Frame(right);row.pack(fill='x', pady=8)
        ttk.Label(row, text='Assigned graphic').pack(side='left')
        self.assignment = ttk.Combobox(row, state='readonly', width=17);self.assignment.pack(side='left', padx=6)
        self.assign_button = ttk.Button(row, text='Assign', command=self.assign);self.assign_button.pack(side='left')
        self.hide_button = ttk.Button(row, text='Hide on stat screen', command=self.hide);self.hide_button.pack(side='left', padx=6)
        row = ttk.Frame(right);row.pack(fill='x')
        ttk.Button(row, text='Export PNG...', command=self.export).pack(side='left')
        self.import_button = ttk.Button(row, text='Import PNG...', command=self.import_image);self.import_button.pack(side='left', padx=6)
        ttk.Button(row, text='Add new icon...', command=self.add_image).pack(side='left')
        ttk.Button(row, text='Private copy', command=self.copy).pack(side='left', padx=6)
        settings = ttk.Frame(right);settings.pack(fill='x', pady=6)
        self.private = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings, text='Keep artwork changes private to selected item / skill', variable=self.private).pack(anchor='w')
        self.reduction = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings, text='Allow color reduction to the displayed native palette', variable=self.reduction).pack(anchor='w')
        painting = ttk.Frame(right);painting.pack(fill='x')
        self.canvas = tk.Canvas(painting, width=224, height=224, bg='#28303c', highlightthickness=0)
        self.canvas.pack(side='left');self.canvas.bind('<Button-1>', self.paint);self.canvas.bind('<B1-Motion>', self.paint)
        self.canvas.bind('<Button-3>', lambda e:self.paint(e, erase=True));self.canvas.bind('<B3-Motion>', lambda e:self.paint(e, erase=True))
        controls = ttk.Frame(painting, padding=12);controls.pack(side='left', fill='both', expand=True)
        ttk.Label(controls, text='Native palette\n0 = transparent', justify='left').pack(anchor='w')
        self.swatches = tk.Canvas(controls, width=128, height=128, highlightthickness=0);self.swatches.pack(anchor='w', pady=8)
        self.swatches.bind('<Button-1>', self.choose_color)
        ttk.Label(controls, text='Left click / drag: paint\nRight click / drag: erase\nPNG size: 16 x 16', justify='left').pack(anchor='w')
        self.note = tk.StringVar();ttk.Label(right, textvariable=self.note, wraplength=720, justify='left').pack(anchor='w', pady=6)
        users = ttk.LabelFrame(right, text='Shared uses', padding=4);users.pack(fill='both', expand=True)
        self.users = tk.Text(users, height=3, wrap='word', state='disabled', font=('Segoe UI', 10))
        user_scroll = ttk.Scrollbar(users, command=self.users.yview);user_scroll.pack(side='right', fill='y')
        self.users.config(yscrollcommand=user_scroll.set);self.users.pack(fill='both', expand=True)
        space = ttk.LabelFrame(self, text='Icon space', padding=8);space.pack(fill='x', padx=10, pady=8)
        self.optimize = tk.BooleanVar(value=self.size_history.optimize)
        ttk.Checkbutton(space, text='Optimize duplicate icon space when writing', variable=self.optimize, command=self.preference).pack(anchor='w')
        ttk.Button(space, text='Preview space / optimization report...', command=self.preview).pack(side='right')
        self.space = tk.StringVar();ttk.Label(space, textvariable=self.space, justify='left').pack(anchor='w')
        self.warning = tk.StringVar();ttk.Label(space, textvariable=self.warning, foreground='#a04900', wraplength=1050).pack(anchor='w')
        ttk.Label(self, text='New icons are artwork for existing items and skills. Icon graphics do not add item types or skill effects. Shared palettes stay intact.',
                  wraplength=1080, padding=(10, 0)).pack(fill='x')
        self.status = tk.StringVar();ttk.Label(self, textvariable=self.status, padding=6, relief='sunken').pack(fill='x')
        self.protocol('WM_DELETE_WINDOW', self.close);self.bind('<F5>', lambda _:self.launch())
        self.populate(record)

    @property
    def category(self):return 'skills' if self.kind.current() == 1 else 'items'

    def names(self):
        if self.category == 'skills':return SKILLS
        from item_art import ItemArt
        art = ItemArt(self.rom)
        names = []
        for i in range(138):
            try:names.append(art.name(i))
            except (ValueError, KeyError):names.append(f'Item {i:02X}')
        return names

    def preview_context(self, record=None):
        if self.category != 'skills':return 0
        context = self.context.current()
        record = self.current if record is None else record
        if self.view.current() == 0 and record is not None and self.document.selected('skills', record, context) is None:
            return 1
        return context

    def populate(self, selected=None):
        if self.busy:return
        self.busy = True
        try:
            kind = self.category;names = self.names();query = self.search.get().casefold().strip()
            self.names_current = names;self.current = None;self.photos = [];self.edited_photos = {};self.list.delete(*self.list.get_children())
            library = self.view.current() == 1;active = self.document.active(kind)
            for i in range(len(self.document.art[kind]) if library else len(names)):
                label = (f'{i:02X} / tile {tile(i):03X}' + ('  Free' if i not in active else '  Unassigned artwork' if not self.document.users(kind, i) else '')) if library else f'{i:02X} {names[i]}'
                if query and query not in label.casefold():continue
                context = self.preview_context(i)
                index = i if library else self.document.selected(kind, i, context)
                if index is None:index = self.document.selected(kind, i, 1)
                photo = tk.PhotoImage(master=self, data=base64.b64encode(self.document.png(kind, index, context)))
                self.photos.append(photo);self.list.insert('', 'end', iid=str(i), text=label, image=photo)
            children = self.list.get_children();self.assignment.config(values=[f'{i:02X} / tile {tile(i):03X}' for i in range(len(self.document.art[kind]))])
            if children:
                key = str(selected) if str(selected) in children else children[0]
                self.list.selection_set(key);self.list.see(key);self.current = int(key)
            self.display()
        finally:self.busy = False

    def select(self, _=None):
        if self.busy:return
        selected = self.list.selection()
        if selected:self.current = int(selected[0]);self.display()

    def display(self):
        kind = self.category;library = self.view.current() == 1;c = self.context.current()
        self.assignment.config(values=[f'{i:02X} / tile {tile(i):03X}' for i in range(len(self.document.art[kind]))])
        self.context.config(state='readonly' if kind == 'skills' else 'disabled')
        self.link_button.config(state='normal' if kind == 'skills' and not library else 'disabled')
        self.assign_button.config(state='disabled' if library or self.current is None or (kind == 'skills' and c == 2 and self.current not in COMPACT_BITS) else 'normal')
        self.hide_button.config(state='normal' if kind == 'skills' and not library and self.current is not None else 'disabled')
        self.canvas.delete('all');self.swatches.delete('all');self.index = None
        self.users.config(state='normal');self.users.delete('1.0', 'end')
        if self.current is not None:
            index = self.current if library else self.document.selected(kind, self.current, c)
            missing = index is None
            if missing:index = self.document.selected(kind, self.current, 1)
            self.index = index;self.assignment.current(index)
            colors = self.document.colors(kind, self.preview_context());rows = unpack(self.document.art[kind][index])
            for y, row in enumerate(rows):
                for x, v in enumerate(row):
                    color = '#%02x%02x%02x' % colors[v] if v else ('#555c68' if (x + y) % 2 else '#747b87')
                    s = self.pixel_scale
                    self.canvas.create_rectangle(x * s, y * s, (x + 1) * s, (y + 1) * s, fill=color, outline='#343b47')
            for i, rgb in enumerate(colors):
                x, y = i % 4 * 32, i // 4 * 32
                self.swatches.create_rectangle(x + 1, y + 1, x + 31, y + 31, fill='#%02x%02x%02x' % rgb,
                                               outline='red' if i == self.pen else '#888888', width=3 if i == self.pen else 1)
                self.swatches.create_text(x + 16, y + 16, text=f'{i:X}', fill='white' if sum(rgb) < 330 else 'black')
            users = self.document.users(kind, index)
            text = '; '.join(f'{i:02X} {self.names_current[i]}' + (f' ({CONTEXTS[context]})' if context is not None else '') for i, context in users)
            if kind == 'items' and index in self.document.weapon_refs:
                text += ('; ' if text else '') + 'Weapon-type / empty-slot display'
            self.users.insert('1.0', text or 'No current assignments. This artwork can be assigned to an item or skill.')
            old_art, old_refs, old_flags = self.document.original
            old_used = old_refs[kind] if kind == 'items' else [v for group in old_refs[kind] for v in group]
            old_size = 128 if index < len(old_art[kind]) and (any(old_art[kind][index]) or index in old_used or index in old_flags[kind]) else 0
            size = 128 if index in self.document.active(kind) else 0
            note = f'Graphic {index:02X} / tile {tile(index):03X} | Artwork: {size} bytes ({old_size} when this editor opened).'
            if missing:note += '\nHidden or absent in this screen; preview shows its stat-help artwork.'
            if kind == 'skills':note += '\nColors follow the in-game skill palette loaded for this screen.'
            if library:note += '\nLibrary edits update every listed use. Use Private copy from an item / skill to separate it.'
            self.note.set(note)
        else:self.note.set('No matching icons.')
        self.users.config(state='disabled');self.update_space()

    def update_space(self):
        current = self.document.sizes();projected = self.document.optimized().sizes() if self.optimize.get() else current
        original = self.size_history.original;old = artwork_bytes(original);new = artwork_bytes(projected)
        private = (256 if self.pending() or self.document.storage[:16] == MAGIC else 0) + (4096 if projected['loaded'] == 20480 else 0)
        self.space.set(f'Items: {projected["items"]} / {ITEM_CAPACITY} addressable icons ({projected["items"] * 128:,} / {ITEM_CAPACITY * 128:,} artwork bytes). '
                       f'Skills: {projected["skills"]} / {(projected["loaded"] - 16384) // 128} loaded slots; maximum 32.\n'
                       f'Original total artwork: {old:,} bytes | New total artwork: {new:,} bytes | Total saved: {old - new:+,} bytes.\n'
                       f'Original loaded sheets: {original["loaded"]:,} bytes | New loaded sheets: {projected["loaded"]:,} bytes.\n'
                       f'Private ROM storage after writing: {private:,} / 8,192 reserved bytes. ROM file size stays fixed.')
        warnings = []
        if current['items'] >= 108:warnings.append(f'Item icon capacity nearly full: {ITEM_CAPACITY - current["items"]} slots remain.')
        if current['skills'] >= 29:warnings.append(f'Skill icon capacity nearly full: {32 - current["skills"]} slots remain.')
        if len(self.document.art['skills']) == 32:warnings.append('Expanded skill sheet: 4,096 loaded bytes (+1,024); uses private ROM storage plus 256 bytes of metadata.')
        if self.document.storage_error:warnings.append(self.document.storage_error)
        if self.size_history.error:warnings.append('Size config unavailable: ' + self.size_history.error)
        self.warning.set(' '.join(warnings))
        dirty = self.pending();self.write_button.config(state='normal' if dirty and not self.document.storage_error else 'disabled')
        self.status.set('Display repair available: Write to ROM applies your saved item icons to the status screen and repairs existing item help.'
                        if self.document.needs_repair else 'Staged edits: Write to ROM saves artwork and assignments together.'
                        if dirty else 'Ready. PNGs use native palettes; index 0 is transparent.')

    def pending(self, include_repair=True):
        if self.document.dirty or include_repair and self.document.needs_repair:return True
        optimized = self.document.optimized() if self.optimize.get() else self.document
        return (optimized.art, optimized.refs, optimized.flags) != self.document.original

    def choose_color(self, event):
        if 0 <= event.x < 128 and 0 <= event.y < 128:
            self.pen = event.y // 32 * 4 + event.x // 32;self.display()

    def editable_index(self):
        if self.index is None:raise ValueError('Select an icon first.')
        kind = self.category;index = self.index
        self.check_target()
        if self.private.get() and self.view.current() == 0:
            others = {i for i, _ in self.document.users(kind, index)} - {self.current}
            if others or kind == 'items' and index in self.document.weapon_refs:
                hidden = kind == 'skills' and self.document.refs[kind][0][self.current] is None
                index = self.document.add(kind, self.document.art[kind][index])
                self.document.assign(kind, self.current, index, self.context.current(), self.linked.get())
                if hidden:self.document.refs[kind][0][self.current] = None
        return index

    def check_target(self):
        if (self.category == 'skills' and self.view.current() == 0 and self.current is not None and
                self.context.current() == 2 and self.current not in COMPACT_BITS):
            raise ValueError('This skill has no entry in the compact Skills menu. Select Stat screen or Stat screen help first.')

    def paint(self, event, erase=False):
        s = self.pixel_scale
        if self.index is None or not 0 <= event.x < 16 * s or not 0 <= event.y < 16 * s:return
        try:
            rows = unpack(self.document.art[self.category][self.index]);value = 0 if erase else self.pen
            if rows[event.y // s][event.x // s] == value:return
            index = self.editable_index();rows[event.y // s][event.x // s] = value
            self.document.replace(self.category, index, rows)
            if self.view.current() == 1:self.document.flags[self.category].add(index)
            self.display()
            self.refresh_thumbnails(index)
        except ValueError as error:messagebox.showerror('Cannot paint icon', str(error), parent=self)

    def refresh_thumbnails(self, index):
        photos = {}
        for iid in self.list.get_children():
            i = int(iid)
            context = self.preview_context(i)
            value = i if self.view.current() == 1 else self.document.selected(self.category, i, context)
            if value is None:value = self.document.selected(self.category, i, 1)
            if value == index:
                if context not in photos:
                    photos[context] = tk.PhotoImage(master=self, data=base64.b64encode(self.document.png(self.category, index, context)))
                photo = photos[context]
                self.list.item(iid, image=photo);self.edited_photos[iid] = photo

    def assign(self):
        try:self.document.assign(self.category, self.current, self.assignment.current(), self.context.current(), self.linked.get())
        except ValueError as error:messagebox.showerror('Cannot assign icon', str(error), parent=self);return
        self.refresh_list()

    def hide(self):
        self.document.refs['skills'][0][self.current] = None;self.display()

    def export(self):
        if self.index is None:return
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.png', filetypes=[('PNG image', '*.png')], initialfile=f'{self.category}-icon-{self.index:02X}.png')
        if path:
            try:Path(path).write_bytes(self.document.png(self.category, self.index, self.preview_context()))
            except OSError as error:messagebox.showerror('Cannot export icon', str(error), parent=self)

    def import_image(self, adding=False):
        if not adding and self.index is None:return
        path = filedialog.askopenfilename(parent=self, filetypes=[('PNG image', '*.png')])
        if not path:return
        before = deepcopy((self.document.art, self.document.refs, self.document.flags))
        try:
            self.check_target()
            raw, reduced = import_png(self, path, self.document.colors(self.category, self.preview_context()), self.reduction.get())
            if adding:
                index = self.document.add(self.category, raw)
                if self.view.current() == 0 and self.current is not None:
                    self.document.assign(self.category, self.current, index, self.context.current(), self.linked.get())
                else:
                    self.view.current(1);self.search.set('');self.populate(index)
            else:
                if raw == self.document.art[self.category][self.index]:return
                index = self.editable_index();self.document.art[self.category][index] = raw
                if self.view.current() == 1:self.document.flags[self.category].add(index)
            self.refresh_list()
            if reduced:self.status.set('Colors reduced to the native palette. Review the staged preview before writing.')
        except Exception as error:
            self.document.art, self.document.refs, self.document.flags = before
            messagebox.showerror('Cannot import icon', str(error), parent=self)

    def add_image(self):self.import_image(True)

    def copy(self):
        if self.index is None:return
        try:
            self.check_target()
            hidden = self.category == 'skills' and self.view.current() == 0 and self.document.refs['skills'][0][self.current] is None
            index = self.document.add(self.category, self.document.art[self.category][self.index])
            if self.view.current() == 0:self.document.assign(self.category, self.current, index, self.context.current(), self.linked.get())
            if hidden:self.document.refs['skills'][0][self.current] = None
            self.refresh_list(index if self.view.current() == 1 else self.current)
        except ValueError as error:messagebox.showerror('Cannot copy icon', str(error), parent=self)

    def refresh_list(self, selected=None):
        self.populate(self.current if selected is None else selected)

    def preference(self):
        self.size_history.update(self.optimize.get());self.update_space()

    def preview(self):
        messagebox.showinfo('Icon space / optimization', report(self.size_history.original, self.document.sizes(), self.document.optimized().sizes()), parent=self)

    def save(self):
        if self.app.rom is not self.rom:
            messagebox.showerror('ROM changed', 'Reopen the icon editor for the current ROM.', parent=self);return False
        if not self.app.settle():return False
        current = self.document.sizes();projected = self.document.optimized().sizes() if self.optimize.get() else current
        try:changed = self.document.commit(self.optimize.get(), self.size_history.original)
        except (ValueError, OSError) as error:messagebox.showerror('Cannot write icons', str(error), parent=self);return False
        if changed:
            self.app.refresh_after_history()
            if self.optimize.get() and not self.size_history.report_shown:
                messagebox.showinfo('Icon optimization saved', report(self.size_history.original, current, projected), parent=self)
                self.size_history.update(True, True)
        self.document = IconDocument(self.rom);self.refresh_list()
        self.status.set('Saved to the ROM with automatic backup and undo history.' if changed else 'No icon changes to write.')
        return True

    def settle(self):
        # A detected repair enables an explicit write; it is not a new user
        # draft that must be saved/discarded to close, reload or redo an undo.
        if not self.pending(include_repair=False):return True
        answer = ask_unsaved(self, 'Write the staged icon artwork and assignments to the ROM?')
        if answer is None:return False
        return self.save() if answer else True

    def reload(self):
        if self.pending(include_repair=False) and not messagebox.askyesno('Reload icons', 'Discard the staged icon changes and reload from the current ROM?', parent=self):return
        try:self.document = IconDocument(self.rom)
        except ValueError as error:messagebox.showerror('Cannot reload icons', str(error), parent=self);return
        self.refresh_list()

    def history(self, redo):
        if not self.settle():return
        self.app.history_step(redo)
        self.document = IconDocument(self.rom);self.refresh_list()

    def launch(self):return self.app.save_and_launch(save_callback=self.save, parent=self)

    def close(self):
        if self.settle():self.destroy()


def open_icon_window(app, kind='items', record=0):
    if not app.rom:
        messagebox.showinfo('Open a ROM', 'Open the supported FE4 ROM first.', parent=app);return
    if not app.settle():return
    try:return IconWindow(app, kind, record)
    except ValueError as error:messagebox.showerror('Icon editor unavailable', str(error), parent=app)
