"""Generate a crisp Windows .ico from vector-like Pillow drawing."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SIZE = 512
im = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
draw = ImageDraw.Draw(im)
draw.rounded_rectangle((15,15,497,497), radius=112, fill=(42,99,236,255))
draw.rounded_rectangle((79,70,432,448), radius=35, fill=(244,247,255,255))
draw.rounded_rectangle((102,92,407,424), radius=18, fill=(224,233,251,255))
draw.polygon([(319,92), (407,92), (407,187)], fill=(177,200,242,255))
draw.rounded_rectangle((133,260,373,351), radius=16, fill=(42,99,236,255))
fontpath = "C:/Windows/Fonts/segoeuib.ttf"
try:
    font = ImageFont.truetype(fontpath, 62)
except OSError:
    font = ImageFont.load_default()
draw.text((166,271), "PDF", fill=(255,255,255,255), font=font)
out = Path(__file__).parent / "icon.ico"
im.save(out, format="ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print("Created", out)
