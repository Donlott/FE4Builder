"""Chapter/faction AI viewer; no ROM mutation controls."""
import tkinter as tk
from tkinter import ttk,messagebox
from tkinter.scrolledtext import ScrolledText
from ai_viewer import AIViewer,chapter_name

class AIWindow(tk.Toplevel):
    def __init__(self,app,chapter=None,faction=None,number=None):
        super().__init__(app);self.app=app;self.rom=app.rom;self.model=AIViewer(self.rom);self.rows={};self.group=None;self.number=None;self.links=[]
        self.title('FE4Builder — AI Viewer');self.geometry('1180x800');self.minsize(900,600);self.transient(app);self.grab_set()
        top=ttk.Frame(self,padding=10);top.pack(fill='x')
        ttk.Label(top,text='AI Viewer',font=('Segoe UI',16,'bold')).pack(side='left')
        self.chapter=ttk.Combobox(top,state='readonly',values=['All chapters']+[chapter_name(i) for i in range(12)],width=20);self.chapter.current(0);self.chapter.pack(side='left',padx=20);self.chapter.bind('<<ComboboxSelected>>',self.populate)
        ttk.Button(top,text='Reload from ROM',command=self.reload).pack(side='right')
        ttk.Label(self,text='Read-only. AI numbers select scripts within a faction. Normal AI processes groups 1–8.\nAssignment matches use reference faction slots; events can change factions, AI and group definitions during play.',padding=(10,0)).pack(anchor='w')
        pane=ttk.Panedwindow(self,orient='horizontal');pane.pack(fill='both',expand=True,padx=10,pady=8)
        left=ttk.Frame(pane);pane.add(left,weight=1)
        self.tree=ttk.Treeview(left,show='tree',selectmode='browse');bar=ttk.Scrollbar(left,command=self.tree.yview);bar.pack(side='right',fill='y');self.tree.config(yscrollcommand=bar.set);self.tree.pack(fill='both',expand=True);self.tree.bind('<<TreeviewSelect>>',self.select)
        right=ttk.Frame(pane);pane.add(right,weight=3)
        self.heading=tk.StringVar();ttk.Label(right,textvariable=self.heading,wraplength=760,font=('Segoe UI',11,'bold')).pack(anchor='w',pady=5)
        tabs=ttk.Notebook(right);tabs.pack(fill='both',expand=True)
        script=ttk.Frame(tabs);tabs.add(script,text='Behavior script')
        self.commands=ttk.Treeview(script,columns=('address','command','parameters'),show='headings',height=12)
        for key,title,width in [('address','SNES address',105),('command','Command',280),('parameters','Parameters',350)]:self.commands.heading(key,text=title);self.commands.column(key,width=width)
        bar=ttk.Scrollbar(script,command=self.commands.yview);bar.pack(side='right',fill='y');self.commands.config(yscrollcommand=bar.set);self.commands.pack(fill='both',expand=True)
        horizontal=ttk.Scrollbar(script,orient='horizontal',command=self.commands.xview);horizontal.pack(fill='x');self.commands.config(xscrollcommand=horizontal.set)
        self.commands.bind('<<TreeviewSelect>>',self.explain)
        self.detail=ScrolledText(right,height=7,wrap='word');self.detail.pack(fill='x',pady=6);self.detail.config(state='disabled')
        units=ttk.Frame(tabs);tabs.add(units,text='Assigned units / coverage')
        self.units_text=ScrolledText(units,wrap='word');self.units_text.pack(fill='both',expand=True);self.units_text.config(state='disabled')
        shared=ttk.Frame(tabs);tabs.add(shared,text='Shared script uses')
        ttk.Label(shared,text='Double-click a use to open that group.').pack(anchor='w')
        self.shared=tk.Listbox(shared,exportselection=False)
        bar=ttk.Scrollbar(shared,command=self.shared.yview);bar.pack(side='right',fill='y');self.shared.config(yscrollcommand=bar.set)
        self.shared.pack(fill='both',expand=True);self.shared.bind('<Double-1>',self.follow)
        self.status=tk.StringVar();ttk.Label(self,textvariable=self.status,padding=8,wraplength=1120).pack(fill='x')
        if chapter is not None:self.chapter.current(chapter+1)
        self.populate()
        if faction is not None:
            group=next((g for g in self.model.groups if g['chapter']==chapter and faction in g['slots']),None)
            if group:
                key=f"g{group['id']}:{number}"
                if not self.tree.exists(key):key=f"g{group['id']}"
                self.tree.selection_set(key);self.tree.see(key);self.select()
    def text(self,widget,value):widget.config(state='normal');widget.delete('1.0','end');widget.insert('1.0',value);widget.config(state='disabled')
    def populate(self,_=None):
        self.tree.delete(*self.tree.get_children());self.rows={}
        chosen=self.chapter.current()-1
        for g in self.model.groups:
            if chosen>=0 and g['chapter']!=chosen:continue
            parent=f"g{g['id']}";self.tree.insert('','end',iid=parent,text=f"{chapter_name(g['chapter'])} / {g['label']}",open=chosen>=0);self.rows[parent]=(g,None)
            for e in g['entries']:
                key=f"{parent}:{e['number']}";self.tree.insert(parent,'end',iid=key,text=f"Group {e['number']} · {len(self.model.units(g,e['number']))} assignment matches");self.rows[key]=(g,e)
        first=next((k for k,(_,e) in self.rows.items() if e),next(iter(self.rows),None))
        if first:self.tree.selection_set(first);self.tree.see(first);self.select()
    def select(self,_=None):
        selected=self.tree.selection()
        if not selected:return
        g,e=self.rows[selected[0]];self.group=g;self.number=e['number'] if e else None
        self.commands.delete(*self.commands.get_children());self.shared.delete(0,'end');self.links=[];self.nodes={}
        self.heading.set(f"{chapter_name(g['chapter'])} / {g['label']} · "+(f"AI group {e['number']} · ${e['pointer']:06X}" if e else 'Faction overview'))
        self.text(self.detail,g['error'] or ('Choose an AI group to inspect its behavior.' if g['entries'] else 'No group AI script table is assigned to this faction.'))
        units=self.model.units(g,e['number']) if e else [u for u in self.model.assignments if u['chapter']==g['chapter'] and u['faction'] in g['slots']]
        lines=['Reference faction slots: '+(', '.join(map(str,g['slots'])) or 'not mapped'), 'Matches include Army records and supported direct-spawn events. These are potential assignments across the chapter, not a snapshot of units currently alive. Variant faction definitions may match the same units. AI 0 has no normal group script; 9–15 are outside the normal 1–8 processing loop.','']
        lines += [f"{self.model.names.get(u['character'],str(u['character']))} · AI {u['ai']}"+(' · commander' if u['leader'] else '')+f" · PC ${u['address']:06X}\n  {u['source']}" for u in units]
        if not units:lines.append('No matching assignments found in the covered data.')
        self.text(self.units_text,'\n'.join(lines));warnings=list(self.model.warnings)
        if e:
            nodes,notes=self.model.decode(e['pointer']);warnings+=notes
            for n in nodes:
                key=str(n['address']);self.nodes[key]=n;self.commands.insert('','end',iid=key,values=(f"${n['address']:06X}",n['name'],n['text']))
            for other,entry in self.model.shared(e['pointer']):
                self.links.append((other,entry));self.shared.insert('end',f"{chapter_name(other['chapter'])} / {other['label']} / Group {entry['number']}")
            if nodes:self.commands.selection_set(str(nodes[0]['address']));self.explain()
        self.status.set(('Warnings: '+' | '.join(warnings)) if warnings else 'Live ROM pointers and script bytes · read-only · shared uses compare exact entry pointers; scripts may also share branch targets.')
    def explain(self,_=None):
        selected=self.commands.selection()
        if not selected:return
        n=self.nodes[selected[0]]
        self.text(self.detail,n['name']+'\n'+n['text']+'\n'+n.get('note','')+f"\nPC ${n['pc']:06X} · Bytes: "+n['raw'].hex(' ').upper())
    def follow(self,_=None):
        if not self.shared.curselection():return
        g,e=self.links[self.shared.curselection()[0]];self.chapter.current(g['chapter']+1);self.populate();key=f"g{g['id']}:{e['number']}";self.tree.selection_set(key);self.tree.see(key);self.select()
    def reload(self):
        if self.app.rom is not self.rom:messagebox.showinfo('ROM changed','Reopen AI Viewer for the current ROM.',parent=self);return
        self.model=AIViewer(self.rom);self.populate()

def open_ai_window(app,chapter=None,faction=None,number=None):
    if not app.rom:messagebox.showinfo('Open a ROM','Open a FE4 ROM first.',parent=app);return
    if app.settle():return AIWindow(app,chapter,faction,number)
