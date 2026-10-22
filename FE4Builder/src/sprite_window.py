"""Read-only native standing/walking sprite sheets for a class."""

import base64

import tkinter as tk

from tkinter import ttk,filedialog,messagebox

from map_sprites import MapSprites

from portraits import export_png



class SpriteWindow(tk.Toplevel):

    def __init__(self,app,class_id):

        super().__init__(app)

        self.title('Class sprite sheets — '+app.heading.cget('text'))

        self.geometry('760x650')

        self.minsize(650,540)

        self.engine=MapSprites(app.rom)

        self.entries=self.engine.variants(class_id)

        bar=ttk.Frame(self,padding=12);bar.pack(fill='x')

        ttk.Label(bar,text='Variant').grid(row=0,column=0,sticky='w')

        labels=[]

        for character,gender,assignment in self.entries:

            who=f'Character {character:03X}' if character else 'Any character'

            sex={0:'male',1:'female',255:'any gender'}.get(gender,f'gender {gender}')

            labels.append(f'{who}, {sex} — sprite {assignment:04X}')

        self.variant=ttk.Combobox(bar,values=labels,state='readonly',width=52)

        self.variant.grid(row=0,column=1,padx=8,sticky='ew');self.variant.current(0)

        self.palette=ttk.Combobox(bar,values=['Blue','Red','Green','Yellow','Gray','Palette 5','Palette 6'],state='readonly',width=12)

        self.palette.grid(row=0,column=2);self.palette.current(0)

        self.variant.bind('<<ComboboxSelected>>',lambda e:self.refresh())

        self.palette.bind('<<ComboboxSelected>>',lambda e:self.refresh())

        self.tabs=ttk.Notebook(self);self.tabs.pack(fill='both',expand=True,padx=12)

        self.pages=[];self.photos=[];self.sheets=[]

        for title in ('Standing — 3 frames','Walking — 4 directions × 4 frames'):

            page=ttk.Frame(self.tabs);self.tabs.add(page,text=title)

            canvas=tk.Canvas(page,bg='#223047',highlightthickness=0)

            scroll=ttk.Scrollbar(page,orient='vertical',command=canvas.yview)
            scroll.pack(side='right',fill='y')
            canvas.configure(yscrollcommand=scroll.set)
            canvas.pack(fill='both',expand=True)
            canvas.bind('<MouseWheel>',lambda e,c=canvas:c.yview_scroll(-int(e.delta/120),'units'))

            self.pages.append(canvas)

        bottom=ttk.Frame(self,padding=12);bottom.pack(fill='x')

        ttk.Label(bottom,text='Native ROM graphics • transparent PNG export • preview only').pack(side='left')

        ttk.Button(bottom,text='Export sheet PNG…',command=self.export).pack(side='right')

        self.refresh()



    def refresh(self):

        self.photos=[];self.sheets=[]

        assignment=self.entries[self.variant.current()][2]

        try:

            for page,standing in zip(self.pages,(True,False)):

                page.delete('all')

                frames,colors=self.engine.frames(assignment,standing,self.palette.current())

                columns=3 if standing else 4

                w,h=len(frames[0][0]),len(frames[0])

                sheet=[[0]*(columns*w) for _ in range(((len(frames)+columns-1)//columns)*h)]

                for i,frame in enumerate(frames):

                    for y,row in enumerate(frame):

                        sheet[i//columns*h+y][i%columns*w:(i%columns+1)*w]=row

                    photo=tk.PhotoImage(master=self,data=base64.b64encode(export_png(frame,colors))).zoom(4)

                    self.photos.append(photo)

                    x=100+i%columns*130;y=40+i//columns*125

                    page.create_image(x,y,anchor='n',image=photo)

                    page.create_text(x,y+h*4+12,text=f'Frame {i%columns+1}' if standing else f'Direction {i//4+1}, frame {i%4+1}',fill='white')

                page.configure(scrollregion=(0,0,600,70+((len(frames)+columns-1)//columns)*125))
                self.sheets.append((sheet,colors))

        except (ValueError,IndexError) as error:

            messagebox.showerror('Sprite preview',str(error),parent=self)



    def export(self):

        index=self.tabs.index(self.tabs.select())

        if index>=len(self.sheets):return

        path=filedialog.asksaveasfilename(parent=self,title='Export sprite sheet',defaultextension='.png',filetypes=[('PNG image','*.png')],initialfile='class-standing.png' if index==0 else 'class-walking.png')

        if path:

            from pathlib import Path

            try:Path(path).write_bytes(export_png(*self.sheets[index]))

            except OSError as error:messagebox.showerror('Export sprite sheet',str(error),parent=self)

