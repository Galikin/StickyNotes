import sys
import json
import os
from pathlib import Path
from datetime import datetime
from threading import Thread

# PyQt6 imports
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLineEdit, QListWidget, QListWidgetItem, QTextEdit,
                             QMessageBox, QMenu, QSystemTrayIcon, QColorDialog, QSlider, QLabel, QFrame, QFontDialog)
from PyQt6.QtGui import QIcon, QAction, QColor, QTextCharFormat, QFont, QGuiApplication, QPixmap, QPainter
from PyQt6.QtCore import Qt, QSize, QEvent, pyqtSignal, QObject

# PIL for icon and image handling
from PIL import Image, ImageDraw, ImageGrab
from PIL.ImageQt import ImageQt

# Global hotkey support
from pynput import keyboard
from pynput.keyboard import Key, KeyCode

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class HotkeySignaler(QObject):
    """Helper class to emit Qt signals from the hotkey thread"""
    create_note_signal = pyqtSignal(str)


class NoteWindow(QWidget):
    """
    A separate window for an individual sticky note.
    """
    def __init__(self, note_id, app_instance):
        super().__init__()
        self.note_id = note_id
        self.app = app_instance
        self.note_data = self.app.notes[self.note_id]
        self.init_ui()

    def init_ui(self):
        # --- Window Setup ---
        self.setWindowTitle(self.note_data.get("title", "Note"))
        self.setWindowIcon(self.app.app_icon)
        
        # Restore position and size
        positions = self.app.load_positions()
        if self.note_id in positions:
            pos = positions[self.note_id]
            self.setGeometry(pos['x'], pos['y'], pos['width'], pos['height'])
        else:
            self.resize(250, 250)
            self.center_on_manager()

        # Mark as no longer new after opening
        self.app.notes[self.note_id]["is_new"] = False
        self.app.save_notes()

        # --- Layouts ---
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(self.main_layout)

        # --- Widgets ---
        # Top control bar
        control_layout = QHBoxLayout()
        self.title_entry = QLineEdit(self.note_data.get("title", "Note"))
        self.title_entry.setStyleSheet("font-weight: bold; border: none;")
        control_layout.addWidget(self.title_entry)
        
        # Buttons - styled to blend in
        self.pin_button = QPushButton("📌")
        self.pin_button.setCheckable(True)
        self.pin_button.setToolTip("Pin/Unpin")
        
        self.color_button = QPushButton("🎨")
        self.color_button.setToolTip("Change Color")
        
        self.delete_button = QPushButton("🗑")
        self.delete_button.setToolTip("Delete Note")
        
        control_layout.addWidget(self.pin_button)
        control_layout.addWidget(self.color_button)
        control_layout.addWidget(self.delete_button)
        self.main_layout.addLayout(control_layout)

        # Transparency Slider
        transparency_frame = QFrame()
        transparency_layout = QHBoxLayout(transparency_frame)
        transparency_layout.setContentsMargins(0, 5, 0, 5)
        
        transparency_layout.addWidget(QLabel("◯"))
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setRange(30, 100) # From 0.3 to 1.0
        transparency_layout.addWidget(self.transparency_slider)
        transparency_layout.addWidget(QLabel("●"))
        
        self.main_layout.addWidget(transparency_frame)

        # Formatting Toolbar
        formatting_layout = QHBoxLayout()
        self.font_button = QPushButton("F")
        self.bold_button = QPushButton("B")
        self.italic_button = QPushButton("I")
        self.underline_button = QPushButton("U")
        
        self.bold_button.setCheckable(True)
        self.italic_button.setCheckable(True)
        self.underline_button.setCheckable(True)
        
        # Apply blended styling to formatting buttons
        self.bold_button.setStyleSheet("font-weight: bold;")
        self.italic_button.setStyleSheet("font-style: italic;")
        self.underline_button.setStyleSheet("text-decoration: underline;")
        
        formatting_layout.addWidget(self.font_button)
        formatting_layout.addWidget(self.bold_button)
        formatting_layout.addWidget(self.italic_button)
        formatting_layout.addWidget(self.underline_button)
        formatting_layout.addStretch()
        self.main_layout.addLayout(formatting_layout)

        # Text Editor
        self.text_edit = QTextEdit()
        self.text_edit.setHtml(self.note_data.get("content_html", ""))
        self.main_layout.addWidget(self.text_edit)

        # --- Initial State & Connections ---
        self.apply_styles()
        self.update_pin_state(self.note_data.get("pinned", False))
        self.transparency_slider.setValue(int(self.note_data.get("transparency", 1.0) * 100))
        self.update_transparency(self.transparency_slider.value())

        self.title_entry.textChanged.connect(self.save_note)
        self.text_edit.textChanged.connect(self.save_note)
        self.pin_button.toggled.connect(self.update_pin_state)
        self.color_button.clicked.connect(self.show_color_dialog)
        self.delete_button.clicked.connect(self.delete_note)
        self.transparency_slider.valueChanged.connect(self.update_transparency)
        self.transparency_slider.sliderReleased.connect(self.app.save_notes)

        # Formatting connections
        self.bold_button.clicked.connect(lambda: self.set_text_format('bold'))
        self.italic_button.clicked.connect(lambda: self.set_text_format('italic'))
        self.underline_button.clicked.connect(lambda: self.set_text_format('underline'))
        self.font_button.clicked.connect(self.show_font_dialog)
        self.text_edit.cursorPositionChanged.connect(self.update_formatting_buttons)
        
        # --- Shortcuts ---
        bold_action = QAction(self)
        bold_action.setShortcut("Ctrl+B")
        bold_action.triggered.connect(lambda: self.set_text_format('bold'))
        self.addAction(bold_action)

        italic_action = QAction(self)
        italic_action.setShortcut("Ctrl+I")
        italic_action.triggered.connect(lambda: self.set_text_format('italic'))
        self.addAction(italic_action)

        underline_action = QAction(self)
        underline_action.setShortcut("Ctrl+U")
        underline_action.triggered.connect(lambda: self.set_text_format('underline'))
        self.addAction(underline_action)
        
    def apply_styles(self):
        color = self.note_data.get("color", "#FFFF99")
        
        # Convert hex to rgb for hover effects
        r, g, b = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        # Create a slightly darker shade for hover
        hover_r = max(0, r - 20)
        hover_g = max(0, g - 20)
        hover_b = max(0, b - 20)
        hover_color = f"#{hover_r:02x}{hover_g:02x}{hover_b:02x}"
        
        style = f"""
            NoteWindow, QWidget {{ background-color: {color}; }}
            QLineEdit {{ background-color: {color}; }}
            QTextEdit {{ background-color: {color}; border: none; }}
            
            /* Blended button style - no borders, transparent background */
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                color: #555;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: rgba(0, 0, 0, 0.1);
            }}
            QPushButton:checked {{
                background-color: rgba(0, 0, 0, 0.15);
                font-weight: bold;
            }}
            
            QSlider::groove:horizontal {{
                border: 1px solid #bbb;
                background: white;
                height: 5px;
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #66e, stop:1 #bbf);
                height: 10px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: #777;
                border: 1px solid #5c5c5c;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QFrame {{ background-color: {color}; }}
            QLabel {{ 
                background-color: {color}; 
                color: #888;
                font-size: 10px;
            }}
        """
        self.setStyleSheet(style)
        
    def update_pin_state(self, pinned):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, pinned)
        self.pin_button.setText("📍" if pinned else "📌")
        self.pin_button.setChecked(pinned)
        self.note_data["pinned"] = pinned
        self.show() # Re-show to apply window flag change
        self.save_note()

    def update_transparency(self, value):
        alpha = value / 100.0
        self.setWindowOpacity(alpha)
        self.note_data["transparency"] = alpha
        # Save is now handled by sliderReleased, so we don't need to call it here.

    def show_color_dialog(self):
        self.app.show_color_chooser([self.note_id])
    
    def set_text_format(self, style):
        # This function now applies formatting to selected text,
        # or sets the format for text that is about to be typed if there is no selection.
        
        # Get the format at the current cursor position to determine how to toggle.
        # We use the cursor's format, which is more accurate for the exact position.
        cursor = self.text_edit.textCursor()
        fmt = cursor.charFormat()

        # Toggle the desired style.
        if style == 'bold':
            fmt.setFontWeight(QFont.Weight.Bold if not fmt.fontWeight() == QFont.Weight.Bold else QFont.Weight.Normal)
        elif style == 'italic':
            fmt.setFontItalic(not fmt.fontItalic())
        elif style == 'underline':
            fmt.setFontUnderline(not fmt.fontUnderline())
        
        # Apply the toggled format.
        # If text is selected, this applies to the selection.
        # If not, this applies to whatever is typed next.
        self.text_edit.mergeCurrentCharFormat(fmt)
        self.text_edit.setFocus()

    def show_font_dialog(self):
        cursor = self.text_edit.textCursor()

        # Get the current font to initialize the dialog.
        # If text is selected, it uses the selection's font.
        # Otherwise, it uses the font at the cursor's position.
        current_font = cursor.charFormat().font()
        
        font, ok = QFontDialog.getFont(current_font, self, "Select Font")

        if ok:
            fmt = QTextCharFormat()
            fmt.setFont(font)
            cursor.mergeCharFormat(fmt)
            self.text_edit.mergeCurrentCharFormat(fmt)
        
        self.text_edit.setFocus()

    def update_formatting_buttons(self):
        fmt = self.text_edit.currentCharFormat()
        self.bold_button.setChecked(fmt.fontWeight() == QFont.Weight.Bold)
        self.italic_button.setChecked(fmt.fontItalic())
        self.underline_button.setChecked(fmt.fontUnderline())

    def update_data_from_ui(self):
        """Reads UI values (except transparency) and updates the in-memory note_data dictionary."""
        if self.note_id not in self.app.notes:
            return
        self.note_data["title"] = self.title_entry.text()
        self.note_data["content_html"] = self.text_edit.toHtml()
        self.note_data["content_text"] = self.text_edit.toPlainText()
        self.setWindowTitle(self.note_data["title"])

    def save_note(self):
        """Updates the in-memory data and saves all notes to the file."""
        self.update_data_from_ui()
        self.app.save_notes()
        self.app.refresh_list()

    def delete_note(self):
        if self.app.confirm_delete(f"Delete note '{self.note_data['title']}'?"):
            self.app.delete_notes_by_id([self.note_id])
            self.close()

    def center_on_manager(self):
        manager_geo = self.app.manager.geometry()
        self.move(manager_geo.center() - self.rect().center())

    def closeEvent(self, event):
        # If the whole app is quitting, don't individually process window closures,
        # as quit_app() has already saved the state.
        if hasattr(self.app, 'is_quitting') and self.app.is_quitting:
            super().closeEvent(event)
            return

        self.save_note()
        if self.note_id in self.app.open_windows:
            del self.app.open_windows[self.note_id]
        self.app.save_state()
        self.app.save_positions()
        super().closeEvent(event)

class StickyNotesManagerWindow(QMainWindow):
    """
    Custom QMainWindow for the manager to properly handle events like
    minimizing to tray and closing the application.
    """
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance

    def changeEvent(self, event):
        """
        Handles window state changes to detect minimization.
        """
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                self.app.save_positions()
                self.app.save_state()
                self.hide()
                self.app.tray_icon.show()
                event.accept()
                return
        super().changeEvent(event)

    def closeEvent(self, event):
        """
        Handles the manager window's close event (the 'X' button)
        to quit the entire application.
        """
        self.app.quit_app()
        event.accept()

class StickyNotesApp:
    def __init__(self):
        # --- File and Path Setup ---
        self.data_dir = Path.home() / ".sticky_notes_qt"
        self.data_dir.mkdir(exist_ok=True)
        self.notes_file = self.data_dir / "notes.json"
        self.state_file = self.data_dir / "state.json"
        self.positions_file = self.data_dir / "positions.json"

        # --- App Data ---
        self.notes = {}
        self.open_windows = {}
        self.search_query = ""
        self.is_quitting = False
        self.load_notes()

        # --- Qt App Initialization ---
        self.app = QApplication(sys.argv)
        self.app_icon = self.create_icon()
        self.app.setWindowIcon(self.app_icon)
        
        # --- Global Hotkey Setup ---
        self.hotkey_signaler = HotkeySignaler()
        self.hotkey_signaler.create_note_signal.connect(self.create_note_with_content)
        self.start_hotkey_listener()
        
        self.init_tray_icon()
        self.init_manager_ui()
        self.restore_open_notes()

    def start_hotkey_listener(self):
        """Start the global hotkey listener in a background thread"""
        def on_activate():
            # Get clipboard content
            clipboard = QApplication.clipboard()
            selected_text = clipboard.text()
            
            # Emit signal to create note (thread-safe)
            self.hotkey_signaler.create_note_signal.emit(selected_text)
        
        # Define the hotkey combination: Ctrl+Shift+C
        hotkey = keyboard.HotKey(
            keyboard.HotKey.parse('<ctrl>+<alt>+n'),
            on_activate
        )
        
        def for_canonical(f):
            return lambda k: f(listener.canonical(k))
        
        # Start listener in background thread
        listener = keyboard.Listener(
            on_press=for_canonical(hotkey.press),
            on_release=for_canonical(hotkey.release)
        )
        listener.daemon = True
        listener.start()

    def create_note_with_content(self, content):
        """Create a new note and optionally populate it with content"""
        note_id = str(int(datetime.now().timestamp() * 1000))
        
        # Determine title based on content
        title = "Quick Note"
        if content and content.strip():
            # Use first line or first 30 chars as title
            first_line = content.strip().split('\n')[0]
            title = first_line[:30] + ('...' if len(first_line) > 30 else '')
        
        self.notes[note_id] = {
            "title": title,
            "content_html": content if content else "",
            "created": datetime.now().isoformat(),
            "color": "#FFFF99",
            "is_new": True,
            "pinned": False,
            "transparency": 1.0
        }
        self.save_notes()
        self.refresh_list()
        self.open_note(note_id)
        
        # Focus the text editor if there's content
        if note_id in self.open_windows:
            window = self.open_windows[note_id]
            window.text_edit.setFocus()
            # Move cursor to end
            cursor = window.text_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            window.text_edit.setTextCursor(cursor)

    def run(self):
        self.manager.show()
        self.tray_icon.hide()
        sys.exit(self.app.exec())
        
    def create_icon(self):
        icon_path_str = resource_path("icon.png")
        icon_path = Path(icon_path_str)
        if not icon_path.exists():
            img = Image.new('RGB', (64, 64), color='black')
            d = ImageDraw.Draw(img)
            d.text((10, 10), "SN", fill='white')
            img.save(icon_path_str)
        return QIcon(icon_path_str)

    def load_notes(self):
        if self.notes_file.exists():
            try:
                with open(self.notes_file, 'r') as f:
                    self.notes = json.load(f)
            except json.JSONDecodeError:
                self.notes = {}
        else:
            self.notes = {}

    def save_notes(self):
        with open(self.notes_file, 'w') as f:
            json.dump(self.notes, f, indent=2)

    def load_state(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {"open_notes": []}
        return {"open_notes": []}

    def save_state(self):
        state = {"open_notes": list(self.open_windows.keys())}
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def load_positions(self):
        if self.positions_file.exists():
            try:
                with open(self.positions_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_positions(self):
        positions = self.load_positions()
        for note_id, window in list(self.open_windows.items()):
            if window.isVisible() and note_id in self.notes:
                # Save position regardless of is_new flag
                positions[note_id] = {
                    "x": window.x(), "y": window.y(),
                    "width": window.width(), "height": window.height()
                }
        with open(self.positions_file, 'w') as f:
            json.dump(positions, f, indent=2)

    def init_manager_ui(self):
        self.manager = StickyNotesManagerWindow(self)
        self.manager.setWindowTitle("Sticky Notes Manager")
        self.manager.setGeometry(0, 0, 400, 500)
        
        # Center window
        screen_center = QGuiApplication.primaryScreen().availableGeometry().center()
        self.manager.move(screen_center - self.manager.frameGeometry().center())

        central_widget = QWidget()
        self.manager.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Header
        header = QLabel("Doug's Sticky Notes")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("background-color: #333; color: white; font-size: 16px; font-weight: bold; padding: 10px;")
        main_layout.addWidget(header)
        
        # Info label for hotkey
        hotkey_info = QLabel("💡 Press Ctrl+Alt+N anywhere to create a quick note from something copied!")
        hotkey_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hotkey_info.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        main_layout.addWidget(hotkey_info)
        
        # Buttons
        btn_layout = QHBoxLayout()
        new_note_btn = QPushButton("+ New Note")
        new_note_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        delete_note_btn = QPushButton("Delete Note")
        delete_note_btn.setStyleSheet("background-color: #f44336; color: white;")
        btn_layout.addWidget(new_note_btn)
        btn_layout.addWidget(delete_note_btn)
        main_layout.addLayout(btn_layout)

        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_entry = QLineEdit()
        search_layout.addWidget(self.search_entry)
        main_layout.addLayout(search_layout)

        # Notes List
        self.notes_listbox = QListWidget()
        self.notes_listbox.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.notes_listbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        main_layout.addWidget(self.notes_listbox)

        # --- Connections ---
        new_note_btn.clicked.connect(self.create_new_note)
        delete_note_btn.clicked.connect(self.delete_selected_notes_btn)
        self.search_entry.textChanged.connect(self.refresh_list)
        self.notes_listbox.itemDoubleClicked.connect(self.on_note_double_click)
        self.notes_listbox.customContextMenuRequested.connect(self.show_list_context_menu)
        
        self.refresh_list()

        # --- Shortcut for New Note ---
        new_note_action = QAction(self.manager)
        new_note_action.setShortcut("Ctrl+Shift+N")
        new_note_action.triggered.connect(self.create_new_note)
        self.manager.addAction(new_note_action)

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self.app_icon, self.app)
        self.tray_icon.setToolTip("Sticky Notes")
        
        menu = QMenu()
        show_action = QAction("Show Manager", self.app)
        quit_action = QAction("Quit", self.app)
        
        show_action.triggered.connect(self.show_manager)
        quit_action.triggered.connect(self.quit_app)
        
        menu.addAction(show_action)
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()
        
        self.tray_icon.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_manager()

    def show_manager(self):
        self.tray_icon.hide()
        self.manager.showNormal() # Use showNormal to restore from minimized state
        self.manager.raise_()
        self.manager.activateWindow()

    def create_new_note(self):
        self.create_note_with_content("")

    def refresh_list(self):
        self.notes_listbox.clear()
        search_query = self.search_entry.text().lower()
        
        sorted_notes = sorted(self.notes.items(), key=lambda x: x[1].get("created", ""), reverse=True)
        
        for note_id, note in sorted_notes:
            title = note.get("title", "Note")
            content = note.get("content_text", "")
            
            if search_query and search_query not in title.lower() and search_query not in content.lower():
                continue
                
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, note_id) # Store note_id in the item
            item.setBackground(QColor(note.get("color", "#FFFF99")))
            self.notes_listbox.addItem(item)
            
    def open_note(self, note_id):
        if note_id in self.open_windows and self.open_windows[note_id].isVisible():
            self.open_windows[note_id].raise_()
            self.open_windows[note_id].activateWindow()
            return
            
        if note_id in self.notes:
            note_window = NoteWindow(note_id, self)
            self.open_windows[note_id] = note_window
            note_window.show()
            note_window.raise_()
            note_window.activateWindow()
            self.save_state()

    def on_note_double_click(self, item):
        note_id = item.data(Qt.ItemDataRole.UserRole)
        self.open_note(note_id)

    def get_selected_note_ids(self):
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.notes_listbox.selectedItems()]

    def delete_selected_notes_btn(self):
        note_ids = self.get_selected_note_ids()
        if not note_ids:
            QMessageBox.warning(self.manager, "Select Note", "Please select one or more notes to delete.")
            return

        if self.confirm_delete(f"Delete {len(note_ids)} selected notes?"):
            self.delete_notes_by_id(note_ids)

    def delete_notes_by_id(self, note_ids):
        for note_id in note_ids:
            if note_id in self.notes:
                del self.notes[note_id]
            if note_id in self.open_windows:
                self.open_windows[note_id].close()
        self.save_notes()
        self.refresh_list()
        
    def show_list_context_menu(self, pos):
        selected_ids = self.get_selected_note_ids()
        if not selected_ids:
            return

        menu = QMenu()
        delete_action = QAction(f"Delete {len(selected_ids)} Note(s)", self.manager)
        color_action = QAction(f"Change Color for {len(selected_ids)} Note(s)", self.manager)

        delete_action.triggered.connect(self.delete_selected_notes_btn)
        color_action.triggered.connect(lambda: self.show_color_chooser(selected_ids))
        
        menu.addAction(delete_action)
        menu.addAction(color_action)
        
        menu.exec(self.notes_listbox.mapToGlobal(pos))
    
    def show_color_chooser(self, note_ids):
        color = QColorDialog.getColor()
        if color.isValid():
            hex_color = color.name()
            for note_id in note_ids:
                if note_id in self.notes:
                    self.notes[note_id]["color"] = hex_color
                    if note_id in self.open_windows:
                        self.open_windows[note_id].note_data["color"] = hex_color
                        self.open_windows[note_id].apply_styles()
            self.save_notes()
            self.refresh_list()
    
    def confirm_delete(self, message):
        reply = QMessageBox.question(self.manager, "Confirm Delete", message, 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes

    def restore_open_notes(self):
        state = self.load_state()
        for note_id in state["open_notes"]:
            if note_id in self.notes:
                self.open_note(note_id)

    def quit_app(self):
        """Saves all data and exits the application."""
        self.is_quitting = True

        # Manually update text/title from open windows before saving.
        # Transparency is already up-to-date in the data model from sliderReleased.
        for window in self.open_windows.values():
            window.update_data_from_ui()
        
        self.save_notes()
        self.save_positions()
        self.save_state()
        QApplication.instance().quit()


if __name__ == "__main__":
    app = StickyNotesApp()
    app.run()