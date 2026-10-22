"""Install optional ROM code changes through the normal backup/history path."""
import tkinter as tk
from tkinter import ttk,messagebox
import growth_patch


def save_patch(app,remove=False):
    rom=app.rom
    before=bytes(rom.data)
    try:
        updating=not remove and growth_patch.version(rom)==1
        (growth_patch.uninstall if remove else growth_patch.install)(rom)
        rom.save_original(('Remove' if remove else 'Update' if updating else 'Install')+' Display growth rates',
                          ['Y toggles effective growth percentages on the normal player unit status screen.'])
    except Exception:
        rom.data[:]=before
        raise
    app.refresh_after_history()


def open_patch_window(app):
    if not app.rom:
        messagebox.showinfo('Patches','Open a ROM first.',parent=app)
        return
    if not app.settle():return
    window=tk.Toplevel(app)
    window.title('FE4Builder — Patches')
    window.resizable(False,False)
    frame=ttk.Frame(window,padding=22);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Display growth rates',font=('Segoe UI',15,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Press SNES Y on a player unit’s normal status screen to show effective\n'
              'growth percentages. Press Y again to return to stats. HP growth appears\n'
              'in the HP field; the other seven growths appear below “Growths %”.\n\n'
              'Uses the game’s growth calculations, including holy blood and inherited\n'
              'growths. Enemy records do not have individual player growths.\n\n'
              'Supports the 8 MiB Project Naga beta 7 ROM profile. Installation checks\n'
              'the required game code and available storage; it does not expand the ROM.\n'
              'Writes to the opened ROM with an automatic backup and undo history.',
              justify='left').pack(anchor='w',pady=14)
    status=tk.StringVar();ttk.Label(frame,textvariable=status).pack(anchor='w',pady=8)
    buttons=ttk.Frame(frame);buttons.pack(fill='x')
    def refresh():
        version=growth_patch.version(app.rom)
        active=version!=0
        status.set('Installed — update available (fixes boosted-stat display)' if version==1 else 'Installed' if active else 'Not installed')
        install.config(text='Update: Display growth rates' if version==1 else 'Install: Display growth rates',
                       state='disabled' if version==2 else 'normal')
        remove.config(state='normal' if active else 'disabled')
    def change(removing=False):
        if not app.settle():return
        try:save_patch(app,removing)
        except Exception as exc:messagebox.showerror('Patch not saved',str(exc),parent=window)
        refresh()
    install=ttk.Button(buttons,text='Install: Display growth rates',command=change);install.pack(side='left')
    remove=ttk.Button(buttons,text='Remove patch',command=lambda:change(True));remove.pack(side='left',padx=8)
    ttk.Button(buttons,text='Close',command=window.destroy).pack(side='right')
    window.bind('<FocusIn>',lambda event:refresh())
    refresh()
    return window
