"""Known module references for shared data, without changing record search behavior."""
import tkinter as tk
from tkinter import ttk
from rom import character_modules, category_modules
from linked_editors import field_target

class UsageIndex:
    def __init__(self,rom):
        self.rom=rom;self.stamp=id(rom.original);self.records=None;self.targets={}
    def target(self,field,value):
        key=(field.reference,value)
        if key not in self.targets:self.targets[key]=field_target(self.rom,field,value)
        return self.targets[key]
    def for_record(self,module,index,values):
        targets={(module.name,index)}
        if 'Portrait Definition' in module.name:targets.add(('__portrait__',index))
        slots=set()
        for field,value in zip(module.fields,values):
            try:
                target=self.target(field,value)
                if target:targets.add((target[1],target[2]))
            except ValueError:pass
            if field.reference=='FE4 Player Equipment.txt' and 1<=value<=142:slots.add(value)
        rows=[]
        if self.records is None:self._build()
        for label,target,refs,stored_slots in self.records:
            reasons=[name for name,ref in refs if ref in targets]
            reasons.extend(name+' (shared inventory slot)' for name,value in stored_slots if value in slots)
            if reasons:rows.append((label+': '+', '.join(dict.fromkeys(reasons)),target))
        return rows
    def _build(self):
        self.records=[];seen=set()
        for mode,tables in [('Character Editor',character_modules()),('Enemy Editor',category_modules('Enemy Editor')),('Holy Character Editor',category_modules('Holy Character Editor')),('Shop Editor',category_modules('Shop Editor'))]:
            for table in tables:
                for record in range(table.count):
                    address=self.rom.address(table,record)
                    if address in seen:continue
                    seen.add(address);refs=[];slots=[]
                    for field,value in zip(table.fields,self.rom.values(table,record)):
                        try:target=self.target(field,value)
                        except ValueError:target=None
                        if target:refs.append((field.name,(target[1],target[2])))
                        if field.reference=='FE4 Player Equipment.txt':slots.append((field.name,value))
                    values={field.name:value for field,value in zip(table.fields,self.rom.values(table,record))}
                    character=next((values[k] for k in ('Char no.','Chararacter Number','Character Number') if k in values),None)
                    if character is not None:
                        from portraits import character_portrait_id
                        try:refs.append(('Portrait',('__portrait__',character_portrait_id(self.rom,character,values.get('Class')))))
                        except ValueError:pass
                    label=table.names[record] if record<len(table.names) else f'Record {record:03X}'
                    for field,value in zip(table.fields,self.rom.values(table,record)):
                        if field.name in ('Char no.','Chararacter Number','Character Number'):label=field.options.get(value,label)
                    if 'Char Name' in values and values['Char Name']<63:
                        from names import NameEditor
                        try:label=NameEditor(self.rom,values['Char Name']).current
                        except ValueError:pass
                    self.records.append((label+' — '+table.name,(mode,table.name,record),refs,slots))
    def summary(self,module,index,values):
        # The list is intentionally limited to stored module references; events may add users.
        if 'Portrait Definition' in module.name:
            from validation import shared_notes
            return ' '.join(shared_notes(self.rom,module,index)[:2])
        count=len(self.for_record(module,index,values))
        return f'Known related records: {count}. Open affected records for shared class, item or inventory references; events may add users.'

def show_users(app,rows):
    dialog=tk.Toplevel(app);dialog.title('Known affected records');dialog.geometry('800x440')
    ttk.Label(dialog,text='Shared profile users. Changing a character assignment affects that record; editing the linked profile affects its users. Events may add references.',padding=10).pack(anchor='w')
    frame=ttk.Frame(dialog);frame.pack(fill='both',expand=True)
    listing=tk.Listbox(frame);bar=ttk.Scrollbar(frame,command=listing.yview);listing.config(yscrollcommand=bar.set)
    bar.pack(side='right',fill='y');listing.pack(fill='both',expand=True)
    for label,_ in rows:listing.insert('end',label)
    def open_record(*_):
        selected=listing.curselection()
        if selected and app.settle_link():
            target=rows[selected[0]][1];context=app.navigation_context();dialog.destroy();app.go_to_record(*target)
            app.navigation.append(context);app.back_button.config(state='normal')
    listing.bind('<Double-1>',open_record)
    ttk.Button(dialog,text='Open selected record',command=open_record).pack(pady=8)
    from ui_common import fit_window
    fit_window(dialog)
