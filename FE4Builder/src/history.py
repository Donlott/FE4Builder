"""Persistent undo history, sparse byte changes, and pre-write ROM backups."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import uuid

def digest(data):
    return hashlib.sha256(data).hexdigest()

def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')

def valid_state(value,path):
    try:
        if not isinstance(value,dict) or value['version']!=1 or value['rom']!=str(path):
            return False
        entries,audit,cursor=value['entries'],value['audit'],value['cursor']
        if not isinstance(entries,list) or not isinstance(audit,list) or not isinstance(cursor,int) or not 0<=cursor<=len(entries):
            return False
        for event in entries+audit:
            if not isinstance(event['description'],str) or not isinstance(event['details'],list):
                return False
            datetime.fromisoformat(event['timestamp'])
            if not isinstance(event['patches'],list):
                return False
            for change in event['patches']:
                if not isinstance(change['offset'],int) or change['offset']<0:
                    return False
                bytes.fromhex(change['before'])
                bytes.fromhex(change['after'])
            if not isinstance(event['before_size'],int) or not isinstance(event['after_size'],int):
                return False
        for event in audit:
            if event['action'] not in ('Edit','Undo','Redo') or Path(event['backup']).name!=event['backup']:
                return False
        if len(bytes.fromhex(value['hash']))!=32:
            return False
        if entries:
            expected=entries[cursor-1]['after_hash'] if cursor else entries[0]['before_hash']
            if expected!=value['hash']:
                return False
            for entry in entries:
                if any(len(bytes.fromhex(entry[k]))!=32 for k in ('before_hash','after_hash')):
                    return False
        return True
    except (ValueError,KeyError,TypeError,AttributeError):
        return False

def patches(before, after):
    result=[]
    common=min(len(before),len(after))
    for start in range(0,common,4096):
        a,b=before[start:start+4096],after[start:start+4096]
        # Restrict the last block to the common part before handling size changes.
        a,b=a[:common-start],b[:common-start]
        if a==b:
            continue
        i=0
        while i<len(a):
            if a[i]==b[i]:
                i+=1
                continue
            first=i
            while i<len(a) and a[i]!=b[i]:
                i+=1
            result.append({'offset':start+first,'before':a[first:i].hex(),'after':b[first:i].hex()})
    if len(before)!=len(after):
        result.append({'offset':common,'before':before[common:].hex(),'after':after[common:].hex()})
    return result

def apply_entry(data,entry,redo):
    expected=entry['before_hash'] if redo else entry['after_hash']
    if digest(data)!=expected:
        raise ValueError('The current ROM no longer matches this history step.')
    output=bytearray(data)
    size=entry['after_size'] if redo else entry['before_size']
    if size>len(output):
        output.extend(bytes(size-len(output)))
    for change in entry['patches']:
        value=bytes.fromhex(change['after' if redo else 'before'])
        if value:
            output[change['offset']:change['offset']+len(value)]=value
    del output[size:]
    target=entry['after_hash'] if redo else entry['before_hash']
    if digest(output)!=target:
        raise ValueError('The history data failed its integrity check.')
    return output

class History:
    def __init__(self,path,current):
        path=Path(path).resolve()
        key=hashlib.sha256(str(path).casefold().encode()).hexdigest()[:16]
        self.folder=path.parent/'FE4Builder Backups'/key
        self.file=self.folder/'history.json'
        self.pending=self.folder/'history.pending.json'
        self.notice=''
        empty={'version':1,'rom':str(path),'hash':digest(current),'entries':[],'cursor':0,'audit':[]}
        loaded=[]
        for candidate in (self.file,self.pending):
            try:
                value=json.loads(candidate.read_text(encoding='utf-8'))
                if valid_state(value,path):
                    loaded.append(value)
                else:
                    self.notice='Invalid history data was ignored; ROM backups were retained.'
            except (OSError,ValueError):
                continue
        matching=[v for v in loaded if v.get('hash')==empty['hash']]
        self.state=max(matching,key=lambda v:len(v['audit'])) if matching else empty
        if loaded and not matching:
            self.state['audit']=max(loaded,key=lambda v:len(v['audit'])).get('audit',[])
            self.notice='ROM differs from saved history; a new undo timeline was started.'

    def backup(self,path,data):
        self.folder.mkdir(parents=True,exist_ok=True)
        filename=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-'+uuid.uuid4().hex[:8]+Path(path).suffix
        target=self.folder/filename
        with target.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return target

    def prepare(self,before,after,description,details,action='Edit',cursor=None):
        backup=self.backup(self.state['rom'],before)
        state=json.loads(json.dumps(self.state))
        changes=patches(before,after)
        when=stamp()
        if action=='Edit':
            entry={'description':description,'details':details or [],'timestamp':when,
                   'before_hash':digest(before),'after_hash':digest(after),
                   'before_size':len(before),'after_size':len(after),'patches':changes}
            state['entries']=state['entries'][:state['cursor']]+[entry]
            state['cursor']=len(state['entries'])
        else:
            state['cursor']=cursor
        state['hash']=digest(after)
        state['audit'].append({'timestamp':when,'action':action,'description':description,
                               'details':details or [],'backup':backup.name,'patches':changes,
                               'before_hash':digest(before),'after_hash':digest(after),
                               'before_size':len(before),'after_size':len(after)})
        temporary=self.folder/('history-'+uuid.uuid4().hex+'.tmp')
        try:
            with temporary.open('x',encoding='utf-8') as stream:
                json.dump(state,stream,indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary,self.pending)
        finally:
            if temporary.exists():
                temporary.unlink()
        return state,backup

    def finish(self,state):
        self.state=state
        try:
            os.replace(self.pending,self.file)
        except OSError:
            # The durable pending journal is recoverable on the next open.
            self.notice='ROM saved; history is stored in the recovery journal.'

    @property
    def can_undo(self):
        return self.state['cursor']>0

    @property
    def can_redo(self):
        return self.state['cursor']<len(self.state['entries'])
