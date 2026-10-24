"""Upload validation: extension, declared MIME type, real content (magic bytes), size, page and
pixel limits. Never trusts the user-supplied filename."""
from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass


class FileValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


_TYPES = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
}
SUPPORTED_DESCRIPTION = "PDF, PNG or JPEG"


@dataclass
class ValidatedFile:
    extension: str
    mime: str
    size: int
    sha256: str
    page_count: int


def sanitise_display_filename(name: str | None) -> str:
    """Return a safe name for DISPLAY only (the stored file gets a random name)."""
    name = (name or "").replace("\\", "/").split("/")[-1]
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "", name).strip(" .")
    return (name or "document")[:200]


def _pdf_pages(content: bytes) -> int:
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(content)
        try:
            return len(pdf)
        finally:
            pdf.close()
    except ImportError:
        return max(1, len(re.findall(rb"/Type\s*/Page[^s]", content)))
    except Exception as exc:  # corrupt or password protected
        raise FileValidationError("invalid_pdf", "The PDF could not be opened (it may be corrupt or password protected).") from exc


def validate_upload(filename: str | None, declared_mime: str | None, content: bytes, *,
                    max_bytes: int, max_pdf_pages: int = 10, max_image_pixels: int = 40_000_000) -> ValidatedFile:
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if filename and "." in filename else ""
    if ext not in _TYPES:
        raise FileValidationError("unsupported_extension", f"Unsupported file type. Please upload a {SUPPORTED_DESCRIPTION} file.")
    mime, magic = _TYPES[ext]
    if (declared_mime or "").split(";")[0].strip().lower() != mime:
        raise FileValidationError("mime_mismatch", f"The declared file type does not match a {ext} file.")
    if len(content) == 0:
        raise FileValidationError("empty_file", "The file is empty.")
    if len(content) > max_bytes:
        raise FileValidationError("file_too_large", f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.")
    if not content.startswith(magic):
        raise FileValidationError("content_mismatch", "The file content does not match its extension.")
    pages = 1
    if ext == ".pdf":
        pages = _pdf_pages(content)
        if pages > max_pdf_pages:
            raise FileValidationError("too_many_pages", f"The PDF has {pages} pages; the limit is {max_pdf_pages}.")
    else:
        try:
            from PIL import Image
            with Image.open(io.BytesIO(content)) as im:
                if im.width * im.height > max_image_pixels:
                    raise FileValidationError("image_too_large", "The image dimensions are too large.")
                im.verify()
        except FileValidationError:
            raise
        except Exception as exc:
            raise FileValidationError("invalid_image", "The image could not be decoded.") from exc
    return ValidatedFile(ext, mime, len(content), hashlib.sha256(content).hexdigest(), pages)
