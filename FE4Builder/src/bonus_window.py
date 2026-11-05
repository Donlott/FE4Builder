from ui_common import ask_unsaved
"""Shared weapon/ring stat bonus editor."""
import tkinter as tk
from tkinter import ttk,messagebox
from item_bonuses import BonusEditor,WEAPON_NAMES,RING_BONUSES,STATS,weapon_bonuses
from bonus_profiles import BonusProfiles,FIRST,LIMIT,SIZE


class BonusWindow(tk.Toplevel):
    def __init__(self,app,kind='weapon',value=1):
        BonusProfiles(app.rom)
        super().__init__(app)
        self.app,self.rom=app,app.rom
        self.title('FE4Builder — Stat Bonus Editor');self.geometry('820x760');self.minsize(720,640)
        self.transient(app);self.grab_set()
        self.keys=[]
        frame=ttk.Frame(self,padding=16);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Stat Bonus Editor',style='Title.TLabel').pack(anchor='w')
        self.selector=ttk.Combobox(frame,state='readonly',width=66)
        self.selector.pack(fill='x',pady=12)
        self.selector.bind('<<ComboboxSelected>>',self.change)
        ttk.Label(frame,text='Shared effects: changes apply to every item referencing this bonus data.\n'
                  'Weapon profiles edit six stat increases; rings and special swords keep their\n'
                  'existing target stat and edit its amount. HP and Luck are not part of these profiles.\n'
                  'This does not change item assignments, growth rates or holy blood requirements.',justify='left').pack(anchor='w')
        self.fields=ttk.Frame(frame);self.fields.pack(fill='x',pady=12)
        self.info=tk.StringVar();ttk.Label(frame,textvariable=self.info,wraplength=720).pack(anchor='w',pady=6)
        actions=ttk.Frame(frame);actions.pack(fill='x',pady=8)
        self.add_button=ttk.Button(actions,text='Add weapon bonus...',command=self.add_dialog);self.add_button.pack(side='left')
        self.remove_button=ttk.Button(actions,text='Remove custom bonus',command=self.remove);self.remove_button.pack(side='left',padx=8)
        self.storage=tk.StringVar();ttk.Label(frame,textvariable=self.storage,wraplength=740,justify='left').pack(anchor='w',pady=(0,8))
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
        self.model=None;self.variables=[];self.load((kind,value))

    def pending(self):return [v.get() for v in self.variables]!=self.loaded

    def load(self,key=None):
        profiles=BonusProfiles(self.rom)
        options=weapon_bonuses(self.rom)
        self.keys=[('weapon',i) for i in options]+[('ring',i) for i in range(8)]
        self.selector.configure(values=[f'Weapon {i:02X} — {label}' for i,label in options.items()]+
                                [f'Ring {i:02X} — {label}' for i,label in RING_BONUSES.items()])
        key=key or getattr(self,'key',('weapon',1))
        self.key=key if key in self.keys else ('weapon',0)
        self.selector.current(self.keys.index(self.key))
        self.add_button.configure(state='normal' if len(profiles.profiles)<LIMIT-FIRST else 'disabled')
        self.remove_button.configure(state='normal' if self.key[0]=='weapon' and self.key[1]>=FIRST else 'disabled')
        count=len(profiles.profiles)
        self.storage.set(f'Custom weapon profiles: {count} / {LIMIT-FIRST} · Bonus data: {count*6:,} bytes\n'
                         f'ROM reservation: {SIZE if profiles.installed else 0:,} bytes ({SIZE:,} while enabled). '
                         'Removing the last custom profile releases it. Save size stays unchanged.')
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
        elif self.key[0]=='weapon' and self.key[1]>=FIRST:self.info.set('Independent custom weapon bonuses. No holy blood requirement or inheritance rule is added. Large bonuses may not fit the in-game numeric display.')
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
        self.refresh_dependents();self.load()
        self.info.set('Saved to the opened ROM. Automatic backup and undo history updated.')
        return True

    def settle(self):
        if not self.pending():return True
        answer=ask_unsaved(self,'Write these bonuses to the opened ROM?')
        if answer is None:return False
        return self.save() if answer else True

    def change(self,_=None):
        target=self.keys[self.selector.current()]
        self.selector.current(self.keys.index(self.key))
        if not self.settle():return
        self.load(target)

    def refresh_dependents(self):
        self.app.refresh_after_history()
        from item_window import ItemWindow
        for window in self.app.editor_windows:
            if isinstance(window,ItemWindow) and window.winfo_exists() and window.rom is self.rom and not window.pending():
                window.populate(window.current)

    def structural(self,action,description,selected):
        if self.app.rom is not self.rom:
            messagebox.showerror('ROM changed','Reopen Stat Bonus Editor for the current ROM.',parent=self);return False
        if not self.settle() or not self.app.settle():return False
        before=bytes(self.rom.data)
        try:
            result=action(BonusProfiles(self.rom))
            self.rom.save_original(description)
        except (ValueError,OSError) as error:
            self.rom.data[:]=before
            messagebox.showerror('Cannot change bonus profiles',str(error),parent=self);return False
        self.refresh_dependents();self.load(('weapon',result if selected is None else selected))
        self.info.set(description+' written with an automatic backup.')
        return True

    def add_profile(self,values=None,source=0,profile=None):
        return self.structural(lambda model:model.add(values,source=source,profile=profile),'Add weapon bonus profile',None)

    def remove(self):
        if self.key[0]!='weapon' or self.key[1]<FIRST:return False
        value=self.key[1]
        if not self.settle():return False
        users=BonusProfiles(self.rom).users(value)
        if users:
            messagebox.showinfo('Bonus is still used','Reassign these items before removing this bonus:\n\n'+'\n'.join(users),parent=self);return False
        if not messagebox.askyesno('Remove custom bonus',f'Remove bonus {value:02X}? Other profile IDs stay unchanged.',parent=self):return False
        return self.structural(lambda model:model.remove(value),'Remove weapon bonus profile',0)

    def add_dialog(self):
        if not self.settle():return
        profiles=BonusProfiles(self.rom)
        free=next((i for i in range(FIRST,LIMIT) if i not in profiles.profiles),None)
        if free is None:return
        dialog=tk.Toplevel(self);dialog.title('Add weapon stat bonus');dialog.transient(self);dialog.grab_set();dialog.resizable(False,False)
        body=ttk.Frame(dialog,padding=18);body.pack(fill='both',expand=True)
        ttk.Label(body,text='New profile ID (hex)').grid(row=0,column=0,sticky='w',pady=5)
        identity=tk.StringVar(value=f'{free:02X}');ttk.Entry(body,textvariable=identity,width=12).grid(row=0,column=1,sticky='w',pady=5)
        options=weapon_bonuses(self.rom);ids=list(options)
        ttk.Label(body,text='Copy bonuses from').grid(row=1,column=0,sticky='w',pady=5)
        source=ttk.Combobox(body,state='readonly',values=[f'{i:02X} {label}' for i,label in options.items()],width=46)
        source.current(ids.index(self.key[1]) if self.key[0]=='weapon' and self.key[1] in ids else 0)
        source.grid(row=1,column=1,sticky='ew',pady=5)
        variables=[]
        for row,stat in enumerate(STATS,2):
            ttk.Label(body,text=stat).grid(row=row,column=0,sticky='w',pady=4)
            var=tk.StringVar(value='0');variables.append(var)
            ttk.Spinbox(body,from_=0,to=255,textvariable=var,width=12).grid(row=row,column=1,sticky='w',pady=4)
        def copy(*_):
            try:
                model=BonusEditor(self.rom,'weapon',ids[source.current()]);values=dict(zip(model.fields,model.values))
                for stat,var in zip(STATS,variables):var.set(str(values.get(stat,0)))
            except ValueError as error:messagebox.showerror('Cannot copy bonuses',str(error),parent=dialog)
        source.bind('<<ComboboxSelected>>',copy);copy()
        ttk.Label(body,text='Creates an independent six-stat profile. Assign it to weapons in Item Editor.\n'
                  'The first addition installs the bonus lookup patch; save format and inheritance stay unchanged.',
                  wraplength=560,justify='left').grid(row=8,column=0,columnspan=2,sticky='w',pady=12)
        def close():
            dialog.destroy()
            if self.winfo_exists():self.grab_set()
        def apply():
            try:profile=int(identity.get().strip(),16);values=[int(v.get()) for v in variables]
            except ValueError:messagebox.showerror('Invalid bonuses','Enter a hexadecimal ID and whole stat bonus amounts.',parent=dialog);return
            if self.add_profile(values,profile=profile):close()
        buttons=ttk.Frame(body);buttons.grid(row=9,column=0,columnspan=2,sticky='ew')
        ttk.Button(buttons,text='Add & write to ROM',command=apply).pack(side='left')
        ttk.Button(buttons,text='Cancel',command=close).pack(side='right')
        dialog.protocol('WM_DELETE_WINDOW',close)

    def reload(self):
        if not self.pending() or messagebox.askyesno('Reload bonuses','Discard the unwritten bonus edits?',parent=self):self.load()

    def history(self,redo):
        if self.app.rom is not self.rom:return 'break'
        if self.settle():self.app.history_step(redo);self.refresh_dependents();self.load()
        return 'break'

    def close(self):
        if self.settle():self.destroy()


def open_bonus_window(app,kind='weapon',value=1):
    if not app.rom:
        messagebox.showinfo('Stat Bonus Editor','Open a ROM first.',parent=app);return
    if not app.settle():return
    try:return BonusWindow(app,kind,value)
    except ValueError as error:messagebox.showerror('Cannot open Stat Bonus Editor',str(error),parent=app);return None
