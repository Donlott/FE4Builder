"""Native Tk interface for ROM-backed Project Naga text and name bitmaps."""
import tkinter as tk
from tkinter import ttk,messagebox,filedialog
from pathlib import Path
import json
from PIL import Image,ImageTk
from nagacore import NagaModel,encode_run,bitmap,TextError
from textcore import COMMANDS

class NagaWindow:
    def __init__(self,parent):
        self.app=parent;self.rom=parent.rom
        if self.rom.text is None:self.rom.text=NagaModel(self.rom)
        self.model=self.rom.text;self.block=None;self.run=None;self.name_index=None;self.menu_index=None;self.photo=None
        self.root=tk.Toplevel(parent.root);self.root.title('FE4 Text Editor • Project Naga');self.root.geometry('1180x850');self.root.minsize(940,680)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        ttk.Label(self.root,text='Project Naga — text from the opened ROM',font=('Sans',17,'bold'),padding=12).pack(anchor='w')
        ttk.Label(self.root,text='Story locations follow live ROM pointers. Reference labels identify resources; they are not the displayed text.',padding=(12,0)).pack(anchor='w')
        self.tabs=ttk.Notebook(self.root);self.tabs.pack(fill='both',expand=True,padx=12,pady=10)
        self.story_tab=ttk.Frame(self.tabs,padding=10);self.names_tab=ttk.Frame(self.tabs,padding=10);self.menu_tab=ttk.Frame(self.tabs,padding=10)
        self.tabs.add(self.story_tab,text='English dialogue & story');self.tabs.add(self.names_tab,text='Castle dialogue names');self.tabs.add(self.menu_tab,text='Menu name graphics')
        self.status=tk.StringVar(value=f'{len(self.model.blocks)} ROM resources. Changes remain staged until Save ROM copy.')
        ttk.Label(self.root,textvariable=self.status,padding=10,wraplength=1100).pack(fill='x')
        bar=ttk.Frame(self.root,padding=(12,0,12,10));bar.pack(fill='x')
        ttk.Button(bar,text='Save edit project…',command=self.export_project).pack(side='left')
        ttk.Button(bar,text='Load edit project…',command=self.import_project).pack(side='left',padx=8)
        ttk.Button(bar,text='Save ROM copy…',command=self.save_rom).pack(side='right')
        self.make_story();self.make_names();self.make_menu();self.populate_blocks();self.populate_names();self.populate_menu()

    def check(self):
        if self.app.busy:messagebox.showinfo('Please wait','A save/load operation is running.',parent=self.root);return False
        if self.rom is not self.app.rom:self.error('Close this window and reopen it for the newly loaded ROM.');return False
        return True
    def error(self,e):messagebox.showerror('Project Naga text',str(e),parent=self.root);self.status.set(str(e))
    def changed(self,message):self.status.set(message);self.app.status.set('Text changes staged; use Save ROM copy.')
    def split(self,tab):
        pane=ttk.Panedwindow(tab,orient='horizontal');pane.pack(fill='both',expand=True)
        left=ttk.Frame(pane);right=ttk.Frame(pane,padding=(14,0));pane.add(left,weight=2);pane.add(right,weight=3)
        return left,right
    def tree(self,frame,columns):
        box=ttk.Frame(frame);box.pack(fill='both',expand=True)
        tree=ttk.Treeview(box,columns=[c[0] for c in columns],show='headings',selectmode='browse')
        for c,label,w in columns:tree.heading(c,text=label);tree.column(c,width=w)
        scroll=ttk.Scrollbar(box,orient='vertical',command=tree.yview);tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');tree.pack(fill='both',expand=True)
        return tree
    def make_story(self):
        left,right=self.split(self.story_tab)
        ttk.Label(left,text='Search English text or reference label').pack(anchor='w')
        self.filter=tk.StringVar();self.filter.trace_add('write',lambda *_:self.populate_blocks());ttk.Entry(left,textvariable=self.filter).pack(fill='x',pady=6)
        self.block_list=self.tree(left,[('label','Reference label',240),('address','ROM address',85)])
        self.block_list.bind('<<TreeviewSelect>>',self.select_block)
        self.info=ttk.Label(left,wraplength=350);self.info.pack(anchor='w',pady=8)
        ttk.Label(right,text='Actual ROM text and control commands').pack(anchor='w')
        self.context=tk.Text(right,height=15,wrap='word',font=('Sans',11));self.context.pack(fill='both',expand=True,pady=6);self.context.config(state='disabled')
        self.run_list=ttk.Combobox(right,state='readonly');self.run_list.pack(fill='x',pady=6);self.run_list.bind('<<ComboboxSelected>>',self.select_run)
        self.editor=tk.Text(right,height=4,wrap='word',font=('Sans',14));self.editor.pack(fill='x');self.editor.bind('<KeyRelease>',lambda _:self.budget())
        self.budget_label=ttk.Label(right,wraplength=650);self.budget_label.pack(anchor='w',pady=5)
        buttons=ttk.Frame(right);buttons.pack(fill='x')
        ttk.Button(buttons,text='Stage passage',command=self.stage_run).pack(side='left');ttk.Button(buttons,text='Undo passage',command=self.undo_run).pack(side='left',padx=8)
        ttk.Label(right,text='Uppercase and lowercase English are supported. Passages must fit their existing byte space. Line breaks and event commands remain fixed. Literal name mentions must be edited separately.',wraplength=650).pack(anchor='w',pady=10)
    def populate_blocks(self):
        if not hasattr(self,'block_list'):return
        q=self.filter.get().casefold();self.block_list.delete(*self.block_list.get_children())
        for i,b in enumerate(self.model.blocks):
            text=' '.join(self.model.run_changes.get(r.start,('',r.text))[1] for r in b.runs)
            if q and q not in (b.label+' '+b.path+' '+text).casefold():continue
            mark=' [read-only]' if b.error else ' *' if any(r.start in self.model.run_changes for r in b.runs) else ''
            self.block_list.insert('','end',iid=str(i),values=(b.label+mark,f'{b.start:06X}'))
    def select_block(self,event=None):
        sel=self.block_list.selection()
        if not sel:return
        self.block=self.model.blocks[int(sel[0])];self.render_context()
        self.run_list['values']=[f'{i+1:03}  {r.text[:70]}' for i,r in enumerate(self.block.runs)]
        if self.block.runs:self.run_list.current(0);self.select_run()
        else:self.run=None;self.editor.delete('1.0','end');self.budget_label.config(text=self.block.error or 'No literal text passages')
    def render_context(self):
        b=self.block;events=[(r.start,'text',r) for r in b.runs]+[(c[0],'cmd',c) for c in b.commands];lines=[]
        for _,kind,v in sorted(events):
            if kind=='text':lines.append(self.model.run_changes.get(v.start,('',v.text))[1])
            else:
                _,_,c,arg=v;lines.append('['+COMMANDS.get(c,f'CMD {c:02X}')+(' '+arg.hex(' ').upper() if arg else '')+']')
        self.context.config(state='normal');self.context.delete('1.0','end');self.context.insert('1.0','\n'.join(lines));self.context.config(state='disabled')
        refs=self.model.references.get(b.start,[])
        self.info.config(text=f'{b.path}\nROM {b.start:06X}–{b.end:06X}\nPointer locations: '+(', '.join(f'{a:06X}' for a in refs[:8]) or 'fixed translated slot')+('\n'+b.error if b.error else ''))
    def select_run(self,event=None):
        i=self.run_list.current()
        if self.block is None or i<0:return
        self.run=self.block.runs[i];self.editor.delete('1.0','end');self.editor.insert('1.0',self.model.run_changes.get(self.run.start,('',self.run.text))[1]);self.budget()
    def value(self):return self.editor.get('1.0','end-1c')
    def budget(self):
        if self.run is None:return
        try:
            _,n=encode_run(self.run,self.value());self.budget_label.config(text=f'{n} / {len(self.run.raw)} bytes at ROM {self.run.start:06X}',foreground='#23743b')
        except Exception as e:self.budget_label.config(text=str(e),foreground='#b3261e')
    def stage_run(self):
        if not self.check() or self.run is None:return
        try:
            if self.block.error:raise TextError(self.block.error)
            self.model.stage_run(self.run,self.value());self.render_context();self.changed('English dialogue passage staged.');self.populate_blocks()
        except Exception as e:self.error(e)
    def undo_run(self):
        if self.check() and self.run:self.model.run_changes.pop(self.run.start,None);self.select_run();self.render_context();self.populate_blocks()
    def make_names(self):
        left,right=self.split(self.names_tab)
        self.name_list=self.tree(left,[('id','ID',60),('current','Current ROM dialogue name',220)])
        self.name_list.bind('<<TreeviewSelect>>',self.select_name)
        self.name_title=ttk.Label(right,text='Select a name',font=('Sans',15,'bold'));self.name_title.pack(anchor='w',pady=10)
        self.name_value=tk.StringVar();ttk.Entry(right,textvariable=self.name_value,font=('Sans',17)).pack(fill='x',pady=10)
        ttk.Button(right,text='Stage castle dialogue name',command=self.stage_name).pack(anchor='w',pady=5)
        ttk.Button(right,text='Undo name',command=self.undo_name).pack(anchor='w',pady=5)
        ttk.Label(right,text='These are the 63 translated character-name slots used in castle dialogue. They are read from the ROM and accept up to 14 encoded glyphs.\n\nMenu nameplates are separate images: use Menu name graphics. Names written literally inside story dialogue are separate passages; use the English search to find them. This button does not perform a global rename.',wraplength=600,justify='left').pack(anchor='w',pady=20)
    def populate_names(self):
        self.name_list.delete(*self.name_list.get_children())
        for i in range(len(self.model.names)):
            self.name_list.insert('','end',iid=str(i),values=(f'{i+1:03X}'+(' *' if i in self.model.name_changes else ''),self.model.name(i)))
    def select_name(self,event=None):
        sel=self.name_list.selection()
        if sel:self.name_index=int(sel[0]);self.name_value.set(self.model.name(self.name_index));self.name_title.config(text=f'Castle name {self.name_index+1:03X} • ROM {self.model.names[self.name_index].start:06X}')
    def stage_name(self):
        if not self.check() or self.name_index is None:return
        try:self.model.stage_name(self.name_index,self.name_value.get());self.populate_names();self.changed('Castle dialogue name staged. Menu images and literal story mentions are separate.')
        except Exception as e:self.error(e)
    def undo_name(self):
        if self.check() and self.name_index is not None:self.model.name_changes.pop(self.name_index,None);self.populate_names();self.name_value.set(self.model.name(self.name_index))
    def make_menu(self):
        left,right=self.split(self.menu_tab)
        ttk.Label(left,text='Search original reference label or ID').pack(anchor='w')
        self.menu_filter=tk.StringVar();self.menu_filter.trace_add('write',lambda *_:self.populate_menu());ttk.Entry(left,textvariable=self.menu_filter).pack(fill='x',pady=6)
        self.menu_list=self.tree(left,[('id','ID',60),('ref','Original Naga reference (not OCR)',240)]);self.menu_list.bind('<<TreeviewSelect>>',self.select_menu)
        self.menu_info=ttk.Label(right,text='Select a bitmap',wraplength=600);self.menu_info.pack(anchor='w',pady=10)
        self.preview=ttk.Label(right);self.preview.pack(anchor='w',pady=20)
        self.menu_value=tk.StringVar();ttk.Entry(right,textvariable=self.menu_value,font=('Sans',16)).pack(fill='x',pady=6)
        ttk.Button(right,text='Render and stage this nameplate',command=self.render_menu).pack(anchor='w',pady=5)
        buttons=ttk.Frame(right);buttons.pack(fill='x',pady=12)
        ttk.Button(buttons,text='Export indexed PNG…',command=self.export_png).pack(side='left')
        ttk.Button(buttons,text='Import indexed PNG…',command=self.import_png).pack(side='left',padx=8)
        ttk.Button(right,text='Undo bitmap',command=self.undo_menu).pack(anchor='w')
        ttk.Label(right,text='The preview is decoded from actual ROM graphics. The reference label is only an identifier and may differ from a modified image.\n\nTyping uses the ROM’s English font and must fit the existing image width. Shared bitmap storage is protected. Both pixel-alignment variants are updated.\n\nThis edits the primary menu/nameplate image only. Project Naga also has separate pre-rendered name copies in other menu screens and Valkyrie text; those copies are not updated by this button. Castle dialogue names and literal story mentions are also separate.',wraplength=600,justify='left').pack(anchor='w',pady=20)
    def populate_menu(self):
        if not hasattr(self,'menu_list'):return
        self.menu_list.delete(*self.menu_list.get_children());q=self.menu_filter.get().casefold()
        for i,e in enumerate(self.model.menu):
            if q not in f'{i+1:03X} {e["label"]}'.casefold():continue
            self.menu_list.insert('','end',iid=str(i),values=(f'{i+1:03X}'+(' *' if i in self.model.image_changes else ''),e['label']))
    def select_menu(self,event=None):
        sel=self.menu_list.selection()
        if not sel:return
        self.menu_index=int(sel[0]);self.menu_value.set('');self.refresh_menu()
    def refresh_menu(self):
        if self.menu_index is None:return
        try:
            e=self.model.menu[self.menu_index];im=self.model.menu_image(self.menu_index)
            self.photo=ImageTk.PhotoImage(im.resize((im.width*6,96),getattr(Image,'Resampling',Image).NEAREST));self.preview.config(image=self.photo)
            self.menu_info.config(text=f'Primary menu nameplate {self.menu_index+1:03X} • ROM {e["pointer"]:06X}\n{im.width} × 16 pixels; last column reserved for alignment')
        except Exception as e:self.error(e)
    def render_menu(self):
        if not self.check() or self.menu_index is None:return
        try:
            self.model.stage_image(self.menu_index,self.model.render_name(self.menu_index,self.menu_value.get()));self.refresh_menu();self.changed('Primary menu nameplate staged. Other menu copies are not changed.')
        except Exception as e:self.error(e)
    def export_png(self):
        if not self.check() or self.menu_index is None:return
        p=filedialog.asksaveasfilename(parent=self.root,defaultextension='.png',initialfile=f'naga_name_{self.menu_index+1:03X}.png')
        if p:
            try:self.model.menu_image(self.menu_index).save(p)
            except Exception as e:self.error(e)
    def import_png(self):
        if not self.check() or self.menu_index is None:return
        p=filedialog.askopenfilename(parent=self.root,filetypes=[('PNG','*.png')])
        if p:
            try:
                with Image.open(p) as im:self.model.stage_image(self.menu_index,im.copy())
                self.refresh_menu();self.changed('Primary name bitmap imported and staged.')
            except Exception as e:self.error(e)
    def undo_menu(self):
        if self.check() and self.menu_index is not None:self.model.image_changes.pop(self.menu_index,None);self.refresh_menu()
    def export_project(self):
        if not self.check():return
        p=filedialog.asksaveasfilename(parent=self.root,defaultextension='.json',initialfile='fe4_naga_text_edits.json')
        if not p:return
        obj=self.model.export()
        try:Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');self.status.set('Edit project saved; save a ROM copy to apply it in-game.')
        except Exception as e:self.error(e)
    def import_project(self):
        if not self.check():return
        p=filedialog.askopenfilename(parent=self.root,filetypes=[('JSON','*.json')])
        if not p:return
        old=(self.model.name_changes.copy(),self.model.run_changes.copy(),self.model.image_changes.copy())
        try:
            obj=json.loads(Path(p).read_text(encoding='utf-8'))
            self.model.import_project(obj)
            self.populate_names();self.populate_blocks();self.populate_menu();self.changed('Project Naga edits loaded.')
        except Exception as e:
            self.model.name_changes,self.model.run_changes,self.model.image_changes=old;self.error(e)
    def save_rom(self):
        if self.check():self.app.save()
    def close(self):self.root.destroy();self.app.text_window=None
