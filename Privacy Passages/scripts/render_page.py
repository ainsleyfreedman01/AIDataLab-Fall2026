"""Render PDF pages to PNG so they can be viewed with the Read tool.

Usage: python render_page.py PDF_PATH PAGE[,PAGE...]   (1-based PDF page numbers)
Writes work/page_images/<pdfname>_p<N>.png and prints the paths.
"""
import os, sys
import pypdfium2 as pdfium

pdf_path, pages = sys.argv[1], [int(p) for p in sys.argv[2].split(",")]
out_dir = os.path.join(os.path.dirname(__file__), "..", "work", "page_images")
os.makedirs(out_dir, exist_ok=True)
pdf = pdfium.PdfDocument(pdf_path)
stem = os.path.splitext(os.path.basename(pdf_path))[0]
for n in pages:
    img = pdf[n - 1].render(scale=1.6).to_pil()
    path = os.path.abspath(os.path.join(out_dir, f"{stem}_p{n}.png"))
    img.save(path)
    print(path)
