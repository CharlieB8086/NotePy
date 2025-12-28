import os
import sys
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets


APP_NAME = "NotePy"
ORG_NAME = "Randomsomethings"
SETTINGS_FILE = Path.home() / ".notepy_settings.json"


# ----------------------------
# Settings / State
# ----------------------------

@dataclass
class AppState:
    recent_files: list[str]
    word_wrap: bool
    font_family: str
    font_size: int

    @staticmethod
    def defaults() -> "AppState":
        return AppState(
            recent_files=[],
            word_wrap=True,
            font_family="Segoe UI",
            font_size=12
        )

def load_state() -> AppState:
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            s = AppState.defaults()
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            if not isinstance(s.recent_files, list):
                s.recent_files = []
            s.recent_files = [p for p in s.recent_files if isinstance(p, str)]
            return s
    except Exception:
        pass
    return AppState.defaults()

def save_state(state: AppState) -> None:
    try:
        SETTINGS_FILE.write_text(json.dumps(state.__dict__, indent=2), encoding="utf-8")
    except Exception:
        pass

def elide_middle(path: str, max_len: int = 60) -> str:
    if len(path) <= max_len:
        return path
    head = max_len // 2 - 2
    tail = max_len - head - 3
    return path[:head] + "..." + path[-tail:]


# ----------------------------
# Home / Start Page (matches your image)
# ----------------------------

class StartPage(QtWidgets.QWidget):
    new_file_clicked = QtCore.Signal()
    open_folder_clicked = QtCore.Signal()

    def __init__(self, app_title: str = "NotePy", parent=None):
        super().__init__(parent)

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left rail (dark strip)
        self.rail = QtWidgets.QFrame()
        self.rail.setObjectName("Rail")
        self.rail.setFixedWidth(260)

        # Center
        center = QtWidgets.QWidget()
        center_lay = QtWidgets.QVBoxLayout(center)
        center_lay.setContentsMargins(40, 40, 40, 40)
        center_lay.setSpacing(0)
        center_lay.addStretch(1)

        title = QtWidgets.QLabel(app_title)
        title.setObjectName("StartTitle")
        title.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

        center_lay.addWidget(title)
        center_lay.addSpacing(34)

        cards_row = QtWidgets.QHBoxLayout()
        cards_row.setAlignment(QtCore.Qt.AlignHCenter)
        cards_row.setSpacing(110)

        self.btn_new = QtWidgets.QToolButton()
        self.btn_new.setObjectName("StartCard")
        self.btn_new.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        self.btn_new.setText("New File")
        self.btn_new.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon))
        self.btn_new.setIconSize(QtCore.QSize(64, 64))
        self.btn_new.setFixedSize(250, 175)

        self.btn_folder = QtWidgets.QToolButton()
        self.btn_folder.setObjectName("StartCard")
        self.btn_folder.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        self.btn_folder.setText("Open Folder")
        self.btn_folder.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirIcon))
        self.btn_folder.setIconSize(QtCore.QSize(64, 64))
        self.btn_folder.setFixedSize(250, 175)

        cards_row.addWidget(self.btn_new)
        cards_row.addWidget(self.btn_folder)

        center_lay.addLayout(cards_row)
        center_lay.addStretch(2)

        root.addWidget(self.rail)
        root.addWidget(center, 1)

        self.btn_new.clicked.connect(self.new_file_clicked.emit)
        self.btn_folder.clicked.connect(self.open_folder_clicked.emit)


# ----------------------------
# Editor Tab (simple notepad tab)
# ----------------------------

class DocumentTab(QtWidgets.QWidget):
    changed = QtCore.Signal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.path: Optional[str] = None

        self.editor = QtWidgets.QPlainTextEdit()
        self.editor.textChanged.connect(self.changed.emit)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(self.editor)

        self.apply_font()
        self.apply_word_wrap(self.state.word_wrap)

    def apply_font(self):
        f = QtGui.QFont(self.state.font_family, self.state.font_size)
        self.editor.setFont(f)

    def apply_word_wrap(self, enabled: bool):
        self.editor.setLineWrapMode(
            QtWidgets.QPlainTextEdit.WidgetWidth if enabled else QtWidgets.QPlainTextEdit.NoWrap
        )

    def is_dirty(self) -> bool:
        return self.editor.document().isModified()

    def title(self) -> str:
        name = os.path.basename(self.path) if self.path else "Untitled"
        return name + (" •" if self.is_dirty() else "")

    def load_file(self, path: str):
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        self.editor.setPlainText(text)
        self.path = path
        self.editor.document().setModified(False)
        self.changed.emit()

    def save_to(self, path: str):
        Path(path).write_text(self.editor.toPlainText(), encoding="utf-8")
        self.path = path
        self.editor.document().setModified(False)
        self.changed.emit()


# ----------------------------
# Main Window
# ----------------------------

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.state = load_state()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 720)

        # Status bar first (so any updates won't crash)
        self._build_status_bar()

        # Editor tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_status_bar)

        # Start page (the image)
        self.start_page = StartPage(APP_NAME)
        self.start_page.new_file_clicked.connect(self.on_start_new_file)
        self.start_page.open_folder_clicked.connect(self.on_start_open_folder)

        # Stack: Start <-> Editor
        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self.start_page)  # 0
        self.stack.addWidget(self.tabs)        # 1
        self.setCentralWidget(self.stack)

        self._build_actions()
        self._build_menus()

        self.apply_theme()      # MUST look like your image
        self.show_start()

    # ---------------- UI: Status Bar ----------------

    def _build_status_bar(self):
        sb = QtWidgets.QStatusBar()
        self.setStatusBar(sb)

        self.lbl_file = QtWidgets.QLabel("")
        self.lbl_pos = QtWidgets.QLabel("")
        self.lbl_dirty = QtWidgets.QLabel("")

        self.lbl_file.setMinimumWidth(420)

        sb.addWidget(self.lbl_file, 1)
        sb.addPermanentWidget(self.lbl_pos)
        sb.addPermanentWidget(self.lbl_dirty)

    def update_status_bar(self):
        # If we're on start page, keep it quiet like the screenshot
        if self.stack.currentIndex() == 0:
            self.lbl_file.setText("")
            self.lbl_pos.setText("")
            self.lbl_dirty.setText("")
            return

        tab = self.current_tab()
        if not tab:
            self.lbl_file.setText("Untitled")
            self.lbl_pos.setText("Ln 1, Col 1")
            self.lbl_dirty.setText("Saved")
            return

        path = tab.path or "Untitled"
        self.lbl_file.setText(elide_middle(path, 70))

        cursor = tab.editor.textCursor()
        ln = cursor.blockNumber() + 1
        col = cursor.positionInBlock() + 1
        self.lbl_pos.setText(f"Ln {ln}, Col {col}")
        self.lbl_dirty.setText("Modified" if tab.is_dirty() else "Saved")

    # ---------------- Navigation ----------------

    def show_start(self):
        self.stack.setCurrentIndex(0)
        self.update_status_bar()

    def show_editor(self):
        self.stack.setCurrentIndex(1)
        self.update_status_bar()

    def on_start_new_file(self):
        self.show_editor()
        self.new_tab()

    def on_start_open_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Open Folder", str(Path.home()))
        if not folder:
            return
        # Keep the same look; just switch to editor for now.
        self.show_editor()
        self.new_tab()
        self.statusBar().showMessage(f"Opened folder: {folder}", 4000)

    # ---------------- Tabs / Editor ----------------

    def current_tab(self) -> Optional[DocumentTab]:
        w = self.tabs.currentWidget()
        return w if isinstance(w, DocumentTab) else None

    def new_tab(self):
        tab = DocumentTab(self.state)
        tab.changed.connect(self.refresh_tab_title)

        idx = self.tabs.addTab(tab, tab.title())
        self.tabs.setCurrentIndex(idx)
        tab.editor.setFocus()

        self.refresh_tab_title()

    def refresh_tab_title(self):
        tab = self.current_tab()
        idx = self.tabs.currentIndex()
        if tab and idx >= 0:
            self.tabs.setTabText(idx, tab.title())
        self.update_status_bar()

    def close_tab(self, index: int):
        if index < 0:
            return
        tab = self.tabs.widget(index)
        if not isinstance(tab, DocumentTab):
            return

        if tab.is_dirty():
            resp = QtWidgets.QMessageBox.question(
                self,
                "Unsaved changes",
                f"Save changes to {os.path.basename(tab.path) if tab.path else 'Untitled'}?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel
            )
            if resp == QtWidgets.QMessageBox.Cancel:
                return
            if resp == QtWidgets.QMessageBox.Yes:
                if not self._save_tab(tab):
                    return

        self.tabs.removeTab(index)
        tab.deleteLater()

        if self.tabs.count() == 0:
            # If no tabs, go back to the start screen (like a “real app”)
            self.show_start()
        else:
            self.update_status_bar()

    # ---------------- File Actions ----------------

    def open_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open File", str(Path.home()),
            "Text Files (*.txt *.md *.log *.json *.py);;All Files (*.*)"
        )
        if not path:
            return

        self.show_editor()

        # focus existing tab if already open
        for i in range(self.tabs.count()):
            t = self.tabs.widget(i)
            if isinstance(t, DocumentTab) and t.path == path:
                self.tabs.setCurrentIndex(i)
                return

        # open into new tab
        self.new_tab()
        tab = self.current_tab()
        if not tab:
            return
        try:
            tab.load_file(path)
            self._add_recent(path)
            self.refresh_tab_title()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Open failed", str(e))

    def save_current(self):
        tab = self.current_tab()
        if not tab:
            return
        if tab.path:
            try:
                tab.save_to(tab.path)
                self._add_recent(tab.path)
                self.refresh_tab_title()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Save failed", str(e))
        else:
            self.save_current_as()

    def save_current_as(self):
        tab = self.current_tab()
        if not tab:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save As", str(Path.home() / "Untitled.txt"),
            "Text Files (*.txt);;Markdown (*.md);;All Files (*.*)"
        )
        if not path:
            return
        try:
            tab.save_to(path)
            self._add_recent(path)
            self.refresh_tab_title()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(e))

    def _save_tab(self, tab: DocumentTab) -> bool:
        if tab.path:
            try:
                tab.save_to(tab.path)
                self._add_recent(tab.path)
                return True
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Save failed", str(e))
                return False
        # Save As
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save As", str(Path.home() / "Untitled.txt"),
            "Text Files (*.txt);;Markdown (*.md);;All Files (*.*)"
        )
        if not path:
            return False
        try:
            tab.save_to(path)
            self._add_recent(path)
            return True
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(e))
            return False

    # ---------------- Recent Files ----------------

    def _add_recent(self, path: str):
        p = str(Path(path).resolve())
        if p in self.state.recent_files:
            self.state.recent_files.remove(p)
        self.state.recent_files.insert(0, p)
        self.state.recent_files = self.state.recent_files[:10]
        save_state(self.state)
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self):
        if not hasattr(self, "menu_recent"):
            return
        self.menu_recent.clear()
        if not self.state.recent_files:
            a = self.menu_recent.addAction("(No recent files)")
            a.setEnabled(False)
            return
        for p in self.state.recent_files:
            act = self.menu_recent.addAction(elide_middle(p, 64))
            act.triggered.connect(lambda checked=False, path=p: self._open_recent(path))
        self.menu_recent.addSeparator()
        clear = self.menu_recent.addAction("Clear recent")
        clear.triggered.connect(self._clear_recent)

    def _open_recent(self, path: str):
        if not Path(path).exists():
            QtWidgets.QMessageBox.warning(self, "Missing file", "That file no longer exists.")
            self.state.recent_files = [p for p in self.state.recent_files if p != path]
            save_state(self.state)
            self._rebuild_recent_menu()
            return
        self.show_editor()
        # open it
        self.new_tab()
        tab = self.current_tab()
        if tab:
            tab.load_file(path)
            self.refresh_tab_title()

    def _clear_recent(self):
        self.state.recent_files = []
        save_state(self.state)
        self._rebuild_recent_menu()

    # ---------------- Menus / Actions ----------------

    def _build_actions(self):
        self.act_new = QtGui.QAction("New File", self)
        self.act_new.setShortcut(QtGui.QKeySequence.New)
        self.act_new.triggered.connect(self.on_start_new_file)

        self.act_open = QtGui.QAction("Open…", self)
        self.act_open.setShortcut(QtGui.QKeySequence.Open)
        self.act_open.triggered.connect(self.open_file)

        self.act_save = QtGui.QAction("Save", self)
        self.act_save.setShortcut(QtGui.QKeySequence.Save)
        self.act_save.triggered.connect(self.save_current)

        self.act_save_as = QtGui.QAction("Save As…", self)
        self.act_save_as.setShortcut(QtGui.QKeySequence.SaveAs)
        self.act_save_as.triggered.connect(self.save_current_as)

        self.act_quit = QtGui.QAction("Quit", self)
        self.act_quit.setShortcut(QtGui.QKeySequence.Quit)
        self.act_quit.triggered.connect(self.close)

        self.act_about = QtGui.QAction("About NotePy", self)
        self.act_about.triggered.connect(self._about)

    def _build_menus(self):
        mb = self.menuBar()

        # Must match your screenshot labels
        m_file = mb.addMenu("File")
        m_edit = mb.addMenu("Edit")
        m_view = mb.addMenu("View")
        m_window = mb.addMenu("Window")
        m_about = mb.addMenu("About")

        m_file.addAction(self.act_new)
        m_file.addAction(self.act_open)

        self.menu_recent = m_file.addMenu("Open Recent")
        self._rebuild_recent_menu()

        m_file.addSeparator()
        m_file.addAction(self.act_save)
        m_file.addAction(self.act_save_as)
        m_file.addSeparator()
        m_file.addAction(self.act_quit)

        # basic edit bindings
        act_undo = QtGui.QAction("Undo", self)
        act_undo.setShortcut(QtGui.QKeySequence.Undo)
        act_undo.triggered.connect(lambda: self.current_tab() and self.current_tab().editor.undo())
        act_redo = QtGui.QAction("Redo", self)
        act_redo.setShortcut(QtGui.QKeySequence.Redo)
        act_redo.triggered.connect(lambda: self.current_tab() and self.current_tab().editor.redo())
        act_cut = QtGui.QAction("Cut", self)
        act_cut.setShortcut(QtGui.QKeySequence.Cut)
        act_cut.triggered.connect(lambda: self.current_tab() and self.current_tab().editor.cut())
        act_copy = QtGui.QAction("Copy", self)
        act_copy.setShortcut(QtGui.QKeySequence.Copy)
        act_copy.triggered.connect(lambda: self.current_tab() and self.current_tab().editor.copy())
        act_paste = QtGui.QAction("Paste", self)
        act_paste.setShortcut(QtGui.QKeySequence.Paste)
        act_paste.triggered.connect(lambda: self.current_tab() and self.current_tab().editor.paste())

        m_edit.addAction(act_undo)
        m_edit.addAction(act_redo)
        m_edit.addSeparator()
        m_edit.addAction(act_cut)
        m_edit.addAction(act_copy)
        m_edit.addAction(act_paste)

        # view placeholders (keeps menus like the image)
        act_home = QtGui.QAction("Home", self)
        act_home.triggered.connect(self.show_start)
        m_view.addAction(act_home)

        m_about.addAction(self.act_about)

    def _about(self):
       msg = QtWidgets.QMessageBox(self)
       msg.setWindowTitle("About NotePy")
       msg.setTextFormat(QtCore.Qt.RichText)
       msg.setText(
        """
        <b>NotePy</b><br>
        A notepad app built by Charlie Blaize<br>
        Version 1.0.0 (Open Source)<br><br>
        <a href="https://github.com/CharlieB8086/NotePy">GitHub Repository</a>
        """
    )
       msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
       msg.exec()


    # ---------------- Theme (MUST look like your image) ----------------

    def apply_theme(self):
        # Dark, muted, soft: matches your screenshot vibe
        self.setStyleSheet("""
            QMainWindow { background: #1e1e1e; }
            QWidget { color: rgba(255,255,255,0.60); font-size: 13px; }

            /* Menu bar: subtle, almost invisible */
            QMenuBar {
                background: rgba(0,0,0,0.15);
                border: 0;
                padding: 2px 4px;
            }
            QMenuBar::item {
                padding: 6px 10px;
                color: rgba(255,255,255,0.38);
            }
            QMenuBar::item:selected {
                background: rgba(255,255,255,0.06);
                border-radius: 8px;
                color: rgba(255,255,255,0.55);
            }

            QMenu {
                background: #242424;
                border: 1px solid rgba(255,255,255,0.10);
                padding: 6px;
                border-radius: 10px;
            }
            QMenu::item { padding: 8px 12px; border-radius: 8px; color: rgba(255,255,255,0.60); }
            QMenu::item:selected { background: rgba(255,255,255,0.08); }

            /* Left rail */
            QFrame#Rail {
                background: #121212;
                border-right: 1px solid rgba(255,255,255,0.08);
            }

            /* Big center title */
            QLabel#StartTitle {
                font-size: 84px;
                font-weight: 300;
                color: rgba(255,255,255,0.14);
                letter-spacing: 1px;
            }

            /* Start cards */
            QToolButton#StartCard {
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 18px;
                padding-top: 14px;
                color: rgba(255,255,255,0.36);
            }
            QToolButton#StartCard:hover {
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(255,255,255,0.14);
                color: rgba(255,255,255,0.52);
            }
            QToolButton#StartCard:pressed {
                background: rgba(255,255,255,0.05);
            }

            /* Tabs + editor (kept low-contrast) */
            QTabWidget::pane { border: 0; background: transparent; }
            QTabBar::tab {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.08);
                padding: 8px 12px;
                margin-right: 6px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                color: rgba(255,255,255,0.50);
            }
            QTabBar::tab:selected {
                background: rgba(255,255,255,0.07);
                border-color: rgba(255,255,255,0.12);
                color: rgba(255,255,255,0.70);
            }

            QPlainTextEdit {
                background: #171717;
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 14px;
                padding: 12px;
                color: rgba(255,255,255,0.72);
                selection-background-color: rgba(255,255,255,0.16);
            }

            QStatusBar {
                background: rgba(0,0,0,0.15);
                border-top: 1px solid rgba(255,255,255,0.08);
                color: rgba(255,255,255,0.40);
            }
        """)

    # ---------------- Close safety ----------------

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # Ask to save dirty tabs
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, DocumentTab) and tab.is_dirty():
                self.tabs.setCurrentIndex(i)
                resp = QtWidgets.QMessageBox.question(
                    self,
                    "Unsaved changes",
                    f"Save changes to {os.path.basename(tab.path) if tab.path else 'Untitled'}?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel
                )
                if resp == QtWidgets.QMessageBox.Cancel:
                    event.ignore()
                    return
                if resp == QtWidgets.QMessageBox.Yes:
                    if not self._save_tab(tab):
                        event.ignore()
                        return

        save_state(self.state)
        event.accept()


# ----------------------------
# Main
# ----------------------------

def main():
    QtCore.QCoreApplication.setOrganizationName(ORG_NAME)
    QtCore.QCoreApplication.setApplicationName(APP_NAME)

    app = QtWidgets.QApplication(sys.argv)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
