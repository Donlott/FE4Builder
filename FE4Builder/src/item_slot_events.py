"""Bounded live event decoding for player item-slot grants and deployments.

Instruction sizes follow ulti-mage/FireEmblem4 commit
387b2e4c63b72b0d3f2854eaa69f26946d83b383, SAFEGUARD/EVENTS/Main.h
and Conditions.h. Reference event text is never used as evidence of a live slot.
"""
from collections import deque

COMMAND_SIZES = {
    0xfd: 1, 0x00: 2, 0x01: 1, 0x02: 3, 0x03: 3, 0x04: 3, 0x05: 3, 0x06: 3, 0x07: 2, 0x08: 3, 0x09: 7, 0x0a: 1,
    0x0b: 1, 0x0c: 4, 0x0d: 6, 0x0e: 2, 0x0f: 2, 0x10: 2, 0x11: 2, 0x12: 3, 0x13: 1, 0x14: 7, 0x15: 7, 0x16: 1,
    0x17: 3, 0x19: 7, 0x1a: 1, 0x1b: 4, 0x1c: 4, 0x1d: 1, 0x1f: 4, 0x20: 8, 0x21: 8, 0x22: 9, 0x23: 8, 0x24: 11,
    0x25: 9, 0x26: 12, 0x27: 10, 0x28: 4, 0x29: 1, 0x2a: 1, 0x2b: 1, 0x2c: 1, 0x2d: 6, 0x2e: 12, 0x2f: 6, 0x30: 5,
    0x31: 1, 0x32: 1, 0x33: 1, 0x34: 3, 0x35: 1, 0x36: 3, 0x37: 1, 0x38: 1, 0x39: 1, 0x3a: 3, 0x3b: 2, 0x3c: 1,
    0x3d: 1, 0x3e: 4, 0x3f: 5, 0x40: 4, 0x41: 2, 0x42: 4, 0x43: 4, 0x44: 5, 0x45: 4, 0x46: 2, 0x47: 2, 0x48: 5,
    0x49: 2, 0x4a: 1, 0x4b: 3, 0x4c: 3, 0x4d: 1, 0x4e: 4, 0x4f: 1, 0x50: 1, 0x51: 5, 0x52: 5, 0x53: 2, 0x54: 4,
    0x55: 4, 0x56: 2, 0x57: 4, 0x58: 4, 0x59: 1, 0x5a: 1, 0x5b: 2, 0x5c: 1,
}
# Condition 69 has two macro source branches, each encoding four operands.
CONDITION_SIZES = {
    0x00: 1, 0x01: 4, 0x02: 6, 0x03: 6, 0x04: 8, 0x05: 6, 0x06: 6, 0x07: 6, 0x08: 6, 0x09: 6, 0x0a: 6, 0x0b: 9,
    0x0c: 8, 0x0d: 10, 0x0e: 10, 0x0f: 6, 0x10: 6, 0x11: 8, 0x12: 8, 0x13: 6, 0x14: 6, 0x15: 6, 0x16: 6, 0x17: 4,
    0x18: 6, 0x19: 10, 0x1a: 6, 0x1b: 6, 0x1c: 6, 0x1d: 4, 0x1e: 8, 0x1f: 6, 0x20: 3, 0x21: 6, 0x22: 1, 0x23: 1,
    0x24: 1, 0x25: 3, 0x26: 4, 0x27: 2, 0x28: 2, 0x29: 2, 0x2a: 2, 0x2b: 3, 0x2c: 3, 0x2d: 3, 0x2e: 3, 0x2f: 3,
    0x30: 4, 0x31: 6, 0x32: 7, 0x33: 1, 0x34: 2, 0x35: 4, 0x36: 2, 0x37: 2, 0x38: 2, 0x39: 2, 0x3a: 2, 0x3b: 3,
    0x3c: 3, 0x3d: 2, 0x3e: 2, 0x3f: 3, 0x40: 3, 0x41: 3, 0x42: 3, 0x43: 1, 0x44: 2, 0x45: 3, 0x46: 3, 0x47: 3,
    0x48: 4, 0x49: 3, 0x4a: 2, 0x4b: 3, 0x4c: 3, 0x4d: 4, 0x4e: 2, 0x4f: 2, 0x50: 6, 0x51: 8, 0x52: 6, 0x53: 4,
    0x54: 5, 0x55: 5, 0x56: 1, 0x57: 4, 0x58: 4, 0x59: 4, 0x5a: 3, 0x5b: 4, 0x5c: 1, 0x5d: 8, 0x5e: 4, 0x5f: 8,
    0x60: 6, 0x61: 4, 0x62: 3, 0x63: 3, 0x64: 3, 0x65: 3, 0x66: 3, 0x67: 3, 0x68: 3, 0x69: 5, 0x6a: 5, 0x6b: 4,
    0x6c: 6, 0x6d: 1, 0x6e: 2, 0x6f: 2, 0x70: 4, 0x71: 2, 0x72: 2, 0x73: 1, 0x74: 1, 0x75: 5, 0x76: 5, 0x77: 4,
    0x78: 1,
}
# DEPLOY_UNIT_GROUP_CHILD is followed by a flag and two character words;
# the macro declaration alone omits those five bytes (Events.asm:86/91CD).
CONDITION_SIZES[0x4f] = 7


def decode(rom,start,length):
    """Follow command boundaries/branches, never search arbitrary operand bytes.

    Returns grants (PC, slot, actor, condition), character loads, and unresolved
    paths. ASM calls stay opaque; a script dump is not a game-state simulation.
    """
    end=min(start+min(length,4096), (start & ~0xffff)+0x10000)
    data=memoryview(rom.data)[rom.header:]
    if start<0 or end>len(data) or length<=0:raise ValueError('Event script is outside the ROM.')
    todo=deque([start]);visited={};occupied={};grants=[];loads=[];errors=[]
    while todo:
        at=todo.popleft()
        if at in visited:continue
        if not start<=at<end:
            errors.append(f'Branch outside the indexed script at {at:06X}.');continue
        if at in occupied:
            errors.append(f'Branch enters an operand at {at:06X}.');continue
        opcode=data[at]
        if opcode in (0xfe,0xff):
            if at+2<=end and data[at+1]==opcode:visited[at]=2;continue
            errors.append(f'Invalid terminator at {at:06X}.');continue
        condition=None
        if opcode in (0x4a,0x4d):
            if at+2>end:errors.append('Truncated event condition.');continue
            condition=data[at+1];size=1+CONDITION_SIZES.get(condition,0)
            if size==1:errors.append(f'Unknown condition {condition:02X} at {at:06X}.');continue
            if condition in (0x2c,0x2d,0x3a):
                cursor=at+2
                while cursor<end and data[cursor]!=0xff:cursor+=1
                if cursor==end:errors.append(f'Unterminated flag list at {at:06X}.');continue
                size=cursor-at+1
        else:size=COMMAND_SIZES.get(opcode)
        if size is None:errors.append(f'Unknown opcode {opcode:02X} at {at:06X}.');continue
        if at+size>end or any(i in occupied or i in visited for i in range(at+1,at+size)):
            errors.append(f'Truncated or overlapping command at {at:06X}.');continue
        visited[at]=size
        for i in range(at+1,at+size):occupied[i]=at
        if condition in (0x57,0x58,0x59,0x5b):
            actor=int.from_bytes(data[at+2:at+4],'little')
            grants.append((at,int(data[at+4]),actor,condition))
        if condition==0x52:
            actor=int.from_bytes(data[at+2:at+4],'little')
            grants.extend((at,int(data[at+i]),actor,condition) for i in (5,6))
        if opcode==0x24:
            loads.append((int.from_bytes(data[at+1:at+3],'little'),None))
        if opcode in (0x23,0x28):
            loads.append((int.from_bytes(data[at+2:at+4],'little'),int(data[at+1])))
        if condition in (0x4e,0x4f):
            loads.append((None,int(data[at+2])))
            if condition==0x4f:
                loads.extend((int.from_bytes(data[at+i:at+i+2],'little'),None) for i in (4,6))
        if condition in (0x50,0x51,0x52):
            loads.append((int.from_bytes(data[at+2:at+4],'little'),None))
        if condition==0x2b:
            todo.append((at & ~0xffff)+int.from_bytes(data[at+2:at+4],'little'))
        if opcode in (2,3,4,5,6):
            offset=int.from_bytes(data[at+1:at+3],'little',signed=opcode in (5,6))
            destination=at+offset if opcode in (5,6) else (at & ~0xffff)+offset
            todo.append(destination)
            if opcode!=2:todo.append(at+size)
        else:todo.append(at+size)
    # A later-discovered branch into another command invalidates that path's
    # observations. Reject ambiguous scripts instead of presenting false grants.
    if any('operand' in e or 'overlapping' in e for e in errors):
        grants=[];loads=[]
    return grants,loads,errors
