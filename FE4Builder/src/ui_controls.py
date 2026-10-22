"""Named flag/blood controls that preserve unsupported bits and the existing ROM encoding."""
import tkinter as tk
from tkinter import ttk,messagebox
from rom import number

def skill_bits(field):
    return {1<<i:field.options[1<<i] for i in range(field.size*8) if 1<<i in field.options
            and field.options[1<<i].strip() and not field.options[1<<i].strip().lower().startswith(('unknown','unused','?'))}

def blood_pairs(field):
    return {i:field.options[1<<i].rstrip('+').strip() for i in range(0,field.size*8,2)
            if (1<<i) in field.options and (2<<i) in field.options}

def set_skills(original,bits,selected):
    mask=sum(bits)
    return (original&~mask)|sum(bit for bit in bits if bit in selected)

def set_blood(original,pairs,grades):
    result=original
    for shift in pairs:
        grade=grades[shift]
        if grade not in (0,1,2,3):raise ValueError('Unsupported holy blood grade.')
        result=(result&~(3<<shift))|(grade<<shift)
    return result

class FlagPicker(ttk.Frame):
    def __init__(self,parent,variable,options,field):
        super().__init__(parent);self.variable=variable;self.options=options;self.field=field
        self.blood=field.name.startswith('Blood');self.bits=blood_pairs(field) if self.blood else skill_bits(field)
        self.summary=tk.StringVar();self.button=ttk.Button(self,textvariable=self.summary,command=self.open)
        self.button.pack(fill='x');self.variable.trace_add('write',self.refresh);self.refresh()

    def value(self):
        text=self.variable.get()
        return self.options[text] if text in self.options else number(text.strip())

    def refresh(self,*_):
        try:
            value=self.value();parts=[]
            for bit,name in self.bits.items():
                if self.blood:
                    grade=value>>bit&3
                    if grade:parts.append(name+(' (major)' if grade==2 else ' (minor)' if grade==1 else ' (both flags)'))
                elif value&bit:parts.append(name)
            mask=sum(3<<i for i in self.bits) if self.blood else sum(self.bits)
            if value&~mask:parts.append(f'Other flags 0x{value&~mask:X}')
            self.summary.set((' • '.join(parts[:2])+f' (+{len(parts)-2} more)' if len(parts)>2 else ' • '.join(parts)) or 'None — choose…')
        except ValueError:self.summary.set('Invalid raw value — edit…')

    def open(self):
        try:initial=self.value()
        except ValueError:initial=0
        dialog=tk.Toplevel(self);dialog.title('Holy blood' if self.blood else 'Skills / flags')
        dialog.transient(self.winfo_toplevel());dialog.grab_set();dialog.resizable(False,False)
        body=ttk.Frame(dialog,padding=14);body.pack(fill='both',expand=True)
        raw=tk.StringVar(value=hex(initial));choices={};busy=[False]
        ttk.Label(body,text='Choose each lineage’s grade.' if self.blood else 'Select individual skills. Other bits are preserved.').pack(anchor='w',pady=(0,10))
        for key,name in self.bits.items():
            row=ttk.Frame(body);row.pack(fill='x',pady=3)
            if self.blood:
                ttk.Label(row,text=name,width=18).pack(side='left')
                var=tk.StringVar();choices[key]=var
                combo=ttk.Combobox(row,state='readonly',textvariable=var,values=['None','Minor','Major','Both flags (existing / advanced)'],width=30)
                combo.pack(side='left');combo.bind('<<ComboboxSelected>>',lambda _:changed())
            else:
                var=tk.BooleanVar();choices[key]=var;ttk.Checkbutton(row,text=name,variable=var,command=lambda:changed()).pack(anchor='w')
        note=tk.StringVar();ttk.Label(body,textvariable=note,wraplength=410).pack(anchor='w',pady=8)
        advanced=ttk.Frame(body)
        def toggle():
            if advanced.winfo_manager():advanced.pack_forget()
            else:advanced.pack(fill='x',before=buttons,pady=8)
        ttk.Button(body,text='Advanced / raw value',command=toggle).pack(anchor='w')
        ttk.Label(advanced,text='Decimal or 0x hexadecimal').pack(anchor='w');ttk.Entry(advanced,textvariable=raw).pack(fill='x')
        def changed():
            if busy[0]:return
            try:value=number(raw.get())
            except ValueError:value=initial
            if self.blood:value=set_blood(value,self.bits,{k:['None','Minor','Major','Both flags (existing / advanced)'].index(v.get()) for k,v in choices.items()})
            else:value=set_skills(value,self.bits,{k for k,v in choices.items() if v.get()})
            raw.set(hex(value))
        def sync(*_):
            try:value=number(raw.get())
            except ValueError:note.set('Enter a decimal number or a 0x hexadecimal value.');return
            busy[0]=True
            for key,var in choices.items():
                var.set(['None','Minor','Major','Both flags (existing / advanced)'][value>>key&3] if self.blood else bool(value&key))
            busy[0]=False
            mask=sum(3<<i for i in self.bits) if self.blood else sum(self.bits)
            note.set(f'Other flags preserved: 0x{value&~mask:X}. Change raw data only deliberately.' if value&~mask else f'Encoded value: 0x{value:X}')
        def commit():
            try:
                value=number(raw.get())
                if not 0<=value<1<<(8*self.field.size):raise ValueError('Value is outside this field’s storage range.')
            except ValueError as error:messagebox.showerror('Invalid value',str(error),parent=dialog);return
            self.variable.set(next((name for name,v in self.options.items() if v==value),str(value)));dialog.destroy()
        buttons=ttk.Frame(body);buttons.pack(fill='x',pady=(12,0))
        ttk.Button(buttons,text='Apply to draft',command=commit).pack(side='right');ttk.Button(buttons,text='Cancel',command=dialog.destroy).pack(side='right',padx=6)
        raw.trace_add('write',sync);sync();dialog.bind('<Escape>',lambda _:dialog.destroy())
        dialog.bind('<Destroy>',lambda event:self.winfo_toplevel().grab_set() if event.widget is dialog and self.winfo_exists() and isinstance(self.winfo_toplevel(),tk.Toplevel) else None)

