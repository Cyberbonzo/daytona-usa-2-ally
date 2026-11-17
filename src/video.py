"""Native Vulkan presentation of the Daytona USA 2 Power Edition Recomp frame packet.
Based on Johann Ruiz's Apache-2.0 renderer; see upstream/NOTICE.
"""
import struct, math
from pathlib import Path
import wgpu as w

class Video:
    def __init__(self, display, window, width, height):
        self.w,self.h=width,height
        self.ctx=w.gpu.get_canvas_context(dict(platform="x11",display=display,window=window))
        self.ctx.set_physical_size(width,height)
        adapter=w.gpu.request_adapter_sync(power_preference="high-performance")
        print("GPU",adapter.info,flush=True)
        self.d=d=adapter.request_device_sync()
        self.format=self.ctx.get_preferred_format(adapter)
        self.ctx.configure(device=d,format=self.format)
        shaders=Path(__file__).resolve().parents[1]/'upstream/shaders'
        world=d.create_shader_module(code=(shaders/'r3d.wgsl').read_text())
        comp=d.create_shader_module(code=(shaders/'compose.wgsl').read_text())
        def texture(x,y,fmt,usage):return d.create_texture(size=(x,y,1),format=fmt,usage=usage)
        T=w.TextureUsage;B=w.BufferUsage;S=w.ShaderStage
        self.sheet=texture(2048,2048,'r16uint',T.TEXTURE_BINDING|T.COPY_DST)
        self.back=texture(896,384,'bgra8unorm',T.TEXTURE_BINDING|T.COPY_DST)
        self.front=texture(496,384,'bgra8unorm',T.TEXTURE_BINDING|T.COPY_DST)
        self.color=texture(width,height,'rgba16float',T.RENDER_ATTACHMENT|T.TEXTURE_BINDING).create_view()
        self.depth=texture(width,height,'depth32float',T.RENDER_ATTACHMENT).create_view()
        g0=d.create_bind_group_layout(entries=[dict(binding=0,visibility=S.FRAGMENT,texture=dict(sample_type='uint'))])
        self.g1=d.create_bind_group_layout(entries=[dict(binding=0,visibility=S.VERTEX|S.FRAGMENT,buffer=dict(type='uniform',has_dynamic_offset=True,min_binding_size=192))])
        self.sheetgroup=d.create_bind_group(layout=g0,entries=[dict(binding=0,resource=self.sheet.create_view())])
        layout=d.create_pipeline_layout(bind_group_layouts=[g0,self.g1])
        attrs=[(0,'float32x3'),(12,'float32x3'),(24,'float32x2'),(32,'unorm8x4'),(36,'uint32'),(40,'uint32'),(44,'float32x3'),(72,'float32'),(76,'uint32')]
        vs=dict(module=world,entry_point='vs',buffers=[dict(array_stride=80,attributes=[dict(shader_location=i,offset=a,format=f) for i,(a,f) in enumerate(attrs)])])
        blend=dict(color=dict(src_factor='src-alpha',dst_factor='one-minus-src-alpha',operation='add'),alpha=dict(src_factor='one',dst_factor='one-minus-src-alpha',operation='add'))
        self.pipes=[]
        for i in range(3):
            target=dict(format='rgba16float',write_mask=0 if i==1 else 15)
            if i==2:target['blend']=blend
            self.pipes.append(d.create_render_pipeline(layout=layout,vertex=vs,fragment=dict(module=world,entry_point='fs',targets=[target]),primitive=dict(topology='triangle-list'),depth_stencil=dict(format='depth32float',depth_write_enabled=i!=2,depth_compare='greater-equal')))
        self.compose=d.create_render_pipeline(layout='auto',vertex=dict(module=comp,entry_point='vs',buffers=[]),fragment=dict(module=comp,entry_point='fs',targets=[dict(format=self.format)]),primitive=dict(topology='triangle-list'))
        self.cu=d.create_buffer(size=96,usage=B.UNIFORM|B.COPY_DST)
        resources=[self.color,self.front.create_view(),self.back.create_view(),d.create_sampler(),d.create_sampler(mag_filter='linear',min_filter='linear'),dict(buffer=self.cu)]
        self.cg=d.create_bind_group(layout=self.compose.get_bind_group_layout(0),entries=[dict(binding=i,resource=v) for i,v in enumerate(resources)])
        self.vb=None;self.ub=None

    def draw(self,game,packet,paused=False):
        raw=game.get(packet,39*4);u=struct.unpack('<39I',raw);f=struct.unpack('<39f',raw)
        d=self.d;q=d.queue
        if u[24]:
            if u[29]:raise ValueError('Unexpected GPU transform packet')
            size=u[1]*80
            if size:
                if self.vb is None or self.vb.size<size:
                    self.vb=d.create_buffer(size=max(size*2,1048576),usage=w.BufferUsage.VERTEX|w.BufferUsage.COPY_DST)
                q.write_buffer(self.vb,0,game.get(u[2],size))
            if u[6]:
                bits=int.from_bytes(game.get(u[7],256),'little')
                while bits:
                    y=(bits&-bits).bit_length()-1;bits>>=y
                    rows=(bits^(bits+1)).bit_length()-1
                    q.write_texture(dict(texture=self.sheet,origin=(0,y,0)),game.get(u[5]+y*4096,rows*4096),dict(bytes_per_row=4096),(2048,rows,1))
                    bits=(bits>>rows)<<(rows+y)
        if u[10]:
            for tex,ptr,x in [(self.back,u[8],896),(self.front,u[9],496)]:
                q.write_texture(dict(texture=tex),game.get(ptr,x*384*4),dict(bytes_per_row=x*4),(x,384,1))
        vw=max(496,self.w/self.h*384);gx=(vw-496)/2;sx=self.w/vw;sy=self.h/384
        draws=[]
        for vp in struct.iter_unpack('<56f',game.get(u[4],u[3]*224)):
            full=vp[5]>.5
            x,y,ww,hh=(0 if full else vp[1]+gx)*sx,vp[2]*sy,(vw if full else vp[3])*sx,vp[4]*sy
            left,top=max(0,x),max(0,y);right,bottom=min(self.w,x+ww),min(self.h,y+hh)
            if right-left<1 or bottom-top<1:continue
            view=(left,top,right-left,bottom-top)
            sc=(math.floor(left),math.floor(top),min(self.w-math.floor(left),math.ceil(right-left)),min(self.h-math.floor(top),math.ceil(bottom-top)))
            uni=list(vp[8:36])+[0,1,2*gx/vw if full else 0,0]+list(vp[36:52])
            if full and vp[7]<=.5:uni[0]/=vw/496;uni[8]/=vw/496
            for j,(p,sz,p1,sz1) in enumerate([(x,ww,left,view[2]),(y,hh,top,view[3])]):
                ratio=sz/sz1;offset=(2*(p-p1)+sz-sz1)/sz1
                for k in range(4):uni[k*4+j]=ratio*uni[k*4+j]+offset*uni[k*4+3]
                if j==0:uni[30]*=ratio
            for typ,first,count,qual in [(0,vp[52],vp[53],1),(1,vp[54],vp[55],-1000),(2,vp[54],vp[55],-1)]:
                if count:
                    uni[28]=qual
                    draws.append((vp[0],typ,int(first),int(count),view,sc,struct.pack('<48f',*uni)))
        draws.sort(key=lambda e:(e[0],int(e[1]>0)))
        if draws:
            size=len(draws)*256
            if self.ub is None or self.ub.size<size:
                self.ub=d.create_buffer(size=max(size*2,16384),usage=w.BufferUsage.UNIFORM|w.BufferUsage.COPY_DST)
                self.ug=d.create_bind_group(layout=self.g1,entries=[dict(binding=0,resource=dict(buffer=self.ub,size=192))])
            q.write_buffer(self.ub,0,b''.join(row[6]+bytes(64) for row in draws))
        enc=d.create_command_encoder()
        current=None;rp=None
        for i,item in enumerate(draws or [None]):
            pri=item[0] if item else 0
            if rp is None or pri!=current:
                if rp:rp.end()
                rp=enc.begin_render_pass(color_attachments=[dict(view=self.color,load_op='clear' if i==0 else 'load',store_op='store',clear_value=(0,0,0,0))],depth_stencil_attachment=dict(view=self.depth,depth_load_op='clear',depth_store_op='discard',depth_clear_value=0))
                current=pri
            if item and self.vb:
                _,typ,first,count,view,sc,_=item
                rp.set_pipeline(self.pipes[typ]);rp.set_vertex_buffer(0,self.vb);rp.set_bind_group(0,self.sheetgroup);rp.set_bind_group(1,self.ug,[i*256])
                rp.set_viewport(*view,0,1);rp.set_scissor_rect(*sc);rp.draw(count,1,first,0)
        rp.end()
        fx=0 if u[23] else f[19]+gx;fw=vw if u[23] else f[21]
        cu=[1,1,0,0,gx/vw,496/vw,bool(u[14]),bool(u[11]),u[13],0,0,0,*f[15:19],fx/vw,f[20]/384,(fx+fw)/vw,(f[20]+f[22])/384]
        q.write_buffer(self.cu,0,struct.pack('<20f',*cu))
        rp=enc.begin_render_pass(color_attachments=[dict(view=self.ctx.get_current_texture().create_view(),load_op='clear',store_op='store',clear_value=(0,0,0,1))])
        rp.set_pipeline(self.compose);rp.set_bind_group(0,self.cg);rp.draw(3)
        if paused:
            if not hasattr(self,'pause_screen'):
                from pause_screen import PauseScreen
                self.pause_screen=PauseScreen(d,self.format)
            self.pause_screen.draw(rp)
        rp.end();q.submit([enc.finish()]);self.ctx.present()
