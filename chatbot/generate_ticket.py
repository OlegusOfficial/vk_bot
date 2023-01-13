import os
import random
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageColor

TEMPLATE_PATH = os.path.join('files', 'ticket_template.png')
FONT_PATH = os.path.join('files', 'Roboto.ttf')
AVATAR_SIZE = (100, 100)
AVATAR_OFFSET = (400, 80)


def generate_ticket(fio, from_, to, flight, email, test=False):
    ticket = Image.open(TEMPLATE_PATH)
    ticket_draw = ImageDraw.Draw(ticket)
    font = ImageFont.truetype(FONT_PATH, size=16)
    ticket_draw.multiline_text((45, 130), text=f'{fio}\n{from_}\n{to}', fill=ImageColor.colormap['black'], font=font,
                               spacing=50)
    ticket_draw.text((265, 265), text=flight[:10], fill=ImageColor.colormap['black'], font=font)
    ticket_draw.text((430, 265), text=flight[10:], fill=ImageColor.colormap['black'], font=font)
    ticket_draw.text((360, 315), text=email, fill=ImageColor.colormap['black'], font=font)
    if not test:
        avatar_file = f'avataaars_{random.randint(0, 5)}.png'
    else:
        avatar_file = f'avataaars_1.png'
    avatar = Image.open(os.path.join('files', avatar_file))
    avatar_little = avatar.resize(AVATAR_SIZE)

    ticket.paste(avatar_little, AVATAR_OFFSET)
    temp_file = BytesIO()
    ticket.save(temp_file, 'png')
    temp_file.seek(0)
    return temp_file
