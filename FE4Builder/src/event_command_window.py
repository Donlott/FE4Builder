"""Prologue command editor: edit verified operands, keep the surrounding script intact."""
import tkinter as tk
from tkinter import ttk,messagebox
from rom import number
from events import hex_dump
from event_commands import EventCommands,catalogue,FIELDS,HELP,schema,character_options,audio_kind,audio_options,deployment_options
from ui_common import ask_unsaved,scrollable_frame

class EventCommandWindow(tk.Toplevel):
    def __init__(self,app,event_id=None):
        super().__init__(app);self.app=app;self.rom=app.rom;self.current=None;self.model=None;self.command=None;self.variables=[];self.field_options=[];self.drafts={};self.loaded={}
        self.title('FE4Builder — Event Editor (Prologue)');self.geometry('1200x780');self.minsize(940,620)
        self.names=character_options(self.rom)
        self.transient(app);self.grab_set()
        top=ttk.Frame(self,padding=12);top.pack(fill='x')
        ttk.Label(top,text='Event Editor · Prologue',style='Title.TLabel').pack(side='left')
        ttk.Button(top,text='Write to ROM',command=self.save).pack(side='right')
        ttk.Button(top,text='Save & Launch (F5)',command=self.launch).pack(side='right',padx=8)
        ttk.Label(self,text='Edit unit deployments, music, sound commands, sprite preparation, cameras, pauses and fades. Other commands are read-only.\n'
                  'Script length, command order, jumps and pointers are preserved. Test edited scenes in-game.',padding=(12,0)).pack(anchor='w')
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=12,pady=8)
        left=ttk.Frame(body);body.add(left,weight=1)
        ttk.Label(left,text='Prologue scripts').pack(anchor='w')
        frame=ttk.Frame(left);frame.pack(fill='both',expand=True)
        self.list=tk.Listbox(frame,exportselection=False,width=32);bar=ttk.Scrollbar(frame,command=self.list.yview)
        bar.pack(side='right',fill='y');self.list.config(yscrollcommand=bar.set);self.list.pack(fill='both',expand=True)
        self.list.bind('<<ListboxSelect>>',self.select)
        right=ttk.Frame(body);body.add(right,weight=3)
        self.heading=tk.StringVar();ttk.Label(right,textvariable=self.heading,font=('Segoe UI',12,'bold')).pack(anchor='w')
        frame=ttk.Frame(right);frame.pack(fill='both',expand=True,pady=8)
        self.commands=ttk.Treeview(frame,columns=('state','address','command'),show='headings',selectmode='browse',height=9)
        for name,title,width in [('state','Capability',85),('address','PC address',85),('command','Command / loaded parameters',500)]:
            self.commands.heading(name,text=title);self.commands.column(name,width=width,stretch=name=='command')
        bar=ttk.Scrollbar(frame,command=self.commands.yview);bar.pack(side='right',fill='y')
        self.commands.config(yscrollcommand=bar.set);self.commands.pack(fill='both',expand=True)
        self.commands.bind('<<TreeviewSelect>>',self.select_command)
        shell=ttk.Frame(right,height=190);shell.pack(fill='both',expand=True)
        self.parameters=scrollable_frame(shell,padding=8)
        self.command_heading=tk.StringVar();ttk.Label(self.parameters,textvariable=self.command_heading,font=('Segoe UI',11,'bold')).pack(anchor='w')
        self.help=tk.StringVar();self.help_label=ttk.Label(self.parameters,textvariable=self.help,wraplength=680)
        self.fields=ttk.Frame(self.parameters);self.fields.pack(fill='x')
        self.help_label.pack(anchor='w',pady=8)
        self.raw=tk.StringVar();ttk.Label(self.parameters,textvariable=self.raw,font=('Consolas',10),wraplength=680).pack(anchor='w',pady=8)
        actions=ttk.Frame(right);actions.pack(fill='x',pady=8)
        self.dialogue_button=ttk.Button(actions,text='Open in Dialogue Editor…',command=self.open_dialogue,state='disabled');self.dialogue_button.pack(side='right',padx=6)
        self.ai_button=ttk.Button(actions,text='Inspect selected AI…',command=self.inspect_ai,state='disabled');self.ai_button.pack(side='right',padx=6)
        self.audio_button=ttk.Button(actions,text='Preview audio…',command=self.preview_audio,state='disabled');self.audio_button.pack(side='right')
        ttk.Button(actions,text='Reload script',command=self.reload).pack(side='left')
        ttk.Button(actions,text='Undo ROM',command=lambda:self.history(False)).pack(side='left',padx=6)
        ttk.Button(actions,text='Redo ROM',command=lambda:self.history(True)).pack(side='left')
        ttk.Button(actions,text='View event / linked editors',command=self.open_viewer).pack(side='left',padx=6)
        self.status=tk.StringVar();ttk.Label(self,textvariable=self.status,padding=8,wraplength=1120,relief='sunken').pack(side='bottom',fill='x')
        self.visible=list(range(len(catalogue()['entries'])))
        for e in catalogue()['entries']:
            count=sum(c['editable'] for c in e['commands']);self.list.insert('end',f'{e["id"]:03X} · {e["label"]} ({count})')
        index=next((i for i,e in enumerate(catalogue()['entries']) if e['id']==event_id),0)
        self.list.selection_set(index);self.load(index)
        self.protocol('WM_DELETE_WINDOW',self.close);self.bind('<F5>',lambda _:self.launch())

    def remember_command(self):
        if self.command in self.drafts:
            self.drafts[self.command]=tuple(str(options.get(var.get(),var.get())) for var,options in zip(self.variables,self.field_options))
            item=str(self.command)
            if self.commands.exists(item):self.commands.set(item,'state','Editable *' if self.drafts[self.command]!=self.loaded.get(self.command) else 'Editable')
    def pending(self):
        self.remember_command();return self.model is not None and self.drafts!=self.loaded
    def settle(self):
        if not self.pending():return True
        answer=ask_unsaved(self,'Write the staged Prologue command changes to the opened ROM?')
        return False if answer is None else self.save() if answer else True
    def select(self,_=None):
        selected=self.list.curselection()
        if not selected:return
        index=self.visible[selected[0]]
        if index==self.current:return
        if self.settle():self.load(index)
        else:
            self.list.selection_clear(0,'end');self.list.selection_set(self.visible.index(self.current))
    def load(self,index):
        self.current=index;self.model=None;self.command=None;self.variables=[];self.field_options=[];self.drafts={};self.loaded={}
        self.commands.delete(*self.commands.get_children());self.command_heading.set('');self.help.set('');self.raw.set('')
        for widget in self.fields.winfo_children():widget.destroy()
        self.audio_button.config(state='disabled');self.ai_button.config(state='disabled');self.dialogue_button.config(state='disabled')
        self.heading.set(catalogue()['entries'][index]['label'])
        try:self.model=EventCommands(self.rom,index)
        except ValueError as error:self.status.set('Editing disabled: '+str(error));return
        for i,c in enumerate(self.model.commands):
            if c['editable']:self.drafts[i]=tuple(map(str,self.model.values(i)))
            self.commands.insert('','end',iid=str(i),values=('Editable' if c['editable'] else 'Read-only',f'{self.model.profile["start"]+c["offset"]:06X}',self.model.describe(i)))
        self.loaded=self.drafts.copy()
        selected=next(iter(self.drafts),0);self.commands.selection_set(str(selected));self.commands.see(str(selected));self.select_command()
        self.status.set('Loaded live operands from a verified layout. Edits remain pending until Write to ROM. No commands are inserted or removed.')
    def select_command(self,_=None):
        selected=self.commands.selection()
        if not selected or self.model is None:return
        index=int(selected[0])
        if index==self.command:return
        self.remember_command();self.command=index;self.variables=[];self.field_options=[]
        for widget in self.fields.winfo_children():widget.destroy()
        c=self.model.commands[index];self.dialogue_button.config(state='normal' if c['opcode']==0x0c else 'disabled');self.ai_button.config(state='normal' if c['opcode']==0x24 else 'disabled');self.command_heading.set(f'Command {index+1} · '+c['name'].replace('_',' ').title())
        self.audio_button.config(state='normal' if c['opcode'] in (0x0e,0x11,0x12) else 'disabled')
        self.help.set(HELP.get(schema(c),'Read-only command. Use the linked dialogue, reinforcement, conversation or objective editor where supported.'))
        for i,(label,offset,size,low,high) in enumerate(FIELDS.get(schema(c),[])):
            ttk.Label(self.fields,text=label+f' ({low}–{high})').grid(row=i,column=0,sticky='w',padx=(0,12),pady=4)
            options={f'{name} (0x{value:04X})':value for value,name in self.names.items()} if schema(c)=='character_sprite' else {}
            if c['opcode']==0x24:
                known=deployment_options(self.rom,i)
                if known:
                    current_value=self.model.values(index)[i]
                    if current_value not in known:known[current_value]=f'Existing unknown {current_value}'
                    options={f'{name} ({value})':value for value,name in known.items()}
            if audio_kind(c):
                known=audio_options(c)
                current_value=self.model.values(index)[i]
                if current_value not in known:known[current_value]=f'Existing unknown ${current_value:04X}'
                options={f'{name} (0x{value:04X})':value for value,name in known.items()}
            if c['opcode']==0x0c:
                options={o['label']+f" (${o['pointer']:06X})":o['pointer'] for o in self.model.dialogues()}
                old=self.model.values(index)[i]
                if old not in options.values():options[f'Existing scene (${old:06X})']=old
            value=self.drafts[index][i]
            if options:value=next((label for label,key in options.items() if str(key)==value),value)
            var=tk.StringVar(value=value);self.variables.append(var);self.field_options.append(options)
            widget=ttk.Combobox(self.fields,state='readonly',textvariable=var,values=list(options),width=38) if options else ttk.Spinbox(self.fields,from_=low,to=high,textvariable=var,width=12)
            widget.grid(row=i,column=1,sticky='w')
            if c['opcode']==0x0c:
                widget.config(width=48)
                ttk.Button(self.fields,text='Find dialogue…',command=self.choose_dialogue).grid(row=i,column=2,padx=6)
            if c['opcode']==0x12:
                def explain_word(*_,v=var,choices=options):
                    from sound_words import describe_word
                    text=v.get()
                    try:value=choices[text] if text in choices else number(text)
                    except ValueError:self.help.set(HELP[0x12]);return
                    self.help.set(HELP[0x12]+'\n\n'+describe_word(value))
                var.trace_add('write',explain_word);explain_word()
        raw=self.model.snapshot[c['offset']:c['offset']+c['size']]
        self.raw.set('Loaded command bytes (read-only):\n'+hex_dump(raw,self.model.profile['start']+c['offset']))
    def choose_dialogue(self):
        if self.model is None or self.command is None:return
        choices=self.model.dialogues()
        if not choices:messagebox.showinfo('Dialogue unavailable','No supported dialogue scenes are available for this ROM profile.',parent=self);return
        from dialogue_picker import DialoguePicker
        def chosen(scene):
            value=scene['pointer'];label=next(k for k,v in self.field_options[0].items() if v==value)
            self.variables[0].set(label);self.remember_command()
        DialoguePicker(self,choices,chosen)

    def open_dialogue(self):
        if self.model is None or self.command is None:return
        command=self.command
        if not self.settle():return
        # Discard also restores the loaded pointer before opening its text.
        self.load(self.current)
        node=self.model.commands[command]
        from dialogue import check_profile
        try:check_profile(self.rom)
        except ValueError as error:messagebox.showerror('Unsupported dialogue layout',str(error),parent=self);return
        entry=dict(address=self.model.profile['start']+node['offset']+1,group='Prologue',label=self.model.entry['label']+f' / command {command+1}',section='Events')
        from dialogue_window import DialogueWindow
        window=DialogueWindow(self.app,entry);window.transient(self)
        def closed(event):
            if event.widget is window and self.winfo_exists():
                self.load(self.current);self.commands.selection_set(str(command));self.select_command();self.grab_set()
        window.bind('<Destroy>',closed,add='+')

    def inspect_ai(self):
        if self.model is None or self.command is None or self.model.commands[self.command]['opcode']!=0x24:return
        self.remember_command()
        try:faction=number(self.drafts[self.command][1]);group=number(self.drafts[self.command][9])
        except ValueError:messagebox.showerror('Invalid AI selection','Choose a valid faction and AI group first.',parent=self);return
        window=self.app.view_ai(self.model.entry['chapter'],faction,group)
        if window:
            window.transient(self)
            window.bind('<Destroy>',lambda event:self.grab_set() if event.widget is window and self.winfo_exists() else None,add='+')

    def preview_audio(self):
        if self.model is None or self.command is None:return
        c=self.model.commands[self.command];kind={0x0e:'music',0x11:'byte',0x12:'word'}.get(c['opcode'])
        if kind is None:return
        self.remember_command()
        try:value=number(self.drafts[self.command][0])
        except ValueError:messagebox.showerror('Invalid audio selection','Choose a named music/effect option before previewing.',parent=self);return
        self.app.open_audio(kind,value,autoplay=True)

    def save(self):
        if self.model is None:return False
        if self.app.rom is not self.rom:messagebox.showerror('ROM changed','Reopen Event Editor for the current ROM.',parent=self);return False
        if not self.pending():self.status.set('No pending command edits.');return True
        before=bytes(self.rom.data)
        try:
            updates={}
            for i,values in self.drafts.items():
                updates[i]=[]
                for value,field in zip(values,FIELDS[schema(self.model.commands[i])]):
                    try:updates[i].append(number(value.strip()))
                    except ValueError:raise ValueError(f'Command {i+1}: {field[0]} needs a decimal number or 0x hexadecimal value.')
            details=self.model.write(updates)
            if details:self.rom.save_original('Event commands: '+self.model.entry['label'],details)
        except (ValueError,OSError,OverflowError) as error:
            self.rom.data[:]=before;messagebox.showerror('Cannot save event commands',str(error),parent=self);return False
        self.app.refresh_after_history();self.load(self.current);self.status.set('Saved to the original ROM with automatic backup and undo history.');return True
    def reload(self):
        if self.pending() and not messagebox.askyesno('Reload script','Discard the current command draft?',parent=self):return
        self.load(self.current)
    def history(self,redo):
        if not self.settle():return
        try:self.rom.redo() if redo else self.rom.undo()
        except (ValueError,OSError) as error:messagebox.showerror('History unavailable',str(error),parent=self);return
        self.app.refresh_after_history();self.load(self.current)
    def launch(self):return self.app.save_and_launch(save_callback=self.save,parent=self)
    def open_viewer(self):
        if not self.settle():return
        if self.pending():self.load(self.current)
        window=self.app.view_events()
        if window:
            self.grab_release();window.transient(self)
            window.bind('<Destroy>',lambda event:self.grab_set() if event.widget is window and self.winfo_exists() else None,add='+')
            window.chapter.current(0);window.search.set('');window.populate()
            match=next((i for i,(trigger,e) in enumerate(window.visible) if not trigger and e['id']==self.model.entry['id']),None) if self.model else None
            if match is not None:window.list.selection_clear(0,'end');window.list.selection_set(match);window.select()
    def close(self):
        if self.settle():self.destroy()

def open_event_command_window(app,event_id=None):
    if not app.rom:messagebox.showinfo('Open a ROM','Open a FE4 ROM first.',parent=app);return
    if app.settle():return EventCommandWindow(app,event_id)
