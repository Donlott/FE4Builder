from ui_common import ask_unsaved
"""Chapter dialogue text editing with visible, validated control tags."""
import base64
from pathlib import Path
import re
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from dialogue import Dialogue,catalogue,encode,readable,preview,check_profile
from portraits import png_bytes


class DialogueWindow(tk.Toplevel):
    def __init__(self,app,entry=None):
        super().__init__(app)
        self.app,self.rom=app,app.rom
        self.title('FE4Builder — Dialogue Editor');self.geometry('1220x840');self.minsize(1000,700)
        self.transient(app);self.grab_set()
        self.entries=catalogue()['entries']
        target=next((i for i,e in enumerate(self.entries) if entry and e['address']==entry['address']),None)
        if entry and target is None:target=len(self.entries);self.entries.append(entry)
        self.cache={};self.errors={}
        for i,entry in enumerate(self.entries):
            try:self.cache[i]=Dialogue(self.rom,entry).text
            except ValueError as error:self.errors[i]=str(error)
        self.current=None;self.model=None;self.loaded='';self.job=None
        top=ttk.Frame(self,padding=12);top.pack(fill='x')
        ttk.Label(top,text='Dialogue Editor',style='Title.TLabel').pack(side='left')
        ttk.Button(top,text='Save & Launch (F5)',command=self.launch).pack(side='right')
        self.save_button=ttk.Button(top,text='Write dialogue to ROM',command=self.save);self.save_button.pack(side='right',padx=8)
        ttk.Button(top,text='Redo ROM',command=lambda:self.history(True)).pack(side='right',padx=4)
        ttk.Button(top,text='Undo ROM',command=lambda:self.history(False)).pack(side='right')
        filters=ttk.Frame(self,padding=(12,0,12,10));filters.pack(fill='x')
        groups=['Prologue']+[f'Chapter {i}' for i in range(1,11)]+['Final Chapter','Intermission','Epilogues','Death Quotes','Lover Quotes','Castle Shops','Attract Mode']
        self.group=ttk.Combobox(filters,state='readonly',values=['All dialogue']+groups,width=22)
        self.group.current(1);self.group.pack(side='left');self.group.bind('<<ComboboxSelected>>',lambda _:self.populate())
        ttk.Label(filters,text='Search scene or text').pack(side='left',padx=12)
        self.search=tk.StringVar();ttk.Entry(filters,textvariable=self.search,width=44).pack(side='left',fill='x',expand=True)
        self.search.trace_add('write',lambda *_:self.populate())
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=12,pady=8)
        left=ttk.Frame(body,width=340);body.add(left,weight=1)
        self.list=tk.Listbox(left,exportselection=False,width=44)
        scroll=ttk.Scrollbar(left,command=self.list.yview);scroll.pack(side='right',fill='y')
        self.list.config(yscrollcommand=scroll.set);self.list.pack(fill='both',expand=True)
        self.list.bind('<<ListboxSelect>>',self.select)
        right=ttk.Frame(body);body.add(right,weight=3)
        self.heading=tk.StringVar();ttk.Label(right,textvariable=self.heading,font=('Segoe UI',12,'bold'),wraplength=700).pack(anchor='w')
        self.info=tk.StringVar();ttk.Label(right,textvariable=self.info,wraplength=700).pack(anchor='w',pady=6)
        bar=ttk.Frame(right);bar.pack(fill='x',pady=6)
        ttk.Button(bar,text='Import TXT…',command=self.import_text).pack(side='left')
        ttk.Button(bar,text='Export TXT…',command=self.export_text).pack(side='left',padx=6)
        ttk.Button(bar,text='Reload',command=self.reload).pack(side='left')
        self.tag=ttk.Combobox(bar,state='readonly',width=17,values=['[Wait]','[Scroll]','[Left]','[Right]','[Portrait 0001]','[PauseText 10]','[End]'])
        self.tag.current(0);self.tag.pack(side='left',padx=8)
        ttk.Button(bar,text='Insert tag',command=self.insert_tag).pack(side='left')
        ttk.Label(right,text='Enter edits as ordinary text. Enter starts a new dialogue line; keep [End] last.\n'
                  'Bracketed tags preserve portraits, timing and other commands. Arguments are hexadecimal.\n'
                  'RunASM and PrintDialogue tags are protected. Ctrl+Z in the text box undoes typing.',justify='left').pack(anchor='w',pady=6)
        area=ttk.Frame(right);area.pack(fill='both',expand=True)
        self.text=tk.Text(area,wrap='word',undo=True,font=('Consolas',11),height=12)
        scroll=ttk.Scrollbar(area,command=self.text.yview);scroll.pack(side='right',fill='y')
        self.text.config(yscrollcommand=scroll.set);self.text.pack(fill='both',expand=True)
        self.text.bind('<<Modified>>',self.modified)
        preview_bar=ttk.Frame(right);preview_bar.pack(fill='x',pady=(10,4))
        ttk.Label(preview_bar,text='Text-only font preview · page').pack(side='left')
        self.page=ttk.Combobox(preview_bar,state='readonly',width=7,values=['1']);self.page.current(0)
        self.page.pack(side='left',padx=8);self.page.bind('<<ComboboxSelected>>',lambda _:self.update_preview())
        self.preview_label=ttk.Label(right);self.preview_label.pack(anchor='w')
        ttk.Label(right,text='Preview omits portraits, positioning, alternate fonts and script effects; dynamic text is a placeholder.',wraplength=700,style='Subtitle.TLabel').pack(anchor='w',pady=4)
        self.status=tk.StringVar();ttk.Label(self,textvariable=self.status,relief='sunken',padding=6).pack(side='bottom',fill='x')
        self.bind('<F5>',lambda _:self.launch());self.protocol('WM_DELETE_WINDOW',self.close)
        self.populate()
        if target is not None:
            self.group.current(0);self.populate();self.load(target)
            if target in self.visible:self.list.selection_set(self.visible.index(target));self.list.see(self.visible.index(target))
        elif self.visible:self.list.selection_set(0);self.select()

    def contents(self):return self.text.get('1.0','end-1c')
    def pending(self):return self.model is not None and self.contents()!=self.loaded

    def populate(self):
        query=self.search.get().casefold();group=self.group.get()
        self.visible=[i for i,e in enumerate(self.entries) if (group=='All dialogue' or e['group']==group) and
                      query in (e['label']+' '+readable(self.cache.get(i,''))).casefold()]
        self.list.delete(0,'end')
        for i in self.visible:
            entry=self.entries[i]
            self.list.insert('end',f'{"! " if i in self.errors else ""}{entry["group"]} · {entry["label"]}')
        if self.current in self.visible:self.list.selection_set(self.visible.index(self.current))

    def select(self,_=None):
        selected=self.list.curselection()
        if not selected:return
        index=self.visible[selected[0]]
        if index==self.current:return
        if not self.settle():
            self.list.selection_clear(0,'end')
            if self.current in self.visible:self.list.selection_set(self.visible.index(self.current))
            return
        self.load(index)

    def load(self,index):
        self.current=index;entry=self.entries[index];self.model=None
        self.heading.set(entry['group']+' — '+entry['label'])
        self.text.config(state='normal');self.text.delete('1.0','end')
        try:
            self.model=Dialogue(self.rom,entry)
            self.cache[index]=self.model.text;self.errors.pop(index,None)
            self.loaded=self.model.text;self.text.insert('1.0',self.loaded)
            pointer=int.from_bytes(self.model.pointer,'little')
            from villages import resolve_dialogue_ref
            refs=[]
            for candidate in self.entries:
                try:refs.append(resolve_dialogue_ref(self.rom,candidate['address'])+self.rom.header)
                except ValueError:continue  # An unrelated unsupported scene must not block this one.
            shared=sum(bytes(self.rom.data[at:at+3])==self.model.pointer for at in refs)
            self.info.set(f'Scene pointer PC {self.model.ref-self.rom.header:06X} → SNES {pointer:06X}. {shared} catalogued reference(s) share this start; saving isolates this entry.')
        except ValueError as error:
            self.model=None;self.loaded='';self.info.set(str(error));self.text.config(state='disabled')
        self.text.edit_reset();self.text.edit_modified(False);self.page.current(0)
        self.update_preview()

    def modified(self,_=None):
        if not self.text.edit_modified():return
        self.text.edit_modified(False)
        if self.job is not None:self.after_cancel(self.job)
        self.job=self.after(300,self.update_preview)

    def update_preview(self):
        if self.job is not None:self.after_cancel(self.job);self.job=None
        if self.model is None:
            self.save_button.config(state='disabled');self.preview_label.config(image='');return
        text=self.contents()
        try:
            payload=encode(text)
            rows,pages,overflow=preview(self.rom,text,max(0,self.page.current()))
            selected=max(0,min(self.page.current(),pages-1));self.page.config(values=[str(i+1) for i in range(pages)]);self.page.current(selected)
            self.photo=tk.PhotoImage(master=self,data=base64.b64encode(png_bytes(rows,[(24,32,44),(170,162,145),(88,80,66),(248,240,216)]))).zoom(2)
            self.preview_label.config(image=self.photo)
            self.status.set(f'{len(payload)} bytes · {pages} preview page(s) · {overflow} line(s) over 240 pixels. '+('Unsaved changes.' if self.pending() else 'Loaded.')+' Preview pages are not automatic in-game page breaks.')
            self.save_button.config(state='normal')
        except ValueError as error:self.status.set(str(error));self.save_button.config(state='disabled')

    def insert_tag(self):
        if self.model:self.text.insert('insert',self.tag.get());self.text.focus_set()

    def save(self):
        if self.app.rom is not self.rom:
            messagebox.showerror('ROM changed','Reopen the dialogue editor for the current ROM.',parent=self);return False
        if self.model is None:return False
        before=bytes(self.rom.data)
        try:
            details=self.model.write(self.contents())
            self.rom.save_original(f'Dialogue: {self.model.entry["group"]} / {self.model.entry["label"]}',details)
        except (ValueError,OSError) as error:
            self.rom.data[:]=before;messagebox.showerror('Cannot save dialogue',str(error),parent=self);return False
        self.app.refresh_after_history();self.cache[self.current]=self.contents();self.load(self.current)
        self.status.set('Dialogue saved. Automatic backup and undo history updated. Reload the ROM in your emulator to test.')
        return True

    def settle(self):
        if not self.pending():return True
        answer=ask_unsaved(self,'Write this scene to the opened ROM?')
        if answer is None:return False
        return self.save() if answer else True

    def reload(self):
        if self.current is not None and (not self.pending() or messagebox.askyesno('Reload dialogue','Discard the unwritten dialogue edits?',parent=self)):self.load(self.current)

    def import_text(self):
        if self.model is None:return
        path=filedialog.askopenfilename(parent=self,filetypes=[('Dialogue text','*.txt'),('All files','*')])
        if not path:return
        try:
            text=Path(path).read_text(encoding='utf-8-sig');encode(text)
        except (ValueError,OSError) as error:messagebox.showerror('Cannot import dialogue',str(error),parent=self);return
        self.text.delete('1.0','end');self.text.insert('1.0',text);self.update_preview()

    def export_text(self):
        if self.model is None:return
        name=re.sub(r'[^\w -]','_',self.model.entry['label'])[:100]+'.txt'
        path=filedialog.asksaveasfilename(parent=self,initialfile=name,defaultextension='.txt',filetypes=[('Dialogue text','*.txt')])
        if path:
            try:Path(path).write_text(self.contents(),encoding='utf-8')
            except OSError as error:messagebox.showerror('Cannot export dialogue',str(error),parent=self)

    def history(self,redo):
        if self.app.rom is not self.rom or not self.settle():return
        self.app.history_step(redo)
        self.errors={}
        for i,entry in enumerate(self.entries):
            try:self.cache[i]=Dialogue(self.rom,entry).text
            except ValueError as error:self.cache.pop(i,None);self.errors[i]=str(error)
        self.populate()
        if self.current is not None:self.load(self.current)

    def launch(self):return self.app.save_and_launch(save_callback=self.save,parent=self)

    def close(self):
        if self.settle():
            if self.job is not None:self.after_cancel(self.job)
            self.destroy()


def open_dialogue_window(app):
    if not app.rom:
        messagebox.showinfo('Dialogue Editor','Open a ROM first.',parent=app);return
    if not app.settle():return
    try:check_profile(app.rom)
    except ValueError as error:
        messagebox.showerror('Unsupported dialogue layout',str(error),parent=app);return
    return DialogueWindow(app)
