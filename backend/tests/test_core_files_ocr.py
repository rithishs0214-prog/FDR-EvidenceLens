import io, os, sys, tempfile, unittest
sys.path.insert(0, ".")
from PIL import Image
from app.core import ocr, synthetic as syn
from app.core.extraction import extract_fields
from app.core.file_validation import FileValidationError, sanitise_display_filename, validate_upload

MB = 1024 * 1024
PNG = syn.to_png_bytes(Image.new("RGB", (50, 50), "white"))
PDF = syn.to_pdf_bytes([Image.new("RGB", (50, 50), "white")])


def check(name, mime, content, **kw):
    return validate_upload(name, mime, content, max_bytes=kw.pop("max_bytes", MB), **kw)


class FileValidationTests(unittest.TestCase):
    def code(self, *a, **kw):
        with self.assertRaises(FileValidationError) as cm:
            check(*a, **kw)
        return cm.exception.code

    def test_valid_files(self):
        self.assertEqual(check("a.png", "image/png", PNG).mime, "image/png")
        self.assertEqual(check("a.pdf", "application/pdf", PDF).page_count, 1)
        jpg = io.BytesIO(); Image.new("RGB", (20, 20)).save(jpg, "JPEG")
        self.assertEqual(check("A.JPG", "image/jpeg", jpg.getvalue()).extension, ".jpg")

    def test_rejections(self):
        self.assertEqual(self.code("a.exe", "application/octet-stream", b"MZ"), "unsupported_extension")
        self.assertEqual(self.code("a.png", "image/jpeg", PNG), "mime_mismatch")
        self.assertEqual(self.code("a.png", "image/png", PDF), "content_mismatch")
        self.assertEqual(self.code("a.pdf", "application/pdf", b"<html>not a pdf</html>"), "content_mismatch")
        self.assertEqual(self.code("a.png", "image/png", b""), "empty_file")
        self.assertEqual(self.code("a.png", "image/png", PNG, max_bytes=10), "file_too_large")
        self.assertEqual(self.code("noextension", "image/png", PNG), "unsupported_extension")

    def test_corrupt_files(self):
        self.assertEqual(self.code("a.png", "image/png", PNG[:30]), "invalid_image")
        self.assertEqual(self.code("a.pdf", "application/pdf", b"%PDF-1.4 garbage"), "invalid_pdf")

    def test_page_and_pixel_limits(self):
        pdf3 = syn.to_pdf_bytes([Image.new("RGB", (50, 50))] * 3)
        self.assertEqual(self.code("a.pdf", "application/pdf", pdf3, max_pdf_pages=2), "too_many_pages")
        self.assertEqual(self.code("a.png", "image/png", PNG, max_image_pixels=100), "image_too_large")

    def test_filename_sanitised(self):
        self.assertEqual(sanitise_display_filename("../../etc/passwd"), "passwd")
        self.assertEqual(sanitise_display_filename("C:\\x\\..\\evil<>.png"), "evil.png")
        self.assertEqual(sanitise_display_filename(None), "document")


@unittest.skipUnless(ocr.check_ocr_available()[0], "Tesseract not available")
class RealOcrTests(unittest.TestCase):
    TRUTH = {"fdr_number": "DEMO-FDR-100234", "principal_amount": "1000000.00", "currency": "INR",
             "issue_date": "2024-03-15", "maturity_date": "2026-03-15", "bank_name": "Northwind Demo Bank Ltd",
             "beneficiary_name": "Sample Institute of Technology"}

    def fields(self, pages):
        return {f.field_name: f for f in extract_fields(pages)}

    def test_clean_png_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.png")
            syn.render_document("FDR Receipt", syn.fdr_scan_lines()).save(p)
            pages = ocr.ocr_file(p, "image/png")
        f = self.fields(pages)
        for k, v in self.TRUTH.items():
            self.assertEqual(f[k].value, v, k)
            self.assertFalse(f[k].needs_confirmation, k)
            self.assertEqual(f[k].page_number, 1)
            self.assertIsNotNone(f[k].confidence)

    def test_multipage_pdf_records_page_numbers(self):
        imgs = [syn.render_document("Cover", ["Subject: Fictional cover page"]),
                syn.render_document("FDR Receipt", syn.fdr_scan_lines())]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.pdf")
            open(p, "wb").write(syn.to_pdf_bytes(imgs))
            pages = ocr.ocr_file(p, "application/pdf")
        self.assertEqual(len(pages), 2)
        f = self.fields(pages)
        self.assertEqual(f["fdr_number"].page_number, 2)
        self.assertEqual(f["fdr_number"].value, "DEMO-FDR-100234")

    def test_pdf_over_page_limit(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.pdf")
            open(p, "wb").write(syn.to_pdf_bytes([Image.new("RGB", (80, 80))] * 3))
            with self.assertRaises(ocr.OcrError):
                ocr.ocr_file(p, "application/pdf", max_pages=2)

    def test_poor_quality_scan_never_yields_trusted_wrong_values(self):
        pages = [ocr.ocr_image(syn.render_document("FDR Receipt", syn.fdr_scan_lines(), degrade=2.5))]
        fields = extract_fields(pages)
        self.assertTrue(any(f.needs_confirmation for f in fields) or len(fields) < 7,
                        "a poor scan must produce flagged or missing fields")
        for f in fields:
            if f.field_name in self.TRUTH and f.value and not f.needs_confirmation:
                self.assertEqual(f.value, self.TRUTH[f.field_name], f"trusted value for {f.field_name} is wrong")

    def test_corrupt_image_raises_ocr_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "bad.png")
            open(p, "wb").write(b"\x89PNG\r\n\x1a\nnot really")
            with self.assertRaises(ocr.OcrError):
                ocr.ocr_file(p, "image/png")


class OcrUnavailableTests(unittest.TestCase):
    def test_missing_tesseract_program_gives_setup_error(self):
        ocr.configure("/definitely/not/tesseract")
        try:
            ok, msg = ocr.check_ocr_available()
            self.assertFalse(ok)
            self.assertIn("Tesseract", msg)
            with self.assertRaises(ocr.OcrUnavailableError):
                ocr.ocr_image(Image.new("RGB", (100, 100), "white"))
        finally:
            ocr.configure(None)


if __name__ == "__main__":
    unittest.main()
