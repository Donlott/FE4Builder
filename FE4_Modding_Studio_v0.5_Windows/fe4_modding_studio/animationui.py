"""Native assignment browser; edits existing assets, no animation playback."""
import tkinter as tk
from tkinter import ttk,messagebox,filedialog
from pathlib import Path
import json
from animationcore import AnimationModel,AnimationError,CAT,MAP_NAMES,MOVEMENT

DESCRIPTIONS={
'Battle':'Choose the class, gender and weapon row. Axe and Hand axe are separate. Copy a matching donor setup or edit the four hexadecimal IDs. Changing a setup does not grant weapon ranks or insert animation graphics.',
'Map combat':'Each profile contains eight directions of motion controls and graphics, plus its sprite type. Copy a complete donor profile to keep those parts together. This affects all users of that profile and all its weapons; separate per-weapon map overrides are not implemented.',
'Female map assignment':'The original loader always uses the class-number profile for males. Females may use a different profile here. Seliph as KnightLord has a separate hard-coded profile 5D, unaffected by this selector.',
'Map movement':'Change the movement/selection sprite used by this class, gender or character-specific row. Fallback rows apply when earlier conditions do not match. This does not change map-combat graphics or idle-sprite artwork.',
'Battle positioning':'Existing class/weapon standing-position control IDs. These apply to both genders. Donors copy only this value; they do not add a missing class/weapon row.',
'Projectile timing':'Existing class-specific Bow / Hand axe / Javelin timing parameters. Two hexadecimal bytes; their full semantics are not established. Prefer copying both from a compatible donor. They apply to both genders.'}

class AnimationWindow:
    def __init__(self,parent):
        self.app=parent;self.rom=parent.rom
        if self.rom.animations is None:self.rom.animations=AnimationModel(self.rom)
        self.model=self.rom.animations;self.selected=None;self.donors=[];self.fields=[]
        self.root=tk.Toplevel(parent.root);self.root.title('FE4 Animation assignments • 0.3');self.root.geometry('1200x850');self.root.minsize(1000,720);self.root.protocol('WM_DELETE_WINDOW',self.close)
        ttk.Label(self.root,text='Animation assignments',font=('Sans',18,'bold'),padding=12).pack(anchor='w')
        ttk.Label(self.root,text='Stage each change, then Save ROM copy. Original FE4 reference names are shown; your hack may use different class names.',padding=(12,0)).pack(anchor='w')
        tools=ttk.Frame(self.root,padding=12);tools.pack(fill='x')
        self.kind=tk.StringVar(value='Battle');combo=ttk.Combobox(tools,textvariable=self.kind,values=list(self.model.by_kind),state='readonly',width=26);combo.pack(side='left');combo.bind('<<ComboboxSelected>>',self.change_kind)
        ttk.Label(tools,text='Search:').pack(side='left',padx=(15,5));self.query=tk.StringVar();entry=ttk.Entry(tools,textvariable=self.query);entry.pack(side='left',fill='x',expand=True);self.query.trace_add('write',lambda *_:self.populate())
        pane=ttk.Panedwindow(self.root,orient='horizontal');pane.pack(fill='both',expand=True,padx=12);left=ttk.Frame(pane);right=ttk.Frame(pane,padding=(12,0));pane.add(left,weight=3);pane.add(right,weight=4)
        self.rows=ttk.Treeview(left,columns=('label',),show='headings',selectmode='browse');self.rows.heading('label',text='Assignment');self.rows.column('label',width=420)
        scroll=ttk.Scrollbar(left,orient='vertical',command=self.rows.yview);self.rows.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');self.rows.pack(fill='both',expand=True);self.rows.bind('<<TreeviewSelect>>',self.select)
        self.description=ttk.Label(right,text='',wraplength=600,justify='left');self.description.pack(anchor='w',pady=6)
        self.title=ttk.Label(right,text='Select a row',font=('Sans',12,'bold'),wraplength=600);self.title.pack(anchor='w',pady=10)
        self.form=ttk.Frame(right);self.form.pack(fill='x')
        ttk.Label(right,text='Copy values from a donor in the opened ROM:').pack(anchor='w',pady=(18,5))
        self.donor=ttk.Combobox(right,state='readonly',width=60);self.donor.pack(fill='x');ttk.Button(right,text='Load donor values into fields',command=self.load_donor).pack(anchor='w',pady=6)
        self.details=tk.Text(right,height=9,wrap='word',font=('Monospace',10));self.details.pack(fill='both',expand=True,pady=8);self.details.config(state='disabled')
        buttons=ttk.Frame(right);buttons.pack(fill='x',pady=8);ttk.Button(buttons,text='Stage assignment',command=self.stage).pack(side='left');ttk.Button(buttons,text='Undo selected assignment',command=self.undo).pack(side='left',padx=8)
        self.group=tk.BooleanVar(value=self.model.reorder);ttk.Checkbutton(self.root,text='Group battle rows for lookup (preserves all records; groups class, gender and character overrides)',variable=self.group,command=self.group_change).pack(anchor='w',padx=12,pady=(12,4))
        warning='Existing battle rows are not grouped correctly. Enable grouping before saving battle edits.' if self.model.bad_order else 'Battle rows are already grouped. Grouping is optional.'
        ttk.Label(self.root,text=warning,foreground='#a05000',padding=(12,0),wraplength=1150).pack(anchor='w')
        self.status=tk.StringVar(value='Ready. No in-game animation preview is provided; test changed assignments in an emulator.');ttk.Label(self.root,textvariable=self.status,padding=12,wraplength=1150).pack(fill='x')
        footer=ttk.Frame(self.root,padding=(12,0,12,12));footer.pack(fill='x')
        ttk.Button(footer,text='Save animation project…',command=self.export).pack(side='left');ttk.Button(footer,text='Load animation project…',command=self.import_project).pack(side='left',padx=8);ttk.Button(footer,text='Save ROM copy…',command=self.save).pack(side='right')
        self.change_kind()
    def check(self):
        if self.app.busy or self.app.rom is not self.rom:self.status.set('Wait for the current save/load operation.');return False
        return True
    def error(self,e):messagebox.showerror('Animation assignments',str(e),parent=self.root)
    def change_kind(self,event=None):
        self.selected=None;self.description.config(text=DESCRIPTIONS[self.kind.get()]);self.populate();ids=self.rows.get_children()
        if ids:self.rows.selection_set(ids[0]);self.select()
    def populate(self):
        old=self.selected;self.rows.delete(*self.rows.get_children());q=self.query.get().casefold()
        for a in self.model.by_kind[self.kind.get()]:
            e=self.model.entries[a]
            if q in e.label.casefold():self.rows.insert('','end',iid=str(a),values=(('* ' if a in self.model.changes else '')+e.label,))
        if old is not None and self.rows.exists(str(old)):self.rows.selection_set(str(old))
    def select(self,event=None):
        sel=self.rows.selection()
        if not sel:return
        self.selected=int(sel[0]);e=self.model.entries[self.selected];self.title.config(text=e.label)
        self.donors=[a for a in self.model.by_kind[e.kind] if e.kind not in ('Battle','Projectile timing') or self.model.entries[a].key[1]==e.key[1]]
        self.donor['values']=[self.model.entries[a].label for a in self.donors]
        if self.selected in self.donors:self.donor.current(self.donors.index(self.selected))
        self.set_fields(self.model.value(self.selected));self.show_details()
    def set_fields(self,value):
        for w in self.form.winfo_children():w.destroy()
        self.fields=[];self.loaded=value;e=self.model.entries[self.selected]
        if e.kind=='Battle':
            for i,name in enumerate(['Control / motion ID','Main graphics ID','Sub-parts ID','Palette ID']):
                ttk.Label(self.form,text=name).grid(row=i,column=0,sticky='w',pady=3);var=tk.StringVar(value=f'{value[i]:02X}');ttk.Entry(self.form,textvariable=var,width=8).grid(row=i,column=1,sticky='w',padx=12);self.fields.append(var)
        elif e.kind=='Map movement':
            self.options=list(MOVEMENT);self.pick=ttk.Combobox(self.form,state='readonly',values=[f'{i:04X} {MOVEMENT[i]}' for i in self.options],width=55);self.pick.pack(fill='x');self.pick.current(self.options.index(int.from_bytes(value,'little')))
        elif e.kind=='Female map assignment':
            self.options=[None]+list(range(94));self.pick=ttk.Combobox(self.form,state='readonly',values=['Default (same profile number as class)']+[f'{i:02X} {n}' for i,n in enumerate(MAP_NAMES)],width=55);self.pick.pack(fill='x');self.pick.current(0 if value==b'\xff\xff' else value[1]+1)
        elif e.kind=='Map combat':ttk.Label(self.form,text='Complete profile: use a donor below, then Stage assignment.',wraplength=600).pack(anchor='w')
        else:
            ttk.Label(self.form,text='Hexadecimal value(s), separated by spaces:').pack(anchor='w');var=tk.StringVar(value=value.hex(' ').upper());ttk.Entry(self.form,textvariable=var,width=24).pack(anchor='w',pady=5);self.fields=[var]
    def field_value(self):
        e=self.model.entries[self.selected]
        if e.kind=='Battle':return bytes(int(v.get(),16) for v in self.fields)
        if e.kind=='Map movement':return self.options[self.pick.current()].to_bytes(2,'little')
        if e.kind=='Female map assignment':
            v=self.options[self.pick.current()];return b'\xff\xff' if v is None else bytes([e.key[0],v])
        if e.kind=='Map combat':return self.loaded
        return bytes.fromhex(self.fields[0].get())
    def show_details(self):
        e=self.model.entries[self.selected];v=self.loaded;lines=[f'Headerless ROM address: {e.address:06X}',f'Original: {e.original.hex(" ").upper()}',f'Current fields: {v.hex(" ").upper()}']
        if e.kind=='Map combat':
            lines=['Profile fields (ROM pointers, not artwork):']
            for i,name in enumerate(['Right','Down-right','Down','Down-left','Left','Up-left','Up','Up-right']):lines.append(f'{name:12} Motion {int.from_bytes(v[i*6:i*6+3],"little"):06X}  Graphics {int.from_bytes(v[i*6+3:i*6+6],"little"):06X}')
            lines.append('Type: '+('tall / mounted' if v[48] else 'short / infantry'))
        warning=self.model.warning(e)
        if warning:lines+=['',warning]
        if e.kind=='Battle':lines+=['','Donor copies appearance/motion IDs only. Review Battle positioning and Projectile timing separately. These shared tables apply to both genders.']
        self.details.config(state='normal');self.details.delete('1.0','end');self.details.insert('1.0','\n'.join(lines));self.details.config(state='disabled')
    def load_donor(self):
        if not self.check() or self.selected is None or self.donor.current()<0:return
        target=self.model.entries[self.selected];donor=self.model.entries[self.donors[self.donor.current()]];v=self.model.value(donor.address)
        if target.kind=='Female map assignment':v=bytes([target.key[0],donor.key[0] if v==b'\xff\xff' else v[1]])
        self.set_fields(v);self.show_details();self.status.set('Donor values loaded into fields. Click Stage assignment to retain them.')
    def stage(self):
        if not self.check() or self.selected is None:return
        try:
            self.model.stage(self.selected,self.field_value());self.loaded=self.model.value(self.selected);self.show_details();self.populate();self.status.set('Assignment staged. Save a ROM copy to apply it.');self.app.status.set('Animation edits staged.')
        except Exception as e:self.error(e)
    def undo(self):
        if self.check() and self.selected is not None:self.model.changes.pop(self.selected,None);self.populate();self.select()
    def group_change(self):
        if self.check():self.model.reorder=self.group.get()
        else:self.group.set(self.model.reorder)
    def save(self):
        if self.check():self.app.save()
    def export(self):
        if not self.check():return
        p=filedialog.asksaveasfilename(parent=self.root,defaultextension='.json',initialfile='fe4_animation_edits.json')
        if p:
            try:Path(p).write_text(json.dumps(self.model.export(),indent=2),encoding='utf-8');self.status.set('Animation project saved for this exact input ROM.')
            except Exception as e:self.error(e)
    def import_project(self):
        if not self.check():return
        p=filedialog.askopenfilename(parent=self.root,filetypes=[('Animation project','*.json')])
        if p:
            try:self.model.import_project(json.loads(Path(p).read_text(encoding='utf-8')));self.group.set(self.model.reorder);self.populate();self.select();self.status.set('Animation edits loaded.')
            except Exception as e:self.error(e)
    def close(self):self.root.destroy();self.app.animation_window=None
