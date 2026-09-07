"""
cardgen.py — Digital membership card renderer.

Generates a branded PNG (white & gold) membership card with the fan's photo,
full name, unique membership number, package, expiry and a scannable QR code
that Ekhaya FC staff can verify.

Runs headless (no display) using Pillow + qrcode.
"""

import os
import io
import base64
import qrcode
from qrcode.constants import ERROR_CORRECT_M

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE_DIR, "static")
CREST = os.path.join(STATIC, "img", "crest.png")
CARD_DIR = os.path.join(STATIC, "img", "fan_cards")
DEFAULT_AVATAR = os.path.join(STATIC, "img", "crest.png")

GOLD = (196, 164, 76)
GOLD_DARK = (146, 118, 46)
BLACK = (15, 15, 15)
WHITE = (255, 255, 255)
GREY = (90, 90, 90)


def _font(size):
    # Prefer a bundled font if present; fall back to default PIL font scaled.
    for cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _bold_font(size):
    for cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _load_photo(path):
    if path and os.path.exists(path):
        try:
            img = Image.open(path).convert("RGB")
            return img
        except Exception:
            pass
    if os.path.exists(DEFAULT_AVATAR):
        try:
            return Image.open(DEFAULT_AVATAR).convert("RGB")
        except Exception:
            pass
    return Image.new("RGB", (240, 240), (30, 30, 30))


def _draw_qr(data, size):
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=8,
                       border=1)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img.resize((size, size), Image.NEAREST)


def _circle_crop(im, size):
    im = im.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def generate_card_png(fan, card, package_name, expiry, status="ACTIVE",
                      photo_path=None, card_path=None):
    """Render the card PNG. Returns the file path it was written to."""
    # Normalise to dictionaries (callers may pass sqlite3.Row objects).
    fan = dict(fan) if not isinstance(fan, dict) else fan
    card = dict(card) if not isinstance(card, dict) else card
    os.makedirs(CARD_DIR, exist_ok=True)

    W, H = 720, 440
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # Gold header band
    d.rectangle([0, 0, W, 92], fill=GOLD)
    d.rectangle([0, 92, W, 96], fill=GOLD_DARK)

    # Crest on the left of header
    try:
        crest = Image.open(CREST).convert("RGBA").resize((64, 64),
                                                         Image.LANCZOS)
        img.paste(crest, (24, 14), crest)
    except Exception:
        pass

    d.text((104, 26), "EKHAYA FC", fill=BLACK, font=_bold_font(34))
    d.text((108, 64), "OFFICIAL FAN MEMBER", fill=BLACK, font=_font(17))

    # Membership / status
    status_text = ("ACTIVE" if status.upper() == "ACTIVE" else status.upper())
    status_color = (22, 128, 62) if status_text == "ACTIVE" else (176, 92, 40)
    d.rounded_rectangle([W - 190, 24, W - 24, 64], radius=8, fill=status_color)
    d.text((W - 174, 34), status_text, fill=WHITE, font=_bold_font(18))

    # Photo (circular) on left body
    photo = _circle_crop(_load_photo(photo_path), 180)
    img.paste(photo, (40, 140), photo)

    # Right-hand details column
    x_name = 250
    y = 140
    # Name
    full_name = "{} {}".format(fan["first_name"], fan["last_name"]).title()
    d.text((x_name, y), full_name[:30], fill=BLACK, font=_bold_font(30))
    y += 46

    def row(label, value, yy):
        d.text((x_name, yy), label.upper(), fill=GREY, font=_font(13))
        d.text((x_name, yy + 20), value, fill=BLACK, font=_bold_font(20))

    row("Member No.", fan.get("member_number") or "-", y)
    y += 62
    row("Membership", package_name or "FAN", y)
    y += 62
    row("Valid Until", expiry or "-", y)

    # Footer strip
    d.rectangle([0, H - 52, W, H], fill=GOLD)
    d.text((24, H - 38), "EKHAYA FC  |  FAN HUB",
           fill=BLACK, font=_bold_font(16))

    # QR bottom-right
    qr_data = "EKH|{}|{}".format(fan.get("member_number") or "-",
                                 card.get("qr_secret") or "")
    qr = _draw_qr(qr_data, 160)
    img.paste(qr, (W - 200, H - 200))

    if card_path is None:
        card_path = os.path.join(CARD_DIR, "card_%s.png" % card["id"])
    img.save(card_path, "PNG")
    return card_path


def card_data_uri(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def generate_qr_png(data, out_path=None):
    """Render a standalone scannable QR PNG (used for e-tickets)."""
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    if out_path is None:
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return buf
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, "PNG")
    return out_path
