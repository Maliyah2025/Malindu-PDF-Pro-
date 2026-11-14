"""Native high-resolution, continuously scrolling PDF canvas and PDF annotations."""
from __future__ import annotations

import math
import os
import shutil
import uuid
from pathlib import Path

import fitz
from PySide6.QtCore import Qt, QEvent, QRectF, QPointF, QTimer, Signal
from PySide6.QtGui import QColor, QBrush, QPen, QPainterPath, QPixmap, QImage
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsPathItem,
    QGraphicsRectItem, QMessageBox, QInputDialog, QDialog, QVBoxLayout, QListWidget,
    QListWidgetItem
)


class PDFCanvas(QGraphicsView):
    page_changed = Signal(int, int)
    zoom_changed = Signal(int)
    operation_done = Signal(str)
    error = Signal(str)
    context_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdf = None
        self.filename = None
        self.tool = "hand"
        self.pen_color = QColor("#2563eb")
        self.pen_width = 2.2
        self.zoom = 1.0
        self.last_page = 0
        self.pages = []
        self.pix_items = []
        self.render_scales = {}
        self.path_preview = None
        self.start_pos = None
        self.draw_points = []
        self.draw_page = -1
        self.undo_stack = []
        self.popup = None
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#e7edf5"))
        self.setRenderHints(self.renderHints())
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.verticalScrollBar().valueChanged.connect(self._schedule_render)
        self.horizontalScrollBar().valueChanged.connect(self._schedule_render)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._render_visible)
        self.viewport().grabGesture(Qt.GestureType.PinchGesture)

    def attach_popup(self, widget):
        self.popup = widget
        widget.setParent(self.viewport())
        widget.adjustSize()
        widget.raise_()
        self._position_popup()

    def _position_popup(self):
        if self.popup:
            self.popup.adjustSize()
            self.popup.move(max(8, self.viewport().width()-self.popup.width()-15), 12)
            self.popup.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._position_popup()
        self._schedule_render()

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.Gesture:
            g = event.gesture(Qt.GestureType.PinchGesture)
            if g:
                previous = float(g.lastScaleFactor())
                current = float(g.scaleFactor())
                if previous > 0 and current > 0:
                    self.zoom_by(current / previous)
                return True
        if event.type() == QEvent.Type.NativeGesture:
            try:
                if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                    self.zoom_by(max(0.6, 1 + float(event.value())))
                    return True
            except AttributeError:
                pass
        return super().viewportEvent(event)

    def open_pdf(self, filename, page=0):
        self.close_pdf()
        self.filename = str(filename)
        self.pdf = fitz.open(self.filename)
        if self.pdf.needs_pass:
            self.close_pdf()
            raise ValueError("This PDF is password protected. Unlock it before importing.")
        self._make_layout()
        self.zoom = 1.0
        self.resetTransform()
        QTimer.singleShot(60, lambda: self.fit_width() if self.pdf else None)
        QTimer.singleShot(140, lambda: self.goto_page(page) if self.pdf else None)

    def close_pdf(self):
        self._timer.stop()
        if self.pdf:
            self.pdf.close()
        self.pdf = None
        self.filename = None
        self.scene().clear()
        self.pages = []
        self.pix_items = []
        self.render_scales = {}
        self.undo_stack = []
        self.last_page = 0

    def _make_layout(self):
        self.scene().clear()
        self.pages = []
        self.pix_items = []
        self.render_scales.clear()
        if not self.pdf or not len(self.pdf):
            return
        max_width = max(float(p.rect.width) for p in self.pdf)
        y = 24.0
        for i, page in enumerate(self.pdf):
            w, h = float(page.rect.width), float(page.rect.height)
            x = 26.0 + (max_width-w)/2
            rect = QRectF(x, y, w, h)
            shadow = self.scene().addRect(rect.translated(3, 5),
                QPen(QColor("#dce2ed"), 1), QBrush(QColor("#d6deea")))
            shadow.setZValue(-2)
            sheet = self.scene().addRect(rect, QPen(QColor("#cbd5e1"), 0.6),
                                         QBrush(Qt.GlobalColor.white))
            sheet.setZValue(-1)
            item = QGraphicsPixmapItem()
            item.setPos(x, y)
            item.setZValue(0)
            self.scene().addItem(item)
            self.pages.append(rect)
            self.pix_items.append(item)
            y += h + 25
        self.scene().setSceneRect(0, 0, max_width + 58, y + 15)
        self._schedule_render()

    def _schedule_render(self, *_):
        if self.pdf:
            self._timer.start()
            QTimer.singleShot(0, self._emit_page)

    def _visible_range(self):
        r = self.mapToScene(self.viewport().rect()).boundingRect()
        pad = r.height() * 0.75
        expanded = r.adjusted(0, -pad, 0, pad)
        return [i for i, page in enumerate(self.pages) if page.intersects(expanded)]

    def _render_visible(self):
        if not self.pdf:
            return
        visible = set(self._visible_range())
        raster = max(1.15, min(4.5, self.zoom * 1.8))
        for i in visible:
            if self.render_scales.get(i) is not None and abs(self.render_scales[i]-raster) < 0.18:
                continue
            try:
                pix = self.pdf.load_page(i).get_pixmap(
                    matrix=fitz.Matrix(raster, raster), alpha=False, colorspace=fitz.csRGB)
                img = QImage(pix.samples, pix.width, pix.height, pix.stride,
                             QImage.Format.Format_RGB888).copy()
                item = self.pix_items[i]
                item.setPixmap(QPixmap.fromImage(img))
                item.setScale(1.0 / raster)
                self.render_scales[i] = raster
            except (RuntimeError, ValueError, MemoryError) as e:
                self.error.emit(f"Unable to render page {i+1}: {e}")
        for i in list(self.render_scales):
            if i not in visible:
                self.pix_items[i].setPixmap(QPixmap())
                del self.render_scales[i]
        self._emit_page()

    def _emit_page(self):
        if not self.pdf or not self.pages:
            return
        c = self.mapToScene(self.viewport().rect().center())
        nearest = min(range(len(self.pages)),
                      key=lambda i: abs(self.pages[i].center().y()-c.y()))
        if self.last_page != nearest:
            self.last_page = nearest
        self.page_changed.emit(nearest, len(self.pages))

    def set_tool(self, name):
        self.tool = name
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if name == "hand"
                         else QGraphicsView.DragMode.NoDrag)
        self.setCursor(Qt.CursorShape.OpenHandCursor if name == "hand"
                       else Qt.CursorShape.CrossCursor)

    def zoom_by(self, factor):
        if not self.pdf:
            return
        self.set_zoom(self.zoom * factor)

    def set_zoom(self, target):
        if not self.pdf:
            return
        val = max(0.25, min(7.0, float(target)))
        if not math.isfinite(val):
            return
        ratio = val / max(self.zoom, 0.0001)
        if abs(ratio-1.0) < 0.002:
            return
        self.scale(ratio, ratio)
        self.zoom = val
        self.zoom_changed.emit(round(val*100))
        self._schedule_render()

    def fit_width(self):
        if not self.pdf:
            return
        max_w = max(x.width() for x in self.pages)
        self.set_zoom(max(.25, (self.viewport().width()-74) / max_w))
        self.operation_done.emit("Fit width")

    def fit_page(self):
        if not self.pdf:
            return
        rect = self.pages[self.last_page]
        target = min((self.viewport().width()-70)/rect.width(),
                     (self.viewport().height()-55)/rect.height())
        self.set_zoom(target)
        self.goto_page(self.last_page)

    def goto_page(self, i):
        if not self.pdf:
            return
        i = max(0, min(len(self.pages)-1, int(i)))
        self.centerOn(self.pages[i].center())
        self.last_page = i
        self.page_changed.emit(i, len(self.pages))
        self._schedule_render()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self.zoom_by(1.17 if delta > 0 else 1/1.17)
            event.accept()
            return
        # Normal wheels/trackpad moves scroll continuously, never flip whole pages.
        super().wheelEvent(event)
        self._schedule_render()

    def contextMenuEvent(self, event):
        """Right-click anywhere on the PDF to recover the compact tools."""
        self.context_requested.emit(event.globalPos())
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if self.tool == "hand" and event.button() == Qt.MouseButton.LeftButton:
            self.zoom_by(1.5 if self.zoom < 3 else 1/1.5)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _page_for(self, p):
        for idx, rect in enumerate(self.pages):
            if rect.contains(p):
                return idx
        return -1

    def _local(self, i, pt):
        r = self.pages[i]
        return fitz.Point(float(pt.x()-r.x()), float(pt.y()-r.y()))

    def mousePressEvent(self, event):
        if not self.pdf or self.tool == "hand" or event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        pos = self.mapToScene(event.position().toPoint())
        page_idx = self._page_for(pos)
        if page_idx < 0:
            return super().mousePressEvent(event)
        if self.tool == "eraser":
            self.erase_at(page_idx, pos)
            event.accept()
            return
        if self.tool in ("text", "note"):
            self.insert_text(page_idx, pos, note=(self.tool=="note"))
            event.accept()
            return
        self.start_pos = pos
        self.draw_points = [pos]
        self.draw_page = page_idx
        self.path_preview = self.scene().addPath(
            QPainterPath(pos), QPen(self.pen_color, self.pen_width, Qt.PenStyle.SolidLine,
                                     Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        self.path_preview.setZValue(4)
        event.accept()

    def mouseMoveEvent(self, event):
        if self.start_pos is None or self.draw_page < 0:
            return super().mouseMoveEvent(event)
        p = self.mapToScene(event.position().toPoint())
        r = self.pages[self.draw_page]
        px = max(r.left(), min(r.right(), p.x()))
        py = max(r.top(), min(r.bottom(), p.y()))
        p = QPointF(px, py)
        self.draw_points.append(p)
        path = QPainterPath(self.start_pos)
        if self.tool in ("rectangle", "ellipse", "underline", "strike", "line"):
            a = QRectF(self.start_pos, p).normalized()
            if self.tool == "ellipse":
                path.addEllipse(a)
            elif self.tool == "rectangle":
                path.addRect(a)
            else:
                path.lineTo(p)
        else:
            for pt in self.draw_points[1:]:
                path.lineTo(pt)
        if self.path_preview:
            self.path_preview.setPath(path)
            pen = self.path_preview.pen()
            pen.setWidthF(self.pen_width if self.tool != "highlight" else 13)
            pen.setColor(QColor(self.pen_color.red(), self.pen_color.green(),
                                self.pen_color.blue(), 110 if self.tool == "highlight" else 255))
            self.path_preview.setPen(pen)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.start_pos is None or self.draw_page < 0:
            return super().mouseReleaseEvent(event)
        idx = self.draw_page
        p1 = self._local(idx, self.draw_points[0])
        p2 = self._local(idx, self.draw_points[-1])
        old_points = [self._local(idx, p) for p in self.draw_points]
        if self.path_preview:
            self.scene().removeItem(self.path_preview)
        self.path_preview = None
        self.start_pos = None
        self.draw_points = []
        self.draw_page = -1
        if len(old_points) < 2:
            event.accept()
            return
        try:
            page = self.pdf.load_page(idx)
            t = self.tool
            r = fitz.Rect(min(p1.x,p2.x), min(p1.y,p2.y),
                          max(p1.x,p2.x), max(p1.y,p2.y))
            if t in ("pen", "highlight"):
                if len(old_points) < 2:
                    return
                points = [(p.x, p.y) for p in old_points[::max(1, len(old_points)//220)]]
                if len(points) < 2:
                    points = [(p1.x,p1.y), (p2.x,p2.y)]
                annot = page.add_ink_annot([points])
            elif t in ("line","underline","strike"):
                annot = page.add_line_annot(p1, p2)
            elif t == "rectangle" and r.width > 3 and r.height > 3:
                annot = page.add_rect_annot(r)
            elif t == "ellipse" and r.width > 3 and r.height > 3:
                annot = page.add_circle_annot(r)
            else:
                return
            color = (self.pen_color.redF(), self.pen_color.greenF(), self.pen_color.blueF())
            annot.set_colors(stroke=color)
            annot.set_border(width=13 if t == "highlight" else self.pen_width)
            annot.set_opacity(0.23 if t == "highlight" else 0.95)
            annot.update()
            self.undo_stack.append((idx, annot.xref))
            self._save_changes()
            self.operation_done.emit("Annotation saved to your PDF")
        except Exception as exc:
            self.error.emit(f"Annotation could not be saved: {exc}")
        event.accept()

    def _save_changes(self):
        """Durably autosave every completed action, including damaged/repaired PDFs.

        MuPDF refuses incremental writes on a repaired document (error code 4).
        For those files write a complete PDF beside the original, then atomically
        replace the owned library copy. The original imported user file is never
        changed. A recovery copy is kept in case an update is interrupted.
        """
        if not self.pdf:
            return
        if self.pdf.can_save_incrementally():
            self.pdf.saveIncr()
        else:
            target = Path(self.filename)
            staged = target.with_name(target.name + ".saving-" + uuid.uuid4().hex + ".pdf")
            backup = target.with_name(target.name + ".recovery.pdf")
            backup_temp = target.with_name(target.name + ".recovery.tmp")
            current_center = self.mapToScene(self.viewport().rect().center())
            current_page = self.last_page

            # A completed staged file is valid even if power fails before replace.
            # Do not close the current document unless the entire save succeeded.
            try:
                self.pdf.save(str(staged), garbage=0, deflate=True,
                              encryption=fitz.PDF_ENCRYPT_KEEP)
                with fitz.open(str(staged)) as check:
                    if not check.is_pdf or len(check) != len(self.pdf):
                        raise RuntimeError("New PDF failed verification")
                with open(staged, "rb") as stream:
                    os.fsync(stream.fileno())
                shutil.copy2(target, backup_temp)
                os.replace(backup_temp, backup)
            except Exception:
                backup_temp.unlink(missing_ok=True)
                # Preserve the staged PDF on disk if one was fully written.
                raise

            # Windows does not allow replacing a PDF while MuPDF has it open.
            self.pdf.close()
            self.pdf = None
            try:
                os.replace(staged, target)
            except Exception:
                self.pdf = fitz.open(str(target))
                raise RuntimeError("Could not replace the saved PDF. "
                                   f"Recovery file is available at: {staged}")
            self.pdf = fitz.open(str(target))
            self._make_layout()
            self.last_page = current_page
            self.centerOn(current_center)
            self._emit_page()

        # Force fresh tiles so the annotation immediately appears.
        self.render_scales.clear()
        for item in self.pix_items:
            item.setPixmap(QPixmap())
        self._schedule_render()

    def insert_text(self, index, scene_pos, note=False):
        label = "Sticky note" if note else "Text annotation"
        value, ok = QInputDialog.getMultiLineText(self, label, "Enter text:")
        if not ok or not value.strip():
            return
        try:
            page = self.pdf.load_page(index)
            p = self._local(index, scene_pos)
            if note:
                a = page.add_text_annot(p, value)
            else:
                rect = fitz.Rect(p.x, p.y, min(page.rect.width-5,p.x+210),
                                 min(page.rect.height-5,p.y+90))
                a = page.add_freetext_annot(rect, value, fontsize=12, text_color=(
                    self.pen_color.redF(), self.pen_color.greenF(), self.pen_color.blueF()))
            a.update()
            self.undo_stack.append((index, a.xref))
            self._save_changes()
            self.operation_done.emit("Text annotation saved")
        except Exception as exc:
            self.error.emit(str(exc))

    def erase_at(self, index, scene_pos):
        try:
            page = self.pdf.load_page(index)
            p = self._local(index, scene_pos)
            for annot in list(page.annots() or []):
                zone = fitz.Rect(annot.rect)
                zone += (-5, -5, 5, 5)
                if zone.contains(p):
                    page.delete_annot(annot)
                    self._save_changes()
                    self.operation_done.emit("Annotation removed")
                    return
            self.operation_done.emit("Tap a drawing or annotation to erase it")
        except Exception as exc:
            self.error.emit(str(exc))

    def undo(self):
        if not self.pdf or not self.undo_stack:
            self.operation_done.emit("Nothing to undo")
            return
        idx, xref = self.undo_stack.pop()
        page = self.pdf.load_page(idx)
        try:
            for annot in list(page.annots() or []):
                if annot.xref == xref:
                    page.delete_annot(annot)
                    self._save_changes()
                    self.operation_done.emit("Last annotation undone")
                    return
        except Exception as exc:
            self.error.emit(str(exc))

    def rotate_page(self):
        if not self.pdf:
            return
        try:
            current = self.last_page
            page = self.pdf.load_page(current)
            page.set_rotation((page.rotation + 90) % 360)
            self._save_changes()
            self._make_layout()
            self.goto_page(current)
            self.operation_done.emit("Page rotated and saved")
        except Exception as exc:
            self.error.emit(str(exc))

    def search_text(self, term):
        if not self.pdf or not term.strip():
            return False
        n = len(self.pdf)
        for offset in range(n):
            i = (self.last_page + offset) % n
            matches = self.pdf.load_page(i).search_for(term)
            if matches:
                self.goto_page(i)
                r = matches[0]
                page = self.pages[i]
                shape = self.scene().addRect(
                    QRectF(page.x()+r.x0, page.y()+r.y0, r.width, r.height),
                    QPen(QColor("#f59e0b"), 2), QBrush(QColor(251, 191, 36, 70)))
                shape.setZValue(5)
                QTimer.singleShot(6000, lambda: self.scene().removeItem(shape)
                                  if shape.scene() else None)
                self.operation_done.emit(f"Found on page {i+1}")
                return True
        return False

    def export_current_image(self, destination):
        if not self.pdf:
            return
        self.pdf.load_page(self.last_page).get_pixmap(
            matrix=fitz.Matrix(2.5, 2.5), alpha=False).save(destination)

    def page_overview(self):
        if not self.pdf:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Page overview")
        dialog.resize(570, 580)
        layout = QVBoxLayout(dialog)
        items = QListWidget(dialog)
        items.setViewMode(QListWidget.ViewMode.IconMode)
        items.setIconSize(__import__("PySide6.QtCore", fromlist=["QSize"]).QSize(100, 140))
        items.setResizeMode(QListWidget.ResizeMode.Adjust)
        items.setSpacing(14)
        items.setWordWrap(True)
        for i in range(min(len(self.pdf), 120)):
            pix = self.pdf.load_page(i).get_pixmap(matrix=fitz.Matrix(.22, .22))
            img = QImage(pix.samples, pix.width, pix.height, pix.stride,
                         QImage.Format.Format_RGB888).copy()
            it = QListWidgetItem(f"Page {i+1}")
            it.setIcon(__import__("PySide6.QtGui", fromlist=["QIcon"]).QIcon(QPixmap.fromImage(img)))
            items.addItem(it)
        def choose(item):
            self.goto_page(items.row(item))
            dialog.accept()
        items.itemDoubleClicked.connect(choose)
        layout.addWidget(items)
        dialog.exec()
