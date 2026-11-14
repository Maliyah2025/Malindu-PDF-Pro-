"""Persistent, local-only PDF library. User originals are never modified."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QStandardPaths


def data_root() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    root = Path(base) if base else Path.home() / "AppData" / "Roaming" / "MalinduPDFPro"
    root.mkdir(parents=True, exist_ok=True)
    (root / "PDFs").mkdir(exist_ok=True)
    return root


def pretty_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return "0 B"


class Library:
    def __init__(self):
        self.root = data_root()
        self.conn = sqlite3.connect(str(self.root / "library.sqlite"), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, stored TEXT NOT NULL,
            original TEXT, size INTEGER DEFAULT 0, imported TEXT NOT NULL,
            opened TEXT NOT NULL, favorite INTEGER NOT NULL DEFAULT 0,
            page INTEGER NOT NULL DEFAULT 0, bookmarks TEXT DEFAULT '[]'
        )""")
        # Existing users retain their documents; migrate without resetting the DB.
        cols = {row["name"] for row in self.conn.execute("PRAGMA table_info(documents)")}
        if "view_state" not in cols:
            self.conn.execute("ALTER TABLE documents ADD COLUMN view_state TEXT DEFAULT '{}'")
        self.conn.commit()

    def all(self, term="", sort="Recent", favorites=False):
        where = []
        params = []
        if term:
            where.append("LOWER(name) LIKE ?")
            params.append(f"%{term.lower()}%")
        if favorites:
            where.append("favorite=1")
        order = {"Recent": "opened DESC", "Name": "name COLLATE NOCASE ASC",
                 "Largest": "size DESC", "Newest": "imported DESC"}.get(sort, "opened DESC")
        q = "SELECT * FROM documents"
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY " + order
        return [dict(x) for x in self.conn.execute(q, params).fetchall()]

    def get(self, key):
        rec = self.conn.execute("SELECT * FROM documents WHERE id=?", (key,)).fetchone()
        return dict(rec) if rec else None

    def import_pdf(self, source: str) -> dict:
        path = Path(source)
        if not path.is_file() or path.suffix.lower() != ".pdf":
            raise ValueError("Choose a valid .pdf file.")
        # Validate before copying. Never keep unreliable temporary content URIs.
        import fitz
        d = fitz.open(str(path))
        if not d.is_pdf:
            d.close()
            raise ValueError("The selected file is not a PDF.")
        if d.needs_pass:
            d.close()
            raise ValueError("Password-protected PDFs must be unlocked first.")
        d.close()
        key = uuid.uuid4().hex
        stored = self.root / "PDFs" / f"{key}.pdf"
        shutil.copyfile(str(path), str(stored))
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute("""INSERT INTO documents
            (id,name,stored,original,size,imported,opened) VALUES(?,?,?,?,?,?,?)""",
            (key, path.name, str(stored), str(path), stored.stat().st_size, now, now))
        self.conn.commit()
        return self.get(key)

    def rename(self, key, new_name):
        name = new_name.strip()
        if not name:
            raise ValueError("Enter a nonempty name.")
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        self.conn.execute("UPDATE documents SET name=? WHERE id=?", (name, key))
        self.conn.commit()

    def open_record(self, key):
        self.conn.execute("UPDATE documents SET opened=? WHERE id=?",
                          (datetime.now().isoformat(timespec="seconds"), key))
        self.conn.commit()
        return self.get(key)

    def mark_page(self, key, page):
        self.conn.execute("UPDATE documents SET page=? WHERE id=?", (int(page), key))
        self.conn.commit()

    def mark_view(self, key, page, zoom, center_x, center_y):
        """Store exact reading position; committed during use, not just on exit."""
        state = {"zoom": float(zoom), "center_x": float(center_x),
                 "center_y": float(center_y)}
        self.conn.execute(
            "UPDATE documents SET page=?, view_state=? WHERE id=?",
            (int(page), json.dumps(state), key))
        self.conn.commit()

    def view(self, key):
        rec = self.get(key)
        if not rec:
            return {}
        try:
            state = json.loads(rec.get("view_state") or "{}")
            return state if isinstance(state, dict) else {}
        except (TypeError, ValueError):
            return {}

    def favorite(self, key, state):
        self.conn.execute("UPDATE documents SET favorite=? WHERE id=?", (int(bool(state)), key))
        self.conn.commit()

    def bookmarks(self, key):
        rec = self.get(key)
        try:
            return json.loads(rec["bookmarks"]) if rec else []
        except Exception:
            return []

    def toggle_bookmark(self, key, page):
        pages = set(self.bookmarks(key))
        if page in pages:
            pages.remove(page)
        else:
            pages.add(page)
        self.conn.execute("UPDATE documents SET bookmarks=? WHERE id=?",
                          (json.dumps(sorted(pages)), key))
        self.conn.commit()
        return page in pages

    def delete_many(self, keys):
        deleted = 0
        for key in keys:
            doc = self.get(key)
            if not doc:
                continue
            try:
                owned = Path(doc["stored"])
                owned.unlink(missing_ok=True)
                owned.with_name(owned.name + ".recovery.pdf").unlink(missing_ok=True)
                for pending in owned.parent.glob(owned.name + ".saving-*.pdf"):
                    pending.unlink(missing_ok=True)
            except OSError:
                # Do not lose the DB record when the file cannot be deleted.
                continue
            self.conn.execute("DELETE FROM documents WHERE id=?", (key,))
            deleted += 1
        self.conn.commit()
        return deleted

    def close(self):
        self.conn.close()
