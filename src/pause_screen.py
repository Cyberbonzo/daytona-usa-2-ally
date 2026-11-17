"""Vulkan overlay drawn once over the frozen racing frame."""
import wgpu as w
from PIL import Image, ImageDraw, ImageFont

class PauseScreen:
    def __init__(self, device, fmt):
        self.device = device
        width, height = 960, 540
        image = Image.new('RGBA', (width, height), (8, 12, 18, 125))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((286, 196, 674, 344), radius=12, fill=(16, 23, 31, 244))
        for size, y, text in [(46, 249, 'PAUSED'), (18, 302, 'R3 / ESC   ·   RESUME')]:
            try:
                font = ImageFont.truetype('DejaVuSans.ttf', size)
            except OSError:
                font = ImageFont.load_default(size=size)
            draw.text((width//2, y), text, fill='white', font=font, anchor='mm')
        tex = device.create_texture(size=(width,height,1),format='rgba8unorm',
                                    usage=w.TextureUsage.COPY_DST|w.TextureUsage.TEXTURE_BINDING)
        device.queue.write_texture({'texture':tex},image.tobytes(),{'bytes_per_row':width*4},(width,height,1))
        shader = device.create_shader_module(code="""
            struct Out { @builtin(position) pos: vec4f, @location(0) uv: vec2f }
            @group(0) @binding(0) var picture: texture_2d<f32>;
            @group(0) @binding(1) var smp: sampler;
            @vertex fn vs(@builtin(vertex_index) i:u32) -> Out {
                let p = array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3))[i];
                return Out(vec4f(p,0,1),vec2f(p.x,-p.y)*0.5+0.5);
            }
            @fragment fn fs(v:Out) -> @location(0) vec4f { return textureSample(picture,smp,v.uv); }
        """)
        blend=dict(color=dict(src_factor='src-alpha',dst_factor='one-minus-src-alpha',operation='add'),
                   alpha=dict(src_factor='one',dst_factor='one-minus-src-alpha',operation='add'))
        self.pipeline=device.create_render_pipeline(layout='auto',vertex=dict(module=shader,entry_point='vs',buffers=[]),
            fragment=dict(module=shader,entry_point='fs',targets=[dict(format=fmt,blend=blend)]),
            primitive=dict(topology='triangle-list'))
        self.group=device.create_bind_group(layout=self.pipeline.get_bind_group_layout(0),entries=[
            dict(binding=0,resource=tex.create_view()),dict(binding=1,resource=device.create_sampler(mag_filter='linear',min_filter='linear'))])

    def draw(self, render_pass):
        render_pass.set_pipeline(self.pipeline)
        render_pass.set_bind_group(0,self.group)
        render_pass.draw(3)
