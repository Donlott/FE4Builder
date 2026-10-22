"""Conservative event decoder for verified village scripts."""
LENGTHS={2:3,3:3,4:3,8:3,0x0c:4,0x0e:2,0x12:3,0x13:1,0x34:3,0x41:2,0x42:4,0x45:4,0xfd:1}


def parse(data,start):
    nodes=[];at=start
    while at<start+400:
        opcode=data[at]
        if bytes(data[at:at+2])==b'\xff\xff':nodes.append((at,0xff,2));return nodes,at+2-start
        if opcode==0x4a:
            if data[at+1] not in (0x54,0x57,0x70):raise ValueError(f'Unsupported village reward at PC {at:06X}.')
            size=6 if data[at+1]==0x54 else 5
        elif opcode in LENGTHS:size=LENGTHS[opcode]
        else:raise ValueError(f'Unsupported village event command {opcode:02X} at PC {at:06X}.')
        nodes.append((at,opcode,size));at+=size
    raise ValueError('Village event exceeds the supported script size.')


def signature(raw):
    import hashlib
    data=bytearray(raw)
    for at,opcode,size in parse(data,0)[0]:
        if opcode==0x0c:data[at+1:at+4]=bytes(3)
        elif opcode==0x4a and data[at+1]==0x57:data[at+4]=0
        elif opcode==0x4a and data[at+1]==0x70:data[at+3:at+5]=bytes(2)
    return hashlib.sha256(data).hexdigest()
