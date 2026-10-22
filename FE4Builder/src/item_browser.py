"""Visual item navigation and inventory-slot selection."""
import base64
import tkinter as tk
from tkinter import ttk
from item_art import ItemArt,ITEM_COUNT,TYPE_NAMES
from portraits import export_png

class ItemBrowser(tk.Toplevel):
    def __init__(self,app,on_pick,field=None,options=None,current=None):
        super().__init__(app)
        self.title('FE4Builder - Equipment browser' if field else 'FE4Builder - Item browser')
        self.geometry('820x700');self.minsize(720,580)
        self.transient(app);self.grab_set()
        self.app=app;self.engine=ItemArt(app.rom);self.on_pick=on_pick;self.field=field
        self.entries=[];self.photos={}
        values=sorted(options) if field else range(ITEM_COUNT)
        for value in values:
            try:
                item=self.engine.resolve(field,value) if field else value
                name='Nothing' if item is None else self.engine.name(item)
                kind='Nothing' if item is None else self.engine.kind(item)
                self.entries.append((value,item,name,kind))
            except ValueError:continue
        controls=ttk.Frame(self,padding=10);controls.pack(fill='x')
        ttk.Label(controls,text='Search').pack(side='left')
        self.search=tk.StringVar();ttk.Entry(controls,textvariable=self.search,width=28).pack(side='left',padx=8)
        self.filter=ttk.Combobox(controls,state='readonly',values=['All']+TYPE_NAMES+['Ring','Nothing'],width=12)
        self.filter.current(0);self.filter.pack(side='left')
        self.filter.bind('<<ComboboxSelected>>',lambda e:self.populate())
        self.search.trace_add('write',lambda *_:self.populate())
        slot=field and field.reference=='FE4 Player Equipment.txt'
        self.slot=bool(slot)
        ttk.Label(self,text='Choose an existing inventory slot. Multiple slots can contain the same item.' if slot else 'Browse item types and their shared weapon/staff/ring stats.',padding=(10,0,10,8)).pack(anchor='w')
        body=ttk.Frame(self,padding=(10,0));body.pack(fill='both',expand=True)
        self.list=ttk.Treeview(body,columns=('id','type'),show='tree headings',selectmode='browse')
        self.list.heading('#0',text='Equipment');self.list.column('#0',width=420)
        self.list.heading('id',text='Slot / Item' if slot else 'Item ID');self.list.column('id',width=100,stretch=False)
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
        buttons=ttk.Frame(self,padding=12);buttons.pack(fill='x')
        ttk.Button(buttons,text='Use equipment slot' if slot else 'Use item' if field else 'Open item editor',command=self.pick).pack(side='right')
        ttk.Button(buttons,text='Close',command=self.destroy).pack(side='right',padx=8)
        self.populate()
        from ui_common import fit_window
        fit_window(self)
        match=next((i for i,e in enumerate(self.entries) if e[0]==current),None)
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
            identifier=f'{value:02X} / {item:02X}' if self.slot and item is not None else f'{value:02X}'
            self.list.insert('','end',iid=str(i),text=name,image=self.photos[item],values=(identifier,item_kind))
        children=self.list.get_children()
        if children:self.list.selection_set(children[0]);self.preview()
        else:self.details.set('No matching equipment.');self.picture.configure(image='')

    def preview(self):
        selected=self.list.selection()
        if not selected:return
        value,item,name,kind=self.entries[int(selected[0])]
        if item is None:self.details.set('Nothing assigned.');self.picture.configure(image='');return
        try:
            rows,colors=self.engine.icon(item)
            note='Native inventory icon'
            self.preview_photo=tk.PhotoImage(master=self,data=base64.b64encode(export_png(rows,colors))).zoom(4)
            self.picture.configure(image=self.preview_photo)
            owners=''
            if self.slot:
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

    def pick(self):
        selected=self.list.selection()
        if not selected:return
        value=self.entries[int(selected[0])][0]
        if self.on_pick(value) is not False:self.destroy()
