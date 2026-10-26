"""Shared save feedback, context persistence and compact-window utilities."""
import json,os,tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from rom import DATA_DIR

class ContextStore:
    def __init__(self,path=None):
        self.path=Path(path or DATA_DIR/'ui-state.json');self.data={}
        try:
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(data,dict):self.data=data
        except (OSError,ValueError):pass

    def get(self,rom,key):
        group=self.data.get((str(rom.path.resolve()).casefold() if os.name=='nt' else str(rom.path.resolve())),{}) if rom else {}
        value=group.get(key,{}) if isinstance(group,dict) else {}
        return value if isinstance(value,dict) else {}
    def put(self,rom,key,value,persist=False):
        if not rom:return
        identity=(str(rom.path.resolve()).casefold() if os.name=='nt' else str(rom.path.resolve()))
        if not isinstance(self.data.get(identity),dict):self.data[identity]={}
        group=self.data[identity]
        if group.get(key)==value:return
        group[key]=value
        if persist:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            handle,name=tempfile.mkstemp(prefix='ui-state-',suffix='.tmp',dir=self.path.parent)
            try:
                with os.fdopen(handle,'w',encoding='utf-8') as out:json.dump(self.data,out,indent=2)
                os.replace(name,self.path)
            finally:
                if Path(name).exists():Path(name).unlink()

def fit_window(window):
    """Use the Windows work area when available, accounting for the taskbar."""
    width,height=window.winfo_screenwidth(),window.winfo_screenheight();left=top=0
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        rect=wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(48,0,ctypes.byref(rect),0):
            left,top,width,height=rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top
    window.update_idletasks()
    w=min(window.winfo_reqwidth() if window.winfo_width()<=1 else window.winfo_width(),width-24)
    h=min(window.winfo_reqheight() if window.winfo_height()<=1 else window.winfo_height(),height-56)
    # Respect requested geometry for unmapped transient windows, capped to the work area.
    import re
    match=re.match(r'(\d+)x(\d+)',window.geometry())
    if match:w=min(max(w,int(match[1])),width-24);h=min(max(h,int(match[2])),height-56)
    old=window.minsize();window.minsize(min(old[0],width-24),min(old[1],height-56))
    window.geometry(f'{max(320,w)}x{max(240,h)}+{left+max(8,(width-w)//2)}+{top+max(8,(height-h)//2)}')

def wheel_steps(event):
    """Normalize Windows/macOS wheel deltas and Linux/X11 buttons."""
    number=getattr(event,'num',None)
    if number==4:return -1
    if number==5:return 1
    delta=getattr(event,'delta',0)
    return -int(delta/120) if abs(delta)>=120 else (-1 if delta>0 else 1 if delta<0 else 0)


def bind_canvas_wheel(canvas,horizontal=True):
    def scroll(event,axis='y'):
        steps=wheel_steps(event)
        if steps:getattr(canvas,axis+'view_scroll')(steps,'units')
        return 'break'
    for sequence in ('<MouseWheel>','<Button-4>','<Button-5>'):
        canvas.bind(sequence,scroll)
        if horizontal:canvas.bind('<Shift-'+sequence[1:],lambda event:scroll(event,'x'))


def scrollable_frame(parent,padding=0):
    area=ttk.Frame(parent);area.pack(fill='both',expand=True)
    canvas=tk.Canvas(area,highlightthickness=0);bar=ttk.Scrollbar(area,command=canvas.yview)
    bar.pack(side='right',fill='y');canvas.pack(fill='both',expand=True);canvas.config(yscrollcommand=bar.set)
    content=ttk.Frame(canvas,padding=padding);item=canvas.create_window(0,0,window=content,anchor='nw')
    content.bind('<Configure>',lambda _:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda event:canvas.itemconfigure(item,width=event.width))
    # Canvas scrolling is local; combobox popups and nested lists retain their own wheel behavior.
    def wheel(event):
        if isinstance(event.widget,(ttk.Combobox,ttk.Spinbox,tk.Listbox,tk.Text,ttk.Treeview)):return
        if str(event.widget).startswith(str(content)) or event.widget is canvas:
            canvas.yview_scroll(wheel_steps(event),'units');return 'break'
    top=parent.winfo_toplevel();bindings=[(sequence,top.bind(sequence,wheel,add='+')) for sequence in ('<MouseWheel>','<Button-4>','<Button-5>')]
    def cleanup(event):
        if event.widget is content:
            for sequence,binding in bindings:top.unbind(sequence,binding)
    content.bind('<Destroy>',cleanup,add='+')
    return content

def scrollable_tab(notebook,title,padding=12):
    shell=ttk.Frame(notebook);notebook.add(shell,text=title)
    return scrollable_frame(shell,padding)

def ask_unsaved(parent,message='Write the staged changes to the opened ROM?'):
    dialog=tk.Toplevel(parent);dialog.title('Unsaved changes');dialog.transient(parent.winfo_toplevel());dialog.grab_set();dialog.resizable(False,False)
    result=[None];body=ttk.Frame(dialog,padding=18);body.pack(fill='both',expand=True)
    ttk.Label(body,text=message,wraplength=450).pack(anchor='w',pady=(0,16))
    buttons=ttk.Frame(body);buttons.pack(fill='x')
    def choose(value):result[0]=value;dialog.destroy()
    for text,value in [('Write changes',True),('Discard changes',False),('Stay here',None)]:ttk.Button(buttons,text=text,command=lambda v=value:choose(v)).pack(side='left',padx=4)
    dialog.bind('<Escape>',lambda _:choose(None));dialog.protocol('WM_DELETE_WINDOW',lambda:choose(None));parent.wait_window(dialog)
    if parent.winfo_exists() and isinstance(parent,tk.Toplevel):parent.grab_set()
    return result[0]

def prepare_window(app,window,restore=True):
    if window is None or getattr(window,'_ux_prepared',False):return window
    window._ux_prepared=True;key=type(window).__name__;rom=app.rom;store=app.ui_context
    state=store.get(rom,key) if restore else {}
    chapter=getattr(window,'chapter',None)
    if chapter is not None and restore:
        value=state.get('chapter',store.get(rom,'workspace').get('chapter',chapter.current()))
        if isinstance(value,int) and 0<=value<len(chapter.cget('values')) and value!=chapter.current():
            chapter.current(value);chapter.event_generate('<<ComboboxSelected>>')
    for name in ('group','zoom','view','filter','unit_palette','palette'):
        widget=getattr(window,name,None);value=state.get(name)
        if name=='group' and value is None and restore and isinstance(widget,ttk.Combobox):
            from events import CHAPTERS
            selected=store.get(rom,'workspace').get('chapter')
            if isinstance(selected,int) and 0<=selected<len(CHAPTERS) and CHAPTERS[selected] in widget.cget('values'):value=CHAPTERS[selected]
        if isinstance(widget,ttk.Combobox) and value in widget.cget('values'):
            widget.set(value);widget.event_generate('<<ComboboxSelected>>')
    search=getattr(window,'search',None)
    if isinstance(search,tk.StringVar) and isinstance(state.get('search'),str):search.set(state['search'])
    current=state.get('current');visible=getattr(window,'visible',[])
    if current in visible and callable(getattr(window,'load',None)):
        window.load(current);listing=getattr(window,'list',None)
        if isinstance(listing,tk.Listbox):listing.selection_clear(0,'end');listing.selection_set(visible.index(current));listing.see(visible.index(current))
    save=getattr(window,'save',None)
    if callable(save):window.bind('<Control-s>',lambda _:(save(),'break')[1]);window.bind('<Control-S>',lambda _:(save(),'break')[1])
    def escape(_):
        command=window.protocol('WM_DELETE_WINDOW')
        if command:window.tk.call(command)
        else:window.destroy()
        return 'break'
    window.bind('<Escape>',escape)
    label=ttk.Label(window,padding=(10,3),foreground='#905300');label.pack(side='bottom',fill='x')
    title=window.title();job=[None];previous=[None];chapter_seen=[None]
    def poll(schedule=True):
        if not window.winfo_exists():return
        pending=getattr(window,'pending',None)
        if callable(pending):dirty=bool(pending())
        else:dirty=bool(getattr(getattr(window,'model',None),'dirty',False))
        text='Unsaved changes — Ctrl+S writes to ROM' if dirty else 'No pending edits' if callable(save) else 'Viewer — no ROM edits'
        if text!=previous[0]:label.config(text=text);window.title(title+(' *' if dirty else ''));previous[0]=text
        data={}
        if isinstance(chapter,ttk.Combobox):data['chapter']=chapter.current()
        for name in ('group','zoom','view','filter','unit_palette','palette'):
            widget=getattr(window,name,None)
            if isinstance(widget,ttk.Combobox):data[name]=widget.get()
        if isinstance(search,tk.StringVar):data['search']=search.get()
        current=getattr(window,'current',None)
        if isinstance(current,int):data['current']=current
        try:
            persist=app.ui_context_ready
            store.put(rom,key,data,persist)
            if 'chapter' in data and data['chapter']!=chapter_seen[0]:
                store.put(rom,'workspace',{'chapter':data['chapter']},persist);chapter_seen[0]=data['chapter']
        except OSError:pass
        if schedule:job[0]=window.after(250,poll)
    def destroyed(event):
        if event.widget is window and job[0] is not None:
            window.after_cancel(job[0]);job[0]=None
    original_destroy=window.destroy
    def destroy():
        if window.winfo_exists():
            poll(False)
            if job[0] is not None:window.after_cancel(job[0]);job[0]=None
        original_destroy()
    window.destroy=destroy
    window.bind('<Destroy>',destroyed,add='+');poll();fit_window(window)
    return window
