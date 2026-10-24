"""OCR using the Tesseract *program* (via pytesseract) and PDF page rendering via pypdfium2.

Installing the `pytesseract` Python package does NOT install Tesseract itself. If the program is
missing, OcrUnavailableError is raised and callers should fall back to manual field entry.
OCR text is never logged here.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from .domain import OcrLine, OcrPage


class OcrError(Exception):
    pass


class OcrUnavailableError(OcrError):
    pass


_tesseract_cmd: Optional[str] = None


def configure(tesseract_cmd: Optional[str] = None) -> None:
    global _tesseract_cmd
    _tesseract_cmd = tesseract_cmd or None


def _pt():
    try:
        import pytesseract
    except ImportError as exc:
        raise OcrUnavailableError("The 'pytesseract' Python package is not installed (pip install -r requirements.txt).") from exc
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd or "tesseract"
    return pytesseract


def check_ocr_available() -> tuple[bool, str]:
    try:
        pt = _pt()
        return True, f"Tesseract {pt.get_tesseract_version()}"
    except OcrUnavailableError as exc:
        return False, str(exc)
    except Exception:
        return False, ("The Tesseract program was not found. Install it and set TESSERACT_CMD in .env "
                       "if it is not on PATH (see README).")


def ocr_image(image, page_number: int = 1, lang: str = "eng", psm: int = 6) -> OcrPage:
    pt = _pt()
    from PIL import ImageOps
    img = ImageOps.autocontrast(image.convert("L"))
    try:
        data = pt.image_to_data(img, lang=lang, config=f"--psm {psm}", output_type=pt.Output.DICT)
    except pt.TesseractNotFoundError as exc:
        raise OcrUnavailableError("The Tesseract program was not found. Install it and set TESSERACT_CMD (see README).") from exc
    except Exception as exc:
        raise OcrError("OCR failed for this page.") from exc

    lines: "OrderedDict[tuple, list]" = OrderedDict()
    all_conf: list[float] = []
    for i, word in enumerate(data["text"]):
        word = (word or "").strip()
        if not word:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append((word, conf))
        if conf >= 0:
            all_conf.append(conf)
    out_lines = []
    for words in lines.values():
        confs = [c for _, c in words if c >= 0]
        out_lines.append(OcrLine(" ".join(w for w, _ in words), sum(confs) / len(confs) if confs else None))
    return OcrPage(page_number, "\n".join(l.text for l in out_lines), out_lines,
                   sum(all_conf) / len(all_conf) if all_conf else None)


def render_pdf_pages(path: str, max_pages: int = 10, scale: float = 2.5):
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise OcrUnavailableError("PDF rendering needs the 'pypdfium2' package (pip install -r requirements.txt).") from exc
    try:
        pdf = pdfium.PdfDocument(path)
    except Exception as exc:
        raise OcrError("The PDF could not be opened.") from exc
    try:
        if len(pdf) > max_pages:
            raise OcrError(f"The PDF has more than {max_pages} pages.")
        return [pdf[i].render(scale=scale).to_pil() for i in range(len(pdf))]
    finally:
        pdf.close()


def ocr_file(path: str, mime: str, max_pages: int = 10, lang: str = "eng", psm: int = 6) -> list[OcrPage]:
    if mime == "application/pdf":
        images = render_pdf_pages(path, max_pages)
    else:
        from PIL import Image
        try:
            with Image.open(path) as im:
                im.load()
                images = [im.copy()]
        except Exception as exc:
            raise OcrError("The image could not be opened.") from exc
    return [ocr_image(img, i + 1, lang, psm) for i, img in enumerate(images)]
