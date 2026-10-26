from ui_common import ask_unsaved
import base64
import tkinter as tk
from tkinter import ttk,messagebox
from chapter_maps import ChapterMap,TERRAIN_NAMES,TERRAIN_COLORS
from map_sprites import MapSprites
from portraits import export_png,png_bytes

GROUP_COLORS=['#cf5454','#4e83d4','#9974cb','#d49337','#399c88','#c46f9b','#729e3d','#ae7453']

class MapWindow(tk.Toplevel):
    def __init__(self,app,chapter=0,mode="army"):
        super().__init__(app)
        self.edit_tiles=mode=="tiles"
        self.app=app
        self.rom=app.rom
        self.title('FE4Builder - Map Editor' if self.edit_tiles else 'FE4Builder - Map Army Editor')
        self.bind('<ButtonPress>',self.raise_on_click)
        self.geometry('1180x820')
        self.minsize(980,660)
        self.transient(app)
        self.grab_set()
        self.model=ChapterMap(self.rom,chapter)
        self.selected=None
        self.painting=False
        self.brush=0
        self.tile_picker=None
        self.dragging=None
        self.panning=False
        self.items={}
        self.image_key=None
        self.visible=[]
        top=ttk.Frame(self,padding=10)
        top.pack(fill='x')
        ttk.Label(top,text='Map Editor' if self.edit_tiles else 'Map Army Editor',style='Title.TLabel').pack(side='left',padx=(0,14))
        self.chapter=ttk.Combobox(top,state='readonly',values=['Prologue']+[f'Chapter {i}' for i in range(1,11)]+['Final Chapter'],width=18)
        self.chapter.current(chapter)
        self.chapter.pack(side='left')
        self.chapter.bind('<<ComboboxSelected>>',self.change_chapter)
        self.save_button=ttk.Button(top,text='Write tiles to ROM' if self.edit_tiles else 'Write positions to ROM',command=self.save,state='disabled')
        ttk.Button(top,text='Save & Launch (F5)',command=self.save_and_launch).pack(side='right',padx=8)
        self.save_button.pack(side='right')
        self.redo_button=ttk.Button(top,text='Redo',command=lambda:self.history_step(True))
        self.redo_button.pack(side='right',padx=5)
        self.undo_button=ttk.Button(top,text='Undo',command=lambda:self.history_step(False))
        self.undo_button.pack(side='right')
        if self.edit_tiles:
            paintbar=ttk.Frame(self,padding=(10,0,10,8));paintbar.pack(fill='x')
            self.choose_tile_button=ttk.Button(paintbar,text='Choose map tile...',command=self.choose_tile)
            self.choose_tile_button.pack(side='left',padx=8)
            self.brush_label=ttk.Label(paintbar);self.brush_label.pack(side='left')
            ttk.Label(paintbar,text='Left-click or drag to paint. Right-click picks a tile; right-drag pans.').pack(side='left',padx=12)
        else:
            ttk.Label(self,text='Drag unit sprites to move deployments. Right-drag to pan.',padding=(10,0,10,8)).pack(fill='x')

        body=ttk.Panedwindow(self,orient='horizontal')
        body.pack(fill='both',expand=True,padx=10,pady=(0,8))
        left=ttk.Frame(body,width=300)
        body.add(left,weight=0)
        ttk.Label(left,text='Deployment group').pack(anchor='w')
        self.group=ttk.Combobox(left,state='readonly',width=36)
        self.group.pack(fill='x',pady=(4,10))
        self.group.bind('<<ComboboxSelected>>',lambda _:self.populate())
        self.search=tk.StringVar()
        ttk.Entry(left,textvariable=self.search).pack(fill='x')
        self.search.trace_add('write',lambda *_:self.populate())
        listing=ttk.Frame(left)
        listing.pack(fill='both',expand=True,pady=8)
        self.list=ttk.Treeview(listing,columns=('name','position'),show='headings',selectmode='browse')
        self.list.heading('name',text='Deployment')
        self.list.heading('position',text='X, Y')
        self.list.column('name',width=225)
        self.list.column('position',width=65,stretch=False)
        scrollbar=ttk.Scrollbar(listing,command=self.list.yview)
        scrollbar.pack(side='right',fill='y')
        self.list.config(yscrollcommand=scrollbar.set)
        self.list.pack(fill='both',expand=True)
        self.list.bind('<<TreeviewSelect>>',self.list_selected)
        self.list.bind('<Double-1>',lambda _:self.center_selected())
        self.unit_info=tk.StringVar(value='Select a deployment.')
        ttk.Label(left,textvariable=self.unit_info,wraplength=285).pack(anchor='w',pady=6)
        position=ttk.Frame(left)
        position.pack(fill='x')
        self.x=tk.StringVar(value='0')
        self.y=tk.StringVar(value='0')
        ttk.Label(position,text='X').pack(side='left')
        ttk.Spinbox(position,from_=0,to=63,textvariable=self.x,width=4).pack(side='left',padx=4)
        ttk.Label(position,text='Y').pack(side='left')
        ttk.Spinbox(position,from_=0,to=63,textvariable=self.y,width=4).pack(side='left',padx=4)
        ttk.Button(position,text='Set position',command=self.set_position).pack(side='left',padx=4)
        ttk.Button(left,text='Center selected unit',command=self.center_selected).pack(fill='x',pady=8)
        ttk.Label(left,text='Corner badges identify deployment groups. Groups can appear at different times, so overlaps are allowed.\nSprite colors are a preview; event-driven allegiance changes are not simulated.\nScripted event placements are separate from these army tables.',wraplength=285,style='Subtitle.TLabel').pack(anchor='w',pady=8)
        ttk.Label(left,text='Unit sprite colors').pack(anchor='w')
        self.unit_palette=ttk.Combobox(left,state='readonly',values=['Auto (faction slot)','Blue','Red','Green','Yellow','Gray'],width=26)
        self.unit_palette.current(0)
        self.unit_palette.pack(fill='x',pady=(4,8))
        self.unit_palette.bind('<<ComboboxSelected>>',lambda _:self.draw())
        self.deployment_panel=left
        if self.edit_tiles:
            body.forget(left)
        right=ttk.Frame(body)
        body.add(right,weight=1)
        controls=ttk.Frame(right)
        controls.pack(fill='x',pady=(0,6))
        ttk.Label(controls,text='Zoom').pack(side='left')
        self.zoom=ttk.Combobox(controls,state='readonly',values=['50%','100%','150%','200%'],width=7)
        self.zoom.current(1)
        self.zoom.pack(side='left',padx=6)
        self.zoom.bind('<<ComboboxSelected>>',lambda _:self.draw())
        self.view=ttk.Combobox(controls,state='readonly',values=['Map artwork','Terrain'],width=12)
        self.view.current(0)
        self.view.pack(side='left',padx=6)
        self.view.bind('<<ComboboxSelected>>',lambda _:self.draw())
        self.grid=tk.BooleanVar(value=False)
        ttk.Checkbutton(controls,text='Grid',variable=self.grid,command=self.draw).pack(side='left',padx=6)
        self.full=tk.BooleanVar(value=False)
        ttk.Checkbutton(controls,text='Full 64×64',variable=self.full,command=self.draw).pack(side='left',padx=6)
        if self.edit_tiles:
            ttk.Button(controls,text='Resize map...',command=self.resize_map).pack(side='left',padx=6)
        self.size_label=ttk.Label(controls)
        self.size_label.pack(side='left',padx=6)
        ttk.Label(controls,text='Wheel: scroll · Right-drag: pan',style='Subtitle.TLabel').pack(side='right')
        area=ttk.Frame(right)
        area.pack(fill='both',expand=True)
        area.rowconfigure(0,weight=1)
        area.columnconfigure(0,weight=1)
        self.canvas=tk.Canvas(area,background='#202832',highlightthickness=0)
        self.canvas.grid(row=0,column=0,sticky='nsew')
        ttk.Scrollbar(area,orient='vertical',command=self.canvas.yview).grid(row=0,column=1,sticky='ns')
        ttk.Scrollbar(area,orient='horizontal',command=self.canvas.xview).grid(row=1,column=0,sticky='ew')
        # Keep wheel events local to the map canvas.
        from ui_common import bind_canvas_wheel
        bind_canvas_wheel(self.canvas)
        self.canvas.bind('<ButtonPress-1>',self.press)
        self.canvas.bind('<B1-Motion>',self.motion)
        self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Motion>',self.hover)
        self.right_start=None
        self.right_dragged=False
        self.canvas.bind('<ButtonPress-3>',self.right_press)
        self.canvas.bind('<B3-Motion>',self.right_motion)
        self.canvas.bind('<ButtonRelease-3>',self.right_release)
        self.status=tk.StringVar()
        ttk.Label(self,textvariable=self.status,relief='sunken',padding=6).pack(fill='x',side='bottom')
        self.bind('<F5>',lambda e:self.save_and_launch())
        self.bind('<Control-z>',lambda _:self.history_step(False))
        self.bind('<Control-y>',lambda _:self.history_step(True))
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.load()

    @property
    def scale(self):
        return [8,16,24,32][self.zoom.current()]

    def raise_on_click(self,event):
        if event.widget.winfo_toplevel() is self:
            self.lift()

    def choose_tile(self):
        if not self.edit_tiles:
            return
        from tileset_window import TilesetWindow
        if self.tile_picker is not None and self.tile_picker.winfo_exists():
            self.tile_picker.lift()
            return
        self.tile_picker=TilesetWindow(self,self.model.chapter,on_pick=self.set_brush)

    def set_brush(self,tile):
        if not self.edit_tiles:
            return
        self.brush=tile
        self.brush_photo=tk.PhotoImage(master=self,data=base64.b64encode(png_bytes(self.tile_art[tile],self.model.palette))).zoom(2)
        self.brush_label.configure(text=f'Tile {tile:03X}',image=self.brush_photo,compound='left')
        self.draw()

    def view_tileset(self):
        self.choose_tile()

    def stage_resize(self,width,height,x,y):
        self.model.resize(width,height,x,y)
        self.full.set(False)
        self.draw()
        self.canvas.xview_moveto(0);self.canvas.yview_moveto(0)
        count=len(self.model.outside_deployments())
        self.status.set(f'Map size staged: {width}×{height}, origin ({x}, {y}). {count} deployments outside bounds. Write tiles to ROM to save.')

    def resize_map(self):
        dialog=tk.Toplevel(self);dialog.title('Resize map — chapter camera bounds')
        dialog.transient(self);dialog.resizable(False,False);dialog.grab_set()
        frame=ttk.Frame(dialog,padding=16);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Resize the chapter’s visible area',font=('Segoe UI',12,'bold')).grid(row=0,column=0,columnspan=4,sticky='w')
        left,top,right,bottom=self.model.bounds
        values=[tk.StringVar(value=str(v)) for v in (right-left,bottom-top,left,top)]
        for row,(label,variable,minimum,maximum) in enumerate(zip(
                ('Width (tiles)','Height (tiles)','Left edge X','Top edge Y'),values,(16,14,0,0),(64,64,48,50)),1):
            ttk.Label(frame,text=label).grid(row=row,column=0,sticky='w',pady=4)
            ttk.Spinbox(frame,from_=minimum,to=maximum,textvariable=variable,width=8).grid(row=row,column=1,sticky='w',padx=12)
        ttk.Label(frame,text='FE4 keeps a 64×64 terrain grid. This changes the saved camera bounds;\n'
                  'cropped tiles stay intact and can be restored by enlarging the area.\n'
                  'Units, castles and event coordinates are not moved. Scripts or AI may\n'
                  'still use tiles outside this area; adjust your chapter design separately.\n'
                  'Minimum 16×14 tiles fits the game screen. No ROM expansion.',justify='left').grid(row=5,column=0,columnspan=4,sticky='w',pady=12)
        warning=tk.StringVar()
        ttk.Label(frame,textvariable=warning,wraplength=480).grid(row=6,column=0,columnspan=4,sticky='w',pady=8)
        def preview(*_):
            try:
                bounds=self.model.resize_bounds(*(int(v.get()) for v in values))
                indices=self.model.outside_deployments(bounds)
                names=', '.join(self.model.units.names[i] for i in indices[:3])
                warning.set(f'{len(indices)} deployments outside this area.'+(' Examples: '+names if names else '')+' Scripted event placements are not counted.')
                apply.config(state='normal')
            except ValueError as error:
                warning.set(str(error));apply.config(state='disabled')
        def stage():
            try:self.stage_resize(*(int(v.get()) for v in values))
            except ValueError as error:
                messagebox.showerror('Invalid map size',str(error),parent=dialog);return
            dialog.destroy();self.grab_set()
        def cancel():dialog.destroy();self.grab_set()
        apply=ttk.Button(frame,text='Stage resize',command=stage);apply.grid(row=7,column=0,pady=8)
        ttk.Button(frame,text='Cancel',command=cancel).grid(row=7,column=1,pady=8)
        dialog.protocol('WM_DELETE_WINDOW',cancel)
        for variable in values:variable.trace_add('write',preview)
        preview()
        return dialog

    def load(self):
        if self.tile_picker is not None and self.tile_picker.winfo_exists():
            self.tile_picker.chapter.current(self.model.chapter)
            self.tile_picker.load()
        self.tile_art=self.model.tiles()
        self.tile_photos={}
        self.sprite_engine=MapSprites(self.rom)
        self.sprite_photos={}
        self.sprite_errors={}
        self.groups=sorted(set(name.split(' / ')[0] for name in self.model.units.names))
        self.group.config(values=['All deployment groups']+self.groups)
        self.group.current(0)
        self.background=tk.PhotoImage(master=self,data=base64.b64encode(self.model.png()))
        self.terrain_background=tk.PhotoImage(master=self,data=base64.b64encode(self.model.png(terrain=True)))
        self.selected=None
        self.populate()
        if self.edit_tiles:
            self.set_brush(self.brush)
        self.draw()
        self.status.set('Choose a tile and click or drag to paint. Changes stay staged until Write tiles to ROM.' if self.edit_tiles else 'Drag units to move them. Changes stay staged until Write positions to ROM.')

    def populate(self):
        if not hasattr(self,'canvas'):
            return
        query=self.search.get().casefold()
        group=self.group.get()
        self.visible=[i for i,name in enumerate(self.model.units.names)
                      if (group=='All deployment groups' or name.split(' / ')[0]==group)
                      and query in f'{i:03X} {name}'.casefold()]
        self.list.delete(*self.list.get_children())
        for index in self.visible:
            x,y=self.model.positions[index]
            self.list.insert('','end',iid=str(index),values=(f'{index:03X} {self.model.units.names[index]}',f'{x}, {y}'))
        if self.selected not in self.visible:
            self.selected=self.visible[0] if self.visible else None
        if self.selected is not None:
            self.list.selection_set(str(self.selected))
            self.update_selection()
        self.draw()

    def draw(self):
        left,top,right,bottom=self.model.bounds
        self.size_label.config(text=f'{right-left}×{bottom-top} · origin {left},{top}')
        self.canvas.delete('all')
        s=self.scale
        background=self.background if self.view.current()==0 else self.terrain_background
        key=(str(background),s)
        if key!=self.image_key:
            if s==8:
                self.image=background.subsample(2,2)
            elif s==16:
                self.image=background
            elif s==24:
                self.image=background.zoom(3,3).subsample(2,2)
            else:
                self.image=background.zoom(2,2)
            self.image_key=key
        self.canvas.create_image(0,0,image=self.image,anchor='nw')
        bounds=(0,0,64,64) if self.full.get() else self.model.bounds
        self.canvas.config(scrollregion=tuple(value*s for value in bounds))
        normal=self.model.bounds
        if self.full.get() and normal!=(0,0,64,64):
            rectangles=[(0,0,64,normal[1]),(0,normal[3],64,64),
                        (0,normal[1],normal[0],normal[3]),(normal[2],normal[1],64,normal[3])]
            for x0,y0,x1,y1 in rectangles:
                if x1>x0 and y1>y0:
                    self.canvas.create_rectangle(x0*s,y0*s,x1*s,y1*s,fill='#29323d',stipple='gray50',outline='')
        # Overlay staged cells so each brush stroke avoids rebuilding the full map.
        for index,(old,tile) in enumerate(zip(self.model.original_map,self.model.map)):
            if old==tile:continue
            x=index%64;y=index//64
            if self.view.current()==1:
                color=TERRAIN_COLORS[self.model.terrain[tile&1023]]
                self.canvas.create_rectangle(x*s,y*s,(x+1)*s,(y+1)*s,fill='#%02x%02x%02x'%color,outline='')
            else:
                key=(tile&1023,s)
                if key not in self.tile_photos:
                    image=tk.PhotoImage(master=self,data=base64.b64encode(png_bytes(self.tile_art[tile&1023],self.model.palette)))
                    if s==8:image=image.subsample(2)
                    elif s==24:image=image.zoom(3).subsample(2)
                    elif s==32:image=image.zoom(2)
                    self.tile_photos[key]=image
                self.canvas.create_image(x*s,y*s,image=self.tile_photos[key],anchor='nw')
        if self.grid.get():
            for i in range(65):
                self.canvas.create_line(i*s,0,i*s,64*s,fill='#7c8d79',tags='grid')
                self.canvas.create_line(0,i*s,64*s,i*s,fill='#7c8d79',tags='grid')
        for y in range(bounds[1],bounds[3]):
            for x in range(bounds[0],bounds[2]):
                terrain,_=self.model.tile_info(x,y)
                if self.view.current()==1 and terrain in (9,18,22,24):
                    self.canvas.create_text(x*s+s/2,y*s+s/2,text={9:'C',18:'V',22:'+',24:'T'}[terrain],fill='#342b27',font=('Segoe UI',max(6,s//2)))
        self.items={}
        for index in (self.visible if not self.edit_tiles else []):
            x,y=self.model.positions[index]
            if not 0<=x<64 or not 0<=y<64:
                continue
            group=self.model.units.names[index].split(' / ')[0]
            color=GROUP_COLORS[self.groups.index(group)%len(GROUP_COLORS)]
            center=(x*s+s/2,(y+1)*s)
            tags=('unit',f'unit-{index}')
            if index==self.selected:
                self.canvas.create_rectangle(x*s,y*s,(x+1)*s,(y+1)*s,outline='#ffe06b',width=2,tags=tags)
            try:
                values=self.rom.values(self.model.units,index)
                palette=self.unit_palette.current()-1 if self.unit_palette.current() else (0 if values[5]==0 else 1)
                rows,colors,assignment=self.sprite_engine.sprite(values[0],palette)
                key=(assignment,palette,s)
                if key not in self.sprite_photos:
                    image=tk.PhotoImage(master=self,data=base64.b64encode(export_png(rows,colors)))
                    if s==8:
                        image=image.subsample(2,2)
                    elif s==24:
                        image=image.zoom(3,3).subsample(2,2)
                    elif s==32:
                        image=image.zoom(2,2)
                    self.sprite_photos[key]=image
                marker=self.canvas.create_image(*center,image=self.sprite_photos[key],anchor='s',tags=tags)
            except ValueError as error:
                self.sprite_errors[index]=str(error)
                marker=self.canvas.create_rectangle(x*s+2,y*s+2,(x+1)*s-2,(y+1)*s-2,fill=color,outline='#e6edf3',tags=tags)
                self.canvas.create_text(x*s+s/2,y*s+s/2,text='?',fill='#ffffff',font=('Segoe UI',max(6,s//2)),tags=tags)
            self.canvas.create_rectangle(x*s+1,y*s+1,x*s+max(3,s//4),y*s+max(3,s//4),fill=color,outline='#182633',tags=tags)
            self.items[index]=marker
        if self.selected in self.items:
            self.canvas.tag_raise(f'unit-{self.selected}')
        if not self.full.get():
            # Canvas widgets can be larger than a small scroll region. Mask the
            # retained terrain so cropped tiles do not spill into that space.
            for x0,y0,x1,y1 in ((0,0,64,top),(0,bottom,64,64),
                                (0,top,left,bottom),(right,top,64,bottom)):
                if x1>x0 and y1>y0:
                    self.canvas.create_rectangle(x0*s,y0*s,x1*s,y1*s,fill='#202832',outline='',tags='crop-mask')
        self.save_button.config(state='normal' if self.model.dirty else 'disabled')
        self.undo_button.config(state='normal' if self.rom.history.can_undo or self.model.dirty else 'disabled')
        self.redo_button.config(state='normal' if self.rom.history.can_redo and not self.model.dirty else 'disabled')

    def update_selection(self):
        if self.selected is None:
            self.unit_info.set('No matching deployment.')
            return
        x,y=self.model.positions[self.selected]
        self.x.set(str(x)); self.y.set(str(y))
        self.unit_info.set(f'{self.model.units.names[self.selected]}\nRecord {self.selected:03X} · X {x}, Y {y}')
        if self.selected in self.sprite_errors:
            self.unit_info.set(self.unit_info.get()+f'\nSprite unavailable: {self.sprite_errors[self.selected]}')

    def list_selected(self,_=None):
        selection=self.list.selection()
        if selection:
            self.selected=int(selection[0])
            self.update_selection()
            self.draw()

    def right_press(self,event):
        self.right_start=(event.x,event.y)
        self.right_dragged=False
        self.canvas.scan_mark(int(event.x),int(event.y))

    def right_motion(self,event):
        if self.right_start is None:
            return
        if max(abs(event.x-self.right_start[0]),abs(event.y-self.right_start[1]))>=4:
            self.right_dragged=True
        if self.right_dragged:
            self.canvas.scan_dragto(int(event.x),int(event.y),gain=1)

    def right_release(self,event):
        if self.right_start is None:
            return
        self.right_motion(event)
        if self.edit_tiles and not self.right_dragged:
            x,y=self.point(event)
            bounds=(0,0,64,64) if self.full.get() else self.model.bounds
            if bounds[0]<=x<bounds[2] and bounds[1]<=y<bounds[3]:
                tile=self.model.map[y*64+x]&1023
                self.set_brush(tile)
                self.status.set(f'Picked tile {tile:03X} at ({x}, {y}). Left-click to paint it.')
        self.right_start=None

    def point(self,event):
        return int(self.canvas.canvasx(event.x)//self.scale),int(self.canvas.canvasy(event.y)//self.scale)

    def paint_cell(self,event):
        x,y=self.point(event)
        bounds=(0,0,64,64) if self.full.get() else self.model.bounds
        if bounds[0]<=x<bounds[2] and bounds[1]<=y<bounds[3]:
            before=self.model.map[y*64+x]
            self.model.paint(x,y,self.brush)
            if self.model.map[y*64+x]!=before:self.draw()
        self.hover(event)

    def press(self,event):
        if self.edit_tiles:
            self.painting=True
            self.paint_cell(event)
            return
        x=self.canvas.canvasx(event.x);y=self.canvas.canvasy(event.y)
        hit=self.canvas.find_overlapping(x-2,y-2,x+2,y+2)
        lookup={value:key for key,value in self.items.items()}
        cell=self.point(event)
        occupants=[index for index in self.visible if self.model.positions[index]==cell and index in self.items]
        # Mounted sprites extend into neighboring tiles; prefer the unit whose
        # actual placement tile was clicked, rather than transparent image bounds.
        self.dragging=(self.selected if self.selected in occupants else occupants[-1]) if occupants else next((lookup[item] for item in reversed(hit) if item in lookup),None)
        if self.dragging is not None:
            self.selected=self.dragging
            self.list.selection_set(str(self.selected))
            self.list.see(str(self.selected))
            self.update_selection()
        else:
            self.canvas.scan_mark(int(event.x),int(event.y))
            self.panning=True

    def motion(self,event):
        if self.painting:
            self.paint_cell(event)
            return
        if self.dragging is not None:
            x,y=self.point(event)
            if 0<=x<64 and 0<=y<64:
                self.model.move(self.dragging,x,y)
                self.update_selection()
                self.list.item(str(self.dragging),values=(f'{self.dragging:03X} {self.model.units.names[self.dragging]}',f'{x}, {y}'))
                self.draw()
        elif self.panning:
            self.canvas.scan_dragto(int(event.x),int(event.y),gain=1)

    def release(self,event):
        self.motion(event)
        self.dragging=None
        self.painting=False
        self.panning=False
        self.hover(event)

    def hover(self,event):
        x,y=self.point(event)
        if 0<=x<64 and 0<=y<64:
            terrain,flags=self.model.tile_info(x,y)
            name=TERRAIN_NAMES[terrain] if terrain<len(TERRAIN_NAMES) else f'Unknown terrain {terrain}'
            dirty=sum(a!=b for a,b in zip(self.model.positions,self.model.original_positions))
            normal=self.model.bounds
            extra=' · Outside chapter camera bounds' if not normal[0]<=x<normal[2] or not normal[1]<=y<normal[3] else ''
            tiles=sum(a!=b for a,b in zip(self.model.map,self.model.original_map))
            self.status.set(f'Tile ({x}, {y}) ID {self.model.map[y*64+x]&1023:03X} · {name} · Blocking flags 0x{flags:02X} · {dirty} staged moves, {tiles} painted cells'+extra)

    def set_position(self):
        if self.edit_tiles or self.selected is None:
            return
        try:
            self.model.move(self.selected,int(self.x.get()),int(self.y.get()))
        except ValueError as error:
            messagebox.showerror('Invalid position',str(error),parent=self)
            return
        self.populate()

    def center_selected(self):
        if self.selected is None:
            return
        x,y=self.model.positions[self.selected]
        bounds=(0,0,64,64) if self.full.get() else self.model.bounds
        if not bounds[0]<=x<bounds[2] or not bounds[1]<=y<bounds[3]:
            self.status.set('This position is outside the visible bounds. Enable Full 64×64 to inspect it; off-map coordinates are preserved.')
            return
        self.canvas.xview_moveto(max(0,(x-bounds[0]-self.canvas.winfo_width()/self.scale/2)/(bounds[2]-bounds[0])))
        self.canvas.yview_moveto(max(0,(y-bounds[1]-self.canvas.winfo_height()/self.scale/2)/(bounds[3]-bounds[1])))

    def save_and_launch(self):
        return self.app.save_and_launch(save_callback=self.save,parent=self)

    def save(self):
        if self.app.rom is not self.rom:
            messagebox.showerror('ROM changed','The opened ROM changed; reopen the map editor.',parent=self)
            return False
        before=bytes(self.rom.data)
        try:
            details=self.model.write()
            self.rom.save_original(f'{"Map tiles" if self.edit_tiles else "Army placements"}: {self.model.units.name}',details)
        except (ValueError,OSError) as error:
            self.rom.data[:]=before
            messagebox.showerror('Cannot write map changes',str(error),parent=self)
            return False
        self.model=ChapterMap(self.rom,self.model.chapter)
        self.load()
        self.app.refresh_after_history()
        self.draw()
        self.status.set('Map changes saved. Automatic backup and undo history updated.')
        return True

    def settle(self):
        if not self.model.dirty:
            return True
        answer=ask_unsaved(self,'Write the staged map tiles and size to the opened ROM?' if self.edit_tiles else 'Write the staged unit positions to the opened ROM?')
        if answer is None:
            return False
        if answer:
            return self.save()
        self.model.positions=self.model.original_positions[:]
        self.model.map=self.model.original_map[:]
        self.model.bounds=self.model.original_bounds
        self.draw()
        return True

    def change_chapter(self,_=None):
        target=self.chapter.current()
        if not self.settle():
            self.chapter.current(self.model.chapter)
            return
        try:
            model=ChapterMap(self.rom,target)
        except ValueError as error:
            self.chapter.current(self.model.chapter)
            messagebox.showerror('Cannot open chapter',str(error),parent=self)
            return
        self.search.set('')
        self.model=model
        self.load()
        self.canvas.xview_moveto(0);self.canvas.yview_moveto(0)

    def history_step(self,redo):
        if not self.settle():
            return 'break'
        selected=self.selected
        self.app.history_step(redo)
        try:
            self.model=ChapterMap(self.rom,self.model.chapter)
            self.load()
            if selected in self.visible:
                self.selected=selected
                self.list.selection_set(str(selected))
                self.update_selection()
                self.draw()
        except ValueError as error:
            messagebox.showerror('Cannot reload map',str(error),parent=self)
        return 'break'

    def close(self):
        if self.settle():
            self.destroy()

class MapEditorWindow(MapWindow):
    def __init__(self,app,chapter=0):
        super().__init__(app,chapter,mode='tiles')

class ArmyMapWindow(MapWindow):
    def __init__(self,app,chapter=0):
        super().__init__(app,chapter,mode='army')

def open_map_window(app,chapter=0,mode='tiles'):
    if not app.rom:
        messagebox.showinfo('Open a ROM','Open a FE4 ROM first.')
        return
    if not app.settle():
        return
    try:
        ChapterMap(app.rom,chapter)
        return (MapEditorWindow if mode=="tiles" else ArmyMapWindow)(app,chapter)
    except ValueError as error:
        messagebox.showerror('Map unavailable',str(error))
