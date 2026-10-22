from ui_common import ask_unsaved
"""Shared weapon/ring stat bonus editor."""
import tkinter as tk
from tkinter import ttk,messagebox
from item_bonuses import BonusEditor,WEAPON_NAMES,RING_BONUSES


class BonusWindow(tk.Toplevel):
    def __init__(self,app,kind='weapon',value=1):
        super().__init__(app)
        self.app,self.rom=app,app.rom
        self.title('FE4Builder — Stat Bonus Editor');self.geometry('800x620');self.minsize(680,540)
        self.transient(app);self.grab_set()
        self.keys=[('weapon',i) for i in range(16)]+[('ring',i) for i in range(8)]
        frame=ttk.Frame(self,padding=16);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Stat Bonus Editor',style='Title.TLabel').pack(anchor='w')
        self.selector=ttk.Combobox(frame,state='readonly',width=66,values=
            [f'Weapon {i:02X} — {name}' for i,name in enumerate(WEAPON_NAMES)]+
            [f'Ring {i:02X} — {label.split(" ",1)[-1] if i else "None"}' for i,label in RING_BONUSES.items()])
        self.selector.pack(fill='x',pady=12)
        self.selector.current(self.keys.index((kind,value)) if (kind,value) in self.keys else 1)
        self.selector.bind('<<ComboboxSelected>>',self.change)
        ttk.Label(frame,text='Shared effects: changes apply to every item referencing this bonus data.\n'
                  'Weapon profiles edit six stat increases; rings and special swords keep their\n'
                  'existing target stat and edit its amount. HP and Luck are not part of these profiles.\n'
                  'This does not change item assignments, growth rates or holy blood requirements.',justify='left').pack(anchor='w')
        self.fields=ttk.Frame(frame);self.fields.pack(fill='x',pady=12)
        self.info=tk.StringVar();ttk.Label(frame,textvariable=self.info,wraplength=720).pack(anchor='w',pady=6)
        ttk.Label(frame,text='Items using this effect (including duplicate editor views only once)').pack(anchor='w')
        users_frame=ttk.Frame(frame);users_frame.pack(fill='both',expand=True,pady=8)
        self.users=tk.Listbox(users_frame,height=5);self.users.pack(side='left',fill='both',expand=True)
        scrollbar=ttk.Scrollbar(users_frame,command=self.users.yview)
        scrollbar.pack(side='right',fill='y');self.users.config(yscrollcommand=scrollbar.set)
        bar=ttk.Frame(frame);bar.pack(fill='x',pady=8)
        ttk.Button(bar,text='Undo',command=lambda:self.history(False)).pack(side='left')
        ttk.Button(bar,text='Redo',command=lambda:self.history(True)).pack(side='left',padx=6)
        ttk.Button(bar,text='Reload',command=self.reload).pack(side='left',padx=6)
        self.save_button=ttk.Button(bar,text='Write bonuses to ROM',command=self.save);self.save_button.pack(side='right')
        ttk.Button(bar,text='Close',command=self.close).pack(side='right',padx=6)
        self.bind('<Control-z>',lambda _:self.history(False));self.bind('<Control-y>',lambda _:self.history(True))
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.model=None;self.variables=[];self.load()

    def pending(self):return [v.get() for v in self.variables]!=self.loaded

    def load(self):
        self.key=self.keys[self.selector.current()]
        for widget in self.fields.winfo_children():widget.destroy()
        self.variables=[];self.loaded=[];self.model=None;self.users.delete(0,'end')
        try:self.model=BonusEditor(self.rom,*self.key)
        except ValueError as error:
            self.info.set(str(error));self.save_button.config(state='disabled');return
        for row,(field,value) in enumerate(zip(self.model.fields,self.model.values)):
            ttk.Label(self.fields,text=field).grid(row=row,column=0,sticky='w',pady=3)
            variable=tk.StringVar(value=str(value));self.variables.append(variable)
            ttk.Spinbox(self.fields,from_=0,to=3 if field=='Movement' else 255,textvariable=variable,width=8).grid(row=row,column=1,padx=14,pady=3)
        self.loaded=[v.get() for v in self.variables]
        self.save_button.config(state='normal' if self.variables else 'disabled')
        if not self.variables:self.info.set('None has no editable effect. Choose a nonzero profile to edit its bonuses.')
        elif self.key==('ring',6):self.info.set('Movement supports +0 to +3. Larger bonuses can exceed the game’s movement lookup. Both movement routines are updated together.')
        elif self.model.size==2:self.info.set('Edits a shared amount in verified native game code. Other effect properties remain the same. Large stat bonuses may not fit the in-game numeric display.')
        else:self.info.set('Edits only the six weapon bonus bytes; holy blood growth bonuses stay unchanged. Large bonuses may not fit the in-game numeric display.')
        for name in self.model.users():self.users.insert('end',name)

    def save(self):
        if self.app.rom is not self.rom:
            messagebox.showerror('ROM changed','Reopen the bonus editor for the current ROM.',parent=self);return False
        if self.model is None:return False
        before=bytes(self.rom.data)
        try:
            values=[int(v.get()) for v in self.variables]
            details=self.model.write(values)
            self.rom.save_original(f'Stat bonuses: {self.model.kind} {self.model.value:02X} {self.model.name}',details)
        except (ValueError,OSError) as error:
            self.rom.data[:]=before
            messagebox.showerror('Cannot write stat bonuses',str(error),parent=self);return False
        self.app.refresh_after_history();self.load()
        self.info.set('Saved to the opened ROM. Automatic backup and undo history updated.')
        return True

    def settle(self):
        if not self.pending():return True
        answer=ask_unsaved(self,'Write these bonuses to the opened ROM?')
        if answer is None:return False
        return self.save() if answer else True

    def change(self,_=None):
        target=self.selector.current()
        self.selector.current(self.keys.index(self.key))
        if not self.settle():return
        self.selector.current(target);self.load()

    def reload(self):
        if not self.pending() or messagebox.askyesno('Reload bonuses','Discard the unwritten bonus edits?',parent=self):self.load()

    def history(self,redo):
        if self.app.rom is not self.rom:return 'break'
        if self.settle():self.app.history_step(redo);self.load()
        return 'break'

    def close(self):
        if self.settle():self.destroy()


def open_bonus_window(app,kind='weapon',value=1):
    if not app.rom:
        messagebox.showinfo('Stat Bonus Editor','Open a ROM first.',parent=app);return
    if not app.settle():return
    return BonusWindow(app,kind,value)
