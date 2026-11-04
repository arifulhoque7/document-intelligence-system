"""Tesseract OCR with clean-up for poor-quality scans."""

import pytesseract
from PIL import Image, ImageFilter, ImageOps

MIN_GOOD_CONF = 70.0


def preprocess(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img).convert("L")
    # Tesseract wants roughly 30 px tall glyphs; small scans and phone photos get upscaled.
    if img.width < 1600:
        scale = 1600 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    # No percentile cutoff: on a sparse page text is under 1% of pixels and would be clipped away.
    img = ImageOps.autocontrast(img)
    return img.filter(ImageFilter.MedianFilter(3))


def _run(img: Image.Image, psm: int) -> tuple[str, float]:
    data = pytesseract.image_to_data(
        img, config=f"--oem 1 --psm {psm}", output_type=pytesseract.Output.DICT, timeout=120
    )
    lines: dict[tuple, list[str]] = {}
    confs = []
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        conf = float(data["conf"][i])
        if conf >= 0:
            confs.append(conf)
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)
    text = "\n".join(" ".join(ws) for _, ws in sorted(lines.items()))
    return text, (sum(confs) / len(confs) if confs else 0.0)


def _fix_rotation(img: Image.Image) -> Image.Image:
    try:
        osd = pytesseract.image_to_osd(img, config="--psm 0", output_type=pytesseract.Output.DICT, timeout=30)
    except (pytesseract.TesseractError, RuntimeError):
        return img
    angle = int(osd.get("rotate", 0))
    return img.rotate(-angle, expand=True) if angle else img


def ocr_image(img: Image.Image) -> tuple[str, float]:
    """Return (text, mean word confidence 0-100). Retries rotation and a second layout mode on weak results."""
    raw = ImageOps.exif_transpose(img).convert("L")
    img = preprocess(img)
    best = _run(img, 6)
    if best[1] >= MIN_GOOD_CONF:
        return best
    rotated = _fix_rotation(img)
    candidates = ((raw, 6), (rotated, 6), (rotated, 4), (rotated.point(lambda p: 255 if p > 150 else 0), 6))
    for candidate, psm in candidates:
        result = _run(candidate, psm)
        if result[1] > best[1]:
            best = result
        if best[1] >= MIN_GOOD_CONF:
            break
    return best
