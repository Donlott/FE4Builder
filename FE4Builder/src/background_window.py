"""Assembled dialogue background previews and staged PNG replacement."""
import base64,tkinter as tk
from pathlib import Path
from tkinter import ttk,filedialog,messagebox
from backgrounds import Background
from event_commands import BACKGROUNDS
from ui_common import ask_unsaved,bind_canvas_wheel

class BackgroundWindow(tk.Toplevel):
    def __init__(self,app,index=0):
        super().__init__(app);self.app=app;self.rom=app.rom;self.current=None;self.model=None
        self.title('FE4Builder — Background Editor');self.geometry('1050x650');self.minsize(800,540);self.transient(app);self.grab_set()
        top=ttk.Frame(self,padding=12);top.pack(fill='x');ttk.Label(top,text='Background Editor',style='Title.TLabel').pack(side='left')
        ttk.Button(top,text='Write to ROM',command=self.save).pack(side='right');ttk.Button(top,text='Save & Launch (F5)',command=self.launch).pack(side='right',padx=8)
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=12,pady=8)
        left=ttk.Frame(body);body.add(left,weight=1)
        self.list=tk.Listbox(left,exportselection=False,width=22)
        for key,name in BACKGROUNDS.items():self.list.insert('end',f'{key} · {name}')
        self.list.pack(fill='both',expand=True);self.list.bind('<<ListboxSelect>>',self.select)
        right=ttk.Frame(body);body.add(right,weight=4)
        self.heading=tk.StringVar();ttk.Label(right,textvariable=self.heading,font=('Segoe UI',12,'bold')).pack(anchor='w')
        bar=ttk.Frame(right);bar.pack(fill='x',pady=10)
        ttk.Button(bar,text='Export PNG…',command=self.export).pack(side='left');ttk.Button(bar,text='Import PNG…',command=self.import_image).pack(side='left',padx=8)
        ttk.Label(bar,text='Zoom').pack(side='left');self.zoom=ttk.Combobox(bar,state='readonly',values=['1×','2×','3×'],width=5);self.zoom.current(1);self.zoom.pack(side='left',padx=8);self.zoom.bind('<<ComboboxSelected>>',lambda _:self.display())
        area=ttk.Frame(right);area.pack(fill='both',expand=True);area.columnconfigure(0,weight=1);area.rowconfigure(0,weight=1)
        self.canvas=tk.Canvas(area,background='#20242a',highlightthickness=0);self.canvas.grid(row=0,column=0,sticky='nsew');bind_canvas_wheel(self.canvas)
        x=ttk.Scrollbar(area,orient='horizontal',command=self.canvas.xview);x.grid(row=1,column=0,sticky='ew');y=ttk.Scrollbar(area,command=self.canvas.yview);y.grid(row=0,column=1,sticky='ns');self.canvas.config(xscrollcommand=x.set,yscrollcommand=y.set)
        self.info=tk.StringVar();ttk.Label(right,textvariable=self.info,wraplength=700,justify='left').pack(anchor='w',pady=8)
        ttk.Label(right,text='Import an opaque 256 × 88 PNG. Colors are matched to the existing 16-color palette for each tile; export first as a template.\nArtwork is shared by every scene selecting this background ID. Portraits, text boxes, animation code and palettes are preserved.',wraplength=700,justify='left').pack(anchor='w')
        actions=ttk.Frame(self,padding=10);actions.pack(fill='x');ttk.Button(actions,text='Reload background',command=self.reload).pack(side='left');ttk.Button(actions,text='Undo ROM',command=lambda:self.history(False)).pack(side='left',padx=8);ttk.Button(actions,text='Redo ROM',command=lambda:self.history(True)).pack(side='left')
        self.status=tk.StringVar();ttk.Label(self,textvariable=self.status,padding=8,wraplength=1000,relief='sunken').pack(fill='x')
        self.list.selection_set(index);self.select();self.protocol('WM_DELETE_WINDOW',self.close);self.bind('<Control-s>',lambda _:self.save());self.bind('<F5>',lambda _:self.launch())
    def pending(self):return self.model is not None and self.model.dirty
    def settle(self):
        if not self.pending():return True
        answer=ask_unsaved(self,'Write this imported background to the opened ROM?')
        return False if answer is None else self.save() if answer else True
    def select(self,_=None):
        selection=self.list.curselection()
        if not selection:return
        index=selection[0]
        if index==self.current:return
        if not self.settle():
            self.list.selection_clear(0,'end')
            if self.current is not None:self.list.selection_set(self.current)
            return
        try:self.model=Background(self.rom,index)
        except ValueError as error:
            messagebox.showerror('Background unavailable',str(error),parent=self);return
        self.current=index;self.display();self.status.set('Loaded from ROM. Imports remain pending until Write to ROM.')
    def display(self):
        if self.model is None:return
        self.heading.set(self.model.name+(' *' if self.pending() else ''))
        image=tk.PhotoImage(master=self,data=base64.b64encode(self.model.png()).decode());self.image=image.zoom(self.zoom.current()+1)
        self.canvas.delete('all');self.canvas.create_image(8,8,anchor='nw',image=self.image);self.canvas.config(scrollregion=self.canvas.bbox('all'))
        self.info.set(f'256 × 88 artwork · {self.model.entry["tile_capacity"]} tile capacity · Background ID {self.current}. Fixed-size ROM storage; no ROM expansion.')
    def export(self):
        if self.model is None:return
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.png',filetypes=[('PNG image','*.png')],initialfile=self.model.name.lower()+'.png')
        if path:
            try:Path(path).write_bytes(self.model.png())
            except OSError as error:messagebox.showerror('Cannot export background',str(error),parent=self)
    def import_image(self):
        if self.model is None:return
        path=filedialog.askopenfilename(parent=self,filetypes=[('PNG image','*.png')])
        if not path:return
        try:self.model.import_png(self,path)
        except (ValueError,OSError,tk.TclError) as error:messagebox.showerror('Cannot import background',str(error),parent=self);return
        self.display();self.status.set('Import staged. Review the palette-matched preview before writing.')
    def save(self):
        if self.model is None:return False
        if self.app.rom is not self.rom:messagebox.showerror('ROM changed','Reopen Background Editor for the current ROM.',parent=self);return False
        if not self.pending():self.status.set('No pending background changes.');return True
        before=bytes(self.rom.data)
        try:
            details=self.model.apply();self.rom.save_original('Background: '+self.model.name,details)
        except (ValueError,OSError) as error:
            self.rom.data[:]=before;messagebox.showerror('Cannot save background',str(error),parent=self);return False
        self.model=Background(self.rom,self.current);self.app.refresh_after_history();self.display();self.status.set('Saved to the original ROM with backup and undo history.');return True
    def reload(self):
        if self.pending() and not messagebox.askyesno('Reload background','Discard the imported image?',parent=self):return
        self.model=Background(self.rom,self.current);self.display()
    def history(self,redo):
        if not self.settle():return
        try:self.rom.redo() if redo else self.rom.undo()
        except (ValueError,OSError) as error:messagebox.showerror('History unavailable',str(error),parent=self);return
        self.app.refresh_after_history();self.model=Background(self.rom,self.current);self.display()
    def launch(self):return self.app.save_and_launch(save_callback=self.save,parent=self)
    def close(self):
        if self.settle():self.destroy()

def open_background_window(app,index=0):
    if not app.rom:messagebox.showinfo('Open a ROM','Open a supported FE4 ROM first.',parent=app);return
    if not app.settle():return
    try:Background(app.rom,index)
    except ValueError as error:messagebox.showerror('Background unavailable',str(error),parent=app);return
    return BackgroundWindow(app,index)
