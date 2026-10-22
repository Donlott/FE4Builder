"""Read-only native FE4 music and sound preview browser."""
import time,wave
import tkinter as tk
from tkinter import ttk,messagebox
from audio_preview import catalogue,PreviewJob,playback_available

KINDS={'Music':'music','Sound effects (byte)':'byte','Sound commands (word)':'word'}
class AudioWindow(tk.Toplevel):
    def __init__(self,app,kind=None,value=None,autoplay=False):
        super().__init__(app);self.app=app;self.rom=app.rom;self.previous_grab=app.grab_current()
        self.job=None;self.timer=None;self.playing_until=0;self.current=None;self.visible=[];self.entries=catalogue()['entries']
        self.title('FE4Builder — Music & Sound Player');self.geometry('950x700');self.minsize(760,520);self.transient(app);self.grab_set()
        top=ttk.Frame(self,padding=12);top.pack(fill='x');ttk.Label(top,text='Music & Sound Player',style='Title.TLabel').pack(side='left')
        ttk.Label(self,text='Read-only playback from the opened ROM. No event parameters, ROM bytes or game saves are changed.',padding=(12,0)).pack(anchor='w')
        bar=ttk.Frame(self,padding=12);bar.pack(fill='x')
        self.filter=ttk.Combobox(bar,state='readonly',values=list(KINDS),width=25);self.filter.set(next((label for label,key in KINDS.items() if key==kind),'Music'));self.filter.pack(side='left')
        self.filter.bind('<<ComboboxSelected>>',lambda _:self.populate())
        ttk.Label(bar,text='Find').pack(side='left',padx=(14,6));self.search=tk.StringVar();ttk.Entry(bar,textvariable=self.search).pack(side='left',fill='x',expand=True)
        self.search.trace_add('write',lambda *_:self.populate())
        body=ttk.Frame(self,padding=(12,0));body.pack(fill='both',expand=True)
        self.list=tk.Listbox(body,exportselection=False,font=('Segoe UI',11));scroll=ttk.Scrollbar(body,command=self.list.yview)
        scroll.pack(side='right',fill='y');self.list.config(yscrollcommand=scroll.set);self.list.pack(fill='both',expand=True)
        self.list.bind('<<ListboxSelect>>',self.select);self.list.bind('<Double-1>',lambda _:self.play());self.list.bind('<Return>',lambda _:self.play())
        from tkinter.scrolledtext import ScrolledText
        self.details=tk.StringVar()
        self.detail_box=ScrolledText(self,height=7,wrap='word',font=('Segoe UI',10),state='disabled')
        self.detail_box.pack(fill='x',padx=12,pady=8)
        def show_details(*_):
            self.detail_box.config(state='normal');self.detail_box.delete('1.0','end');self.detail_box.insert('1.0',self.details.get());self.detail_box.config(state='disabled')
        self.details.trace_add('write',show_details)
        options=ttk.Frame(self,padding=(12,0,12,8));options.pack(fill='x')
        ttk.Label(options,text='Preview length').pack(side='left');self.length=ttk.Combobox(options,state='readonly',values=['6','15','30','60','120'],width=6);self.length.set('6' if kind in ('byte','word') else '30');self.length.pack(side='left',padx=8)
        ttk.Label(options,text='seconds').pack(side='left')
        self.loop=tk.BooleanVar();ttk.Checkbutton(options,text='Repeat clip',variable=self.loop).pack(side='left',padx=16)
        context=ttk.Frame(self,padding=(12,0,12,8));context.pack(fill='x')
        ttk.Label(context,text='Word-command background').pack(side='left')
        self.context_options={'None (isolated)':0}
        self.context_options.update({f'{e["label"]} (${e["value"]:02X})':e['value'] for e in self.entries if e['kind']=='music'})
        self.context=ttk.Combobox(context,state='readonly',values=list(self.context_options),width=38)
        self.context.set(next((label for label,key in self.context_options.items() if key==0x11),'None (isolated)'));self.context.pack(side='left',padx=8)
        actions=ttk.Frame(self,padding=12);actions.pack(fill='x')
        self.play_button=ttk.Button(actions,text='▶ Play preview',command=self.play);self.play_button.pack(side='left')
        ttk.Button(actions,text='■ Stop',command=self.stop).pack(side='left',padx=8)
        ttk.Button(actions,text='Close',command=self.close).pack(side='right')
        self.status=tk.StringVar(value='Choose a track or effect, then Play. The first preview is rendered in the background; later plays use a cache.')
        ttk.Label(self,textvariable=self.status,padding=10,relief='sunken',wraplength=890).pack(side='bottom',fill='x')
        self.populate();self.target(kind,value)
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.bind('<Escape>',lambda _:self.close())
        if not playback_available():
            self.play_button.config(state='disabled');self.status.set('Built-in playback requires 64-bit Windows. You can still browse sounds and edit event audio commands on this platform.')
        elif autoplay:self.after_idle(self.play)
    def target(self,kind,value):
        if kind is None:return
        label=next((label for label,key in KINDS.items() if key==kind),None)
        if label is None:return
        self.filter.set(label);self.search.set('');self.populate()
        index=next((i for i in self.visible if self.entries[i]['value']==value),None)
        if index is None and value is not None:
            self.current=None;self.list.selection_clear(0,'end');self.play_button.config(state='disabled')
            self.status.set(f'Sound ID ${value:04X} is not in this preview catalogue. No substitute sound will be played.')
        if index is not None:
            self.list.selection_clear(0,'end');self.list.selection_set(self.visible.index(index));self.list.see(self.visible.index(index));self.load(index)
    def populate(self):
        kind=KINDS.get(self.filter.get(),'music');query=self.search.get().casefold();self.visible=[];self.list.delete(0,'end')
        for i,e in enumerate(self.entries):
            text=f'{e["label"]}  ·  ${e["value"]:04X}'
            if e['kind']!=kind or query not in (text+' '+' '.join(e['uses'])).casefold():continue
            self.visible.append(i);self.list.insert('end',text)
        if self.visible:self.list.selection_set(0);self.load(self.visible[0])
        else:self.current=None;self.details.set('No matching sounds.');self.play_button.config(state='disabled')
    def select(self,_=None):
        if self.list.curselection():self.load(self.visible[self.list.curselection()[0]])
    def load(self,index):
        self.current=index;e=self.entries[index]
        uses='; '.join(label.replace('Event','').replace('Chapter','Chapter ') for label in e['uses'][:4]) or 'Nightmare music label; no direct event use catalogued.'
        note='Music is a timed preview. Repeat restarts the clip; it is not a seamless soundtrack loop.' if e['kind']=='music' else 'These are observed byte sound IDs, not an exhaustive sound-bank catalogue.' if e['kind']=='byte' else 'Word commands can fade/stop audio or change driver state, so some have no sound of their own. Choose background music to hear their effect.'
        if e['kind']=='word':
            from sound_words import describe_word
            note=describe_word(e['value'])+'\n'+note
        self.details.set(e['label']+f' · ID ${e["value"]:04X}\n'+note+'\nReference uses: '+uses)
        self.context.config(state='readonly' if e['kind']=='word' else 'disabled');self.play_button.config(state='normal' if playback_available() else 'disabled')
    def play(self):
        if self.current is None:return
        self.stop(update=False)
        if self.app.rom is not self.rom:messagebox.showerror('ROM changed','Reopen the audio player for the current ROM.',parent=self);return
        e=self.entries[self.current];seconds=int(self.length.get());context=self.context_options[self.context.get()] if e['kind']=='word' else 0
        try:self.job=PreviewJob(bytes(self.rom.data),e['kind'],e['value'],seconds,context)
        except (OSError,ValueError) as error:self.status.set(str(error));return
        self.active_label=e['label'];self.status.set('Preparing '+self.active_label+'… Stop cancels preparation.');self.check_job()
    def check_job(self):
        self.timer=None
        if self.job is None:return
        try:output=self.job.poll()
        except (OSError,ValueError) as error:
            self.job.cancel();self.job=None;self.status.set('Preview unavailable: '+str(error));return
        if output is None:self.timer=self.after(100,self.check_job);return
        try:
            import winsound
            flags=winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT
            if self.loop.get():flags|=winsound.SND_LOOP
            winsound.PlaySound(str(output),flags)
            with wave.open(str(output),'rb') as sound:duration=sound.getnframes()/sound.getframerate()
        except (OSError,RuntimeError,ImportError,wave.Error) as error:self.status.set('Cannot play preview: '+str(error));self.job=None;return
        self.playing_until=0 if self.loop.get() else time.monotonic()+duration
        self.status.set('Playing '+self.active_label+(' · repeating clip' if self.loop.get() else f' · {duration:.0f}-second preview'))
        if self.playing_until:self.timer=self.after(200,self.check_playback)
    def check_playback(self):
        self.timer=None
        if time.monotonic()>=self.playing_until:self.status.set('Preview finished.');return
        self.timer=self.after(200,self.check_playback)
    def stop(self,update=True):
        if self.timer is not None:self.after_cancel(self.timer);self.timer=None
        if self.job is not None:self.job.cancel();self.job=None
        try:
            import winsound
            winsound.PlaySound(None,0)
        except (ImportError,RuntimeError):pass
        self.playing_until=0
        if update:self.status.set('Stopped.')
    def close(self):self.destroy()
    def destroy(self):
        self.stop(update=False);previous=self.previous_grab;super().destroy()
        if previous is not None and previous.winfo_exists():previous.grab_set()

def open_audio_window(app,kind=None,value=None,autoplay=False):
    if not app.rom:messagebox.showinfo('Open a ROM','Open a FE4 ROM first.',parent=app);return
    existing=getattr(app,'audio_window',None)
    if existing is not None and existing.winfo_exists():
        existing.target(kind,value);existing.lift();existing.grab_set()
        if autoplay:existing.play()
        return existing
    app.audio_window=AudioWindow(app,kind,value,autoplay);return app.audio_window
