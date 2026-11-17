"""SDL2 window, XInput-compatible pad, cabinet audio and native game loop."""
import ctypes as c
import os,re,signal,struct,time
from pathlib import Path
import sdl2 as s
from core import Game,GameClosed,ROOT
import progress
from video import Video

class Panel:
    def __init__(self):
        os.environ.setdefault('SDL_VIDEODRIVER','x11')
        if s.SDL_Init(s.SDL_INIT_VIDEO|s.SDL_INIT_AUDIO|s.SDL_INIT_GAMECONTROLLER)<0:raise RuntimeError(s.SDL_GetError())
        self.window=s.SDL_CreateWindow(b'Daytona USA 2 Power Edition',s.SDL_WINDOWPOS_CENTERED,s.SDL_WINDOWPOS_CENTERED,1920,1080,s.SDL_WINDOW_FULLSCREEN_DESKTOP|s.SDL_WINDOW_SHOWN)
        if not self.window:raise RuntimeError(s.SDL_GetError())
        info=s.SDL_SysWMinfo();s.SDL_VERSION(info.version)
        if not s.SDL_GetWindowWMInfo(self.window,c.byref(info)):raise RuntimeError(s.SDL_GetError())
        ww,hh=c.c_int(),c.c_int();s.SDL_GetWindowSize(self.window,c.byref(ww),c.byref(hh))
        self.video=Video(info.info.x11.display,info.info.x11.window,ww.value,hh.value)
        s.SDL_ShowCursor(0)
        want=s.SDL_AudioSpec(44100,s.AUDIO_S16LSB,2,1024)
        self.dev=s.SDL_OpenAudioDevice(None,0,c.byref(want),None,0)
        if self.dev:s.SDL_PauseAudioDevice(self.dev,0)
        print('SDL audio',self.dev,ww.value,hh.value,flush=True)
        self.pad=None;self.gear=0;self.prev=0;self.paused=False;self.closing=False
        self.select_pad()
    def select_pad(self):
        ids=[i for i in range(s.SDL_NumJoysticks()) if s.SDL_IsGameController(i)]
        ids.sort(key=lambda i:b'360' not in (s.SDL_GameControllerNameForIndex(i) or b''))
        if ids:
            p=s.SDL_GameControllerOpen(ids[0])
            if p:
                if self.pad:s.SDL_GameControllerClose(self.pad)
                self.pad=p;print('Controller',s.SDL_GameControllerName(p),flush=True)
    def audio(self,g,ptr,count):
        if self.dev and count and s.SDL_GetQueuedAudioSize(self.dev)<44100*4//6:
            data=bytes(g.get(ptr,count*4));s.SDL_QueueAudio(self.dev,data,len(data))
    def controls(self):
        e=s.SDL_Event()
        while s.SDL_PollEvent(c.byref(e)):
            if e.type==s.SDL_QUIT:self.closing=True
            if e.type==s.SDL_CONTROLLERDEVICEADDED:self.select_pad()
            if e.type==s.SDL_KEYDOWN and not e.key.repeat and e.key.keysym.sym==s.SDLK_ESCAPE:self.paused=not self.paused
        keys=s.SDL_GetKeyboardState(None)
        b=sum(1<<i for i in range(15) if self.pad and s.SDL_GameControllerGetButton(self.pad,i))
        edges=b&~self.prev;self.prev=b
        if edges&(1<<8):self.paused=not self.paused
        if self.paused or self.closing:
            return struct.pack('<IBBB',0,128,0,0)
        for i,num in [(1,1),(0,2),(2,3),(3,4)]:
            if edges&(1<<i) or keys[getattr(s,'SDL_SCANCODE_'+str(num))]:self.gear=num
        if edges&(1<<9):self.gear=max(1,self.gear-1)
        if edges&(1<<10):self.gear=min(4,self.gear+1)
        buttons=0x100000<<(self.gear-1) if self.gear else 0
        if b&16 or keys[s.SDL_SCANCODE_5]:buttons|=1
        if b&64 or keys[s.SDL_SCANCODE_RETURN]:buttons|=16
        for i,k in enumerate((11,14,12,13)):
            if b&(1<<k):buttons|=0x10000<<i
        axis=lambda i:s.SDL_GameControllerGetAxis(self.pad,i) if self.pad else 0
        steer=axis(0)/32768
        if abs(steer)<.08:steer=0
        if keys[s.SDL_SCANCODE_LEFT]:steer=-1
        if keys[s.SDL_SCANCODE_RIGHT]:steer=1
        gas=255 if keys[s.SDL_SCANCODE_UP] else max(0,axis(5))//129
        brake=255 if keys[s.SDL_SCANCODE_DOWN] else max(0,axis(4))//129
        return struct.pack('<IBBB',buttons,round(128+127*steer),gas,brake)
    def present(self,g,pkt):
        value=self.controls()
        if self.paused and not self.closing:
            if self.dev:s.SDL_PauseAudioDevice(self.dev,1)
            g.checkpoint()
            self.video.draw(g,pkt,paused=True)
            print('PAUSED at field',g.frames,flush=True)
            while self.paused and not self.closing:
                time.sleep(.02)
                value=self.controls()
            if self.dev:s.SDL_PauseAudioDevice(self.dev,0)
            g.deadline=time.perf_counter()
            print('Leaving pause at field',g.frames,flush=True)
        if self.closing:
            g.checkpoint()
            raise GameClosed()
        g.put(g.input,value);self.video.draw(g,pkt)


def cabinet():
    p=ROOT/'state/save/backup.bin'
    if progress.load(p) is None:
        p.parent.mkdir(parents=True,exist_ok=True)
        src=(ROOT/'upstream/nvram.js').read_text()
        big=bytes.fromhex(re.search(r"DEFAULT_EEPROM = '([0-9a-f]+)'",src)[1])
        progress.atomic_write(p,bytes(131072)+bytes(big[i^1] for i in range(128)))

if __name__=='__main__':
    cabinet()
    panel=Panel()
    def request_close(signum, frame):
        panel.closing=True
    signal.signal(signal.SIGTERM,request_close)
    signal.signal(signal.SIGINT,request_close)
    try:Game(panel).start()
    except GameClosed:pass
    finally:s.SDL_Quit()
