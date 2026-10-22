"""Text editing window sharing the portrait editor's ROM and save operation."""
import tkinter as tk
from tkinter import ttk,messagebox,filedialog
import json
from textcore import TextModel,TextError,NAMES,END,POOL,encode_run

class TextWindow:
    def __new__(cls,parent):
        from nagacore import detected
        if cls is TextWindow and detected(parent.rom.data):
            from nagaui import NagaWindow
            return NagaWindow(parent)
        return super().__new__(cls)
    def __init__(self,parent):
        self.app=parent;self.rom=parent.rom
        if self.rom.text is None:self.rom.text=TextModel(self.rom)
        self.model=self.rom.text;self.block=None;self.run=None;self.name_index=None;self.loading=False
        self.root=tk.Toplevel(parent.root);self.root.title('FE4 Text Editor • names and story');self.root.geometry('1160x820');self.root.minsize(950,700)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        ttk.Label(self.root,text='Names & story text',font=('Sans',19,'bold'),padding=12).pack(anchor='w')
        ttk.Label(self.root,text='Stage changes here, then use Save ROM copy in the main window. Portrait and text edits are saved together.',padding=(12,0)).pack(anchor='w')
        self.tabs=ttk.Notebook(self.root);self.tabs.pack(fill='both',expand=True,padx=12,pady=10)
        self.names_tab=ttk.Frame(self.tabs,padding=10);self.story_tab=ttk.Frame(self.tabs,padding=10)
        self.tabs.add(self.names_tab,text='Menu character names');self.tabs.add(self.story_tab,text='Dialogue & story')
        self.make_names();self.make_story()
        self.status=tk.StringVar(value='Ready. Menu names and dialogue names are separate; changing one does not automatically change the other.')
        ttk.Label(self.root,textvariable=self.status,padding=10,wraplength=1100).pack(fill='x')
        bar=ttk.Frame(self.root,padding=(12,0,12,10));bar.pack(fill='x')
        ttk.Button(bar,text='Save edit project…',command=self.export_project).pack(side='left')
        ttk.Button(bar,text='Load edit project…',command=self.import_project).pack(side='left',padx=8)
        ttk.Button(bar,text='Save ROM copy…',command=self.save_rom).pack(side='right')
        self.populate_names();self.populate_blocks()
    def check(self):
        if self.app.busy:messagebox.showinfo('Please wait','A save/load operation is running.',parent=self.root);return False
        if self.rom is not self.app.rom:messagebox.showerror('ROM changed','Close and reopen the text editor for the currently opened ROM.',parent=self.root);return False
        return True
    def error(self,e):messagebox.showerror('Text editor',str(e),parent=self.root);self.status.set(str(e))
    def make_names(self):
        pane=ttk.Panedwindow(self.names_tab,orient='horizontal');pane.pack(fill='both',expand=True);left=ttk.Frame(pane);right=ttk.Frame(pane,padding=12);pane.add(left,weight=2);pane.add(right,weight=3)
        self.name_filter=tk.StringVar();self.name_filter.trace_add('write',lambda *_:self.populate_names());ttk.Entry(left,textvariable=self.name_filter).pack(fill='x',pady=(0,6))
        self.name_list=ttk.Treeview(left,columns=('id','ref','name'),show='headings',selectmode='browse')
        for c,label,w in [('id','ID',55),('ref','Original reference',150),('name','Current menu name',180)]:self.name_list.heading(c,text=label);self.name_list.column(c,width=w)
        self.name_list.pack(fill='both',expand=True);self.name_list.bind('<<TreeviewSelect>>',self.select_name)
        self.name_title=ttk.Label(right,text='Select a character entry',font=('Sans',14,'bold'));self.name_title.pack(anchor='w',pady=8)
        self.name_value=tk.StringVar();ttk.Entry(right,textvariable=self.name_value,font=('Sans',18)).pack(fill='x',pady=10)
        self.name_info=ttk.Label(right,text='',wraplength=460);self.name_info.pack(anchor='w',pady=10)
        ttk.Button(right,text='Stage name',command=self.stage_name).pack(anchor='w',pady=5)
        ttk.Button(right,text='Undo selected name',command=self.undo_name).pack(anchor='w',pady=5)
        ttk.Label(right,text='ASCII letters are stored as full-width UPPERCASE. Japanese is supported. Keep names short: the game does not resize its windows.\n\nThe editor repacks the existing name pool and updates its pointers. Shared names can be changed independently.\n\nThis changes menu names only. Open Dialogue & story → CharacterNames to edit dynamic dialogue names, and search story text for literal mentions.',wraplength=460,justify='left').pack(anchor='w',pady=18)
        ttk.Button(right,text='Find dialogue-name resources',command=self.show_dialogue_names).pack(anchor='w')
        self.pool_label=ttk.Label(right,text='');self.pool_label.pack(anchor='w',pady=20)
    def populate_names(self):
        if not hasattr(self,'name_list'):return
        selected=self.name_index;self.name_list.delete(*self.name_list.get_children());query=self.name_filter.get().casefold()
        for i,label in enumerate(NAMES):
            value=self.model.name(i);mark=' *' if i in self.model.name_changes else ''
            if query in f'{i+1:03X} {label} {value}'.casefold():self.name_list.insert('', 'end',iid=str(i),values=(f'{i+1:03X}'+mark,label,value))
        if selected is not None and self.name_list.exists(str(selected)):self.name_list.selection_set(str(selected))
        self.pool_label.config(text=f'Packed name pool: {len(self.model.name_patch()[1])} / {END-POOL} bytes')
    def select_name(self,event=None):
        sel=self.name_list.selection()
        if not sel:return
        self.name_index=int(sel[0]);i=self.name_index;self.name_title.config(text=f'{i+1:03X} — {NAMES[i]}');self.name_value.set(self.model.name(i))
        aliases=[f'{j+1:03X}' for j,p in enumerate(self.model.positions) if p==self.model.positions[i] and j!=i]
        self.name_info.config(text=f'Original text address: {self.model.positions[i]:06X}\nEntries sharing this original pointer: {", ".join(aliases) or "none"}')
    def stage_name(self):
        if not self.check() or self.name_index is None:return
        try:
            value=self.model.stage_name(self.name_index,self.name_value.get());self.name_value.set(value);self.populate_names();self.status.set('Menu name staged as '+value+'. Dialogue occurrences are not automatically renamed.');self.app.status.set('Text changes staged; use Save ROM copy.')
        except Exception as e:self.error(e)
    def undo_name(self):
        if self.check() and self.name_index is not None:self.model.name_changes.pop(self.name_index,None);self.populate_names();self.select_name()
    def show_dialogue_names(self):self.tabs.select(self.story_tab);self.block_filter.set('CharacterNames/')
    def make_story(self):
        pane=ttk.Panedwindow(self.story_tab,orient='horizontal');pane.pack(fill='both',expand=True);left=ttk.Frame(pane);right=ttk.Frame(pane,padding=(12,0));pane.add(left,weight=2);pane.add(right,weight=4)
        ttk.Label(left,text='Search path, reference name or current text').pack(anchor='w')
        self.block_filter=tk.StringVar();self.block_filter.trace_add('write',lambda *_:self.populate_blocks());ttk.Entry(left,textvariable=self.block_filter).pack(fill='x',pady=6)
        self.block_list=ttk.Treeview(left,columns=('path',),show='headings',selectmode='browse');self.block_list.heading('path',text='Dialogue resource');self.block_list.column('path',width=300);self.block_list.pack(fill='both',expand=True);self.block_list.bind('<<TreeviewSelect>>',self.select_block)
        self.block_info=ttk.Label(left,text='',wraplength=330);self.block_info.pack(anchor='w',pady=8)
        ttk.Label(right,text='Scene context — commands are read-only').pack(anchor='w')
        self.context=tk.Text(right,height=12,wrap='word',font=('Sans',11));self.context.pack(fill='both',expand=True,pady=5);self.context.config(state='disabled')
        ttk.Label(right,text='Select a text passage to rewrite').pack(anchor='w')
        self.run_list=ttk.Combobox(right,state='readonly');self.run_list.pack(fill='x',pady=5);self.run_list.bind('<<ComboboxSelected>>',self.select_run)
        self.editor=tk.Text(right,height=4,wrap='word',font=('Sans',14));self.editor.pack(fill='x',pady=5)
        self.budget=ttk.Label(right,text='');self.budget.pack(anchor='w');self.editor.bind('<KeyRelease>',lambda e:self.update_budget())
        actions=ttk.Frame(right);actions.pack(fill='x',pady=8)
        ttk.Button(actions,text='Stage passage',command=self.stage_run).pack(side='left')
        ttk.Button(actions,text='UPPERCASE',command=self.uppercase).pack(side='left',padx=7)
        ttk.Button(actions,text='Undo passage',command=self.undo_run).pack(side='left')
        ttk.Label(right,text='The vanilla dialogue font has no lowercase English. Spaces use the narrow space glyph.\nEach passage must fit its original byte budget; commands, line breaks, portrait IDs and pointers stay in place.\nThis is a text view, not an in-game font/layout preview. Test line widths in an emulator.',wraplength=660).pack(anchor='w',pady=6)
    def populate_blocks(self):
        if not hasattr(self,'block_list'):return
        query=self.block_filter.get().casefold();self.block_list.delete(*self.block_list.get_children())
        count=0
        for i,b in enumerate(self.model.blocks):
            if query and query not in (b.path+' '+' '.join(self.model.run_changes.get(r.start,('',r.text))[1] for r in b.runs)).casefold():continue
            mark=' [read-only]' if b.error else (' *' if any(r.start in self.model.run_changes for r in b.runs) else '')
            self.block_list.insert('','end',iid=str(i),values=(b.path+mark,));count+=1
        self.block_info.config(text=f'{count} resources shown. Original paths identify scenes; no translation is generated.')
    def select_block(self,event=None):
        sel=self.block_list.selection()
        if not sel:return
        self.block=self.model.blocks[int(sel[0])];self.render_context()
        self.run_list['values']=[f'{i+1:03}  {r.text[:65]}' for i,r in enumerate(self.block.runs)]
        if self.block.runs:self.run_list.current(0);self.select_run()
        else:self.run=None;self.editor.delete('1.0','end')
        if self.block.error:self.status.set('Read-only resource: '+self.block.error)
    def render_context(self):
        from textcore import COMMANDS
        b=self.block;lines=[]
        events=[(r.start,'text',r) for r in b.runs]+[(c[0],'command',c) for c in b.commands]
        for _,kind,value in sorted(events):
            if kind=='text':lines.append(self.model.run_changes.get(value.start,('',value.text))[1])
            else:
                _,_,c,args=value;lines.append('['+COMMANDS.get(c,f'CMD {c:02X}')+(' '+args.hex(' ').upper() if args else '')+']')
        self.context.config(state='normal');self.context.delete('1.0','end');self.context.insert('1.0','\n'.join(lines));self.context.config(state='disabled')
        self.block_info.config(text=f'{b.path}\n{b.start:06X}–{b.end:06X}\n'+(b.error or f'{len(b.runs)} text passages; {len(b.commands)} fixed commands'))
    def select_run(self,event=None):
        idx=self.run_list.current()
        if self.block is None or idx<0:return
        self.run=self.block.runs[idx];text=self.model.run_changes.get(self.run.start,('',self.run.text))[1]
        self.editor.delete('1.0','end');self.editor.insert('1.0',text);self.update_budget()
    def value(self):return self.editor.get('1.0','end-1c')
    def update_budget(self):
        if self.run is None:return
        try:
            _,used=encode_run(self.run,self.value());self.budget.config(text=f'{used} / {len(self.run.raw)} bytes • address {self.run.start:06X}'+(' • read-only block' if self.block.error else ''),foreground='#23743b')
        except Exception as e:self.budget.config(text=str(e),foreground='#b3261e')
    def uppercase(self):
        value=self.value().upper();self.editor.delete('1.0','end');self.editor.insert('1.0',value);self.update_budget()
    def stage_run(self):
        if not self.check() or self.run is None:return
        if self.block.error:self.error('Unknown control code in this resource; edits are disabled.');return
        try:
            used=self.model.stage_run(self.run,self.value());self.render_context();self.status.set(f'Passage staged: {used}/{len(self.run.raw)} bytes. Other name occurrences are unchanged.');self.app.status.set('Text changes staged; use Save ROM copy.')
        except Exception as e:self.error(e)
    def undo_run(self):
        if self.check() and self.run:self.model.run_changes.pop(self.run.start,None);self.select_run();self.render_context()
    def export_project(self):
        if not self.check():return
        p=filedialog.asksaveasfilename(parent=self.root,defaultextension='.json',initialfile='fe4_text_edits.json',filetypes=[('Text edit project','*.json')])
        if not p:return
        obj={'format':'fe4-text-edits-v1','rom_sha256':self.rom.sha256,'names':{str(i):self.model.name(i) for i in self.model.name_changes},'passages':{f'{k:06X}':v[1] for k,v in self.model.run_changes.items()}}
        try:
            from pathlib import Path
            Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');self.status.set('Saved staged edits as a project. Use it with the same input ROM.')
        except Exception as e:self.error(e)
    def import_project(self):
        if not self.check():return
        p=filedialog.askopenfilename(parent=self.root,filetypes=[('Text edit project','*.json')])
        if not p:return
        oldn=self.model.name_changes.copy();oldr=self.model.run_changes.copy()
        try:
            from pathlib import Path
            obj=json.loads(Path(p).read_text(encoding='utf-8'))
            if obj.get('format')!='fe4-text-edits-v1' or obj.get('rom_sha256')!=self.rom.sha256:raise TextError('This project does not match the opened ROM SHA-256.')
            for k,v in obj['names'].items():
                i=int(k)
                if not 0<=i<570:raise TextError('Invalid name ID in project')
                self.model.stage_name(i,v)
            for k,v in obj['passages'].items():self.model.stage_run(self.model.runs[int(k,16)],v)
            self.populate_names();self.populate_blocks();self.status.set('Loaded staged text edits.')
        except Exception as e:self.model.name_changes=oldn;self.model.run_changes=oldr;self.error(e)
    def save_rom(self):
        if self.check():self.app.save()
    def close(self):self.root.destroy();self.app.text_window=None
