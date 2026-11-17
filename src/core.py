"""Host the ahead-of-time compiled Daytona engine on Linux."""
import os
import struct
import time
from pathlib import Path
import wasmtime as wt
import progress

ROOT = Path(__file__).resolve().parents[1]

class FieldLimitReached(Exception):
    pass

class GameClosed(Exception):
    pass

class Game:
    def __init__(self, panel=None, limit=0):
        self.panel = panel
        self.limit = limit
        self.frames = 0
        self.last_save_frame = 0
        self.deadline = time.perf_counter()
        self.files = {}
        self.next_fd = 3
        self.fs = ROOT / 'state'
        for name in ('roms', 'save', 'tmp'):
            (self.fs / name).mkdir(parents=True, exist_ok=True)
        config = wt.Config()
        config.wasm_exceptions = True
        engine = wt.Engine(config)
        module = wt.Module.deserialize_file(engine, str(ROOT/'daytona2.x86_64.cwasm'))
        self.store = wt.Store(engine)
        linker = wt.Linker(engine)
        for item in module.imports:
            def call(*args, name=item.name, returns=bool(item.type.results)):
                value = self.host(name, args)
                return (0 if value is None else value) if returns else None
            linker.define_func(item.module, item.name, item.type, call)
        self.ex = linker.instantiate(self.store,module).exports(self.store)
        self.mem = self.ex['memory']

    def runfn(self,name,*args):
        return self.ex[name](self.store,*args)

    def get(self, ptr, size):
        return self.mem.read(self.store,ptr,ptr+size)

    def put(self,ptr,data):
        self.mem.write(self.store,data,ptr)

    def cstr(self,ptr):
        return self.get(ptr,1024).split(b'\x00',1)[0].decode(errors='replace')

    def path(self,ptr):
        name = self.cstr(ptr).lstrip('/')
        p = (self.fs/name).resolve()
        if not p.is_relative_to(self.fs): raise ValueError(name)
        return p

    def alloc(self,data):
        p=self.runfn('malloc',len(data))
        if not p:raise MemoryError(len(data))
        self.put(p,data)
        return p

    def checkpoint(self):
        if self.runfn("dayto_web_save_backup"):
            self.last_save_frame = self.frames

    def start(self):
        self.runfn('__wasm_call_ctors')
        boot=self.fs/'roms'/'import-complete'
        if not boot.exists():
            data=(ROOT/'roms/dayto2pe.zip').read_bytes()
            src=self.alloc(data);directory=self.alloc(b'/roms\0')
            code=self.runfn('dayto_web_import_rom',src,len(data),directory)
            self.runfn('free',src);self.runfn('free',directory)
            if code:raise RuntimeError(('ROM import',code,self.cstr(self.runfn('dayto_web_import_missing'))))
            boot.touch()
        for k,v in dict(DAYTO_ROM_DIR='/roms',M3_SOUND_THREAD='0',DAYTO_COMM_ASYNC_TICK='1',M3_SOUND_FIELD_US='16667',M3_BACKUP='/save/backup.bin',DAYTO_WEB_CPU_TILEGEN='1',DAYTO_GPU_XFORM='0').items():
            a=self.alloc(k.encode()+b'\0'); b=self.alloc(v.encode()+b'\0')
            self.runfn('setenv',a,b,1);self.runfn('free',a);self.runfn('free',b)
        self.input=self.runfn('dayto_web_input_ptr')
        self.put(self.input,struct.pack('<IBBB',0,128,0,0))
        print('Starting native engine',flush=True)
        arg=self.alloc(b'daytona2\0');argv=self.alloc(struct.pack('<II',arg,0))
        self.runfn('__main_argc_argv',1,argv)

    def host(self,n,a):
        if n=='__syscall_openat':
            path=self.path(a[1]);flags=a[2]
            try: fd=os.open(path,flags & (3|os.O_CREAT|os.O_TRUNC|os.O_APPEND|os.O_EXCL),0o600)
            except OSError:return -44
            key=self.next_fd;self.next_fd+=1;self.files[key]=fd
            return key
        if n in ('fd_close','fd_seek','fd_write','fd_read'):
            key=a[0]; fd=self.files.get(key,key if key in (0,1,2) else None)
            if fd is None:return 8
            if n=='fd_close':
                if key>=3:os.close(self.files.pop(key))
            elif n=='fd_seek':
                try:pos=os.lseek(fd,a[1],a[2])
                except OSError:return 70
                self.put(a[3],struct.pack('<Q',pos))
            else:
                total=0
                for ptr,size in struct.iter_unpack('<II',self.get(a[1],8*a[2])):
                    if n=='fd_write':count=os.write(fd,self.get(ptr,size))
                    else:
                        data=os.read(fd,size);self.put(ptr,data);count=len(data)
                    total+=count
                    if count<size:break
                self.put(a[3],struct.pack('<I',total))
            return 0
        if n=='emscripten_resize_heap':
            target=a[0]&0xffffffff
            try:self.mem.grow(self.store,max(0,(target+65535)//65536-self.mem.size(self.store)));return 1
            except wt.WasmtimeError:return 0
        if n=='emscripten_get_heap_max':return 2147483648
        if n=='emscripten_get_now':return time.perf_counter()*1000
        if n=='emscripten_date_now':return time.time()*1000
        if n=='environ_sizes_get':
            for p in a:self.put(p,bytes(4))
        if n in ('_localtime_js','_gmtime_js'):
            t=time.gmtime(a[0]);self.put(a[1],struct.pack('<9i',t.tm_sec,t.tm_min,t.tm_hour,t.tm_mday,t.tm_mon-1,t.tm_year-1900,(t.tm_wday+1)%7,t.tm_yday-1,0))
        if n=='__syscall_renameat':
            source,dest=self.path(a[1]),self.path(a[3])
            try:
                if dest==self.fs/'save/backup.bin':
                    progress.commit(dest, source.read_bytes())
                    source.unlink()
                else:
                    source.replace(dest)
                return 0
            except (OSError, ValueError) as exc:
                print("Could not commit cabinet file:", exc, flush=True)
                return -29
        if n=='__syscall_unlinkat':
            try:self.path(a[1]).unlink();return 0
            except OSError:return -44
        if n=='__assert_fail':raise RuntimeError(('assert',self.cstr(a[0]),self.cstr(a[1]),a[2]))
        if n in ('exit','_abort_js'):raise RuntimeError((n,a))
        if n=='dayto_js_audio' and self.panel:self.panel.audio(self,*a)
        if n=='dayto_js_present':
            self.frames+=1
            if self.panel:self.panel.present(self,a[0])
            if self.frames==1 or self.frames%300==0:print('Field',self.frames,flush=True)
            if self.limit and self.frames>=self.limit:raise FieldLimitReached
        if n=='dayto_js_take_save_request' and self.panel and self.frames-self.last_save_frame>=300:
            self.last_save_frame=self.frames
            return 1
        if n=='dayto_js_must_wait':return bool(self.panel)
        if n=='__asyncjs__dayto_js_next_field' and self.panel:
            self.deadline=max(self.deadline+1/60,time.perf_counter()-.05)
            time.sleep(max(0,self.deadline-time.perf_counter()))
        if n=='__syscall_ioctl':return -59
        if n in ('__syscall_socket','__syscall_connect','__syscall_accept4'):return -52
        if n=='tp_fetch_js':return 0
        if n in ('tp_published_js','tp_lead_js'):return 0.0
        return 0

if __name__=='__main__':
    try:Game(limit=120).start()
    except FieldLimitReached:print('120 native fields verified',flush=True)
