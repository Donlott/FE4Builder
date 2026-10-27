"""Bounded, read-only decoding of FE4 scripted map sprite movement."""
from portraits import pc_address
DIRECTIONS=('Left','Right','Up','Down','Up-left','Down-left','Up-right','Down-right')

def route_preview(rom,pointer,limit=128):
    output=[f'Movement route ${pointer:06X} (read-only; pointer preserved)']
    try:
        start=pc_address(pointer)+rom.header
        end=min(len(rom.data),start+0x10000-(pointer&0xffff))
        at=start
        for _ in range(limit):
            if at>=end:raise ValueError('Route is truncated or reaches the bank boundary.')
            opcode=rom.data[at];at+=1
            if 1<=opcode<=8:label=DIRECTIONS[opcode-1]+' 1 tile'
            elif 10<=opcode<=18 or opcode==0x84:
                if at>=end:raise ValueError('Route operand is truncated.')
                value=rom.data[at];at+=1
                if opcode<=17:label=f'{DIRECTIONS[opcode-10]} {value} tile(s)'
                elif opcode==18:label=f'Wait {value} ticks'
                else:label=f'Set speed {value}'
            elif opcode==0x80:
                output.append('End route');return '\n'.join(output)
            elif opcode==0x81:label='Halt (wait for event to resume movement)'
            elif 0x85<=opcode<=0x88:label='Face '+('left','right','up','down')[opcode-0x85]
            else:raise ValueError(f'Unknown movement byte ${opcode:02X}; preview stops here.')
            output.append(label)
        output.append('Preview limit reached; remaining route not decoded.')
    except (ValueError,IndexError) as error:output.append(str(error))
    return '\n'.join(output)
