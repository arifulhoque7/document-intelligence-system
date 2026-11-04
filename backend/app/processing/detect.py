"""File type detection by content (magic bytes). The client's extension and MIME type are not trusted."""

import zipfile
from pathlib import Path


def detect_type(path: Path) -> str:
    """Return pdf|image|tiff|xlsx|xls|csv|unknown."""
    with open(path, "rb") as f:
        head = f.read(8192)
    if not head:
        return "unknown"
    # A PDF header may sit anywhere in the first 1 KB.
    if b"%PDF-" in head[:1024]:
        return "pdf"
    if head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image"
    if head.startswith(b"II*\x00") or head.startswith(b"MM\x00*"):
        return "tiff"
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(path) as z:
                if "xl/workbook.xml" in z.namelist():
                    return "xlsx"
        except zipfile.BadZipFile:
            pass
        return "unknown"
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "xls"  # OLE2 container
    if b"\x00" not in head:
        for enc in ("utf-8-sig", "cp1252"):
            try:
                sample = head.decode(enc)
            except UnicodeDecodeError:
                continue
            first = sample.splitlines()[0] if sample.splitlines() else ""
            if any(sep in first for sep in (",", ";", "\t", "|")):
                return "csv"
    return "unknown"
