"""Executable pre-packaging functional smoke test on Windows runner."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import fitz
from PySide6.QtWidgets import QApplication
from MalinduPDFPro import MainWindow, VERSION

app = QApplication([])
win = MainWindow()
with tempfile.TemporaryDirectory() as folder:
    source = Path(folder) / "Test PDF.pdf"
    pdf = fitz.open()
    for i in range(3):
        p = pdf.new_page()
        p.insert_text((70,70), f"Malindu PDF Pro test page {i+1}")
    pdf.save(str(source))
    pdf.close()
    record = win.library.import_pdf(str(source))
    assert Path(record["stored"]).is_file()
    win.open_record(record["id"])
    app.processEvents()
    assert len(win.canvas.pdf) == 3
    win.canvas.fit_width()
    win.canvas.zoom_by(1.5)
    assert win.canvas.zoom > 0.25
    win.canvas.goto_page(2)
    assert win.canvas.last_page == 2
    assert win.canvas.search_text("test page")
    assert win.library.get(record["id"]) is not None
    page = win.canvas.pdf.load_page(0)
    a = page.add_ink_annot([[(80,100), (150,120)]])
    a.update()
    win.canvas._save_changes()
    win.canvas.close_pdf()
    with fitz.open(record["stored"]) as checked:
        assert any(True for x in checked[0].annots())
    assert win.library.delete_many([record["id"]]) == 1
    assert not Path(record["stored"]).exists()
win.library.close()
print(f"PASS: {VERSION} Windows application, zoom, 3 pages, local library and persistent annotations")
