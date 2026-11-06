"""One workspace for item definitions, persistent slots and their appearances."""
import base64
import tkinter as tk
from tkinter import ttk, messagebox

from item_expansion import (ItemExpansion, BASE_ITEMS, MAX_ITEMS, MAX_SLOTS,
                            enabled, table, record, put, read, DONORS, ORIGINS)
from item_art import ItemArt
from rom import number, category_modules
from ui_common import ask_unsaved, scrollable_frame


class ItemWindow(tk.Toplevel):
    def __init__(self, app, kind='items', selected=0):
        model = ItemExpansion(app.rom)
        super().__init__(app)
        self.app, self.rom, self.model = app, app.rom, model
        self.current = None;self.controls = [];self.initial = [];self.photos = {};self.busy = False
        self.weapon_skill_vars={};self.weapon_skill_initial=0;self.weapon_skill_checks={}
        self.title('FE4Builder — Item Editor');self.geometry('1180x850');self.minsize(950, 650)
        top = ttk.Frame(self, padding=12);top.pack(fill='x')
        ttk.Label(top, text='Item Editor', style='Title.TLabel').pack(side='left')
        ttk.Button(top, text='Save & Launch (F5)', command=self.launch).pack(side='right')
        self.write_button = ttk.Button(top, text='Write to ROM', command=self.save);self.write_button.pack(side='right', padx=8)
        ttk.Button(top, text='Reload', command=self.reload).pack(side='right')
        ttk.Button(top, text='Redo', command=lambda:self.history(True)).pack(side='right', padx=8)
        ttk.Button(top, text='Undo', command=lambda:self.history(False)).pack(side='right')
        body = ttk.Panedwindow(self, orient='horizontal');body.pack(fill='both', expand=True, padx=12)
        left = ttk.Frame(body, width=300);body.add(left, weight=0)
        self.view = ttk.Combobox(left, state='readonly', values=['Item types', 'Player item slots', 'Advanced item modules'])
        self.view.current({'items':0,'slots':1,'modules':2}[kind]);self.previous_view = self.view.current();self.view.pack(fill='x')
        self.view.bind('<<ComboboxSelected>>', self.change_view)
        self.module_panel = ttk.Frame(left)
        ttk.Label(self.module_panel,text='Original item module').pack(anchor='w')
        self.module_selector = ttk.Combobox(self.module_panel,state='readonly',width=36)
        self.module_selector.pack(fill='x',pady=(4,0));self.module_selector.bind('<<ComboboxSelected>>',self.change_module)
        self.previous_module = 'FE4 Broken Weapon Editor'
        self.search = tk.StringVar();ttk.Entry(left, textvariable=self.search).pack(fill='x', pady=8)
        listing = ttk.Frame(left);listing.pack(fill='both', expand=True)
        ttk.Style(self).configure('ItemWorkspace.Treeview',rowheight=36)
        self.list = ttk.Treeview(listing, show='tree', selectmode='browse',style='ItemWorkspace.Treeview');self.list.column('#0', width=280)
        bar = ttk.Scrollbar(listing, command=self.list.yview);bar.pack(side='right', fill='y')
        self.list.configure(yscrollcommand=bar.set);self.list.pack(fill='both', expand=True)
        self.list.bind('<<TreeviewSelect>>', self.select)
        controls = self.entry_actions = ttk.Frame(left);controls.pack(fill='x', pady=8)
        self.add_button = ttk.Button(controls, text='Add item...', command=self.add);self.add_button.pack(side='left')
        self.remove_button = ttk.Button(controls, text='Remove entry', command=self.remove);self.remove_button.pack(side='left', padx=6)
        self.count = tk.StringVar();self.count_label=ttk.Label(left, textvariable=self.count, wraplength=300);self.count_label.pack(anchor='w')
        right = ttk.Frame(body, padding=(16, 0, 0, 0));body.add(right, weight=1)
        self.heading = tk.StringVar();ttk.Label(right, textvariable=self.heading, style='Title.TLabel',wraplength=760).pack(anchor='w')
        self.details = tk.StringVar();ttk.Label(right, textvariable=self.details, wraplength=760).pack(anchor='w', pady=6)
        self.content = scrollable_frame(right)
        space = ttk.LabelFrame(self, text='Item storage', padding=10);space.pack(fill='x', padx=12, pady=10)
        ttk.Button(space, text='Optimize storage / report...', command=self.optimize).pack(side='right', padx=8)
        self.space = tk.StringVar();ttk.Label(space, textvariable=self.space, justify='left', wraplength=860).pack(anchor='w')
        self.status = tk.StringVar(value='Changes are written with automatic backups. IDs remain stable when entries are removed.')
        ttk.Label(self, textvariable=self.status, relief='sunken', padding=8, wraplength=1100).pack(fill='x')
        self.search.trace_add('write', lambda *_:self.populate())
        self.protocol('WM_DELETE_WINDOW', self.close);self.bind('<F5>', lambda _:self.launch())
        self.populate(selected)

    @property
    def kind(self):return ('items','slots','modules')[self.view.current()]

    def pending(self):return self.current is not None and ([var.get() for var, _ in self.controls] != self.initial or self.extra_skill_mask()!=self.weapon_skill_initial)

    def extra_skill_mask(self):return sum(bit for bit,var in self.weapon_skill_vars.items() if var.get())

    def settle(self):
        if not self.pending():return True
        answer = ask_unsaved(self, 'Write this module record to the opened ROM?' if self.kind=='modules' else 'Write this item or player slot to the opened ROM?')
        return False if answer is None else self.save() if answer else True

    def change_view(self, _=None):
        choice = self.view.current()
        self.view.current(self.previous_view)
        if not self.settle():return
        self.view.current(choice)
        self.previous_view = choice;self.current = None;self.controls = [];self.initial = []
        self.search.set('');self.populate()

    def change_module(self, _=None):
        choice=self.module_selector.get()
        self.module_selector.set(self.previous_module)
        if not self.settle():return
        self.previous_module=choice;self.module_selector.set(choice)
        self.current=None;self.controls=[];self.initial=[]
        self.search.set('');self.populate()

    def populate(self, selected=None):
        if self.busy:return
        self.busy = True
        try:
            self.model = ItemExpansion(self.rom);self.art = ItemArt(self.rom)
            if self.kind=='modules':
                self.populate_modules(selected)
                return
            self.module_panel.pack_forget()
            if not self.entry_actions.winfo_manager():self.entry_actions.pack(fill='x',pady=8,before=self.count_label)
            ids = enabled(self.rom, self.kind);self.visible = []
            query = self.search.get().casefold().strip()
            self.list.delete(*self.list.get_children());self.photos = {}
            for value in ids:
                item = self.model.assignments[value] if self.kind == 'slots' else value
                try:name = self.art.name(item)
                except (ValueError, KeyError):name = f'Item {item:02X}'
                label = f'{value:02X} {name}'
                if query and query not in label.casefold():continue
                try:
                    from portraits import export_png
                    rows, colors = self.art.icon(item)
                    self.photos[value] = tk.PhotoImage(master=self, data=base64.b64encode(export_png(rows, colors))).zoom(2)
                    self.list.insert('', 'end', iid=str(value), text=label, image=self.photos[value])
                except ValueError:self.list.insert('', 'end', iid=str(value), text=label)
                self.visible.append(value)
            maximum = MAX_SLOTS if self.kind == 'slots' else MAX_ITEMS
            self.count.set(f'{len(ids)} / {maximum} enabled; {maximum-len(ids)} IDs available.\nFF = Nothing; player slot 00 is reserved.')
            self.add_button.configure(text='Add player slot...' if self.kind == 'slots' else 'Add item...')
            self.add_button.configure(state='normal' if len(ids) < maximum else 'disabled')
            value = selected if selected in self.visible else self.current if self.current in self.visible else self.visible[0] if self.visible else None
            if value is not None:
                self.list.selection_set(str(value));self.list.see(str(value))
                if selected is not None or self.current is None or self.current not in self.visible:self.load(value)
            self.update_space()
            self.update_idletasks()
            if value is not None:self.list.see(str(value))
        finally:self.busy = False

    def populate_modules(self, selected=None):
        from item_expansion import ITEM_MODULE
        self.native_modules=[m for m in category_modules('Item Editor',self.rom) if m.name!=ITEM_MODULE]
        names=[m.name for m in self.native_modules]
        self.module_selector.configure(values=names)
        choice=self.previous_module if self.previous_module in names else names[0]
        self.module_selector.set(choice);self.previous_module=choice
        self.module_panel.pack(fill='x',pady=(8,0),after=self.view)
        self.entry_actions.pack_forget()
        module=next(m for m in self.native_modules if m.name==choice)
        query=self.search.get().casefold().strip();self.visible=[];self.photos={}
        self.list.delete(*self.list.get_children())
        first=1 if module.name=='FE4 Player Weapon Editor' else 0
        allowed=set(enabled(self.rom,'slots')) if first else set(enabled(self.rom,'items')) if module.name=='FE4 Item Sprite Editor by Lorena' else None
        from item_art import item_for_record
        for index in range(module.count):
            if allowed is not None and index+first not in allowed:continue
            name=module.names[index]
            item=self.rom.values(module,index)[0] if first else item_for_record(module,index)
            if item is not None:
                try:name=self.art.name(item)
                except ValueError:pass
            label=f'{index+first:02X} {name}'
            if query and query not in label.casefold():continue
            try:
                from portraits import export_png
                rows,colors=self.art.icon(item) if item is not None else (None,None)
                if rows is None:raise ValueError('No item for this record.')
                self.photos[index]=tk.PhotoImage(master=self,data=base64.b64encode(export_png(rows,colors))).zoom(2)
                self.list.insert('','end',iid=str(index),text=label,image=self.photos[index])
            except ValueError:self.list.insert('','end',iid=str(index),text=label)
            self.visible.append(index)
        self.count.set(f'{len(self.native_modules)} original modules · {module.count} records\nSearch filters this module’s records.')
        value=selected if selected in self.visible else self.current if self.current in self.visible else self.visible[0] if self.visible else None
        if value is not None:
            self.list.selection_set(str(value))
            if selected is not None or self.current is None or self.current not in self.visible:self.load(value)
        self.update_space();self.update_idletasks()
        if value is not None:self.list.see(str(value))

    def select(self, _=None):
        if self.busy:return
        selection = self.list.selection()
        if not selection:return
        value = int(selection[0])
        if value == self.current:return
        if not self.settle():
            self.list.selection_set(str(self.current));return
        if self.kind=='modules' and bytes(self.rom.data)!=self.form_snapshot:
            self.populate(value);return
        self.load(value)

    def add_control(self, parent, label, value, options=None, row=0, column=0, field=None):
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky='w', padx=(0, 8), pady=5)
        mapping = {f'{key:02X} {name}':key for key, name in (options or {}).items()}
        text = next((name for name, key in mapping.items() if key == value), str(value))
        var = tk.StringVar(value=text)
        control=ttk.Frame(parent);control.grid(row=row,column=column+1,sticky='ew',padx=(0,16),pady=5)
        if field is not None and field.reference in ('FE4 Player Equipment.txt','FE4 Weapon List.txt'):
            icon=ttk.Label(control);icon.pack(side='left',padx=(0,6))
            self.equipment_icons[len(self.controls)]=(icon,field)
        widget = ttk.Combobox(control, textvariable=var, values=list(mapping), width=23) if mapping else ttk.Entry(control, textvariable=var, width=25)
        widget.pack(side='left',fill='x',expand=True)
        if field is not None and field.reference in ('FE4 Weapon Bonus.txt','FE4 Ring Bonuses.txt','FE4 Item Bonuses.txt'):
            kind='weapon' if field.reference=='FE4 Weapon Bonus.txt' else 'ring'
            ttk.Button(control,text='Edit...',command=lambda i=len(self.controls),k=kind:self.edit_bonus(i,k)).pack(side='left',padx=(6,0))
        self.controls.append((var, mapping));return var

    def load(self, value):
        self.current = value;self.model = ItemExpansion(self.rom);self.art = ItemArt(self.rom)
        self.form_snapshot = bytes(self.rom.data)
        self.controls = [];self.initial = [];self.equipment_icons={}
        self.weapon_skill_vars={};self.weapon_skill_initial=0;self.weapon_skill_checks={}
        self.preview_picture=None;self.held_picture=None;self.preview=None;self.held_preview=None
        for widget in self.content.winfo_children():widget.destroy()
        if self.kind=='modules':
            self.load_module_record(value)
            return
        item = self.model.assignments[value] if self.kind == 'slots' else value
        try:name = self.art.name(item)
        except ValueError:name = f'Item {item:02X}'
        self.heading.set(f'{value:02X} {name}')
        self.details.set(f'Player item slot {value:02X} → item type {item:02X}' if self.kind == 'slots' else f'Item type {item:02X} · Shared by every instance of this item')
        self.create_previews()
        original = int.from_bytes(self.model.block[18:20], 'little') if self.model.installed else max(self.model.slots, default=0)
        removable = value > original if self.kind == 'slots' else value >= BASE_ITEMS
        self.remove_button.configure(state='normal' if removable else 'disabled')
        if self.kind == 'slots':
            box = ttk.LabelFrame(self.content, text='Slot assignment', padding=10);box.pack(fill='x')
            options = {i:self.art.name(i) for i in self.model.items}
            self.add_control(box, 'Item type', item, options,field=self.art.player.fields[0])
            ttk.Button(box, text='Edit this item', command=lambda:self.open_item(item)).grid(row=1, column=0, columnspan=2, sticky='w', pady=8)
            self.show_locations(value)
            self.module = None;self.stat_count = 1
        else:
            self.module, self.module_index = self.art.record(item)
            box = ttk.LabelFrame(self.content, text='Item properties', padding=10);box.pack(fill='x')
            box.columnconfigure(1, weight=1);box.columnconfigure(3, weight=1)
            for i, (field, stored) in enumerate(zip(self.module.fields, self.rom.values(self.module, self.module_index))):
                options=self.rom.field_options(field)
                if field.name=='Type':options={key:label for key,label in options.items() if key==2} if len(record(self.rom,item))==10 else {key:label for key,label in options.items() if key in (0,1)}
                self.add_control(box, field.name, stored, options, i//2, i%2*2,field)
            self.stat_count = len(self.controls)
            actions = ttk.Frame(self.content);actions.pack(fill='x', pady=10)
            for text, category in (('Edit name...', 'Item names'), ('Edit description...', 'Item descriptions'), ('Edit event name...', 'Item names — messages')):
                ttk.Button(actions, text=text, command=lambda c=category:self.edit_text(c)).pack(side='left', padx=(0, 6))
            ttk.Button(actions, text='Edit icon...', command=self.edit_icon).pack(side='left')
            if len(record(self.rom,item))==19:self.create_weapon_skill_controls(item,actions)
            if item < 125 or item >= BASE_ITEMS:
                graphics = ttk.LabelFrame(self.content, text='Held weapon graphics', padding=10);graphics.pack(fill='x', pady=8,before=box)
                sprite, palette = read(self.rom, table(self.rom, 'held') + item*2, 2)
                self.add_control(graphics, 'Sprite', sprite, {i:f'Sprite {i:02X}' for i in range(65)} | {255:'None'}, 0)
                self.add_control(graphics, 'Palette', palette, {i:f'Palette {i:02X}' for i in range(36)} | {255:'None'}, 1)
                ttk.Button(graphics, text='Combat animations...', command=self.edit_combat).grid(row=2, column=0, columnspan=2, sticky='w', pady=8)
                if item >= BASE_ITEMS:
                    donor = read(self.rom, DONORS + item, 1)[0]
                    self.add_control(graphics, 'Animation template', donor, {i:self.art.name(i) for i in range(BASE_ITEMS)}, 3)
                    origin = read(self.rom, ORIGINS + item, 1)[0]
                    self.add_control(graphics, 'Blood / inheritance template', origin, {i:self.art.name(i) for i in range(BASE_ITEMS)}, 4)
                ttk.Label(graphics, text='Reuse existing held sprites and palettes. Animation templates supply attack poses, map graphics and effects. Blood/inheritance templates supply the copied item’s holy blood requirement and inheritance exceptions.', wraplength=650).grid(row=5, column=0, columnspan=2, sticky='w', pady=8)
        self.initial = [var.get() for var, _ in self.controls]
        for var,_ in self.controls:var.trace_add('write',lambda *_:self.draw_preview())
        self.draw_preview()

    def create_weapon_skill_controls(self,item,before):
        from weapon_skills import WeaponSkills,SKILLS
        model=WeaponSkills(self.rom)
        box=ttk.LabelFrame(self.content,text='Additional weapon skills',padding=10);box.pack(fill='x',pady=8,before=before)
        if not model.installed:
            ttk.Label(box,text='Install Additional weapon skills in Patches to assign Adept, Charge/Accost, Vantage, Luna and Sol.',wraplength=650).pack(anchor='w')
            ttk.Button(box,text='Open weapon skill patch...',command=self.open_weapon_skill_patch).pack(anchor='w',pady=(8,0));return
        self.weapon_skill_initial=model.get(item)
        for i,(bit,_,name) in enumerate(SKILLS):
            var=tk.BooleanVar(value=bool(self.weapon_skill_initial&bit));self.weapon_skill_vars[bit]=var
            button=ttk.Checkbutton(box,text=name+(' (swords only)' if bit&24 else ''),variable=var,command=self.draw_preview)
            button.grid(row=i//2,column=i%2,sticky='w',padx=(0,18),pady=4);self.weapon_skill_checks[bit]=button
        ttk.Label(box,text='Only equipped weapons grant these skills. Luna and Sol retain their native sword requirement and activation rules.',
                  wraplength=650).grid(row=3,column=0,columnspan=2,sticky='w',pady=(8,0))

    def open_weapon_skill_patch(self):
        if not self.settle():return
        window=self.app.edit_patches()
        if window is not None:
            tabs=next(w for w in window.winfo_children() if isinstance(w,ttk.Notebook));tabs.select(2)

    def update_weapon_skill_controls(self):
        if not self.weapon_skill_checks:return
        try:values=self.values()
        except ValueError:return
        stats=dict(zip((f.name for f in self.module.fields),values))
        for bit,button in self.weapon_skill_checks.items():
            available=stats.get('Type')==0 and (not bit&24 or stats.get('Weapon Type')==0)
            button.configure(state='normal' if available or self.weapon_skill_vars[bit].get() else 'disabled')

    def load_module_record(self, index):
        from item_expansion import ITEM_MODULE
        self.native_modules=[m for m in category_modules('Item Editor',self.rom) if m.name!=ITEM_MODULE]
        self.module=next(m for m in self.native_modules if m.name==self.module_selector.get())
        self.module_index=index
        self.heading.set(self.module.name.removeprefix('FE4 '))
        self.details.set(f'{self.module.names[index]} · Record {index:02X} · File address 0x{self.rom.address(self.module,index):06X} · {self.module.stride} bytes')
        from item_art import item_for_record
        self.module_item_field=next((i for i,f in enumerate(self.module.fields) if f.reference=='FE4 Weapon List.txt'),None)
        if item_for_record(self.module,index) is not None or self.module.name=='FE4 Player Weapon Editor' or self.module_item_field is not None:
            self.create_previews()
        box=ttk.LabelFrame(self.content,text='Original module fields',padding=10);box.pack(fill='x',pady=8)
        box.columnconfigure(1,weight=1);box.columnconfigure(3,weight=1)
        for i,(field,value) in enumerate(zip(self.module.fields,self.rom.values(self.module,index))):
            self.add_control(box,field.name,value,self.rom.field_options(field),i//2,i%2*2,field)
        self.stat_count=len(self.controls);self.initial=[var.get() for var,_ in self.controls]
        ttk.Label(self.content,text='These are the original module controls, including raw pointer tables.\n'
                  'Values accept decimal or 0x hexadecimal numbers. Expanded slots and held graphics use their relocated tables.\n'
                  'Write to ROM uses the same automatic backups and undo/redo as the item views.',
                  wraplength=700,justify='left').pack(anchor='w',pady=8)
        self.remove_button.configure(state='disabled')
        for var,_ in self.controls:var.trace_add('write',lambda *_:self.draw_preview())
        self.draw_preview()

    def create_previews(self):
        box=ttk.LabelFrame(self.content,text='Graphics preview',padding=10);box.pack(fill='x',pady=8)
        box.columnconfigure(1,weight=1)
        ttk.Label(box,text='Inventory icon').grid(row=0,column=0,sticky='w',padx=(0,24))
        ttk.Label(box,text='Held weapon — current sprite and palette').grid(row=0,column=1,sticky='w')
        self.preview_picture=ttk.Label(box);self.preview_picture.grid(row=1,column=0,sticky='nw',padx=(0,24),pady=6)
        self.held_picture=ttk.Label(box);self.held_picture.grid(row=1,column=1,sticky='nw',pady=6)
        self.held_caption=tk.StringVar();ttk.Label(box,textvariable=self.held_caption,wraplength=480,justify='left').grid(row=2,column=1,sticky='w')
        self.preview_caption=tk.StringVar();ttk.Label(box,textvariable=self.preview_caption,wraplength=700,justify='left').grid(row=3,column=0,columnspan=2,sticky='w',pady=(6,0))

    def control_value(self,index):
        var,mapping=self.controls[index]
        return mapping[var.get()] if var.get() in mapping else number(var.get().strip())

    def draw_preview(self):
        if self.current is None:return
        self.update_weapon_skill_controls()
        from portraits import export_png
        for index,(label,field) in self.equipment_icons.items():
            try:
                item=self.art.resolve(field,self.control_value(index))
                if item is None:label.configure(image='',text='—');label.image=None;continue
                rows,colors=self.art.icon(item)
                label.image=tk.PhotoImage(master=self,data=base64.b64encode(export_png(rows,colors))).zoom(2)
                label.configure(image=label.image,text='')
            except (ValueError,OverflowError):label.configure(image='',text='?');label.image=None
        if self.preview_picture is None:return
        self.preview_picture.configure(image='');self.held_picture.configure(image='')
        self.preview=None;self.held_preview=None
        try:
            values=self.values();overrides=None;stats=None
            if self.kind=='modules':
                from item_art import item_for_record
                item=item_for_record(self.module,self.current)
                if self.module.name=='FE4 Player Weapon Editor':item=values[0]
                elif item is None and self.module_item_field is not None:item=values[self.module_item_field]
                if self.module.name=='FE4 Item Sprite Editor by Lorena':overrides=tuple(values[:2])
                elif item_for_record(self.module,self.current) is not None:
                    stats=dict(zip((f.name for f in self.module.fields),values))
            elif self.kind=='slots':item=values[0]
            else:
                item=self.current;stats=dict(zip((f.name for f in self.module.fields),values[:self.stat_count]))
                if len(values)>self.stat_count:overrides=tuple(values[self.stat_count:self.stat_count+2])
            if item==255:
                self.preview_caption.set('Nothing');self.held_caption.set('No item selected.');return
            if item not in self.model.items:raise ValueError('Disabled or unsupported item ID.')
            self.preview_caption.set(self.art.name(item,stats)+'\n'+self.art.summary(item,stats))
            rows,colors=self.art.icon(item)
            self.preview = tk.PhotoImage(master=self,data=base64.b64encode(export_png(rows,colors))).zoom(4)
            self.preview_picture.configure(image=self.preview)
        except (ValueError,OverflowError) as error:
            self.preview_caption.set('Preview unavailable: '+str(error));self.held_caption.set('');return
        try:
            rows,colors,note=self.art.art(item,overrides,stats)
            if note!='Native held-weapon preview':self.held_caption.set('This item has no held-weapon artwork.');return
            self.held_preview=tk.PhotoImage(master=self,data=base64.b64encode(export_png(rows,colors))).zoom(4)
            self.held_picture.configure(image=self.held_preview)
            assignment=overrides if overrides is not None else read(self.rom,table(self.rom,'held')+item*2,2)
            self.held_caption.set(f'Sprite {assignment[0]:02X} · Palette {assignment[1]:02X}\nUpdates before writing to ROM.')
        except (ValueError,OverflowError) as error:self.held_caption.set('Held preview unavailable: '+str(error))

    def values(self):
        result = []
        for var, mapping in self.controls:
            try:result.append(mapping[var.get()] if var.get() in mapping else number(var.get().strip()))
            except ValueError:raise ValueError('Choose an option or enter a decimal or 0x hexadecimal number.')
        return result

    def save(self):
        if self.app.rom is not self.rom:
            messagebox.showerror('ROM changed', 'Reopen the Item Editor for the current ROM.', parent=self);return False
        if not self.pending():return True
        if not self.app.settle():return False
        before = bytes(self.rom.data)
        try:
            if bytes(self.rom.data) != self.form_snapshot:raise ValueError('The ROM changed in another editor. Reload this item before writing.')
            self.model.require_current();values = self.values()
            if self.kind=='modules':self.rom.write(self.module,self.module_index,values)
            elif self.kind == 'slots':self.model.assign(self.current, values[0])
            else:
                raw = bytearray(record(self.rom, self.current))
                for field, value in zip(self.module.fields, values[:self.stat_count]):
                    raw[field.offset:field.offset+field.size] = value.to_bytes(field.size, 'little', signed=field.signed)
                if raw[0] not in self.model.items:raise ValueError('The name ID must belong to an enabled item entry.')
                origin = values[self.stat_count+3] if self.current >= BASE_ITEMS else None
                skills=self.extra_skill_mask() if self.weapon_skill_vars else None
                self.model.write_record(self.current, raw, origin,skills=skills)
                if len(values) > self.stat_count:
                    sprite, palette = values[self.stat_count:self.stat_count+2]
                    if sprite not in range(65) and sprite != 255 or palette not in range(36) and palette != 255:
                        raise ValueError('Choose an existing held sprite and palette.')
                    put(self.rom, table(self.rom, 'held') + self.current*2, bytes([sprite, palette]))
                    if self.current >= BASE_ITEMS:
                        donor = values[self.stat_count+2]
                        if not 0 <= donor < BASE_ITEMS:raise ValueError('Choose an original item as the animation template.')
                        put(self.rom, DONORS+self.current, bytes([donor]))
                        if raw[1] == 0 and raw[10] < 4:
                            from combat_art import CombatArtwork
                            if donor not in CombatArtwork(self.rom).candidates(self.current):
                                raise ValueError('Choose a physical animation template matching this weapon type and range.')
                            if sprite >= 65 or palette >= 36:raise ValueError('A physical weapon needs an existing held sprite and palette.')
            description='Item module: '+self.module.name if self.kind=='modules' else 'Item Editor'
            self.rom.save_original(description, [f'Record {self.current:02X}' if self.kind=='modules' else f'{self.kind}: {self.current:02X}'])
        except (OSError, ValueError, OverflowError) as error:
            self.rom.data[:] = before
            self.model = ItemExpansion(self.rom)
            messagebox.showerror('Cannot write item', str(error), parent=self);return False
        selected = self.current;self.app.refresh_after_history();self.populate(selected)
        self.status.set('Written to ROM with an automatic backup. Restart the emulator to load the written ROM.')
        return True

    def show_locations(self, slot):
        from player_items import SlotLocations
        index = SlotLocations(self.rom)
        box = ttk.LabelFrame(self.content, text=f'Appearances of slot {slot:02X}', padding=10);box.pack(fill='x', pady=10)
        ttk.Label(box, text=index.summary(slot), wraplength=700, justify='left').pack(anchor='w')
        self.location_rows = index.rows[slot]
        for row in self.location_rows:
            frame = ttk.Frame(box);frame.pack(fill='x', pady=8)
            ttk.Button(frame, text='Go to location', command=lambda r=row:self.go_location(r)).pack(side='right')
            ttk.Label(frame, text=row.title, wraplength=530, justify='left').pack(anchor='w')
            ttk.Label(frame, text=row.note, wraplength=530, justify='left', style='Subtitle.TLabel').pack(anchor='w')
        if not self.location_rows:ttk.Label(box, text='No indexed appearances. Assign this slot in inventories, shops or events to make it obtainable.').pack(anchor='w', pady=8)
        ttk.Label(box, text='Custom ASM references and actual save ownership are not simulated.', wraplength=680).pack(anchor='w', pady=8)
        if index.warnings:ttk.Button(box, text=f'Coverage notes ({len(index.warnings)})', command=lambda:messagebox.showinfo('Slot reference coverage', '\n'.join(index.warnings), parent=self)).pack(anchor='w')

    def go_location(self, row):
        if not self.settle():return False
        target = row.target
        if target[0] == 'record':return self.app.go_to_record(*target[1:])
        if target[0] == 'village':
            window = self.app.edit_villages()
            if window is None:return False
            window.chapter.current(target[1]);window.populate();return window.load(target[2])
        if target[0] == 'event':
            window = self.app.edit_events(target[2])
            return window.focus_event(target[2], target[3]) if window is not None else False
        return False

    def open_item(self, item):
        if not self.settle():return
        self.view.current(0);self.previous_view = 0;self.current = None;self.search.set('');self.populate(item)

    def edit_text(self, category):
        if not self.settle():return
        item = self.current;name_id = record(self.rom, item)[0]
        if category == 'Item names — messages':
            if item >= BASE_ITEMS:index = item
            else:
                pointer = int.from_bytes(read(self.rom, 0xD9402 + (item if item < 0x89 else 0)*2, 2), 'little')
                from menu_text import catalogue
                entry = next((e for e in catalogue()['entries'] if e['kind'] == 'encoded' and e['category'] == category and e['address'] == 0x500000 + pointer), None)
                if entry is None:messagebox.showerror('Cannot open event name', 'This item uses an unsupported message-name mapping.', parent=self);return
                index = entry['id']
        else:index = name_id
        self.app.edit_menu_text(category, index)

    def edit_icon(self):
        if self.settle():self.app.edit_icons('items', self.current)

    def edit_bonus(self,index,kind='weapon'):
        try:value=self.control_value(index)
        except ValueError:messagebox.showerror('Invalid bonus','Choose a bonus profile or enter its numeric ID.',parent=self);return None
        if self.settle():return self.app.edit_stat_bonuses(kind,value)

    def edit_combat(self):
        if not self.settle():return
        from combat_art_window import CombatArtWindow
        try:self.app.prepare_window(CombatArtWindow(self.app, self.current), restore=False)
        except ValueError as error:messagebox.showerror('Cannot open combat animations', str(error), parent=self)

    def add(self):
        if self.kind=='modules':return
        if not self.settle():return
        self.model = ItemExpansion(self.rom)
        available = sorted(set(range(1,255) if self.kind == 'slots' else range(138,255)) - set(enabled(self.rom, self.kind)))
        if not available:return
        dialog = tk.Toplevel(self);dialog.title('Add player item slot' if self.kind == 'slots' else 'Add item type');dialog.transient(self);dialog.grab_set()
        body = ttk.Frame(dialog, padding=18);body.pack(fill='both', expand=True)
        ttk.Label(body, text='Player slot ID (hex)' if self.kind == 'slots' else 'Item type ID (hex)').pack(anchor='w')
        identity = tk.StringVar(value=f'{available[0]:02X}');ttk.Entry(body, textvariable=identity).pack(fill='x', pady=6)
        ttk.Label(body, text='Assigned item' if self.kind == 'slots' else 'Copy existing item as a template').pack(anchor='w')
        options = {f'{i:02X} {self.art.name(i)}':i for i in self.model.items}
        donor = ttk.Combobox(body, values=list(options), state='readonly', width=45);donor.current(0);donor.pack(fill='x', pady=6)
        if self.kind == 'items' and self.current in self.model.items:donor.current(self.model.items.index(self.current))
        ttk.Label(body, text=('Enabling expansion requires a NEW GAME. Existing saves will be hidden by the new save format. '
                             'All four save slots remain available. Later additions use the same save layout.' if not self.model.installed else
                             'Existing IDs remain unchanged. The new entry reuses its template artwork until you edit it.'), wraplength=450, justify='left').pack(anchor='w', pady=10)
        def apply():
            try:value = int(identity.get().strip().removeprefix('0x'),16)
            except ValueError:messagebox.showerror('Invalid ID', 'Enter a hexadecimal ID.', parent=dialog);return
            if value not in available:messagebox.showerror('Unavailable ID', 'Choose a currently disabled ID.', parent=dialog);return
            source = options[donor.get()];dialog.destroy()
            self.structural(lambda m:m.add_slot(source,value) if self.kind == 'slots' else m.add_item(source,value), 'Add player item slot' if self.kind == 'slots' else 'Add item type', value)
        ttk.Button(body, text='Add & write to ROM', command=apply).pack(side='left', pady=8)
        ttk.Button(body, text='Cancel', command=dialog.destroy).pack(side='right', pady=8)

    def structural(self, action, description, selected=None):
        if self.app.rom is not self.rom:return False
        if not self.app.settle():return False
        before = bytes(self.rom.data)
        try:
            action(ItemExpansion(self.rom));self.rom.save_original(description)
        except (OSError, ValueError) as error:
            self.rom.data[:] = before;messagebox.showerror('Cannot change item entries', str(error), parent=self);return False
        self.current = None;self.controls = [];self.initial = [];self.app.refresh_after_history();self.populate(selected)
        self.status.set(description + ' written with an automatic backup.');return True

    def remove(self):
        if self.kind=='modules':return
        if self.current is None or not self.settle():return
        value, kind = self.current, self.kind
        refs = ItemExpansion(self.rom).references(kind,value)
        if refs:messagebox.showinfo('Entry is still used', 'Reassign or clear these references first:\n\n'+'\n'.join(refs[:40]), parent=self);return
        if not messagebox.askyesno('Remove entry', f'Remove {kind} entry {value:02X} and reclaim its private storage? Other IDs keep their numbers.', parent=self):return
        self.structural(lambda m:m.remove(kind,value), f'Remove {kind} entry {value:02X}')

    def optimize(self):
        if not self.settle():return
        from icons import IconDocument
        document = IconDocument(self.rom);edits,target = document.plan(optimize=True)
        before,after = document.sizes(),target.sizes()
        report = (f"Item icon artwork: {before['items']*128:,} → {after['items']*128:,} bytes\n"
                  f"Skill icon artwork: {before['skills']*128:,} → {after['skills']*128:,} bytes\n"
                  f"Artwork space recovered: {(before['items']+before['skills']-after['items']-after['skills'])*128:,} bytes\n\n" + self.storage_report())
        if not edits:
            messagebox.showinfo('Item storage',report+'\n\nNo further duplicate artwork to reclaim.',parent=self);return
        if not messagebox.askyesno('Apply storage optimization?',report+'\n\nWrite this optimization with an automatic backup?',parent=self):return
        def action(model):
            if model.installed:model._pack()
            doc = IconDocument(self.rom);edits, _ = doc.plan(optimize=True)
            for at, raw in edits:put(self.rom, at, raw)
        if self.structural(action, 'Optimize item storage'):
            messagebox.showinfo('Item storage', report, parent=self)

    def storage_report(self):
        model = ItemExpansion(self.rom);sizes = model.sizes()
        text = f"Items: {sizes['items']} / 255 · Player slots: {sizes['slots']} / 254\n"
        if model.installed:
            from menu_text import ARENA as TEXT, MAGIC as TEXT_MAGIC
            private = 0
            if read(self.rom,TEXT,16) == TEXT_MAGIC:
                for item in model.items:
                    if item < BASE_ITEMS:continue
                    for key in (710+(item-138)*3,711+(item-138)*3):
                        private += int.from_bytes(read(self.rom,TEXT+128+key*8+4,4),'little')
            text += (f"Added stat records: {sizes['record_bytes']:,} / {sizes['record_capacity']:,} bytes; free {sizes['record_capacity']-sizes['record_bytes']:,}.\n"
                     f"Added name/help private artwork: {private:,} bytes; descriptors/message names: {(len(model.items)-138)*48:,} bytes.\n"
                     f"Fixed expansion tables/code reservation: 8,192 bytes. Item save payload: 794 bytes per save; four save slots retained.\n"
                     'Identical added stat records share storage. Removing entries reclaims their records and private text; ROM file size stays fixed.')
        else:text += 'Expansion is disabled. Adding an entry enables capacity for a new game; opening this editor makes no ROM changes.'
        return text

    def update_space(self):self.space.set(self.storage_report())

    def reload(self):
        if self.pending() and not messagebox.askyesno('Reload item', 'Discard the unwritten item changes?', parent=self):return
        if self.app.rom is not self.rom:self.close();return
        self.controls = [];self.initial = [];self.populate(self.current)

    def history(self, redo):
        if not self.settle():return
        selected=self.current
        self.app.history_step(redo);self.current = None;self.controls = [];self.initial = [];self.populate(selected)

    def launch(self):
        if self.save():return self.app.save_and_launch(save_current=False, parent=self)
        return False

    def close(self):
        if self.settle():self.destroy()


def open_item_window(app, kind='items', selected=0):
    if not app.rom:
        messagebox.showinfo('Open a ROM', 'Open a FE4 ROM first.', parent=app);return None
    for window in app.editor_windows:
        if isinstance(window, ItemWindow) and window.rom is app.rom and window.winfo_exists():
            if not window.settle():return None
            window.view.current({'items':0,'slots':1,'modules':2}[kind]);window.previous_view = window.view.current();window.current = None
            window.search.set('');window.populate(selected);window.lift();return window
    try:return ItemWindow(app,kind,selected)
    except (ValueError,OSError) as error:messagebox.showerror('Cannot open Item Editor', str(error), parent=app);return None
