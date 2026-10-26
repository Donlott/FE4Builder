"""Configure an existing emulator; no downloads or game files are required."""
import os
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from emulator import load_config,save_config,default_config

def configure_emulator(app,parent=None):
    owner=parent or app
    try:config=load_config()
    except ValueError as error:
        messagebox.showerror('Emulator settings',str(error),parent=owner);config=default_config()
    dialog=tk.Toplevel(owner);dialog.title('FE4Builder - Emulator settings')
    dialog.geometry('760x420');dialog.minsize(660,380)
    dialog.transient(owner);dialog.grab_set()
    body=ttk.Frame(dialog,padding=16);body.pack(fill='both',expand=True)
    ttk.Label(body,text='Emulator executable').pack(anchor='w')
    row=ttk.Frame(body);row.pack(fill='x',pady=(4,12))
    executable=tk.StringVar(value=config['executable'])
    ttk.Entry(row,textvariable=executable).pack(side='left',fill='x',expand=True)
    def browse():
        path=filedialog.askopenfilename(parent=dialog,title='Choose emulator',filetypes=([('Windows executable','*.exe'),('All files','*')] if os.name=='nt' else [('Executable or script','*')]))
        if path:executable.set(path)
    ttk.Button(row,text='Browse...',command=browse).pack(side='right',padx=(8,0))
    ttk.Label(body,text='Arguments (one per line)').pack(anchor='w')
    arguments=tk.Text(body,height=5,wrap='none');arguments.pack(fill='both',expand=True,pady=4)
    arguments.insert('1.0','\n'.join(config['arguments']))
    ttk.Label(body,text='Use {rom} for the saved ROM path. Leave {rom} alone on its line for Snes9x.\nPaths containing spaces do not need quotes. If {rom} is omitted, the ROM is appended as the last argument.',wraplength=710).pack(anchor='w',pady=10)
    result=None
    def save():
        nonlocal result
        try:result=save_config({'executable':executable.get().strip(),'arguments':[line.strip() for line in arguments.get('1.0','end').splitlines() if line.strip()]})
        except (OSError,ValueError) as error:messagebox.showerror('Emulator settings',str(error),parent=dialog);return
        dialog.destroy()
    buttons=ttk.Frame(body);buttons.pack(fill='x')
    ttk.Button(buttons,text='Save settings',command=save).pack(side='right')
    ttk.Button(buttons,text='Cancel',command=dialog.destroy).pack(side='right',padx=8)
    dialog.bind('<Escape>',lambda e:dialog.destroy())
    dialog.wait_window()
    if owner.winfo_exists() and owner is not app:owner.grab_set()
    return result
