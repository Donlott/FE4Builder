#!/usr/bin/env python3
"""FE4 Modding Studio — native desktop GUI."""
import sys,threading,queue,json
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
from PIL import Image,ImageTk
from core import ROM,COUNT,EditorError

class App:
    def __init__(self,root):
        self.root=root;root.title('FE4 Modding Studio • 0.5');root.geometry('1060x760');root.minsize(900,680)
        self.rom=None;self.text_window=None;self.animation_window=None;self.idx=0;self.photos=[];self.busy=False;self.jobs=queue.Queue()
        style=ttk.Style();style.theme_use('clam');style.configure('TButton',padding=7);style.configure('Header.TLabel',font=('Sans',19,'bold'))
        top=ttk.Frame(root,padding=16);top.pack(fill='x')
        ttk.Label(top,text='FE4 Modding Studio',style='Header.TLabel').pack(side='left')
        self.openbutton=ttk.Button(top,text='Open ROM…',command=self.open);self.openbutton.pack(side='right')
        ttk.Button(top,text='Names & story…',command=self.open_text).pack(side='right',padx=8)
        ttk.Button(top,text='Animations…',command=self.open_animations).pack(side='right',padx=4)
        self.filelabel=ttk.Label(root,text='Open a test ROM to browse its 248 portrait slots.',padding=(16,0));self.filelabel.pack(fill='x')
        body=ttk.Panedwindow(root,orient='horizontal');body.pack(fill='both',expand=True,padx=16,pady=12)
        left=ttk.Frame(body);right=ttk.Frame(body);body.add(left,weight=1);body.add(right,weight=4)
        ttk.Label(left,text='Portrait slot (hex ID)').pack(anchor='w')
        self.search=tk.StringVar();self.search.trace_add('write',lambda *_:self.populate())
        ttk.Entry(left,textvariable=self.search).pack(fill='x',pady=6)
        lf=ttk.Frame(left);lf.pack(fill='both',expand=True)
        self.list=tk.Listbox(lf,width=26,font=('Monospace',10),exportselection=False);self.list.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(lf,command=self.list.yview);scroll.pack(side='right',fill='y');self.list.configure(yscrollcommand=scroll.set);self.list.bind('<<ListboxSelect>>',self.select)
        ttk.Label(left,text='Names are original FE4 references.\nYour hack may use different characters.',wraplength=220).pack(pady=8)
        self.title=ttk.Label(right,text='No ROM loaded',font=('Sans',14,'bold'));self.title.pack(anchor='w')
        self.canvas=tk.Canvas(right,height=340,bg='#222833',highlightthickness=0);self.canvas.pack(fill='x',pady=10)
        self.detail=ttk.Label(right,text='PNG sheet: 64×64 pixels\nLeft: 48×64 portrait. Right: 16×64 animation tiles.',wraplength=690);self.detail.pack(anchor='w',pady=4)
        bar=ttk.Frame(right);bar.pack(fill='x',pady=8)
        for text,fn in [('Export PNG…',self.export),('Import PNG…',self.import_png),('Undo slot',self.undo)]:ttk.Button(bar,text=text,command=fn).pack(side='left',padx=(0,6))
        self.reduce=tk.BooleanVar(value=False);ttk.Checkbutton(right,text='Allow colour reduction on RGB/RGBA import (preview before saving)',variable=self.reduce).pack(anchor='w')
        ttk.Label(right,text='Export a sheet first and edit it in GIMP. Keep the animation strip aligned.\nOpaque RGB PNGs use the top-left colour as the transparent background.',wraplength=680).pack(anchor='w',pady=10)
        self.optimize=tk.BooleanVar(value=False)
        ttk.Checkbutton(right,text='Optimize portrait storage when saving',variable=self.optimize,command=self.set_optimize).pack(anchor='w')
        bottom=ttk.Frame(right);bottom.pack(fill='x',pady=6)
        ttk.Button(bottom,text='Preview packing…',command=self.preview_packing).pack(side='left',padx=(0,6))
        ttk.Button(bottom,text='Reserve space…',command=self.reserve).pack(side='left')
        ttk.Button(bottom,text='Save ROM copy…',command=self.save).pack(side='right')
        self.reservation=ttk.Label(right,text='Saving uses exclusive existing space when possible.',wraplength=680);self.reservation.pack(anchor='w')
        self.status=tk.StringVar(value='Ready');ttk.Label(root,textvariable=self.status,relief='sunken',padding=8,wraplength=1000).pack(fill='x')
        self.names={}
        try:self.names=json.loads((Path(__file__).parent/'slot_names.json').read_text(encoding='utf-8'))
        except OSError:pass
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(100,self.poll)
    def dirty(self):
        return bool(self.rom and (self.rom.pending or self.rom.optimize_portraits or (self.rom.text and self.rom.text.dirty) or (self.rom.animations and self.rom.animations.dirty)))
    def open_animations(self):
        if not self.available():return
        if self.animation_window is not None:self.animation_window.root.lift();return
        try:
            from animationui import AnimationWindow
            self.animation_window=AnimationWindow(self)
        except Exception as e:self.error(e)
    def open_text(self):
        if not self.available():return
        if self.text_window is not None:
            self.text_window.root.lift();return
        try:
            from textui import TextWindow
            self.text_window=TextWindow(self)
        except Exception as e:self.error(e)
    def task(self,fn,done):
        if self.busy:return
        self.busy=True;self.status.set('Working…');self.root.config(cursor='watch')
        def run():
            try:self.jobs.put((done,fn(),None))
            except Exception as e:self.jobs.put((done,None,e))
        threading.Thread(target=run,daemon=True).start()
    def poll(self):
        try:
            done,result,error=self.jobs.get_nowait();self.busy=False;self.root.config(cursor='')
            if error:self.error(error)
            else:done(result)
        except queue.Empty:pass
        self.root.after(100,self.poll)
    def error(self,e):self.status.set(str(e));messagebox.showerror('Portrait Studio',str(e))
    def available(self):return self.rom is not None and not self.busy
    def open(self):
        if self.busy:return
        if self.rom and self.dirty() and not messagebox.askyesno('Discard staged edits?','Open another ROM and discard the staged edits?'):return
        p=filedialog.askopenfilename(filetypes=[('SNES ROM','*.smc *.sfc'),('All files','*')])
        if not p:return
        def done(rom):
            if self.text_window is not None:self.text_window.close()
            if self.animation_window is not None:self.animation_window.close()
            self.rom=rom;self.optimize.set(False);self.idx=0;self.search.set('');self.populate();self.list.selection_set(0);self.show()
            self.filelabel.config(text=f'{rom.path.name} • {len(rom.data)//1048576} MiB • {"ExHiROM" if rom.exhirom else "HiROM"} • {len(rom.header)}-byte copier header')
            self.reservation.config(text='Saving uses exclusive existing space when possible.');self.status.set('All 248 slots decoded. Input ROM remains protected.')
        self.task(lambda:ROM(p),done)
    def populate(self):
        if not self.rom:return
        self.list.delete(0,'end');self.ids=[];query=self.search.get().lower()
        for i in range(COUNT):
            name=f'{i:02X}  {self.names.get(str(i),"Portrait")}'+(' *' if i in self.rom.pending else '')
            if query in name.lower():self.ids.append(i);self.list.insert('end',name)
    def select(self,event=None):
        if self.busy:return
        sel=self.list.curselection()
        if sel:self.idx=self.ids[sel[0]];self.show()
    def show(self):
        if not self.rom:return
        p=self.rom.portraits[self.idx];self.title.config(text=f'Slot {self.idx:02X} — '+self.names.get(str(self.idx),'Portrait'))
        im=self.rom.image(self.idx).convert('RGBA');self.canvas.delete('all');self.photos=[]
        for x,img,label in [(12,im.crop((0,0,48,64)),'Portrait'),(230,im,'Complete PNG sheet')]:
            # Checkerboard makes transparency visible without changing exported pixels.
            bg=Image.new('RGBA',img.size)
            for y in range(bg.height):
                for xx in range(bg.width):bg.putpixel((xx,y),(65,72,84,255) if (xx//4+y//4)%2 else (46,53,65,255))
            bg.alpha_composite(img);photo=ImageTk.PhotoImage(bg.resize((img.width*4,img.height*4),getattr(Image, 'Resampling', Image).NEAREST));self.photos.append(photo)
            self.canvas.create_text(x,18,text=label,fill='#e5e9f0',anchor='w',font=('Sans',11));self.canvas.create_image(x,38,image=photo,anchor='nw')
        gs=[f'{q.id:02X}' for q in self.rom.portraits if q.id!=p.id and q.gfx==p.gfx];ps=[f'{q.id:02X}' for q in self.rom.portraits if q.id!=p.id and q.pal==p.pal]
        self.detail.config(text=f'Palette mode: {"shared grey" if self.rom.shared_grey else "unlocked (15 editable colours)"}\nGraphics: {p.gfx:06X}  •  Palette: {p.pal:06X}  •  {len(p.touched)} compressed source bytes\nShared graphics: {", ".join(gs) or "none"}  |  Shared palette: {", ".join(ps) or "none"}')
    def export(self):
        if not self.available():return
        p=filedialog.asksaveasfilename(defaultextension='.png',initialfile=f'portrait_{self.idx:02X}.png',filetypes=[('PNG','*.png')])
        if p:
            try:self.rom.image(self.idx).save(p,transparency=0);self.status.set('Exported complete indexed PNG sheet: '+p)
            except Exception as e:self.error(e)
    def import_png(self):
        if not self.available():return
        p=filedialog.askopenfilename(filetypes=[('PNG','*.png')])
        if p:
            try:
                _,notice=self.rom.import_png(self.idx,p,self.reduce.get());self.populate();self.show();self.status.set('Staged slot '+f'{self.idx:02X}. '+notice)
            except Exception as e:self.error(e)
    def undo(self):
        if self.available():self.rom.pending.pop(self.idx,None);self.populate();self.show();self.status.set('Slot restored to the opened ROM.')
    def set_optimize(self):
        if self.busy:
            self.optimize.set(bool(self.rom and self.rom.optimize_portraits));return
        if self.rom:self.rom.optimize_portraits=self.optimize.get()
    def preview_packing(self):
        if not self.available():return
        def done(plan):
            self.status.set('Packing preview ready. Enable Optimize portrait storage to use it when saving.')
            messagebox.showinfo('Portrait storage preview',plan.summary+'\n\nThis preview has not changed your ROM.')
        self.task(self.rom.packing_plan,done)
    def reserve(self):
        if not self.available():return
        text=simpledialog.askstring('Reserve unused space','Enter a HEADERLESS hex range you own, START-END (end exclusive).\nIt must be uniformly 00 or FF. Blank bytes alone do not prove it is unused.\nVerify the range against your project map.\nReserved bytes will hold larger replacements and split shared assets.')
        if not text:return
        try:
            a,b=[int(x.strip(),16) for x in text.split('-')];self.rom.reserve(a,b);self.reservation.config(text=f'Reserved {a:06X}–{b:06X} (end exclusive) for this save.');self.status.set('Reservation validated against all decoded portrait streams and palettes.')
        except Exception as e:self.error(e)
    def save(self):
        if not self.available():return
        if not self.dirty():messagebox.showinfo('Nothing to save','Import a PNG or stage text/animation edits first.');return
        p=filedialog.asksaveasfilename(defaultextension=self.rom.path.suffix,initialfile=self.rom.path.stem+'_portraits'+self.rom.path.suffix,filetypes=[('SNES ROM','*.smc *.sfc')])
        if not p:return
        def done(log):
            self.status.set('Saved copy; portraits and staged edits verified. '+str(len(log))+' asset changes.')
            messagebox.showinfo('Saved ROM copy',str(p)+'\n\n'+('\n'.join(log[:12]) or 'No binary changes.')+'\n\nTest dialogue, status screens and battle portraits in your emulator.\nEdits remain staged so you can save another copy.')
        self.task(lambda:self.rom.save(p),done)
    def close(self):
        if self.busy:messagebox.showinfo('Please wait','Wait for the current operation to finish.');return
        if self.rom and self.dirty() and not messagebox.askyesno('Close editor?','Close with staged edits? Save a ROM copy first if you need them.'):return
        self.root.destroy()

if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
