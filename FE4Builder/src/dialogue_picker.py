"""Search dialogue names and readable text before choosing an event pointer."""
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

class DialoguePicker(tk.Toplevel):
    def __init__(self,parent,choices,on_choose):
        super().__init__(parent);self.parent=parent;self.choices=choices;self.on_choose=on_choose;self.visible=[]
        self.title('Find dialogue');self.geometry('900x650');self.minsize(650,450);self.transient(parent);self.grab_set()
        filters=ttk.Frame(self,padding=10);filters.pack(fill='x')
        self.chapter=ttk.Combobox(filters,state='readonly',values=['All dialogue']+list(dict.fromkeys(o['entry']['group'] for o in choices)),width=20);self.chapter.current(0);self.chapter.pack(side='left');self.chapter.bind('<<ComboboxSelected>>',self.populate)
        self.search=tk.StringVar();entry=ttk.Entry(filters,textvariable=self.search);entry.pack(side='left',fill='x',expand=True,padx=10);entry.focus_set();self.search.trace_add('write',self.populate)
        ttk.Label(self,text='Search scene name or dialogue text. Selecting a result previews it; Choose stages its pointer.',padding=(10,0)).pack(anchor='w')
        frame=ttk.Frame(self,padding=10);frame.pack(fill='both',expand=True)
        self.list=tk.Listbox(frame,exportselection=False,height=13);bar=ttk.Scrollbar(frame,command=self.list.yview);bar.pack(side='right',fill='y');self.list.config(yscrollcommand=bar.set);self.list.pack(fill='both',expand=True);self.list.bind('<<ListboxSelect>>',self.preview);self.list.bind('<Double-1>',self.choose)
        self.text=ScrolledText(self,height=10,wrap='word',state='disabled');self.text.pack(fill='both',expand=True,padx=10,pady=5)
        actions=ttk.Frame(self,padding=10);actions.pack(fill='x');self.count=tk.StringVar();ttk.Label(actions,textvariable=self.count).pack(side='left');ttk.Button(actions,text='Choose dialogue',command=self.choose).pack(side='right');ttk.Button(actions,text='Cancel',command=self.close).pack(side='right',padx=8)
        self.protocol('WM_DELETE_WINDOW',self.close);self.populate()
    def populate(self,*_):
        query=self.search.get().casefold();chapter=self.chapter.get()
        self.visible=[o for o in self.choices if (chapter=='All dialogue' or o['entry']['group']==chapter) and query in (o['label']+' '+o['text']).casefold()]
        self.list.delete(0,'end')
        for o in self.visible:self.list.insert('end',o['label'])
        self.count.set(f'{len(self.visible)} scenes');self.preview()
    def preview(self,_=None):
        selection=self.list.curselection();value=self.visible[selection[0]]['text'] if selection else 'Select a scene to preview its text.'
        self.text.config(state='normal');self.text.delete('1.0','end');self.text.insert('1.0',value);self.text.config(state='disabled')
    def choose(self,_=None):
        if not self.list.curselection():return
        self.on_choose(self.visible[self.list.curselection()[0]]);self.close()
    def close(self):
        self.destroy()
        if self.parent.winfo_exists():self.parent.grab_set()
