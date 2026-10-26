"""Studio-based portrait workspace integrated with FE4Builder's ROM/history."""
import base64
import struct
import zlib
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from collections import Counter
from portraits import (COUNT, face_from_sheet, sheet_from_face, editable_sheet,
    native_sheet_from_editable, studio_sheet, native_sheet_from_studio,
    export_png, png_bytes, decode_tiles, decode_palette, encode_palette)
from portrait_document import PortraitDocument
from ui_common import scrollable_frame, ask_unsaved, bind_canvas_wheel


def photo(master, rows, colors, scale=3):
    return tk.PhotoImage(master=master, data=base64.b64encode(png_bytes(rows, colors, scale)))


def quantize(pixels,transparent,background,limit=15):
    # Work in the SNES's native five-bit color space before choosing a palette.
    def snes(color):
        return tuple(round(value*31/255) for value in color)
    converted=[[snes(color) for color in row] for row in pixels]
    bg=snes(background)
    has_alpha=any(any(row) for row in transparent)
    masks=[[transparent[y][x] if has_alpha else value==bg for x,value in enumerate(row)] for y,row in enumerate(converted)]
    counts=Counter(value for y,row in enumerate(converted) for x,value in enumerate(row) if not masks[y][x])
    boxes=[list(counts)] if counts else []
    while len(boxes)<limit:
        choices=[(max(max(c[k] for c in box)-min(c[k] for c in box) for k in range(3)),sum(counts[c] for c in box),i)
                 for i,box in enumerate(boxes) if len(box)>1]
        if not choices:
            break
        _,_,index=max(choices)
        box=boxes.pop(index)
        axis=max(range(3),key=lambda k:max(c[k] for c in box)-min(c[k] for c in box))
        box.sort(key=lambda c:c[axis])
        halfway=sum(counts[c] for c in box)/2
        running=0
        cut=1
        for i,color in enumerate(box[:-1]):
            running+=counts[color]
            cut=i+1
            if running>=halfway:
                break
        boxes.extend((box[:cut],box[cut:]))
    selected=[tuple(round(sum(c[k]*counts[c] for c in box)/sum(counts[c] for c in box)) for k in range(3)) for box in boxes]
    palette=[bg]+selected
    palette+= [(0,0,0)]*(16-len(palette))
    mapping={color:1+min(range(len(selected)),key=lambda i:sum((a-b)**2 for a,b in zip(color,selected[i]))) for color in counts}
    rows=[[0 if masks[y][x] else mapping[value] for x,value in enumerate(row)] for y,row in enumerate(converted)]
    colors=[tuple(component*255//31 for component in color) for color in palette]
    return rows,colors,len(counts)>15

def load_png(master, path, allow_reduction=True, shared_grey=False, palette=None):
    """Read both artist layouts without adding Pillow as a runtime dependency."""
    data=Path(path).read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Choose a PNG file.')
    # Let Tk validate the PNG before inspecting optional indexed information.
    image=tk.PhotoImage(master=master,file=str(path))
    width,height=image.width(),image.height()
    sizes=((64,64),(64,80),(48,64),(128,32))
    if (width,height) not in sizes:
        raise ValueError('Use a Studio 64 x 64 sheet (animation strip on the right), a FE4Builder 64 x 80 sheet (mouth frames below), a 48 x 64 face, or a native 128 x 32 sheet. No resizing is performed.')
    static=(width,height)==(48,64)
    def native(rows):
        if (width,height)==(64,64):return native_sheet_from_studio(rows)
        if (width,height)==(64,80):return native_sheet_from_editable(rows)
        if static:return sheet_from_face(rows)
        return rows
    pixels=native([[image.get(x,y) for x in range(width)] for y in range(height)])
    alpha=native([[image.transparency_get(x,y) for x in range(width)] for y in range(height)])
    # Preserve exact palette indices (including duplicate colors) for exported
    # indexed templates. Other indexed PNGs go through the RGB path below.
    from intro_graphics import indexed_png
    try:indexed=indexed_png(path)
    except (ValueError,IndexError,struct.error,zlib.error):indexed=None
    grey=tuple(((0x35ad>>s)&31)*255//31 for s in (0,5,10))
    if indexed:
        rows,colors=indexed;rows=native(rows)
        colors=colors[:16]+[(0,0,0)]*max(0,16-len(colors))
        used={v for row in rows for v in row}
        # Check alpha chunk too: Tk's boolean accessor cannot distinguish
        # partial alpha from opaque on every Tcl/Tk version.
        position=8;transparency=None
        while position+12<=len(data):
            length=int.from_bytes(data[position:position+4],'big')
            if data[position+4:position+8]==b'tRNS':transparency=data[position+8:position+8+length]
            position+=length+12
        alpha_ok=transparency is None or (transparency[:1]==b'\0' and all(v==255 for v in transparency[1:]))
        if used and max(used)<16 and alpha_ok:
            colors=decode_palette(encode_palette(colors))
            if shared_grey:
                if 14 in used and colors[14]!=grey:
                    raise ValueError('Index 14 is the shared grey color in this ROM. Retain the exported palette or use an RGB PNG.')
                colors[14]=grey
            return rows,colors,static,False
    # Reject partial transparency, including RGBA PNGs, using Tk's RGBA reader.
    # Tk 8.6 exposes alpha through `data -format` only on newer releases.
    # PNG alpha is checked by the small reader below, independent of Tk version.
    _check_png_alpha(data)
    def word(c):return tuple(round(v*31/255) for v in c)
    has_alpha=any(any(row) for row in alpha)
    bg=pixels[0][0]
    masks=[[alpha[y][x] if has_alpha else c==bg for x,c in enumerate(row)] for y,row in enumerate(pixels)]
    words=[[word(c) for c in row] for row in pixels]
    grey_word=word(grey)
    counts=Counter(c for y,row in enumerate(words) for x,c in enumerate(row)
                   if not masks[y][x] and not (shared_grey and c==grey_word))
    slots=list(range(1,14))+[15] if shared_grey else list(range(1,16))
    reduced=len(counts)>len(slots)
    if reduced and not allow_reduction:
        raise ValueError(f'PNG uses {len(counts)} editable colors after SNES conversion; this ROM allows {len(slots)}. Enable color reduction and inspect the preview.')
    if reduced:
        # Reuse FE4Builder's median-cut quantizer, excluding shared grey pixels.
        extra=[[masks[y][x] or (shared_grey and c==grey_word) for x,c in enumerate(row)] for y,row in enumerate(words)]
        # quantize accepts a selectable limit for the shared-grey profile.
        _,chosen,_=quantize(pixels,extra,bg,limit=len(slots))
        selected=[word(c) for c in chosen[1:1+len(slots)]]
    else:selected=sorted(counts)
    colors=list(palette) if palette is not None else [(0,0,0)]*16
    colors[0]=tuple(v*255//31 for v in word(bg))
    for slot,c in zip(slots,selected):colors[slot]=tuple(v*255//31 for v in c)
    if shared_grey:colors[14]=grey
    mapping={c:slots[min(range(len(selected)),key=lambda i:sum((a-b)**2 for a,b in zip(c,selected[i])))] for c in counts}
    if shared_grey:mapping[grey_word]=14
    rows=[[0 if masks[y][x] else mapping[c] for x,c in enumerate(row)] for y,row in enumerate(words)]
    return rows,colors,static,reduced


def _check_png_alpha(data):
    """Reject partial alpha; decode with stdlib for RGBA/gray-alpha PNGs only."""
    position=8;compressed=bytearray();header=None
    while position+12<=len(data):
        n=int.from_bytes(data[position:position+4],'big');kind=data[position+4:position+8];body=data[position+8:position+8+n];position+=n+12
        if kind==b'IHDR':header=struct.unpack('>IIBBBBB',body)
        elif kind==b'IDAT':compressed.extend(body)
        elif kind==b'tRNS' and header and header[3]==3 and any(v not in (0,255) for v in body):
            raise ValueError('Use fully opaque or transparent pixels; partial transparency is unsupported.')
    if not header or header[3] not in (4,6):return
    width,height,depth,kind,_,_,interlace=header
    if depth!=8 or interlace:
        raise ValueError('Save RGBA PNGs as non-interlaced 8-bit images, or use an exported indexed template.')
    channels=4 if kind==6 else 2;stride=width*channels
    raw=zlib.decompress(compressed);previous=bytearray(stride);pos=0
    for _ in range(height):
        filt=raw[pos];line=bytearray(raw[pos+1:pos+1+stride]);pos+=stride+1
        for x in range(stride):
            a=line[x-channels] if x>=channels else 0;b=previous[x];c=previous[x-channels] if x>=channels else 0
            if filt==1:line[x]=(line[x]+a)&255
            elif filt==2:line[x]=(line[x]+b)&255
            elif filt==3:line[x]=(line[x]+(a+b)//2)&255
            elif filt==4:
                p=a+b-c;ds=(abs(p-a),abs(p-b),abs(p-c));line[x]=(line[x]+(a,b,c)[ds.index(min(ds))])&255
            elif filt!=0:raise ValueError('Unsupported PNG filter.')
        if any(v not in (0,255) for v in line[channels-1::channels]):
            raise ValueError('Use fully opaque or transparent pixels; partial transparency is unsupported.')
        previous=line


class PortraitWindow(tk.Toplevel):
    """Studio's slot browser, full-sheet workspace and packing controls."""
    def __init__(self,app,portrait_id=0,action=None):
        self.app=app
        self.document=PortraitDocument(app.rom)
        super().__init__(app)
        self.title('FE4Builder — Portrait Editor');self.geometry('1130x790');self.minsize(780,600)
        self.transient(app);self.grab_set()
        self.current=portrait_id;self.photos=[];self.animation_job=None;self.animation_step=0;self.busy=False;self.pack_job=None;self.pack_results=queue.Queue()
        self.names=self.slot_names()
        top=ttk.Frame(self,padding=(16,12));top.pack(fill='x')
        ttk.Label(top,text='Portrait Editor',style='Title.TLabel').pack(side='left')
        ttk.Label(top,text=app.rom.path.name).pack(side='right')
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=16)
        left=ttk.Frame(body);shell=ttk.Frame(body);body.add(left,weight=1);body.add(shell,weight=4)
        ttk.Label(left,text='Portrait slot — hex ID or name').pack(anchor='w')
        self.search=tk.StringVar();self.search.trace_add('write',lambda *_:self.populate())
        ttk.Entry(left,textvariable=self.search).pack(fill='x',pady=6)
        listing=ttk.Frame(left);listing.pack(fill='both',expand=True)
        self.list=tk.Listbox(listing,width=25,exportselection=False);self.list.pack(side='left',fill='both',expand=True)
        bar=ttk.Scrollbar(listing,command=self.list.yview);bar.pack(side='right',fill='y');self.list.config(yscrollcommand=bar.set)
        self.list.bind('<<ListboxSelect>>',self.select)
        ttk.Label(left,text='* = staged replacement\nNames follow the loaded ROM’s character records.',wraplength=200).pack(anchor='w',pady=8)
        right=scrollable_frame(shell)
        self.slot_title=ttk.Label(right,font=('Sans',14,'bold'));self.slot_title.pack(anchor='w')
        # Horizontal scrolling keeps all three panels accessible on smaller screens.
        preview=ttk.Frame(right);preview.pack(fill='x',pady=10)
        self.canvas=tk.Canvas(preview,height=380,bg='#222833',highlightthickness=0)
        self.canvas.pack(fill='x',expand=True)
        scroll=ttk.Scrollbar(preview,orient='horizontal',command=self.canvas.xview);scroll.pack(fill='x')
        self.canvas.config(xscrollcommand=scroll.set);bind_canvas_wheel(self.canvas)
        self.frame=ttk.Combobox(right,state='readonly',values=('Animate talking','Normal face','Talking frame 1','Talking frame 2'),width=24)
        self.frame.current(0);self.frame.pack(anchor='w');self.frame.bind('<<ComboboxSelected>>',lambda _:self.show())
        layout_bar=ttk.Frame(right);layout_bar.pack(fill='x',pady=8)
        ttk.Label(layout_bar,text='Complete PNG sheet / export layout:').pack(side='left')
        self.layout=ttk.Combobox(layout_bar,state='readonly',values=('Studio — 64 x 64','FE4Builder — 64 x 80'),width=25)
        self.layout.current(0);self.layout.pack(side='left',padx=6);self.layout.bind('<<ComboboxSelected>>',lambda _:self.show())
        self.detail=ttk.Label(right,wraplength=720);self.detail.pack(anchor='w',pady=4)
        actions=ttk.Frame(right);actions.pack(fill='x',pady=8)
        for label,command in (('Export sheet…',self.export),('Import PNG…',self.import_png),('Undo slot',self.undo)):
            ttk.Button(actions,text=label,command=command).pack(side='left',padx=(0,6))
        self.reduce=tk.BooleanVar(value=False)
        ttk.Checkbutton(right,text='Allow color reduction on PNG import (inspect preview before writing)',variable=self.reduce).pack(anchor='w')
        ttk.Label(right,text='Import either layout; it is detected from PNG dimensions. Studio: animation tiles on the right.\nFE4Builder: two mouth frames below the face. One shared palette covers the whole sheet.\nExport a template first. Transparent pixels use index 0; opaque RGB uses the top-left color.',wraplength=720).pack(anchor='w',pady=10)
        self.optimize=tk.BooleanVar(value=False)
        ttk.Checkbutton(right,text='Optimize portrait storage when writing',variable=self.optimize,command=self.set_optimize).pack(anchor='w')
        storage=ttk.Frame(right);storage.pack(fill='x',pady=6)
        ttk.Button(storage,text='Preview packing…',command=self.preview_packing).pack(side='left',padx=(0,6))
        ttk.Button(storage,text='Reserve space…',command=self.reserve).pack(side='left')
        self.reservation=ttk.Label(right,text='Writing uses exclusive existing space when possible.',wraplength=720);self.reservation.pack(anchor='w')
        bottom=ttk.Frame(self,padding=(16,10));bottom.pack(fill='x')
        ttk.Button(bottom,text='Close',command=self.close).pack(side='right')
        ttk.Button(bottom,text='Save & Launch (F5)',command=self.launch).pack(side='right',padx=8)
        self.write=ttk.Button(bottom,text='Write Portrait to ROM',command=self.save);self.write.pack(side='right')
        self.status=tk.StringVar(value='Ready — imports are staged until written to ROM.')
        ttk.Label(self,textvariable=self.status,padding=(16,4),wraplength=1050).pack(fill='x')
        self.bind('<F5>',lambda _:(self.launch(),'break')[1])
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.bind('<Destroy>',self.destroyed,add='+')
        self.populate();self.show()
        if action=='import':self.after_idle(self.import_png)
        elif action=='export':self.after_idle(self.export)

    def slot_names(self):
        from rom import character_modules
        from portraits import character_portrait_id
        names={}
        for table in character_modules():
            for record in range(table.count):
                values={f.name:v for f,v in zip(table.fields,self.app.rom.values(table,record))}
                try:idx=character_portrait_id(self.app.rom,values['Char no.'],values.get('Class'))
                except (ValueError,KeyError):continue
                name=self.app.record_name(table,record)
                if name not in names.setdefault(idx,[]):names[idx].append(name)
        return {idx:', '.join(group[:3])+('…' if len(group)>3 else '') for idx,group in names.items()}

    def pending(self):return self.document.dirty

    def populate(self):
        query=self.search.get().casefold();self.list.delete(0,'end');self.visible=[]
        for idx in range(COUNT):
            label=f'{idx:02X}  {self.names.get(idx,"Portrait")}' + (' *' if idx in self.document.pending else '')
            if query in label.casefold():self.visible.append(idx);self.list.insert('end',label)
        if self.current in self.visible:
            index=self.visible.index(self.current);self.list.selection_set(index);self.list.see(index)

    def select(self,_=None):
        if self.busy:return
        selected=self.list.curselection()
        if selected:self.current=self.visible[selected[0]];self.show()

    def colors(self,palette):
        colors=decode_palette(palette)
        if self.document.shared_grey:colors[14]=(106,106,106)
        return colors

    def show(self):
        if self.animation_job is not None:self.after_cancel(self.animation_job);self.animation_job=None
        doc=self.document;p=doc.portraits[self.current]
        raw,palette=doc.pending.get(self.current,(p.raw,p.palette));sheet=decode_tiles(raw);colors=self.colors(palette)
        source=decode_tiles(p.raw);source_colors=self.colors(p.palette)
        self.slot_title.config(text=f'Slot {self.current:02X} — {self.names.get(self.current,"Portrait")}'+(' *' if self.current in doc.pending else ''))
        self.canvas.delete('all');self.photos=[]
        rows=studio_sheet(sheet) if self.layout.current()==0 else editable_sheet(sheet)
        # Store pre-rendered talking frames; a timer only swaps canvas images.
        self.talking=[self.checker_photo(face_from_sheet(sheet,i),colors) for i in range(3)]
        for x,rows_,colors_,label in ((12,face_from_sheet(source),source_colors,'Current ROM portrait'),(230,rows,colors,'Complete PNG sheet')):
            image=self.checker_photo(rows_,colors_);self.photos.append(image)
            self.canvas.create_text(x,18,text=label,fill='#e5e9f0',anchor='w')
            self.canvas.create_image(x,38,image=image,anchor='nw')
        self.canvas.create_text(512,18,text='Talking preview — staged portrait',fill='#e5e9f0',anchor='w')
        self.talking_item=self.canvas.create_image(512,38,image=self.talking[0],anchor='nw')
        self.canvas.config(height=max(310,len(rows)*4+50),scrollregion=(0,0,735,max(310,len(rows)*4+50)))
        self.animation_step=0;self.animate()
        gs=[f'{q.id:02X}' for q in doc.portraits if q.id!=p.id and q.gfx==p.gfx]
        ps=[f'{q.id:02X}' for q in doc.portraits if q.id!=p.id and q.pal==p.pal]
        def aliases(values):
            return ', '.join(values[:10])+ (f' … (+{len(values)-10})' if len(values)>10 else '') or 'none'
        self.detail.config(text=f'Palette: {"shared grey (14 editable colors)" if doc.shared_grey else "unlocked (15 editable colors)"}\nGraphics: {p.gfx:06X} · Palette: {p.pal:06X} · {len(p.touched)} compressed source bytes\nShared graphics: {aliases(gs)} | Shared palette: {aliases(ps)}')
        self.write.config(state='normal' if self.pending() else 'disabled')

    def checker_photo(self,rows,colors):
        # Composite index-zero transparency for previews only, never exports.
        preview_colors=list(colors)+[(65,72,84),(46,53,65)]
        pixels=[[value if value else 16+(x//4+y//4)%2 for x,value in enumerate(row)] for y,row in enumerate(rows)]
        return photo(self,pixels,preview_colors,4)

    def animate(self):
        mode=self.frame.current()
        variant=(0,1,2,1)[self.animation_step%4] if mode==0 else mode-1
        self.canvas.itemconfigure(self.talking_item,image=self.talking[variant])
        if mode==0:
            self.animation_step+=1;self.animation_job=self.after(180,self.animate)

    def import_png(self):
        if self.busy:return
        path=filedialog.askopenfilename(parent=self,filetypes=[('PNG portraits','*.png')])
        if not path:return
        try:
            p=self.document.portraits[self.current]
            sheet,colors,static,reduced=load_png(self,path,self.reduce.get(),self.document.shared_grey,self.colors(p.palette))
            self.document.stage(self.current,sheet,colors)
        except (ValueError,OSError,tk.TclError) as error:
            messagebox.showerror('Cannot import portrait',str(error),parent=self);return
        self.populate();self.show()
        self.status.set(f'Staged {Path(path).name}. ROM unchanged.'+(' Static mouth fallback.' if static else '')+(' Colors reduced; inspect the preview.' if reduced else ''))

    def export(self):
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.png',initialfile=f'portrait_{self.current:02X}_sheet.png',filetypes=[('PNG image','*.png')])
        if not path:return
        try:
            p=self.document.portraits[self.current];raw,palette=self.document.pending.get(self.current,(p.raw,p.palette))
            sheet=decode_tiles(raw);rows=studio_sheet(sheet) if self.layout.current()==0 else editable_sheet(sheet)
            Path(path).write_bytes(export_png(rows,self.colors(palette)))
        except (ValueError,OSError) as error:messagebox.showerror('Cannot export portrait',str(error),parent=self);return
        self.status.set('Exported complete PNG sheet: '+str(path))

    def undo(self):
        if self.busy:return
        self.document.pending.pop(self.current,None);self.populate();self.show();self.status.set('Slot restored to the current ROM; other staged slots are retained.')

    def set_optimize(self):
        if self.busy:
            self.optimize.set(self.document.optimize_portraits);return
        self.document.optimize_portraits=self.optimize.get();self.show()

    def preview_packing(self):
        if self.busy:return
        self.busy=True;self.config(cursor='watch')
        self.status.set('Calculating portrait packing… This may take a minute on the first preview.')
        def work():
            try:self.pack_results.put((self.document.packing_plan(),None))
            except Exception as error:self.pack_results.put((None,error))
        threading.Thread(target=work,daemon=True).start()
        self.pack_job=self.after(100,self.poll_packing)

    def poll_packing(self):
        self.pack_job=None
        try:plan,error=self.pack_results.get_nowait()
        except queue.Empty:
            self.pack_job=self.after(100,self.poll_packing);return
        self.busy=False;self.config(cursor='')
        if error:
            self.status.set(str(error));messagebox.showerror('Cannot pack portraits',str(error),parent=self)
        else:
            self.status.set('Packing preview ready. Enable optimization to use it when writing.')
            messagebox.showinfo('Portrait storage preview',plan.summary+'\n\nPreview only; enable optimization to use this plan when writing.',parent=self)

    def reserve(self):
        if self.busy:return
        text=simpledialog.askstring('Reserve unused portrait space','Enter a HEADERLESS hex range START-END (end exclusive).\nOnly reserve space you have verified is unused by your project.\nBlank bytes alone do not prove ownership.',parent=self)
        if not text:return
        try:
            start,end=(int(v.strip(),16) for v in text.split('-'));self.document.reserve(start,end)
        except ValueError as error:messagebox.showerror('Cannot reserve space',str(error),parent=self);return
        self.reservation.config(text=f'Reserved {start:06X}–{end:06X} for this write. Reservation clears after saving.')

    def save(self):
        if self.busy:return False
        if not self.pending():return True
        try:
            self.config(cursor='watch');self.update_idletasks()
            self.document.commit(self.app.rom)
        except (ValueError,OSError) as error:
            messagebox.showerror('Cannot write portrait',str(error),parent=self);return False
        finally:self.config(cursor='')
        self.document=PortraitDocument(self.app.rom);self.optimize.set(False)
        self.reservation.config(text='Writing uses exclusive existing space when possible.')
        self.populate();self.show();self.app.refresh_after_history()
        self.status.set('Portraits written to ROM. Backup and undo history updated.')
        self.app.status.set(self.status.get());return True

    def launch(self):
        if self.busy:return False
        return self.app.save_and_launch(save_callback=self.save,parent=self)

    def close(self):
        if self.busy:
            messagebox.showinfo('Portrait packing','Wait for the packing preview to finish before closing.',parent=self);return
        if self.pending():
            choice=ask_unsaved(self,'Write all staged portrait changes to the opened ROM?')
            if choice is None or (choice and not self.save()):return
        self.destroy()

    def destroyed(self,event):
        if event.widget is self:
            for name in ('animation_job','pack_job'):
                job=getattr(self,name)
                if job is not None:self.after_cancel(job);setattr(self,name,None)


def open_portrait_window(app,portrait_id=0,action=None):
    if not app.rom:
        messagebox.showinfo('Open a ROM','Open a FE4 ROM first.');return
    if not app.settle():return
    try:return PortraitWindow(app,portrait_id,action)
    except ValueError as error:messagebox.showerror('Portrait unavailable',str(error),parent=app)
