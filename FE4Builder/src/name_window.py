import tkinter as tk
from tkinter import ttk, messagebox
from names import NameEditor,NameNeedsSpace

def open_name_window(app, name_id=0):
    if not app.rom:
        messagebox.showinfo('Open a ROM', 'Open a Project Naga beta v7 ROM first.')
        return
    if not app.settle():
        return
    try:
        model = NameEditor(app.rom,name_id)
        models = [NameEditor(app.rom,i) for i in range(63)]
    except ValueError as error:
        messagebox.showerror('Name editing unavailable',str(error))
        return
    dialog = tk.Toplevel(app)
    dialog.title('FE4Builder — Character Name Editor')
    dialog.geometry('690x440')
    dialog.transient(app)
    dialog.grab_set()
    body = ttk.Frame(dialog,padding=20)
    body.pack(fill='both',expand=True)
    ttk.Label(body,text='Edit the actual character name',style='Title.TLabel').pack(anchor='w')
    selector = ttk.Combobox(body,state='readonly',values=[f'{i:02X} — {m.current}' for i,m in enumerate(models)],width=40)
    selector.current(name_id)
    selector.pack(anchor='w',pady=(14,10))
    text = tk.StringVar(value=model.current)
    entry = ttk.Entry(body,textvariable=text,font=('Segoe UI',16))
    entry.pack(fill='x')
    info = tk.StringVar()
    ttk.Label(body,textvariable=info,wraplength=640).pack(anchor='w',pady=10)
    preview = tk.Label(body,background='#243047',height=70)
    preview.pack(fill='x',pady=8)
    ttk.Label(body,text='Updates menu graphics, stored name text, castle dialogue names and resurrection names.\nLarger graphics can reuse existing ROM space after confirmation.\nNames written literally into story dialogue are not replaced.',wraplength=640,style='Subtitle.TLabel').pack(anchor='w',pady=8)
    actions = ttk.Frame(body)
    actions.pack(fill='x',side='bottom')
    initial = model.current

    def update(*_):
        try:
            expanding=False
            try:
                rows,_ = model.plan(text.get())
            except NameNeedsSpace:
                rows,_ = model.plan(text.get(),allow_expand=True)
                expanding=True
            photo = tk.PhotoImage(width=len(rows[0]),height=16,master=dialog)
            colors = ['#243047','#ffffff','#e1ecff','#090d18']
            photo.put(' '.join('{'+' '.join(colors[pixel] for pixel in row)+'}' for row in rows))
            preview.image = photo.zoom(4,4)
            preview.config(image=preview.image,height=70)
            shared = ' Both young and adult Finn share these graphics and will be renamed.' if len(model.shared_ids)>1 else ''
            info.set(f'{len(text.get())}/8 characters · {len(rows[0])}/{model.tiles*8} pixels available.'+shared)
            if expanding:
                info.set('A larger name allocation is needed. Write to ROM will ask before repacking the menu graphics.'+shared)
            write.config(state='normal')
        except ValueError as error:
            info.set(str(error))
            preview.config(image='')
            write.config(state='disabled')

    def choose(_=None):
        nonlocal model,initial
        if text.get()!=initial and not messagebox.askyesno('Unwritten name','Discard the current unwritten name?',parent=dialog):
            selector.current(model.name_id)
            return
        model = NameEditor(app.rom,selector.current())
        initial = model.current
        text.set(initial)

    def save():
        nonlocal model,initial
        before = bytes(app.rom.data)
        try:
            allow_expand=False
            try:
                model.plan(text.get())
            except NameNeedsSpace:
                model.plan(text.get(),allow_expand=True)
                if not messagebox.askyesno('Expand name space?',
                    'This name is wider than its current allocation. FE4Builder will expand its name graphics and repack the generation’s menu tiles.\n\n'
                    'This ROM is already 8 MiB, so its file size will remain unchanged; existing reserved space is reused. Very wide names may clip in some menus.\n\nContinue?',parent=dialog):
                    return False
                allow_expand=True
            model.write(text.get(),allow_expand=allow_expand)
            app.rom.save_original(f'Character name {model.name_id:02X}: {initial} → {text.get()}',
                                  [f'Name: {initial} → {text.get()}',f'Shared name IDs: {model.shared_ids}'])
        except (ValueError,OSError) as error:
            app.rom.data[:] = before
            messagebox.showerror('Cannot write name',str(error),parent=dialog)
            return False
        initial = text.get()
        model = NameEditor(app.rom,model.name_id)
        selector.config(values=[f'{i:02X} — {NameEditor(app.rom,i).current}' for i in range(63)])
        app.status.set(f'Name written directly to {app.rom.path.name}; ROM size unchanged.')
        app.update_history_controls()
        if app.record is not None:
            app.render()
            app.populate()
        info.set('Saved successfully. ROM size and pointers are unchanged.')
        return True

    def close():
        if text.get()!=initial and not messagebox.askyesno('Unwritten name','Discard the current unwritten name?',parent=dialog):
            return
        dialog.destroy()

    launch=lambda:app.save_and_launch(save_callback=save,parent=dialog)
    ttk.Button(actions,text='Save & Launch (F5)',command=launch).pack(side='right',padx=8)
    dialog.bind('<F5>',lambda e:launch())
    write = ttk.Button(actions,text='Write to ROM',command=save)
    write.pack(side='right')
    ttk.Button(actions,text='Close',command=close).pack(side='right',padx=10)
    selector.bind('<<ComboboxSelected>>',choose)
    text.trace_add('write',update)
    dialog.protocol('WM_DELETE_WINDOW',close)
    update()
    entry.focus_set()
    dialog.save=save;dialog.pending=lambda:text.get()!=initial;dialog.close=close
    return dialog
