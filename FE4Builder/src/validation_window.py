"""Read-only diagnostics and shared-data explanations."""
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

def show_report(app,title,issues,notes=()):
    window=tk.Toplevel(app);window.title('FE4Builder - '+title)
    window.geometry('880x650');window.minsize(700,500);window.transient(app)
    ttk.Label(window,text=title,style='Title.TLabel',padding=12).pack(anchor='w')
    text=ScrolledText(window,wrap='word',font=('Segoe UI',10),padx=12,pady=10)
    text.pack(fill='both',expand=True,padx=12,pady=(0,12))
    text.tag_configure('Error',foreground='#b12b2b')
    text.tag_configure('Warning',foreground='#926400')
    if issues:
        for issue in issues:text.insert('end',f'{issue.severity} - {issue.field}: {issue.message}\n\n',issue.severity)
    else:text.insert('end','No issues found by the implemented checks.\n\n')
    if notes:
        text.insert('end','Shared data and scope\n\n')
        for note in notes:text.insert('end',note+'\n\n')
    text.insert('end','Warnings do not block saving. Errors do. Checks are limited to the supported ROM profile; inheritance, events, personal weapon restrictions and undocumented pointer formats need manual review.')
    text.configure(state='disabled')
    ttk.Button(window,text='Close',command=window.destroy).pack(anchor='e',padx=12,pady=(0,12))
    return window
