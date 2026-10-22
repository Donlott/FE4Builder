"""Chapter event reference viewer with live ROM pointers and linked tools."""
import tkinter as tk
from tkinter import ttk,messagebox
from events import catalogue,inspect,hex_dump,CHAPTERS

class EventWindow(tk.Toplevel):
    def __init__(self,app):
        super().__init__(app);self.app=app;self.rom=app.rom
        self.title('FE4Builder — Chapter Event Viewer');self.geometry('1200x800');self.minsize(900,600)
        self.transient(app)
        top=ttk.Frame(self,padding=12);top.pack(fill='x')
        self.chapter=ttk.Combobox(top,state='readonly',values=CHAPTERS,width=20);self.chapter.current(0);self.chapter.pack(side='left')
        self.chapter.bind('<<ComboboxSelected>>',lambda _:self.populate())
        ttk.Label(top,text='Search names or script commands').pack(side='left',padx=10)
        self.search=tk.StringVar();ttk.Entry(top,textvariable=self.search).pack(side='left',fill='x',expand=True)
        self.search.trace_add('write',lambda *_:self.populate())
        ttk.Button(top,text='Refresh from ROM',command=self.select).pack(side='left',padx=8)
        ttk.Label(self,text='Read-only viewer. Conditions and actions use annotated reference scripts; changed data is flagged.\n'
                  'Symbolic names follow the disassembly and may differ from your translation. This viewer does not execute events.',padding=(12,0)).pack(anchor='w')
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=12,pady=12)
        left=ttk.Frame(body);body.add(left,weight=1)
        self.list=tk.Listbox(left,width=42,exportselection=False);scroll=ttk.Scrollbar(left,command=self.list.yview)
        scroll.pack(side='right',fill='y');self.list.config(yscrollcommand=scroll.set);self.list.pack(fill='both',expand=True)
        self.list.bind('<<ListboxSelect>>',self.select)
        right=ttk.Frame(body);body.add(right,weight=3)
        self.status=tk.StringVar();ttk.Label(right,textvariable=self.status,wraplength=750).pack(anchor='w',pady=(0,8))
        tabs=ttk.Notebook(right);tabs.pack(fill='both',expand=True)
        self.source=self.text_tab(tabs,'Conditions / actions (reference)');self.raw=self.text_tab(tabs,'Live ROM bytes')
        links=ttk.Frame(right);links.pack(fill='x',pady=8)
        self.dialogue=ttk.Combobox(links,state='readonly',width=38);self.dialogue.pack(side='left',fill='x',expand=True)
        self.open_button=ttk.Button(links,text='Open dialogue',command=self.open_dialogue);self.open_button.pack(side='left',padx=6)
        self.reinforcements_button=ttk.Button(links,text='Edit reinforcements…',command=self.open_reinforcements);self.reinforcements_button.pack(side='left',padx=6)
        ttk.Button(links,text='Village Rewards',command=app.edit_villages).pack(side='left')
        ttk.Button(links,text='Army Editor',command=lambda:app.show_editor('Army Editor')).pack(side='left',padx=6)
        conversation_links=ttk.Frame(right);conversation_links.pack(fill='x')
        self.conversation_button=ttk.Button(conversation_links,text='Edit recruitment / conversation…',command=self.open_conversation)
        self.conversation_button.pack(side='left')
        self.objective_button=ttk.Button(conversation_links,text='Edit objectives / progression…',command=self.open_objective)
        self.objective_button.pack(side='left',padx=6)
        command_links=ttk.Frame(right);command_links.pack(fill='x',pady=(6,0))
        self.commands_button=ttk.Button(command_links,text='Edit Prologue commands…',command=self.open_commands,state='disabled')
        self.commands_button.pack(side='left',padx=6)
        self.populate()

    def text_tab(self,tabs,label):
        frame=ttk.Frame(tabs);tabs.add(frame,text=label)
        text=tk.Text(frame,wrap='none',font=('Consolas',10),state='disabled')
        y=ttk.Scrollbar(frame,command=text.yview);y.pack(side='right',fill='y')
        x=ttk.Scrollbar(frame,orient='horizontal',command=text.xview);x.pack(side='bottom',fill='x')
        text.config(yscrollcommand=y.set,xscrollcommand=x.set);text.pack(fill='both',expand=True);return text

    def put(self,widget,value):
        widget.config(state='normal');widget.delete('1.0','end');widget.insert('1.0',value);widget.config(state='disabled')

    def populate(self):
        ch=self.chapter.current();query=self.search.get().strip().casefold()
        data=catalogue();self.visible=[(True,data['chapters'][ch])]
        self.visible += [(False,e) for e in data['events'] if e['chapter']==ch and query in (e['label']+' '+e['source']).casefold()]
        self.list.delete(0,'end');self.list.insert('end','Chapter conditions / trigger overview')
        for _,e in self.visible[1:]:self.list.insert('end',f'{e["id"]:03X} · {e["label"]}')
        self.list.selection_set(0);self.select()

    def select(self,_=None):
        self.command_event_id=None;self.commands_button.config(state='disabled')
        self.objective_index=None;self.objective_button.config(state='disabled')
        self.conversation_index=None;self.conversation_button.config(state='disabled')
        self.reinforcement_index=None;self.reinforcements_button.config(state='disabled')
        self.scene_entries=[];self.dialogue.set('');self.dialogue.config(values=[]);self.open_button.config(state='disabled')
        if not self.list.curselection():return
        trigger,e=self.visible[self.list.curselection()[0]]
        from objectives import catalogue as objectives
        self.objective_index=next((i for i,o in enumerate(objectives()['entries']) if o['chapter']==self.chapter.current() and (trigger or e['id'] in o['events'])),None)
        if self.objective_index is not None:self.objective_button.config(state='normal')
        if not trigger:
            from event_commands import catalogue as command_catalogue
            if any(c['id']==e['id'] for c in command_catalogue()['entries']):
                self.command_event_id=e['id'];self.commands_button.config(state='normal')
            from conversations import catalogue as conversations
            self.conversation_index=next((i for i,c in enumerate(conversations()['entries']) if e['id'] in c['events']),None)
            if self.conversation_index is not None:self.conversation_button.config(state='normal')
            from reinforcements import catalogue as reinforcements
            self.reinforcement_index=next((i for i,r in enumerate(reinforcements()['entries']) if r['id']==e['id']),None)
            if self.reinforcement_index is not None:self.reinforcements_button.config(state='normal')
        try:state=inspect(self.rom,e,trigger)
        except ValueError as error:
            self.status.set(str(error));self.put(self.source,'Reference only — live data could not be read.\n\n'+e['source']);self.put(self.raw,'');return
        label='Reference bytes match' if state['matches'] else 'CHANGED / RELOCATED — annotations are reference only'
        pointer='' if trigger else f' · SNES ${state["pointer"]:06X}'
        self.status.set(f'{label}\nPC ${state["start"]:06X}{pointer} · {len(state["raw"])} inspected bytes\n'
                        'Inspection spans end at the next catalogued event (maximum 4096 bytes); padding may be included.')
        self.put(self.source,e['source']);self.put(self.raw,hex_dump(state['raw'],state['start']))
        # Reference operand locations remain usable through the dialogue editor's village relocation resolver.
        if not trigger:
            from dialogue import catalogue as dialogues
            from villages import entries
            village=next((v for v in entries() if v['event_id']==e['id']),None)
            from event_layouts import checked,profiles
            verified=False;profile=profiles().get((e['start'],e['length']))
            if profile and state['start']==e['start']:
                try:checked(self.rom,profile);verified=True
                except ValueError:pass
            if state['matches'] or village or verified:
                self.scene_entries=[(i,d) for i,d in enumerate(dialogues()['entries']) if e['start']<=d['address']<e['start']+e['length']]
        self.dialogue.config(values=[d['label'] for _,d in self.scene_entries])
        if self.scene_entries:self.dialogue.current(0);self.open_button.config(state='normal')

    def open_commands(self):
        if self.command_event_id is None:return
        window=self.app.edit_events(self.command_event_id)
        if window:window.bind('<Destroy>',lambda event:self.select() if event.widget is window and self.winfo_exists() else None,add='+')

    def open_dialogue(self):
        if self.dialogue.current()<0:return
        i,e=self.scene_entries[self.dialogue.current()];window=self.app.edit_dialogue()
        if window:
            window.group.set(e['group']);window.populate();window.load(i)
            if i in window.visible:window.list.selection_clear(0,'end');window.list.selection_set(window.visible.index(i))
            window.bind('<Destroy>',lambda event:self.select() if event.widget is window and self.winfo_exists() else None)

    def open_reinforcements(self):
        if self.reinforcement_index is None:return
        window=self.app.edit_reinforcements()
        if window:
            window.transient(self);window.chapter.current(self.chapter.current());window.populate()
            window.list.selection_clear(0,'end');window.list.selection_set(window.visible.index(self.reinforcement_index))
            window.load(self.reinforcement_index)
            window.bind('<Destroy>',lambda event:self.select() if event.widget is window and self.winfo_exists() else None)

    def open_conversation(self):
        if self.conversation_index is None:return
        window=self.app.edit_conversations()
        if window:
            window.transient(self);window.chapter.current(self.chapter.current());window.populate()
            window.list.selection_clear(0,'end');window.list.selection_set(window.visible.index(self.conversation_index))
            window.load(self.conversation_index)
            window.bind('<Destroy>',lambda event:self.select() if event.widget is window and self.winfo_exists() else None)

    def open_objective(self):
        if self.objective_index is None:return
        window=self.app.edit_objectives()
        if window:
            window.transient(self);window.chapter.current(self.chapter.current());window.populate()
            window.list.selection_clear(0,'end');window.list.selection_set(window.visible.index(self.objective_index))
            window.load(self.objective_index)
            window.bind('<Destroy>',lambda event:self.select() if event.widget is window and self.winfo_exists() else None)

def open_event_window(app):
    if not app.rom:messagebox.showinfo('Chapter Event Viewer','Open a ROM first.',parent=app);return
    if app.settle():return EventWindow(app)
