"""Read-only chapter tileset inspection and PNG export."""
import base64
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
from chapter_maps import ChapterMap,TERRAIN_NAMES
from portraits import png_bytes

CHAPTERS=['Prologue']+[f'Chapter {i}' for i in range(1,11)]+['Final Chapter']
TILESET_COLUMNS=32
VIEWS=['Map tiles: all 1024','Map tiles: chapter-specific 256','Map tiles: shared 768','Graphics: all 768','Graphics: chapter-specific 128','Graphics: shared 640']

def graphics_tiles(model,palette):
    tiles=[]
    for number in range(len(model.graphics)//32):
        raw=model.graphics[number*32:(number+1)*32]
        tile=[]
        for y in range(8):
            tile.append([palette*16+sum(((raw[y*2+(16 if p>=2 else 0)+p%2]>>(7-x))&1)<<p for p in range(4)) for x in range(8)])
        tiles.append(tile)
    return tiles

def sheet(tiles,columns=TILESET_COLUMNS):
    size=len(tiles[0])
    rows=[[0]*(columns*size) for _ in range(((len(tiles)+columns-1)//columns)*size)]
    for i,tile in enumerate(tiles):
        for y,row in enumerate(tile):
            rows[i//columns*size+y][i%columns*size:(i%columns+1)*size]=row
    return rows

class TilesetWindow(tk.Toplevel):
    def __init__(self,app,chapter=0,on_pick=None):
        super().__init__(app)
        self.rom=app.rom
        self.on_pick=on_pick
        self.title('FE4Builder - Tileset Viewer / Exporter')
        self.geometry('1000x760');self.minsize(820,600)
        if not on_pick:
            self.transient(app)
        self.bind('<ButtonPress>',self.raise_on_click)
        bar=ttk.Frame(self,padding=10);bar.pack(fill='x')
        self.chapter=ttk.Combobox(bar,values=CHAPTERS,state='readonly',width=16)
        self.chapter.current(chapter);self.chapter.pack(side='left')
        self.view=ttk.Combobox(bar,values=VIEWS,state='readonly',width=34)
        self.view.current(0);self.view.pack(side='left',padx=8)
        ttk.Label(bar,text='Zoom').pack(side='left')
        self.zoom=ttk.Combobox(bar,values=['100%','200%','300%','400%'],state='readonly',width=7)
        self.zoom.current(1);self.zoom.pack(side='left',padx=6)
        self.chapter.bind('<<ComboboxSelected>>',lambda e:self.load())
        if on_pick:
            self.chapter.configure(state='disabled')
        for combo in (self.view,self.zoom):combo.bind('<<ComboboxSelected>>',lambda e:self.draw())
        controls=ttk.Frame(self,padding=(10,0,10,8));controls.pack(fill='x')
        ttk.Label(controls,text='8x8 graphics palette').pack(side='left')
        self.palette=ttk.Combobox(controls,values=[f'Palette {i}' for i in range(8)],state='readonly',width=12)
        self.palette.current(1);self.palette.pack(side='left',padx=8)
        self.palette.bind('<<ComboboxSelected>>',lambda e:self.draw())
        if on_pick:
            ttk.Label(controls,text='Click a map tile to set the brush.').pack(side='left',padx=8)
        ttk.Button(controls,text='Export sheet PNG...',command=self.export_sheet).pack(side='right')
        ttk.Button(controls,text='Export selected tile...',command=self.export_tile).pack(side='right',padx=8)
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=10,pady=8)
        area=ttk.Frame(body);body.add(area,weight=1)
        area.rowconfigure(0,weight=1);area.columnconfigure(0,weight=1)
        self.canvas=tk.Canvas(area,bg='#223047',highlightthickness=0)
        self.canvas.grid(row=0,column=0,sticky='nsew')
        ys=ttk.Scrollbar(area,orient='vertical',command=self.canvas.yview);ys.grid(row=0,column=1,sticky='ns')
        xs=ttk.Scrollbar(area,orient='horizontal',command=self.canvas.xview);xs.grid(row=1,column=0,sticky='ew')
        self.canvas.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        self.canvas.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(-int(e.delta/120),'units'))
        self.canvas.bind('<Button-1>',self.select)
        side=ttk.Frame(body,width=260,padding=12);body.add(side,weight=0)
        self.preview=ttk.Label(side);self.preview.pack(anchor='w',pady=8)
        self.info=tk.StringVar();ttk.Label(side,textvariable=self.info,wraplength=250,justify='left').pack(anchor='w')
        ttk.Label(self,text='Read-only. Map tiles retain their chapter colors; raw 8x8 graphics use the chosen palette. PNG exports use native size without labels or grid.',padding=10,wraplength=950).pack(fill='x')
        self.selected=0;self.load()

    def raise_on_click(self,event):
        if event.widget.winfo_toplevel() is self:
            self.lift()

    def load(self):
        try:
            self.model=ChapterMap(self.rom,self.chapter.current())
            self.map_tiles=self.model.tiles()
            self.selected=0;self.draw()
        except (ValueError,IndexError) as error:
            messagebox.showerror('Tileset viewer',str(error),parent=self)

    def draw(self):
        view=self.view.current();self.raw=view>=3
        self.palette.configure(state='readonly' if self.raw else 'disabled')
        tiles=graphics_tiles(self.model,self.palette.current()) if self.raw else self.map_tiles
        start,end={0:(0,1024),1:(0,256),2:(256,1024),3:(0,768),4:(640,768),5:(0,640)}[view]
        self.ids=list(range(start,end));self.tiles=tiles[start:end]
        self.rows=sheet(self.tiles);self.scale=self.zoom.current()+1
        self.size=len(self.tiles[0]);self.cell=self.size*self.scale
        self.photo=tk.PhotoImage(master=self,data=base64.b64encode(png_bytes(self.rows,self.model.palette))).zoom(self.scale)
        self.canvas.delete('all');self.canvas.create_image(0,0,image=self.photo,anchor='nw')
        width=len(self.rows[0])*self.scale;height=len(self.rows)*self.scale
        for x in range(0,width+1,self.cell):self.canvas.create_line(x,0,x,height,fill='#586574')
        for y in range(0,height+1,self.cell):self.canvas.create_line(0,y,width,y,fill='#586574')
        self.canvas.configure(scrollregion=(0,0,width,height))
        self.canvas.xview_moveto(0);self.canvas.yview_moveto(0)
        self.selected=min(self.selected,len(self.tiles)-1);self.details()

    def select(self,event):
        x=int(self.canvas.canvasx(event.x)//self.cell);y=int(self.canvas.canvasy(event.y)//self.cell)
        index=y*TILESET_COLUMNS+x
        if 0<=x<TILESET_COLUMNS and 0<=index<len(self.tiles):
            self.selected=index
            self.details()
            if self.on_pick and not self.raw:
                self.pick()

    def details(self):
        index=self.ids[self.selected];tile=self.tiles[self.selected]
        self.preview_photo=tk.PhotoImage(master=self,data=base64.b64encode(png_bytes(tile,self.model.palette))).zoom(8)
        self.preview.configure(image=self.preview_photo)
        self.canvas.delete('selection')
        x=self.selected%TILESET_COLUMNS*self.cell;y=self.selected//TILESET_COLUMNS*self.cell
        self.canvas.create_rectangle(x+1,y+1,x+self.cell-1,y+self.cell-1,outline='#ffe575',width=2,tags='selection')
        kind=('Shared' if index<640 else 'Chapter-specific') if self.raw else ('Chapter-specific' if index<256 else 'Shared')
        text=f'Tile {index:03X} ({index})\n{kind}\n{self.size} x {self.size} pixels'
        if self.raw:
            text+=f'\nPalette {self.palette.current()}'
        else:
            terrain=self.model.terrain[index]
            name=TERRAIN_NAMES[terrain] if terrain<len(TERRAIN_NAMES) else f'Terrain {terrain}'
            count=sum((self.model.map[y*64+x]&1023)==index for y in range(self.model.bounds[1],self.model.bounds[3]) for x in range(self.model.bounds[0],self.model.bounds[2]))
            text+=f'\nTerrain: {name}\nUses in visible map: {count}\n\n8x8 components (TL, BL, TR, BR):'
            defs=self.model.definitions+self.model.dictionary
            for part in defs[index*4:index*4+4]:
                text+=f'\n{part&1023:03X}, palette {(part>>10)&7}'+(' flip X' if part&0x4000 else '')+(' flip Y' if part&0x8000 else '')
        self.info.set(text)

    def pick(self):
        if self.raw:
            messagebox.showinfo('Choose a map tile','Choose an assembled 16x16 map tile to paint.',parent=self)
            return
        if self.on_pick:
            self.on_pick(self.ids[self.selected])

    def export_sheet(self):self.export(self.rows,'tileset')
    def export_tile(self):self.export(self.tiles[self.selected],f'tile-{self.ids[self.selected]:03X}')
    def export(self,rows,name):
        path=filedialog.asksaveasfilename(parent=self,title='Export tileset PNG',defaultextension='.png',filetypes=[('PNG image','*.png')],initialfile=f'chapter-{self.chapter.current()}-{name}.png')
        if path:
            try:Path(path).write_bytes(png_bytes(rows,self.model.palette))
            except OSError as error:messagebox.showerror('Export tileset',str(error),parent=self)
