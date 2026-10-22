import tkinter as tk
from tkinter import ttk,messagebox
from datetime import datetime

def open_history_window(app):
    rom=app.rom
    dialog=tk.Toplevel(app)
    dialog.title('FE4Builder — Change History & Backups')
    dialog.geometry('960x670')
    body=ttk.Frame(dialog,padding=12)
    body.pack(fill='both',expand=True)
    ttk.Label(body,text='Change history',style='Title.TLabel').pack(anchor='w')
    status=ttk.Label(body)
    status.pack(anchor='w',pady=6)
    listing=ttk.Frame(body)
    listing.pack(fill='both',expand=True)
    tree=ttk.Treeview(listing,columns=('time','action','description'),show='headings',selectmode='browse')
    for key,label,width in [('time','Time (America/Santiago)',175),('action','Action',70),('description','Edit',610)]:
        tree.heading(key,text=label)
        tree.column(key,width=width)
    scroll=ttk.Scrollbar(listing,orient='vertical',command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right',fill='y')
    tree.pack(fill='both',expand=True)
    details=tk.Text(body,height=10,wrap='word',state='disabled')
    details.pack(fill='x',pady=10)
    ttk.Label(body,text='Backup folder:').pack(anchor='w')
    folder=tk.StringVar(value=str(rom.history.folder))
    ttk.Entry(body,textvariable=folder,state='readonly').pack(fill='x',pady=4)
    actions=ttk.Frame(body)
    actions.pack(fill='x',pady=8)

    def refresh():
        if app.rom is not rom:
            dialog.destroy()
            return
        tree.delete(*tree.get_children())
        for i,event in reversed(list(enumerate(rom.history.state['audit']))):
            try:
                seconds=int(datetime.fromisoformat(event['timestamp']).timestamp())
                when=app.tk.call('clock','format',seconds,'-format','%Y-%m-%d %H:%M:%S','-timezone',':America/Santiago')
            except (ValueError,tk.TclError):
                when=event['timestamp']+' (UTC)'
            tree.insert('','end',iid=str(i),values=(when,event['action'],event['description']))
        state=rom.history.state
        status.config(text=f'{len(state["audit"])} actions · Undo position {state["cursor"]} of {len(state["entries"])}. Undo/redo also writes the opened ROM. '+rom.history.notice)
        undo.config(state='normal' if rom.history.can_undo else 'disabled')
        redo.config(state='normal' if rom.history.can_redo else 'disabled')
        if tree.get_children():
            tree.selection_set(tree.get_children()[0])
            selected()

    def selected(_=None):
        selection=tree.selection()
        if not selection:
            return
        event=rom.history.state['audit'][int(selection[0])]
        lines=[event['description'],*event.get('details',[]),'',f'Backup: {event["backup"]}',
               f'ROM size: {event["before_size"]:,} → {event["after_size"]:,} bytes','',
               'Changed byte ranges (file offsets; includes copier header):']
        changes=event['patches']
        for change in changes[:200]:
            before=change['before'];after=change['after']
            lines.append(f'0x{change["offset"]:06X}: {before[:96] or "(empty)"} → {after[:96] or "(empty)"}'+
                         (' …' if max(len(before),len(after))>96 else ''))
        if len(changes)>200:
            lines.append(f'{len(changes)-200} additional ranges are recorded in history.json.')
        details.config(state='normal')
        details.delete('1.0','end')
        details.insert('1.0','\n'.join(lines))
        details.config(state='disabled')

    def step(redoing):
        if app.rom is not rom:
            dialog.destroy()
            return
        app.history_step(redoing)
        refresh()

    def restore():
        selection=tree.selection()
        if not selection or app.rom is not rom:
            return
        event=rom.history.state['audit'][int(selection[0])]
        if not app.settle():
            return
        if rom.dirty:
            messagebox.showinfo('Staged ROM changes','Write or discard staged ROM edits before restoring a backup.',parent=dialog)
            return
        if not messagebox.askyesno('Restore backup?',f'Restore the ROM to before this action?\n\n{event["description"]}\n\nThe current ROM will be backed up, and this restoration can be undone.',parent=dialog):
            return
        try:
            rom.restore_backup(rom.history.folder/event['backup'])
        except (ValueError,OSError) as error:
            messagebox.showerror('Cannot restore backup',str(error),parent=dialog)
            return
        app.refresh_after_history()
        app.status.set('Backup restored and saved to the opened ROM.')
        refresh()

    undo=ttk.Button(actions,text='Undo',command=lambda: step(False))
    undo.pack(side='left')
    redo=ttk.Button(actions,text='Redo',command=lambda: step(True))
    redo.pack(side='left',padx=8)
    ttk.Button(actions,text='Restore selected backup',command=restore).pack(side='left',padx=8)
    ttk.Button(actions,text='Refresh',command=refresh).pack(side='right')
    tree.bind('<<TreeviewSelect>>',selected)
    refresh()
