from ui_common import ask_unsaved
"""Intro/title resource editing with staged imports, backups and emulator testing."""
import base64
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
from intro_graphics import IntroAsset,assets

class IntroWindow(tk.Toplevel):
    def __init__(self,app):
        super().__init__(app);self.app=app;self.rom=app.rom
        self.title('FE4Builder - Intro & Title Editor');self.geometry('1150x790');self.minsize(950,650)
        self.transient(app);self.grab_set();self.entries=assets();self.current=None
        top=ttk.Frame(self,padding=10);top.pack(fill='x')
        ttk.Label(top,text='Intro & Title Editor',style='Title.TLabel').pack(side='left')
        ttk.Button(top,text='Save & Launch (F5)',command=self.launch).pack(side='right')
        self.write_button=ttk.Button(top,text='Write to ROM',command=self.save,state='disabled');self.write_button.pack(side='right',padx=8)
        ttk.Button(top,text='Undo',command=lambda:self.history(False)).pack(side='right',padx=4)
        ttk.Button(top,text='Redo',command=lambda:self.history(True)).pack(side='right',padx=4)
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=10,pady=8)
        left=ttk.Frame(body,width=330);body.add(left,weight=0)
        self.list=tk.Listbox(left,exportselection=False,width=42)
        scrollbar=ttk.Scrollbar(left,command=self.list.yview);scrollbar.pack(side='right',fill='y');self.list.configure(yscrollcommand=scrollbar.set);self.list.pack(fill='both',expand=True)
        for entry in self.entries:self.list.insert('end',entry['name'])
        self.list.bind('<<ListboxSelect>>',self.select)
        right=ttk.Frame(body);body.add(right,weight=1)
        layout_row=ttk.Frame(right);layout_row.pack(fill='x',pady=(0,6))
        ttk.Label(layout_row,text='Logo layout').pack(side='left')
        self.layout=ttk.Combobox(layout_row,state='disabled',values=['Readable layout','Raw tiles'],width=18);self.layout.current(0);self.layout.pack(side='left',padx=6)
        self.layout.bind('<<ComboboxSelected>>',lambda e:self.display())
        actions=ttk.Frame(right);actions.pack(fill='x',pady=(0,8))
        ttk.Button(actions,text='Export PNG...',command=self.export).pack(side='left')
        ttk.Button(actions,text='Import PNG...',command=self.import_image).pack(side='left',padx=8)
        ttk.Label(actions,text='Sheet palette').pack(side='left')
        self.palette=ttk.Combobox(actions,state='disabled',values=[f'{i:02}' for i in range(16)],width=5);self.palette.current(0);self.palette.pack(side='left',padx=6)
        self.palette.bind('<<ComboboxSelected>>',lambda e:self.display())
        self.zoom=ttk.Combobox(actions,state='readonly',values=['100%','200%','300%'],width=7);self.zoom.current(1);self.zoom.pack(side='right');self.zoom.bind('<<ComboboxSelected>>',lambda e:self.display())
        self.text_frame=ttk.Frame(right)
        ttk.Label(self.text_frame,text='Replacement caption').pack(anchor='w')
        row=ttk.Frame(self.text_frame);row.pack(fill='x',pady=4)
        self.text=tk.StringVar();ttk.Entry(row,textvariable=self.text).pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='Preview text',command=self.caption_text).pack(side='right',padx=6)
        area=ttk.Frame(right);area.pack(fill='both',expand=True);area.rowconfigure(0,weight=1);area.columnconfigure(0,weight=1)
        self.area=area
        self.canvas=tk.Canvas(area,bg='#182331',highlightthickness=0);self.canvas.grid(row=0,column=0,sticky='nsew')
        xs=ttk.Scrollbar(area,orient='horizontal',command=self.canvas.xview);xs.grid(row=1,column=0,sticky='ew')
        ys=ttk.Scrollbar(area,command=self.canvas.yview);ys.grid(row=0,column=1,sticky='ns');self.canvas.configure(xscrollcommand=xs.set,yscrollcommand=ys.set)
        from ui_common import bind_canvas_wheel
        bind_canvas_wheel(self.canvas)
        self.info=tk.StringVar();ttk.Label(right,textvariable=self.info,wraplength=730,justify='left').pack(anchor='w',pady=8)
        ttk.Label(self,text='Edit exported sheets without moving tile positions. Scene previews show individual layers; logos, clouds and effects have separate resources. Scene order and timing remain unchanged.',padding=10,wraplength=1050).pack(fill='x')
        self.status=tk.StringVar();ttk.Label(self,textvariable=self.status,padding=6,relief='sunken').pack(fill='x')
        self.protocol('WM_DELETE_WINDOW',self.close);self.bind('<F5>',lambda e:self.launch())
        self.list.selection_set(0);self.select()

    def select(self,_=None):
        selected=self.list.curselection()
        if not selected:return
        index=selected[0]
        if self.current==index:return
        if not self.settle():
            self.list.selection_clear(0,'end');self.list.selection_set(self.current);return
        try:model=IntroAsset(self.rom,self.entries[index])
        except ValueError as error:
            messagebox.showerror('Scene unavailable',str(error),parent=self)
            self.list.selection_clear(0,'end')
            if self.current is not None:self.list.selection_set(self.current)
            return
        self.current=index;self.model=model;entry=self.entries[index]
        from logo_layout import KEYS
        self.layout.configure(state='readonly' if model.key in KEYS else 'disabled');self.layout.current(0)
        self.palette.configure(state='readonly' if entry['view']=='sheet' and entry['palette']=='title' else 'disabled');self.palette.current(entry.get('default_palette',0))
        self.text_frame.pack_forget();self.text.set('')
        if entry['kind']=='caption':self.text_frame.pack(fill='x',pady=4,before=self.area)
        self.display()

    def display(self):
        readable=self.layout.current()==0
        self.palette.configure(state='disabled' if readable and self.model.key in ('title_english','title_logo') else 'readonly' if self.model.entry['view']=='sheet' and self.model.entry['palette']=='title' else 'disabled')
        scale=(self.zoom.current()+1)*(16 if self.model.entry['view']=='palette' else 1)
        self.photo=tk.PhotoImage(master=self,data=base64.b64encode(self.model.png(self.palette.current(),readable))).zoom(scale)
        self.canvas.delete('all');self.canvas.create_image(0,0,image=self.photo,anchor='nw');self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        rows,_=self.model.rows(self.palette.current(),readable);e=self.model.entry
        description=f'{e["name"]} | PNG {len(rows[0])} x {len(rows)} | {len(self.model.raw)} decoded bytes'
        if e['palette']=='gray' and e['kind']!='caption':description+='\nIndex-color preview: the game retains its scene palette. Use an exported indexed PNG to change the artwork.'
        if e['view']=='screen':description+='\nImports rebuild this layer within its existing tile budget and palette layout.'
        if readable and self.model.key in ('title_english','title_logo'):
            description+='\nAssembled in game positions. Export/import restores native tile order; hidden and unused data is preserved. Raw tiles includes auxiliary graphics.'
            if self.model.key=='title_logo':description+='\nComplete sword/banner in one captured frame of its animation; game animation and sprite positions remain unchanged.'
            description+='\nEditing one shared tile updates its other copies. Painting outside the native artwork area is not supported.'
        elif e['view']=='sheet':description+='\nKeep sheet dimensions and tile positions; palette selection changes the preview only.'
        if e['view']=='palette':description+='\nOne pixel per palette entry. Changes affect every layer using this palette.'
        if e['kind']=='caption':description+='\nCaption text is converted to graphics using the ROM font; maximum line width is 248 pixels.'
        self.info.set(description);self.write_button.configure(state='normal' if self.model.dirty else 'disabled')
        self.status.set('Imported edits are staged until Write to ROM.' if self.model.dirty else 'Ready. Backups and undo cover graphics, maps and changed pointers.')

    def caption_text(self):
        try:self.model.text(self.text.get())
        except ValueError as error:messagebox.showerror('Caption',str(error),parent=self);return
        self.display()

    def export(self):
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.png',filetypes=[('PNG image','*.png')],initialfile=self.model.key+'.png')
        if path:
            try:Path(path).write_bytes(self.model.png(self.palette.current(),self.layout.current()==0))
            except OSError as error:messagebox.showerror('Export PNG',str(error),parent=self)

    def import_image(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('PNG image','*.png')])
        if not path:return
        before_raw,before_map=self.model.raw,self.model.map
        try:self.model.import_png(self,path,self.palette.current(),self.layout.current()==0)
        except (ValueError,OSError,tk.TclError) as error:
            self.model.raw,self.model.map=before_raw,before_map
            messagebox.showerror('Cannot import image',str(error),parent=self);return
        self.display()

    def save(self):
        if self.app.rom is not self.rom:
            messagebox.showerror('ROM changed','Reopen this editor for the current ROM.',parent=self);return False
        before=bytes(self.rom.data)
        try:
            details=self.model.apply();self.rom.save_original('Intro/title: '+self.model.entry['name'],details)
        except (ValueError,OSError) as error:
            self.rom.data[:]=before;messagebox.showerror('Cannot write scene',str(error),parent=self);return False
        self.model=IntroAsset(self.rom,self.entries[self.current]);self.app.refresh_after_history();self.display()
        self.status.set('Saved with backup and undo history. Test the opening with Save & Launch.')
        return True

    def launch(self):return self.app.save_and_launch(save_callback=self.save,parent=self)

    def settle(self):
        if not hasattr(self,'model') or not self.model.dirty:return True
        answer=ask_unsaved(self,'Save the imported scene changes to the ROM?')
        if answer is None:return False
        if answer:return self.save()
        return True

    def history(self,redo):
        if not self.settle():return
        self.app.history_step(redo)
        self.model=IntroAsset(self.rom,self.entries[self.current]);self.display()

    def close(self):
        if self.settle():self.destroy()

def open_intro_window(app):
    if not app.rom:messagebox.showinfo('Open a ROM','Open the supported FE4 ROM first.');return
    if not app.settle():return
    try:IntroAsset(app.rom,assets()[0])
    except ValueError as error:messagebox.showerror('Intro/title editor',str(error));return
    return IntroWindow(app)
