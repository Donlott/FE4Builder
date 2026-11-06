"""Visual item navigation and inventory-slot selection."""
import base64
import tkinter as tk
from tkinter import ttk, messagebox
from item_art import ItemArt,ITEM_COUNT,TYPE_NAMES
from portraits import export_png

class ItemBrowser(tk.Toplevel):
    def __init__(self,app,on_pick,field=None,options=None,current=None,*,rom=None,item=None,on_new_slot=None):
        super().__init__(app)
        self.title('FE4Builder - Equipment browser' if field else 'FE4Builder - Item browser')
        self.geometry('820x700');self.minsize(720,580)
        self.transient(app);self.grab_set()
        self.app=app;self.rom=rom or app.rom;self.engine=ItemArt(self.rom);self.on_pick=on_pick;self.field=field
        self.on_new_slot=on_new_slot;self.current=current
        self.slot=bool(field and field.reference=='FE4 Player Equipment.txt')
        self.entries=[];self.photos={}
        self.options=options or (self.rom.field_options(field) if field else {})
        self.view=None
        if self.slot and on_new_slot is not None:
            views=ttk.Frame(self,padding=(10,10,10,0));views.pack(fill='x')
            ttk.Label(views,text='Choose from').pack(side='left')
            self.view=ttk.Combobox(views,state='readonly',values=['Player item slots','All item types'],width=24)
            self.view.current(1 if item is not None else 0);self.view.pack(side='left',padx=8)
            self.view.bind('<<ComboboxSelected>>',lambda _:self.load_entries())
        controls=ttk.Frame(self,padding=10);controls.pack(fill='x')
        ttk.Label(controls,text='Search').pack(side='left')
        self.search=tk.StringVar();ttk.Entry(controls,textvariable=self.search,width=28).pack(side='left',padx=8)
        self.filter=ttk.Combobox(controls,state='readonly',values=['All']+TYPE_NAMES+['Ring','Nothing'],width=12)
        self.filter.current(0);self.filter.pack(side='left')
        self.filter.bind('<<ComboboxSelected>>',lambda e:self.populate())
        self.search.trace_add('write',lambda *_:self.populate())
        ttk.Label(self,text='Player equipment stores a persistent slot. Choose an existing slot or select an item type to create one.' if self.slot and self.view else 'Choose an existing inventory slot. Multiple slots can contain the same item.' if self.slot else 'Browse item types and their shared weapon/staff/ring stats.',wraplength=760,padding=(10,0,10,8)).pack(anchor='w')
        body=ttk.Frame(self,padding=(10,0));body.pack(fill='both',expand=True)
        self.list=ttk.Treeview(body,columns=('id','type'),show='tree headings',selectmode='browse')
        self.list.heading('#0',text='Equipment');self.list.column('#0',width=420)
        self.list.heading('id',text='Slot / Item' if self.slot else 'Item ID');self.list.column('id',width=100,stretch=False)
        self.list.heading('type',text='Type');self.list.column('type',width=100,stretch=False)
        scroll=ttk.Scrollbar(body,command=self.list.yview);scroll.pack(side='right',fill='y')
        self.list.configure(yscrollcommand=scroll.set);self.list.pack(fill='both',expand=True)
        style=ttk.Style(self);style.configure('ItemBrowser.Treeview',rowheight=36)
        self.list.configure(style='ItemBrowser.Treeview')
        self.list.bind('<<TreeviewSelect>>',lambda e:self.preview())
        self.list.bind('<Double-1>',lambda e:self.pick())
        lower=ttk.Frame(self,padding=12);lower.pack(fill='x')
        self.picture=ttk.Label(lower);self.picture.pack(side='left',padx=(0,16))
        self.details=tk.StringVar();ttk.Label(lower,textvariable=self.details,wraplength=580,justify='left').pack(side='left',fill='x',expand=True)
        self.slot_panel=ttk.Frame(self,padding=(12,0,12,0))
        ttk.Label(self.slot_panel,text='Player slot').pack(side='left')
        self.slot_choice=ttk.Combobox(self.slot_panel,state='readonly',width=48)
        self.slot_choice.pack(side='left',padx=8);self.slot_choice.bind('<<ComboboxSelected>>',lambda _:self.slot_details())
        self.slot_note=tk.StringVar();self.slot_note_label=ttk.Label(self,textvariable=self.slot_note,wraplength=760,padding=(12,4))
        buttons=ttk.Frame(self,padding=12);buttons.pack(fill='x')
        self.buttons=buttons
        self.use_button=ttk.Button(buttons,text='Use equipment slot' if self.slot else 'Use item' if field else 'Open item editor',command=self.pick);self.use_button.pack(side='right')
        ttk.Button(buttons,text='Close',command=self.destroy).pack(side='right',padx=8)
        self.load_entries(item if self.type_view else current)
        from ui_common import fit_window
        fit_window(self)
    @property
    def type_view(self):return self.view is not None and self.view.current()==1

    def load_entries(self,current=None):
        from item_expansion import enabled
        self.entries=[]
        values=enabled(self.rom,'items') if self.type_view or not self.field else sorted(self.options)
        for value in values:
            try:
                item=self.engine.resolve(self.field,value) if self.field and not self.type_view else value
                self.entries.append((value,item,'Nothing' if item is None else self.engine.name(item),'Nothing' if item is None else self.engine.kind(item)))
            except ValueError:continue
        self.list.heading('id',text='Slot / Item' if self.slot and not self.type_view else 'Item ID')
        self.populate()
        match=next((i for i,e in enumerate(self.entries) if e[0]==current and self.list.exists(str(i))),None)
        if match is not None:
            self.list.selection_set(str(match));self.list.see(str(match));self.preview()

    def populate(self):
        if not hasattr(self,'list'):return
        self.list.delete(*self.list.get_children())
        query=self.search.get().casefold();kind=self.filter.get()
        for i,(value,item,name,item_kind) in enumerate(self.entries):
            if kind not in ('All',item_kind) or query not in f'{value:02X} {value} {name} {item_kind}'.casefold():continue
            if item not in self.photos:
                try:
                    rows,colors=self.engine.icon(item) if item is not None else ([[0]*16 for _ in range(16)],[(0,0,0)]*16)
                    self.photos[item]=tk.PhotoImage(master=self,data=base64.b64encode(export_png(rows,colors))).zoom(2)
                except ValueError:self.photos[item]=tk.PhotoImage(master=self,width=32,height=32)
            identifier=f'{value:02X} / {item:02X}' if self.slot and not self.type_view and item is not None else f'{value:02X}'
            self.list.insert('','end',iid=str(i),text=name,image=self.photos[item],values=(identifier,item_kind))
        children=self.list.get_children()
        if children:self.list.selection_set(children[0]);self.preview()
        else:
            self.details.set('No matching equipment.');self.picture.configure(image='');self.use_button.configure(state='disabled')
            self.slot_panel.pack_forget();self.slot_note_label.pack_forget()

    def preview(self):
        selected=self.list.selection()
        if not selected:return
        value,item,name,kind=self.entries[int(selected[0])]
        self.use_button.configure(state='normal',text='Use equipment slot' if self.slot else 'Use item' if self.field else 'Open item editor')
        self.slot_panel.pack_forget();self.slot_note_label.pack_forget()
        if self.type_view:
            from item_expansion import ItemExpansion
            model=ItemExpansion(self.rom)
            self.slot_options={f'{slot:02X} — existing player slot':(slot,False) for slot,assigned in model.assignments.items() if assigned==item}
            free=next((slot for slot in range(1,255) if slot not in model.slots),None)
            if free is not None:self.slot_options[f'{free:02X} — create new player slot']=(free,True)
            self.slot_choice.configure(values=list(self.slot_options))
            self.slot_panel.pack(fill='x',before=self.buttons);self.slot_note_label.pack(fill='x',before=self.buttons)
            if self.slot_options:
                self.slot_choice.current(0);self.slot_details()
            else:
                self.slot_choice.set('');self.slot_note.set('No player slot contains this item, and all 254 slots are enabled. Reassign a slot in Item Editor first.');self.use_button.configure(state='disabled')
        if item is None:self.details.set('Nothing assigned.');self.picture.configure(image='');return
        try:
            rows,colors=self.engine.icon(item)
            note='Native inventory icon'
            self.preview_photo=tk.PhotoImage(master=self,data=base64.b64encode(export_png(rows,colors))).zoom(4)
            self.picture.configure(image=self.preview_photo)
            owners=''
            if self.slot and not self.type_view:
                from usage import UsageIndex
                index=getattr(self.app,'usage_index',None)
                if index is None or index.stamp!=id(self.app.rom.original):
                    index=UsageIndex(self.app.rom);self.app.usage_index=index
                if index.records is None:index._build()
                labels=[label for label,_,_,slots in index.records if any(slot==value for _,slot in slots)]
                owners='\nKnown slot users: '+('; '.join(label.split(' — ')[0] for label in labels[:4]) or 'none in indexed records')
                if len(labels)>4:owners+=f' (+{len(labels)-4} more)'
                owners+='; events may also reference this slot.'
            self.details.set(name+'\n'+self.engine.summary(item)+'\n'+note+owners)
        except ValueError as error:self.details.set(name+'\nPreview unavailable: '+str(error));self.picture.configure(image='')

    def slot_details(self):
        from item_expansion import installed
        selected=self.slot_options.get(self.slot_choice.get())
        if selected is None:return
        slot,new=selected
        self.use_button.configure(text=f'Use new player slot {slot:02X}' if new else 'Use equipment slot')
        self.slot_note.set(('The new slot and this equipment choice are staged until Write to ROM. '+
                            ('Enabling extra slots requires a NEW GAME.' if not installed(self.rom) else 'Existing slots keep their items.')) if new else
                           f'Uses persistent slot {slot:02X}. Existing appearances and inheritance still refer to this same slot.')

    def pick(self):
        selected=self.list.selection()
        if not selected:return
        value=self.entries[int(selected[0])][0]
        if self.type_view:
            choice=self.slot_options.get(self.slot_choice.get())
            if choice is None:return
            slot,new=choice
            if new:
                try:
                    if self.on_new_slot(value,slot) is False:return
                except (ValueError,OverflowError) as error:
                    messagebox.showerror('Cannot create player slot',str(error),parent=self);return
            value=slot
        if self.on_pick(value) is not False:self.destroy()
