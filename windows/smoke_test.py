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

    # Reproduce screenshot error 4: an invalid startxref forces MuPDF repair.
    # saveIncr() must never be used on this document.
    import re
    repaired_input = Path(folder) / "Repaired source.pdf"
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((50, 60), "PDF repair / durable annotations")
    doc.save(str(repaired_input))
    doc.close()
    raw = repaired_input.read_bytes()
    corrupted = re.sub(rb"(startxref\s+)\d+", lambda m: m.group(1) + b"9999999", raw)
    assert corrupted != raw
    repaired_input.write_bytes(corrupted)
    record = win.library.import_pdf(str(repaired_input))
    win.open_record(record["id"])
    app.processEvents()
    assert win.canvas.pdf.is_repaired
    assert not win.canvas.pdf.can_save_incrementally()
    page = win.canvas.pdf.load_page(0)
    annot = page.add_ink_annot([[(90,110),(160,140)]])
    annot.update()
    win.canvas._save_changes()
    assert not win.canvas.pdf.is_repaired
    assert win.canvas.pdf.can_save_incrementally()
    with fitz.open(record["stored"]) as verified:
        assert len(list(verified[0].annots())) == 1
    # After the first complete repair, subsequent strokes autosave normally.
    page = win.canvas.pdf.load_page(0)
    second = page.add_ink_annot([[(90,155),(160,175)]])
    second.update()
    win.canvas._save_changes()
    win.canvas.close_pdf()
    with fitz.open(record["stored"]) as verified:
        assert len(list(verified[0].annots())) == 2
    assert Path(record["stored"] + ".recovery.pdf").exists()

    # The app remembers the last page / zoom / scroll location after closing.
    win.open_record(record["id"])
    win.canvas.zoom_by(1.3)
    win.persist_view()
    state = win.library.view(record["id"])
    assert state["zoom"] > 0
    assert state["center_y"] >= 0
    win.canvas.close_pdf()
    assert win.library.delete_many([record["id"]]) == 1

win.library.close()
print(f"PASS: {VERSION} Windows application, zoom, 3 pages, local library and persistent annotations")
