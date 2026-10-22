import base64
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
from collections import Counter
from portraits import Portrait,COUNT,face_from_sheet,sheet_from_face,editable_sheet,native_sheet_from_editable,export_png,png_bytes

def photo(master,rows,colors,scale=3):
    return tk.PhotoImage(master=master,data=base64.b64encode(png_bytes(rows,colors,scale)))

def quantize(pixels,transparent,background):
    # Work in the SNES's native five-bit color space before choosing a palette.
    def snes(color):
        return tuple(round(value*31/255) for value in color)
    converted=[[snes(color) for color in row] for row in pixels]
    bg=snes(background)
    has_alpha=any(any(row) for row in transparent)
    masks=[[transparent[y][x] if has_alpha else value==bg for x,value in enumerate(row)] for y,row in enumerate(converted)]
    counts=Counter(value for y,row in enumerate(converted) for x,value in enumerate(row) if not masks[y][x])
    boxes=[list(counts)] if counts else []
    while len(boxes)<15:
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

def load_png(master,path):
    image=tk.PhotoImage(master=master,file=str(path))
    width,height=image.width(),image.height()
    if (width,height) not in ((64,80),(48,64),(128,32)):
        raise ValueError('Import a 64 x 80 portrait sheet: 48 x 64 face at the top-left, with two 32 x 16 mouth frames side by side below. Export a sheet for a template. Legacy 48 x 64 faces and 128 x 32 native sheets are also accepted.')
    pixels=[[image.get(x,y) for x in range(width)] for y in range(height)]
    transparency=[[image.transparency_get(x,y) for x in range(width)] for y in range(height)]
    background=pixels[0][0]
    static=(width,height)==(48,64)
    if (width,height)==(64,80):
        # Ignore the unused top-right padding before selecting the palette.
        pixels=native_sheet_from_editable(pixels)
        transparency=native_sheet_from_editable(transparency)
    rows,colors,reduced=quantize(pixels,transparency,background)
    return sheet_from_face(rows) if static else rows,colors,static,reduced

def open_portrait_window(app,portrait_id=0,action=None):
    if not app.rom:
        messagebox.showinfo('Open a ROM','Open a FE4 ROM first.')
        return
    if not app.settle():
        return
    try:
        model=Portrait(app.rom,portrait_id)
    except ValueError as error:
        messagebox.showerror('Portrait unavailable',str(error))
        return
    dialog=tk.Toplevel(app)
    dialog.title('FE4Builder — Portrait Editor')
    dialog.geometry('900x720')
    dialog.minsize(820,680)
    dialog.transient(app)
    dialog.grab_set()
    body=ttk.Frame(dialog,padding=16)
    body.pack(fill='both',expand=True)
    ttk.Label(body,text='Portrait sheet preview & import',style='Title.TLabel').pack(anchor='w')
    from rom import character_modules
    from portraits import character_portrait_id
    users={}
    for table in character_modules():
        for record in range(table.count):
            values={f.name:v for f,v in zip(table.fields,app.rom.values(table,record))}
            try:portrait=character_portrait_id(app.rom,values['Char no.'],values.get('Class'))
            except (ValueError,KeyError):continue
            label=app.record_name(table,record)
            if label not in users.setdefault(portrait,[]):users[portrait].append(label)
    labels=[(', '.join(users[i][:3])+('…' if len(users[i])>3 else '') if i in users else 'Portrait')+f' (0x{i:02X})' for i in range(COUNT)]
    selector=ttk.Combobox(body,state='readonly',values=labels,width=48)
    selector.current(portrait_id)
    selector.pack(anchor='w',pady=12)
    images=ttk.Frame(body)
    images.pack(fill='x')
    current_box=ttk.LabelFrame(images,text='Current portrait sheet',padding=8)
    current_box.pack(side='left',fill='x',expand=True,padx=(0,12))
    imported_box=ttk.LabelFrame(images,text='Imported preview',padding=8)
    imported_box.pack(side='left',fill='x',expand=True)
    current=tk.Label(current_box,bg='#172238')
    current.placeholder=tk.PhotoImage(master=dialog,width=192,height=240)
    current.config(image=current.placeholder)
    current.pack()
    imported=tk.Label(imported_box,bg='#172238')
    imported.placeholder=tk.PhotoImage(master=dialog,width=192,height=240)
    imported.config(image=imported.placeholder)
    imported.pack()
    frame=ttk.Combobox(body,state='readonly',values=['Full sheet (64 x 80)','Normal face','Talking frame 1','Talking frame 2'],width=26)
    frame.current(0)
    frame.pack(anchor='w',pady=8)
    info=tk.StringVar()
    ttk.Label(body,textvariable=info,wraplength=810).pack(anchor='w',pady=8)
    ttk.Label(body,text='Import/export a 64 x 80 PNG sheet: 48 x 64 face at the top-left, with two 32 x 16 mouth frames below.\nThe top-right 16 x 64 area is unused and ignored on import. Keep the face and mouth frames on one shared palette.\nExtra colors are reduced to 15 plus the background. Transparent pixels use color 0; for opaque PNGs, the top-left color is the background.\nLegacy face/native sheets are accepted. Replacement affects every character using the selected portrait ID.',wraplength=850,style='Subtitle.TLabel').pack(anchor='w',pady=8)
    actions=ttk.Frame(body)
    actions.pack(fill='x',pady=(0,12),before=images)
    candidate=None
    filename=None

    def display():
        variant=frame.current()
        current.image=photo(dialog,editable_sheet(model.sheet) if variant==0 else face_from_sheet(model.sheet,variant-1),model.colors)
        current.config(image=current.image)
        if candidate:
            sheet,colors=candidate
            imported.image=photo(dialog,editable_sheet(sheet) if variant==0 else face_from_sheet(sheet,variant-1),colors)
            imported.config(image=imported.image)
        else:
            imported.config(image=imported.placeholder)

    def refresh_info():
        info.set(f'Portrait {model.id:02X} · Graphics 0x{model.address:06X} · Palette 0x{model.palette_address:06X} · {model.compressed_size} compressed bytes')

    def select(_=None):
        nonlocal model,candidate,filename
        if candidate and not messagebox.askyesno('Imported portrait','Discard the imported preview?',parent=dialog):
            selector.current(model.id)
            return
        try:
            updated=Portrait(app.rom,selector.current())
        except ValueError as error:
            selector.current(model.id)
            messagebox.showerror('Portrait unavailable',str(error),parent=dialog)
            return
        model,candidate,filename=updated,None,None
        write.config(state='disabled')
        display()
        refresh_info()

    def import_image():
        nonlocal candidate,filename
        path=filedialog.askopenfilename(parent=dialog,filetypes=[('PNG portraits','*.png')])
        if not path:
            return
        try:
            sheet,colors,static,reduced=load_png(dialog,path)
            _,plan=model.plan_import(sheet,colors)
        except (ValueError,OSError,tk.TclError) as error:
            messagebox.showerror('Cannot import portrait',str(error),parent=dialog)
            return
        candidate,filename=(sheet,colors),Path(path).name
        display()
        info.set(f'{filename}: {plan}'+(' Static mouth fallback.' if static else ' Talking frames imported.')+
                 (' Colors reduced to the SNES palette.' if reduced else ''))
        write.config(state='normal')

    def export():
        path=filedialog.asksaveasfilename(parent=dialog,initialfile=f'portrait_{model.id:02X}_sheet.png',defaultextension='.png',filetypes=[('PNG image','*.png')])
        if path:
            try:
                Path(path).write_bytes(export_png(editable_sheet(model.sheet),model.colors))
            except OSError as error:
                messagebox.showerror('Cannot export portrait',str(error),parent=dialog)

    def save():
        nonlocal model,candidate
        if not candidate:
            return True
        before=bytes(app.rom.data)
        try:
            sheet,colors=candidate
            description=model.import_sheet(sheet,colors)
            changed=app.rom.dirty
            app.rom.save_original(f'Import portrait {model.id:02X}: {filename}',[description])
        except (ValueError,OSError) as error:
            app.rom.data[:]=before
            messagebox.showerror('Cannot write portrait',str(error),parent=dialog)
            return False
        model=Portrait(app.rom,model.id)
        candidate=None
        write.config(state='disabled')
        app.refresh_after_history()
        app.status.set(f'Portrait {model.id:02X} saved. Backup and undo history updated.' if changed else 'Portrait already matches the ROM; no changes were written.')
        display()
        refresh_info()
        return True

    def close():
        if candidate and not messagebox.askyesno('Imported portrait','Discard the unwritten imported portrait?',parent=dialog):
            return
        dialog.destroy()

    launch=lambda:app.save_and_launch(save_callback=save,parent=dialog)
    ttk.Button(actions,text='Save & Launch (F5)',command=launch).pack(side='right',padx=8)
    dialog.bind('<F5>',lambda e:launch())
    ttk.Button(actions,text='Import PNG…',command=import_image).pack(side='left')
    ttk.Button(actions,text='Export sheet…',command=export).pack(side='left',padx=8)
    write=ttk.Button(actions,text='Write portrait to ROM',command=save,state='disabled')
    write.pack(side='right')
    ttk.Button(actions,text='Close',command=close).pack(side='right',padx=8)
    selector.bind('<<ComboboxSelected>>',select)
    frame.bind('<<ComboboxSelected>>',lambda _:display())
    dialog.protocol('WM_DELETE_WINDOW',close)
    display()
    refresh_info()
    if action=='import':
        dialog.after_idle(import_image)
    elif action=='export':
        dialog.after_idle(export)
    dialog.save=save;dialog.pending=lambda:candidate is not None;dialog.close=close
    return dialog
