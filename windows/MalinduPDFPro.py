"""Malindu PDF Pro for Windows 10/11 x64.
A self-contained offline desktop reader with durable PDF copies and annotation.
"""
from __future__ import annotations

import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

import fitz
from PySide6.QtCore import Qt, QTimer, Signal, QSize, QSettings
from PySide6.QtGui import QColor, QIcon, QPainter, QFont, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QToolButton,
    QVBoxLayout, QHBoxLayout, QStackedWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QListWidget, QListWidgetItem, QLineEdit, QComboBox, QCheckBox,
    QFileDialog, QMessageBox, QInputDialog, QColorDialog, QSizePolicy, QAbstractItemView,
    QMenu, QStatusBar
)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

from pdfpro_library import Library, pretty_bytes
from pdfpro_viewer import PDFCanvas

APP_NAME = "Malindu PDF Pro"
VERSION = "1.1.0"


def app_icon():
    pix = QPixmap(256, 256)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#2563eb"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(10, 10, 236, 236, 55, 55)
    painter.setPen(QColor("#ffffff"))
    f = QFont("Segoe UI", 96, QFont.Weight.Bold)
    painter.setFont(f)
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "P")
    painter.end()
    return QIcon(pix)


DARK_STYLE = """
* { font-family: "Segoe UI", "Arial"; font-size: 13px; }
QMainWindow, QWidget#main, QWidget#sidebar { background: #0b1120; color: #e5edff; }
QWidget#content, QWidget#home, QWidget#reader { background: #111c30; color: #e5edff; }
QLabel { color: #d9e6fa; background: transparent; }
QLabel#heading { color: #f8fbff; font-size: 28px; font-weight: 750; }
QLabel#subtitle { color: #95a8c5; font-size: 13px; }
QLabel#brand { color: #ffffff; font-size: 21px; font-weight: 800; }
QLabel#tinyLabel { color: #7086a5; font-size: 10px; font-weight: 700; }
QFrame#panel { border: 1px solid #293c5a; border-radius: 18px; background: #17243a; }
QFrame#topbar { background: #111c30; border-bottom: 1px solid #29374f; }
QFrame#toolStrip { background: #182740; border-bottom: 1px solid #31435e; }
QPushButton, QToolButton { border: 1px solid #314563; background: #1d2e49;
                         border-radius: 10px; padding: 9px 13px; color: #e4ecfc;
                         font-weight: 600; }
QPushButton:hover, QToolButton:hover { background: #2b4367; border: 1px solid #4f75ae; }
QPushButton:pressed, QToolButton:pressed { background: #355480; }
QPushButton#primary { background: #3165ef; border-color: #4278ff; color: white; }
QPushButton#primary:hover { background: #417aff; }
QPushButton#danger { color: #ffb5b5; border-color: #7a3545; }
QPushButton#side { text-align: left; border: none; background: transparent;
                  font-size: 14px; padding: 12px 14px; color: #b5c9e5; }
QPushButton#side:hover { background: #243450; color: white; }
QPushButton#sideActive { text-align: left; background: #243c70; border: none;
                        font-size: 14px; padding: 12px 14px; color: white; }
QToolButton#tinyTool { padding: 6px 6px; border: none; background: transparent;
                      font-size: 17px; min-width: 31px; max-width: 40px; }
QToolButton#tinyTool:hover { background: #2a4b77; }
QToolButton#tinyTool[active="true"] { color: #88b4ff; background: #294a85; }
QLineEdit, QComboBox { border: 1px solid #324660; background: #0d192b;
                       color: #f0f5ff; border-radius: 10px; padding: 9px 12px;
                       selection-background-color: #346cff; }
QComboBox QAbstractItemView { color: #f0f5ff; background: #14253e; }
QTableWidget, QListWidget { border: 1px solid #2b405c; border-radius: 12px;
                            background: #142239; gridline-color: #293c58;
                            color: #deebfc; outline: 0; }
QTableWidget::item, QListWidget::item { padding: 10px; border-bottom: 1px solid #263650; }
QTableWidget::item:selected, QListWidget::item:selected { background: #244879; }
QHeaderView::section { color: #a9bfdf; background: #1c304c; padding: 10px;
                       border: none; font-weight: 700; }
QScrollBar:vertical { background: #121f33; width: 11px; }
QScrollBar::handle:vertical { background: #425779; min-height: 23px; border-radius: 5px; }
QScrollBar:horizontal { background: #121f33; height: 11px; }
QScrollBar::handle:horizontal { background: #425779; min-width: 23px; border-radius: 5px; }
QStatusBar { color: #a6bbd8; background: #091322; border-top: 1px solid #23344d; }
QMenu { background: #1a2942; color: #e6efff; border: 1px solid #3b5372; }
QMenu::item { padding: 9px 23px; }
QMenu::item:selected { background: #315b97; }
QCheckBox { color: #d9e6fa; spacing: 9px; }
QFrame#quick { border: 1px solid #3b5478; border-radius: 12px; background: #172943; }
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.library = Library()
        self.settings = QSettings("Malindu", "MalinduPDFPro")
        self.active_id = None
        self.focused = False
        self.active_tool = "hand"
        self.favorite_only = False
        self.toolbar_visible = False
        self._toolbar_timer = QTimer(self)
        self._toolbar_timer.setSingleShot(True)
        self._toolbar_timer.timeout.connect(self.hide_tools)
        self._view_save_timer = QTimer(self)
        self._view_save_timer.setSingleShot(True)
        self._view_save_timer.setInterval(650)
        self._view_save_timer.timeout.connect(self.persist_view)
        self.setWindowTitle(f"{APP_NAME} — Windows x64")
        self.setWindowIcon(app_icon())
        self.resize(1370, 860)
        self.setMinimumSize(900, 620)
        self.setStyleSheet(DARK_STYLE)
        self._ui()
        self._shortcuts()
        self.refresh_library()
        self.statusBar().showMessage("Ready · All PDFs stay on your PC · No account required")
        if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():
            QTimer.singleShot(400, lambda: self.import_files([sys.argv[1]]))
        else:
            # Resume the document opened before the previous app/PC shutdown.
            QTimer.singleShot(350, self.restore_last_document)

    def _button(self, text, callback, primary=False, tooltip="", danger=False):
        b = QPushButton(text)
        if primary:
            b.setObjectName("primary")
        if danger:
            b.setObjectName("danger")
        if tooltip:
            b.setToolTip(tooltip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(callback)
        return b

    def _label(self, text, ident=None):
        x = QLabel(text)
        if ident:
            x.setObjectName(ident)
        return x

    def _tool(self, symbol, desc, action, active=False):
        b = QToolButton()
        b.setObjectName("tinyTool")
        b.setText(symbol)
        b.setToolTip(desc)
        b.setFixedSize(38, 37)
        b.setProperty("active", bool(active))
        b.clicked.connect(action)
        return b

    def _ui(self):
        main = QWidget()
        main.setObjectName("main")
        self.setCentralWidget(main)
        lay = QHBoxLayout(main)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(246)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(17, 22, 17, 17)
        side.setSpacing(11)
        logo = QHBoxLayout()
        badge = QLabel("P")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(43, 43)
        badge.setStyleSheet("background:#3165ef;border-radius:13px;color:white;font-size:27px;font-weight:800;")
        logo.addWidget(badge)
        logo.addWidget(self._label("Malindu\nPDF Pro", "brand"), 1)
        side.addLayout(logo)
        side.addSpacing(19)
        side.addWidget(self._label("YOUR WORKSPACE", "tinyLabel"))
        self.nav_home = self._button("⌂   My Library", self.show_home)
        self.nav_home.setObjectName("sideActive")
        side.addWidget(self.nav_home)
        self.nav_fav = self._button("★   Favorites", self.show_favorites)
        self.nav_fav.setObjectName("side")
        side.addWidget(self.nav_fav)
        side.addWidget(self._button("＋   Import PDFs", self.open_files, primary=True))
        side.addSpacing(22)
        side.addWidget(self._label("RECENTLY OPENED", "tinyLabel"))
        self.recent_list = QListWidget()
        self.recent_list.setFrameShape(QFrame.Shape.NoFrame)
        self.recent_list.setMaximumHeight(330)
        self.recent_list.itemDoubleClicked.connect(self.open_recent)
        side.addWidget(self.recent_list)
        side.addStretch()
        side.addWidget(self._label("OFFLINE & PRIVATE", "tinyLabel"))
        side.addWidget(self._label("Documents are saved locally.\nNo cloud · No ads · No sign-in.", "subtitle"))
        side.addWidget(self._label(f"Windows 10/11 64-bit · v{VERSION}", "tinyLabel"))
        lay.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("content")
        lay.addWidget(self.stack, 1)
        self._make_home()
        self._make_reader()
        self.setStatusBar(QStatusBar())

    def _make_home(self):
        home = QWidget()
        home.setObjectName("home")
        main = QVBoxLayout(home)
        main.setContentsMargins(30, 28, 30, 28)
        main.setSpacing(18)
        bar = QHBoxLayout()
        titles = QVBoxLayout()
        self.home_heading = self._label("Your PDF Library", "heading")
        titles.addWidget(self.home_heading)
        titles.addWidget(self._label("All your documents, edits and bookmarks — saved on this computer.", "subtitle"))
        bar.addLayout(titles, 1)
        bar.addWidget(self._button("＋  Add PDF files", self.open_files, primary=True))
        main.addLayout(bar)

        stats = QHBoxLayout()
        self.stats_docs = self._stats_card("DOCUMENTS", "0", stats)
        self.stats_favs = self._stats_card("FAVORITES", "0", stats)
        self.stats_size = self._stats_card("LIBRARY STORAGE", "0 MB", stats)
        main.addLayout(stats)

        searchbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("⌕  Search documents by file name…")
        self.search.textChanged.connect(self.refresh_library)
        searchbar.addWidget(self.search, 1)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Recent", "Name", "Newest", "Largest"])
        self.sort_combo.currentTextChanged.connect(self.refresh_library)
        searchbar.addWidget(self.sort_combo)
        searchbar.addWidget(self._button("✎ Rename", self.rename_selected))
        searchbar.addWidget(self._button("★ Favorite", self.favorite_selected))
        searchbar.addWidget(self._button("▣ Delete selected", self.delete_selected, danger=True))
        main.addLayout(searchbar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["DOCUMENT", "SIZE", "IMPORTED", "LAST OPENED", "STAR"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 5):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self.open_selected)
        main.addWidget(self.table, 1)
        foot = self._label("Tip: Double-click to read · Ctrl-click for multi-select · Drag PDFs into the window.", "subtitle")
        main.addWidget(foot)
        self.stack.addWidget(home)

    def _stats_card(self, heading, value, layout):
        panel = QFrame()
        panel.setObjectName("panel")
        p = QVBoxLayout(panel)
        p.setContentsMargins(18, 17, 18, 16)
        p.addWidget(self._label(heading, "tinyLabel"))
        label = self._label(value)
        label.setStyleSheet("font-size:23px;font-weight:800;color:#e8f0ff;")
        p.addWidget(label)
        layout.addWidget(panel, 1)
        return label

    def _make_reader(self):
        reader = QWidget()
        reader.setObjectName("reader")
        v = QVBoxLayout(reader)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.reader_header = QFrame()
        self.reader_header.setObjectName("topbar")
        hr = QHBoxLayout(self.reader_header)
        hr.setContentsMargins(13, 10, 14, 10)
        hr.setSpacing(8)
        hr.addWidget(self._button("← Library", self.show_home))
        self.reader_title = self._label("No document", None)
        self.reader_title.setStyleSheet("font-size:15px;font-weight:700;color:#f3f7ff;")
        self.reader_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.reader_title.setWordWrap(False)
        hr.addWidget(self.reader_title, 1)
        hr.addWidget(self._button("☰  Tools", self.toggle_tools))
        hr.addWidget(self._button("⌕  Search", self.find_in_pdf))
        hr.addWidget(self._button("⇩ Save as", self.save_as))
        hr.addWidget(self._button("⛶ Focus", self.toggle_fullscreen, primary=True))
        v.addWidget(self.reader_header)

        self.tools = QFrame()
        self.tools.setObjectName("toolStrip")
        tools_lay = QHBoxLayout(self.tools)
        tools_lay.setContentsMargins(12, 6, 12, 6)
        tools_lay.setSpacing(4)
        self.tool_widgets = {}
        for name, symbol, tooltip in [
            ("hand", "✋", "Move / scroll"), ("pen", "✎", "Freehand pen"),
            ("highlight", "▰", "Highlighter"), ("underline", "U̲", "Underline"),
            ("strike", "S̶", "Strike through"), ("line", "／", "Line"),
            ("rectangle", "□", "Rectangle"), ("ellipse", "◯", "Ellipse"),
            ("text", "T", "Text box"), ("note", "▤", "Sticky note"),
            ("eraser", "⌫", "Erase annotation")
        ]:
            b = self._tool(symbol, tooltip, lambda checked=False, n=name: self.choose_tool(n),
                           active=(name == "hand"))
            tools_lay.addWidget(b)
            self.tool_widgets[name] = b
        tools_lay.addWidget(self._tool("●", "Choose pen color", self.pick_color))
        tools_lay.addWidget(self._tool("↶", "Undo last drawing", self.canvas_undo))
        tools_lay.addSpacing(16)
        tools_lay.addWidget(self._tool("☷", "Page overview", self.page_overview))
        tools_lay.addWidget(self._tool("⟳", "Rotate page", self.rotate_page))
        tools_lay.addWidget(self._tool("▣", "Export page as PNG", self.export_png))
        tools_lay.addStretch()
        self.tools.setVisible(False)
        v.addWidget(self.tools)

        self.canvas = PDFCanvas()
        self.canvas.page_changed.connect(self.page_changed)
        self.canvas.zoom_changed.connect(self.zoom_changed)
        self.canvas.operation_done.connect(self.say)
        self.canvas.error.connect(self.error)
        self.canvas.context_requested.connect(self.show_context_tools)
        self.canvas.horizontalScrollBar().valueChanged.connect(self.schedule_view_save)
        self.canvas.verticalScrollBar().valueChanged.connect(self.schedule_view_save)
        v.addWidget(self.canvas, 1)
        # No permanent floating controls. Right-click on any PDF page to see
        # the small context toolbar, including in fullscreen annotation mode.

        self.reader_bottom = QFrame()
        self.reader_bottom.setObjectName("topbar")
        bottom = QHBoxLayout(self.reader_bottom)
        bottom.setContentsMargins(14, 5, 14, 5)
        bottom.setSpacing(8)
        bottom.addWidget(self._button("◀", lambda: self.canvas.goto_page(self.canvas.last_page-1)))
        self.page_text = self._label("Page —")
        self.page_text.setFixedWidth(115)
        bottom.addWidget(self.page_text)
        bottom.addWidget(self._button("▶", lambda: self.canvas.goto_page(self.canvas.last_page+1)))
        bottom.addWidget(self._button("Go to page", self.goto_page_prompt))
        bottom.addSpacing(16)
        bottom.addWidget(self._button("Fit width", self.canvas.fit_width))
        bottom.addWidget(self._button("Fit page", self.canvas.fit_page))
        bottom.addWidget(self._button("−", lambda: self.canvas.zoom_by(1/1.2)))
        self.zoom_text = self._label("100%")
        self.zoom_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_text.setFixedWidth(55)
        bottom.addWidget(self.zoom_text)
        bottom.addWidget(self._button("+", lambda: self.canvas.zoom_by(1.2)))
        bottom.addStretch()
        bottom.addWidget(self._button("☆ Bookmark", self.toggle_bookmark))
        bottom.addWidget(self._button("⋯  More", self.more_actions))
        v.addWidget(self.reader_bottom)
        self.stack.addWidget(reader)

    def _shortcuts(self):
        for seq, fn in [
            ("Ctrl+O", self.open_files), ("Ctrl+S", self.save_as),
            ("Ctrl+F", self.find_in_pdf), ("Ctrl+Plus", lambda: self.canvas.zoom_by(1.2)),
            ("Ctrl+Equal", lambda: self.canvas.zoom_by(1.2)),
            ("Ctrl+Minus", lambda: self.canvas.zoom_by(1/1.2)),
            ("Ctrl+0", self.canvas.fit_width), ("Ctrl+P", self.print_pdf),
            ("F11", self.toggle_fullscreen), ("Escape", self.escape_key),
            ("Ctrl+Z", self.canvas_undo), ("Ctrl+T", self.toggle_tools),
        ]:
            QShortcut(QKeySequence(seq), self).activated.connect(fn)

    def refresh_library(self, *_):
        if not hasattr(self, "table"):
            return
        docs = self.library.all(self.search.text(), self.sort_combo.currentText(), self.favorite_only)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(docs))
        for row, rec in enumerate(docs):
            for col, label in enumerate([
                "▣  " + rec["name"], pretty_bytes(rec["size"]),
                rec["imported"].replace("T","  ")[:16],
                rec["opened"].replace("T","  ")[:16],
                "★" if rec["favorite"] else "☆"
            ]):
                item = QTableWidgetItem(str(label))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, rec["id"])
                self.table.setItem(row, col, item)
            self.table.setRowHeight(row, 49)
        all_docs = self.library.all()
        self.stats_docs.setText(str(len(all_docs)))
        self.stats_favs.setText(str(sum(x["favorite"] for x in all_docs)))
        self.stats_size.setText(pretty_bytes(sum(x["size"] for x in all_docs)))
        self.recent_list.clear()
        for doc in all_docs[:10]:
            item = QListWidgetItem("▣  " + doc["name"])
            item.setToolTip(doc["name"])
            item.setData(Qt.ItemDataRole.UserRole, doc["id"])
            self.recent_list.addItem(item)

    def show_home(self):
        self.persist_view()
        if self.focused:
            self.toggle_fullscreen()
        self.stack.setCurrentIndex(0)
        self.favorite_only = False
        self.nav_home.setObjectName("sideActive")
        self.nav_fav.setObjectName("side")
        self.home_heading.setText("Your PDF Library")
        self.refresh_library()
        self._polish(self.nav_home)
        self._polish(self.nav_fav)

    def show_favorites(self):
        self.stack.setCurrentIndex(0)
        self.favorite_only = True
        self.home_heading.setText("Starred Documents")
        self.nav_home.setObjectName("side")
        self.nav_fav.setObjectName("sideActive")
        self._polish(self.nav_home)
        self._polish(self.nav_fav)
        self.refresh_library()

    def _polish(self, widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Import PDF documents", "",
                                               "PDF files (*.pdf)")
        if files:
            self.import_files(files)

    def import_files(self, paths):
        imported = []
        errors = []
        for filename in paths:
            try:
                imported.append(self.library.import_pdf(str(filename)))
            except Exception as exc:
                errors.append(f"{Path(filename).name}: {exc}")
        self.refresh_library()
        if errors:
            QMessageBox.warning(self, "Import issue", "\n".join(errors[:5]))
        if imported:
            self.open_record(imported[0]["id"])
            self.say(f"Imported {len(imported)} document(s) into permanent offline library")

    def _selected_ids(self):
        rows = sorted({x.row() for x in self.table.selectedItems()})
        result = []
        for row in rows:
            cell = self.table.item(row, 0)
            if cell:
                result.append(cell.data(Qt.ItemDataRole.UserRole))
        return result

    def open_selected(self, *_):
        keys = self._selected_ids()
        if keys:
            self.open_record(keys[0])

    def open_recent(self, item):
        self.open_record(item.data(Qt.ItemDataRole.UserRole))

    def restore_last_document(self):
        """Open the previous PDF automatically, even after Windows restarts."""
        key = self.settings.value("last_open_id", "", type=str)
        if not key or not self.library.get(key):
            # First launch after upgrading an older EXE: use its saved
            # Recent Documents history instead of starting from a blank home.
            recent = self.library.all()
            key = recent[0]["id"] if recent else ""
        if key and self.active_id is None and self.library.get(key):
            self.open_record(key)

    def restore_view(self, key):
        if self.active_id != key or not self.canvas.pdf:
            return
        state = self.library.view(key)
        if not state:
            return
        try:
            z = float(state.get("zoom", self.canvas.zoom))
            x = float(state.get("center_x", 0))
            y = float(state.get("center_y", 0))
            self.canvas.set_zoom(z)
            self.canvas.centerOn(x, y)
            self.canvas._schedule_render()
        except (TypeError, ValueError, OverflowError) as exc:
            self.say(f"Reopened last page (custom zoom could not be restored: {exc})")

    def schedule_view_save(self, *_):
        if self.active_id and self.canvas.pdf:
            self._view_save_timer.start()

    def persist_view(self):
        if not self.active_id or not self.canvas.pdf:
            return
        point = self.canvas.mapToScene(self.canvas.viewport().rect().center())
        self.library.mark_view(self.active_id, self.canvas.last_page,
                               self.canvas.zoom, point.x(), point.y())

    def open_record(self, key):
        self._view_save_timer.stop()
        self.persist_view()
        rec = self.library.open_record(key)
        if not rec:
            return
        self.active_id = None
        try:
            self.canvas.open_pdf(rec["stored"], rec["page"])
        except Exception as exc:
            QMessageBox.critical(self, "Cannot open PDF", str(exc))
            return
        self.active_id = key
        self.settings.setValue("last_open_id", key)
        self.settings.sync()
        self.active_tool = "hand"
        self.canvas.set_tool("hand")
        self.reader_title.setText(rec["name"])
        self.reader_title.setToolTip(rec["name"])
        self.stack.setCurrentIndex(1)
        self.hide_tools()
        self.refresh_library()
        QTimer.singleShot(260, lambda: self.restore_view(key))
        self.say(f"{rec['name']} · {len(self.canvas.pdf)} pages · PDF copy stored locally")

    def rename_selected(self):
        keys = self._selected_ids()
        if len(keys) != 1:
            self.say("Select one PDF to rename")
            return
        rec = self.library.get(keys[0])
        name, ok = QInputDialog.getText(self, "Rename document", "Display name:", text=rec["name"])
        if ok:
            try:
                self.library.rename(keys[0], name)
                self.refresh_library()
            except Exception as exc:
                self.error(str(exc))

    def favorite_selected(self):
        keys = self._selected_ids()
        if not keys:
            self.say("Select one or more PDFs")
            return
        for key in keys:
            doc = self.library.get(key)
            self.library.favorite(key, not doc["favorite"])
        self.refresh_library()
        self.say(f"Updated favorites for {len(keys)} PDF(s)")

    def delete_selected(self):
        keys = self._selected_ids()
        if not keys:
            self.say("Select the PDFs you want to remove")
            return
        confirm = QMessageBox.question(
            self, "Delete selected PDFs",
            f"Remove {len(keys)} selected document(s) and their stored copies from this app?\n\n"
            "This permanently deletes the app's copies, including any saved annotations. "
            "Your original imported PDFs outside the app remain untouched.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if self.active_id in keys:
            self._view_save_timer.stop()
            self.canvas.close_pdf()
            self.active_id = None
            self.settings.remove("last_open_id")
        count = self.library.delete_many(keys)
        self.refresh_library()
        self.say(f"Removed {count} saved PDF(s)")

    def choose_tool(self, name):
        self.active_tool = name
        self.canvas.set_tool(name)
        for key, btn in self.tool_widgets.items():
            btn.setProperty("active", key == name)
            self._polish(btn)
        self.say(f"{name.title()} tool active · Each completed annotation is autosaved")
        self._toolbar_timer.start(4200)

    def pick_color(self):
        color = QColorDialog.getColor(self.canvas.pen_color, self, "Choose ink color")
        if color.isValid():
            self.canvas.pen_color = color
        self._toolbar_timer.start(2400)

    def show_context_tools(self, global_position):
        """Right-click the PDF to choose tools without an intrusive overlay."""
        if not self.canvas.pdf:
            return
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        for name, symbol, caption in [
            ("hand", "✋", "Hand · scroll and zoom"),
            ("pen", "✎", "Pencil"),
            ("highlight", "▰", "Highlighter"),
            ("underline", "U̲", "Underline"),
            ("strike", "S̶", "Strikethrough"),
            ("line", "／", "Line"),
            ("rectangle", "□", "Rectangle"),
            ("ellipse", "◯", "Ellipse"),
            ("text", "T", "Text"),
            ("note", "▤", "Sticky note"),
            ("eraser", "⌫", "Eraser"),
        ]:
            action = menu.addAction(f"{symbol}  {caption}")
            action.setCheckable(True)
            action.setChecked(self.active_tool == name)
            action.triggered.connect(lambda checked=False, mode=name: self.choose_tool(mode))
        menu.addSeparator()
        menu.addAction("●  Pen color", self.pick_color)
        menu.addAction("↶  Undo last annotation", self.canvas_undo)
        menu.addAction("☰  Show / hide full toolbar  ·  Ctrl+T", self.toggle_tools)
        menu.addSeparator()
        menu.addAction("＋  Zoom in", lambda: self.canvas.zoom_by(1.2))
        menu.addAction("−  Zoom out", lambda: self.canvas.zoom_by(1/1.2))
        menu.addAction("⛶  Toggle fullscreen  ·  F11", self.toggle_fullscreen)
        menu.exec(global_position)

    def toggle_tools(self):
        self.toolbar_visible = not self.toolbar_visible
        self.tools.setVisible(self.toolbar_visible)
        if self.toolbar_visible:
            self._toolbar_timer.start(6500)
        else:
            self._toolbar_timer.stop()

    def hide_tools(self):
        self.toolbar_visible = False
        self.tools.setVisible(False)

    def toggle_fullscreen(self):
        self.focused = not self.focused
        self.sidebar.setVisible(not self.focused)
        self.reader_header.setVisible(not self.focused)
        self.reader_bottom.setVisible(not self.focused)
        self.hide_tools()
        if self.focused:
            self.showFullScreen()
            self.say("Focus mode · Right-click anywhere for pencil/tools · Ctrl+T toggles toolbar · Esc exits")
        else:
            self.showNormal()

    def escape_key(self):
        if self.focused:
            self.toggle_fullscreen()
        elif self.toolbar_visible:
            self.hide_tools()
        elif self.stack.currentIndex() == 1:
            self.show_home()

    def page_changed(self, page, total):
        if self.active_id:
            self.library.mark_page(self.active_id, page)
            self.schedule_view_save()
        self.page_text.setText(f"Page {page+1} / {total}")

    def zoom_changed(self, amount):
        self.zoom_text.setText(f"{amount}%")
        self.schedule_view_save()

    def canvas_undo(self):
        self.canvas.undo()

    def page_overview(self):
        self.canvas.page_overview()

    def goto_page_prompt(self):
        if not self.canvas.pdf:
            return
        page, ok = QInputDialog.getInt(self, "Go to page", "Page number:",
                                      self.canvas.last_page+1, 1, len(self.canvas.pdf))
        if ok:
            self.canvas.goto_page(page-1)

    def find_in_pdf(self):
        if not self.canvas.pdf:
            return
        term, ok = QInputDialog.getText(self, "Find text", "Search inside this PDF:")
        if ok and term.strip():
            if not self.canvas.search_text(term):
                self.say(f"No matches for “{term}”")

    def toggle_bookmark(self):
        if not self.active_id:
            return
        current = self.canvas.last_page
        exists = self.library.toggle_bookmark(self.active_id, current)
        self.say(f"Page {current+1} {'bookmarked' if exists else 'removed from bookmarks'}")

    def show_bookmarks(self):
        if not self.active_id:
            return
        pages = self.library.bookmarks(self.active_id)
        if not pages:
            self.say("No bookmarked pages yet")
            return
        values = [str(x+1) for x in pages]
        choice, ok = QInputDialog.getItem(self, "Bookmarks", "Jump to page:", values, 0, False)
        if ok:
            self.canvas.goto_page(int(choice)-1)

    def save_as(self):
        if not self.canvas.pdf:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export annotated PDF", self.reader_title.text(),
                                             "PDF (*.pdf)")
        if path:
            try:
                if Path(path).resolve() == Path(self.canvas.filename).resolve():
                    self.say("PDF is already saved in the offline library")
                    return
                shutil.copy2(self.canvas.filename, path)
                self.say(f"Exported PDF: {Path(path).name}")
            except Exception as exc:
                self.error(str(exc))

    def export_png(self):
        if not self.canvas.pdf:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export current page as PNG", f"page-{self.canvas.last_page+1}.png",
            "PNG Image (*.png)")
        if path:
            try:
                self.canvas.export_current_image(path)
                self.say(f"Exported {Path(path).name}")
            except Exception as exc:
                self.error(str(exc))

    def rotate_page(self):
        self.canvas.rotate_page()

    def merge_pdfs(self):
        if not self.canvas.pdf:
            return
        sources, _ = QFileDialog.getOpenFileNames(self, "Select PDFs to append", "", "PDF (*.pdf)")
        if not sources:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save merged PDF", "merged.pdf", "PDF (*.pdf)")
        if not out:
            return
        try:
            merged = fitz.open()
            merged.insert_pdf(self.canvas.pdf)
            for src in sources:
                with fitz.open(src) as incoming:
                    if incoming.needs_pass:
                        raise ValueError(f"{Path(src).name}: locked PDF")
                    merged.insert_pdf(incoming)
            merged.save(out, garbage=4, deflate=True)
            merged.close()
            self.import_files([out])
            self.say("Merged document saved and added to library")
        except Exception as exc:
            self.error(f"Merge failed: {exc}")

    def extract_pages(self):
        if not self.canvas.pdf:
            return
        text, ok = QInputDialog.getText(self, "Extract pages",
            "Pages to extract (example: 1-3,5,8):")
        if not ok:
            return
        try:
            nums = set()
            limit = len(self.canvas.pdf)
            for raw in text.split(","):
                raw = raw.strip()
                if not raw:
                    continue
                if "-" in raw:
                    left, right = map(int, raw.split("-", 1))
                    if left < 1 or right > limit or left > right:
                        raise ValueError("Invalid page range")
                    nums.update(range(left-1,right))
                else:
                    val = int(raw)
                    if not 1 <= val <= limit:
                        raise ValueError("Page number out of range")
                    nums.add(val-1)
            if not nums:
                raise ValueError("Choose at least one page")
            path, _ = QFileDialog.getSaveFileName(self, "Save extracted PDF", "extracted.pdf",
                                                  "PDF (*.pdf)")
            if not path:
                return
            dest = fitz.open()
            for i in sorted(nums):
                dest.insert_pdf(self.canvas.pdf, from_page=i, to_page=i)
            dest.save(path, garbage=4, deflate=True)
            dest.close()
            self.import_files([path])
            self.say("Extracted pages saved and imported")
        except Exception as exc:
            self.error(str(exc))

    def print_pdf(self):
        if not self.canvas.pdf:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        painter = QPainter()
        try:
            if not painter.begin(printer):
                raise RuntimeError("Could not start print job")
            page_box = printer.pageRect(QPrinter.Unit.DevicePixel)
            for i in range(len(self.canvas.pdf)):
                if i:
                    printer.newPage()
                p = self.canvas.pdf.load_page(i)
                target_scale = min(page_box.width()/p.rect.width,
                                   page_box.height()/p.rect.height, 3.5)
                pix = p.get_pixmap(matrix=fitz.Matrix(target_scale, target_scale))
                img = __import__("PySide6.QtGui", fromlist=["QImage"]).QImage(
                    pix.samples, pix.width, pix.height, pix.stride,
                    __import__("PySide6.QtGui", fromlist=["QImage"]).QImage.Format.Format_RGB888).copy()
                dest = __import__("PySide6.QtCore", fromlist=["QRect"]).QRect(
                    int(page_box.x()), int(page_box.y()),
                    int(page_box.width()), int(page_box.height()))
                painter.drawImage(dest, img)
            self.say("Print job submitted")
        except Exception as exc:
            self.error(f"Printing failed: {exc}")
        finally:
            if painter.isActive():
                painter.end()

    def more_actions(self):
        menu = QMenu(self)
        entries = [
            ("☷  Page overview", self.page_overview),
            ("☑  Bookmarked pages", self.show_bookmarks),
            ("⌕  Find text", self.find_in_pdf),
            ("⟳  Rotate page 90°", self.rotate_page),
            ("▣  Export current page as image", self.export_png),
            ("⇩  Export PDF copy", self.save_as),
            ("▤  Merge with other PDFs", self.merge_pdfs),
            ("✂  Extract pages", self.extract_pages),
            ("▧  Print PDF", self.print_pdf),
            ("ⓘ  Document details", self.document_info),
        ]
        for label, callback in entries:
            menu.addAction(label, callback)
        menu.exec(self.mapToGlobal(self.rect().center()))

    def document_info(self):
        if not self.canvas.pdf:
            return
        d = self.library.get(self.active_id)
        QMessageBox.information(self, "Document information",
            f"Name: {d['name']}\nPages: {len(self.canvas.pdf)}\n"
            f"Stored: {d['stored']}\nSize: {pretty_bytes(d['size'])}\n"
            f"Imported: {d['imported']}\n\n"
            "This copy is held in your local app library. Original files are unchanged.")

    def say(self, message):
        self.statusBar().showMessage(str(message), 6000)

    def error(self, message):
        self.say(message)
        QMessageBox.warning(self, APP_NAME, str(message))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(
            u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf")
            for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls()
                 if u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf")]
        if paths:
            self.import_files(paths)
            event.acceptProposedAction()

    def closeEvent(self, event):
        try:
            self._view_save_timer.stop()
            self.persist_view()
            self.canvas.close_pdf()
            self.library.close()
        finally:
            super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Malindu")
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    win = MainWindow()
    win.setAcceptDrops(True)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
