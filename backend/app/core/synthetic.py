"""Generates clearly FICTIONAL document images for tests and demo data. Never uses real data."""
from __future__ import annotations

import io
import random
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BANNER = "FICTIONAL DOCUMENT - SYNTHETIC DEMO DATA"
_FONT_CANDIDATES = ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _font(size: int):
    for name in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render_document(title: str, lines: list[str], degrade: float = 0.0, seed: int = 7) -> Image.Image:
    """degrade: 0 = clean; ~2.5 = partly legible poor scan (downscale + blur + noise)."""
    img = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 1200, 1714], outline="black", width=3)
    d.text((90, 90), BANNER, fill="black", font=_font(30))
    d.text((90, 170), title, fill="black", font=_font(44))
    y = 300
    for line in lines:
        d.text((90, y), line, fill="black", font=_font(36))
        y += 70
    d.text((90, 1630), BANNER + " - NOT A REAL FINANCIAL DOCUMENT", fill="black", font=_font(24))
    if degrade:
        rnd = random.Random(seed)
        img = img.resize((int(img.width / degrade), int(img.height / degrade)), Image.BILINEAR)
        img = img.filter(ImageFilter.GaussianBlur(0.28 * degrade))
        px = img.load()
        for _ in range(img.width * img.height // 60):
            x, yy = rnd.randrange(img.width), rnd.randrange(img.height)
            v = rnd.randrange(120, 230)
            px[x, yy] = (v, v, v)
    return img


def to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def to_pdf_bytes(imgs: list[Image.Image]) -> bytes:
    buf = io.BytesIO()
    imgs[0].convert("RGB").save(buf, "PDF", save_all=True, append_images=[i.convert("RGB") for i in imgs[1:]])
    return buf.getvalue()


def fdr_scan_lines(fdr_no="DEMO-FDR-100234", bank="Northwind Demo Bank Ltd", branch="Example Main Branch",
                   amount="INR 1,000,000.00", issue="15 Mar 2024", maturity="15 Mar 2026",
                   beneficiary="Sample Institute of Technology", status="Active") -> list[str]:
    return [f"FDR No: {fdr_no}", f"Issuing Bank: {bank}", f"Branch: {branch}",
            f"Principal Amount: {amount}", f"Date of Issue: {issue}", f"Maturity Date: {maturity}",
            f"Beneficiary: {beneficiary}", f"Status: {status}"]


def application_form_lines(fdr_no="DEMO-FDR-100234", amount="INR 1,000,000.00",
                           beneficiary="Sample Institute of Technology", reference="DEMO-APP-2026-001") -> list[str]:
    return [f"Application No: {reference}", f"Institution Name: {beneficiary}", f"FDR Number: {fdr_no}",
            f"Deposit Amount: {amount}"]


def authorisation_letter_lines(beneficiary="Sample Institute of Technology") -> list[str]:
    return [f"Institution Name: {beneficiary}", "Subject: Fictional authorisation letter for demonstration"]
