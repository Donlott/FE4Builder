"""Portrait-only packing. Never infer ownership from blank bytes or pointer gaps."""
from portrait_codec import compress, decompress
from portrait_document import EditorError, GFX_TABLE, PAL_TABLE, COUNT

# Original FE4 portrait graphics area: lower halves of banks CA through D0.
# This is an eligibility boundary, NOT permission to use every byte in it.
# Only live, directly-read stream bytes inside these bounds are reclaimable.
PROFILE_WINDOWS = [(0xA65B5,0xA8000)] + [(b*0x10000,b*0x10000+0x8000) for b in range(0xB,0x10)] + [(0x100000,0x105639)]

def intervals(addresses):
    runs=[]
    for a in sorted(addresses):
        if runs and runs[-1][1]==a and a%0x8000:runs[-1][1]=a+1
        else:runs.append([a,a+1])
    return runs

class Plan:
    def __init__(self,rom):
        self.writes=[];self.pointers={};self.palette_pointers={}
        self.allowed=set();self.rows=[]
        # Read direct payload bytes separately from compressed lookback reads.
        # An out-of-area lookback must never become writable storage.
        direct=set()
        for p in rom.portraits:
            decompress(rom.data,p.gfx,2048,direct=direct)
        eligible=set()
        for a,b in PROFILE_WINDOWS:eligible.update(range(a,b))
        owned=direct & eligible
        protected=set(range(GFX_TABLE,PAL_TABLE+COUNT*3))
        for p in rom.portraits:protected.update(range(p.pal,p.pal+32))
        for h in (0xFFB0,0x40FFB0):protected.update(range(h,h+80))
        owned-=protected
        self.allowed.update(owned)
        free=intervals(owned)
        self.portrait_capacity=len(owned)
        self.reserved_capacity=0
        if rom.arena:
            a,b=rom.arena
            # reserve() validates the original bytes; repeat in case data changed.
            rom.reserve(a,b)
            self.allowed.update(range(a,b));self.reserved_capacity=b-a
            pos=a
            while pos<b:
                end=min(b,(pos//0x8000+1)*0x8000);free.append([pos,end]);pos=end
        groups={}
        for p in rom.portraits:
            raw,pal=rom.pending.get(p.id,(p.raw,p.palette))
            groups.setdefault(raw,[]).append(p.id)
        # Cache compression across preview/save; content is the key, not slot ID.
        cache=rom._compression_cache
        items=[]
        for raw,ids in groups.items():
            if raw not in cache:
                blob=compress(raw)
                if decompress(blob,0,2048)[0]!=raw:raise EditorError('Encoder verification failed.')
                cache[raw]=blob
            items.append((cache[raw],ids))
        self.graphics_required=sum(len(blob) for blob,_ in items)
        def allocate(blob,label):
            fits=[(b-a,a,i) for i,(a,b) in enumerate(free) if b-a>=len(blob)]
            if not fits:
                left=sum(b-a for a,b in free);largest=max((b-a for a,b in free),default=0)
                raise EditorError(f'Portrait packing cannot fit {label} ({len(blob):,} bytes). '
                    f'{left:,} bytes remain; largest safe block is {largest:,}. '
                    'No file changed. Try smaller portraits or reserve a verified unused region. '
                    'Unrelated data and unknown gaps will not be moved.')
            _,a,i=min(fits);free[i][0]+=len(blob)
            self.writes.append((a,blob));return a
        # Try a full packing first. A second strategy preserves already-encoded
        # independent streams to avoid a greedy fragmentation failure on reopen.
        original_free=[x[:] for x in free]
        ordered=sorted(items,key=lambda x:(-len(x[0]),x[1][0]))
        def record(a,blob,ids):
            for i in ids:self.pointers[i]=a
            self.rows.append(f'{",".join(f"{i:02X}" for i in ids)}: {len(blob)} bytes at {a:06X}')
        try:
            for blob,ids in ordered:
                record(allocate(blob,f'slot {ids[0]:02X}'),blob,ids)
        except EditorError:
            free[:]=[x[:] for x in original_free]
            self.writes.clear();self.pointers.clear();self.rows.clear()
            pending=[]
            for blob,ids in ordered:
                placed=False
                for p in rom.portraits:
                    if rom.pending.get(ids[0],(rom.portraits[ids[0]].raw,None))[0]!=p.raw:continue
                    a=p.gfx;b=a+len(blob)
                    if bytes(rom.data[a:b])!=blob:continue
                    segment=next((i for i,(lo,hi) in enumerate(free) if lo<=a<b<=hi),None)
                    if segment is None:continue
                    lo,hi=free.pop(segment)
                    if lo<a:free.append([lo,a])
                    if b<hi:free.append([b,hi])
                    self.writes.append((a,blob));record(a,blob,ids);placed=True;break
                if not placed:pending.append((blob,ids))
            for blob,ids in pending:
                record(allocate(blob,f'slot {ids[0]:02X}'),blob,ids)
        # Palettes stay at their old addresses when all aliases request the same
        # contents. Conflicting aliases get copies in the remaining graphic pool.
        palette_groups={}
        for p in rom.portraits:palette_groups.setdefault(p.pal,[]).append(p)
        self.palette_required=0
        for addr,ps in sorted(palette_groups.items()):
            desired={}
            for p in ps:desired.setdefault(rom.pending.get(p.id,(p.raw,p.palette))[1],[]).append(p.id)
            old=bytes(rom.data[addr:addr+32])
            # Partial aliases and graphics dependencies prohibit writing in place.
            overlap=any((q.pal!=addr and addr<q.pal+32 and q.pal<addr+32) or
                        bool(set(range(addr,addr+32)) & q.touched) for q in rom.portraits)
            primary=old if old in desired or overlap else next(iter(desired))
            for pal,ids in desired.items():
                if pal==old:target=addr
                elif pal==primary and not overlap:
                    target=addr;self.allowed.update(range(addr,addr+32));self.writes.append((addr,pal))
                else:
                    target=allocate(pal,'shared palette');self.palette_required+=32
                for i in ids:self.palette_pointers[i]=target
        self.remaining=sum(b-a for a,b in free)
        self.unique=len(groups)
        self.summary=(f'{self.unique} unique portrait sheets for {COUNT} slots.\n'
            f'Portrait storage available: {self.portrait_capacity:,} bytes\n'
            f'Explicit reservation: {self.reserved_capacity:,} bytes\n'
            f'Packed graphics: {self.graphics_required:,} bytes\n'
            f'New palette copies: {self.palette_required:,} bytes\n'
            f'Remaining safe space for this save: {self.remaining:,} bytes\n\n'
            'Only directly decoded portrait bytes in the supported portrait area are reused. '
            'Unknown gaps and all other data stay in place. Identical sheets share graphics; palettes remain independent.')
    def apply(self,rom,data):
        for a,blob in self.writes:
            if not set(range(a,a+len(blob)))<=self.allowed:raise EditorError('Packing write outside allowed portrait storage.')
            data[a:a+len(blob)]=blob
        for table,pointers in ((GFX_TABLE,self.pointers),(PAL_TABLE,self.palette_pointers)):
            for i,a in pointers.items():
                at=table+i*3;data[at:at+3]=rom.pointer(a).to_bytes(3,'little')
        allowed=self.allowed|set(range(GFX_TABLE,PAL_TABLE+COUNT*3))
        if any(a not in allowed for a,(x,y) in enumerate(zip(rom.data,data)) if x!=y):
            raise EditorError('Portrait packing changed a protected byte.')
        return [self.summary]+self.rows
