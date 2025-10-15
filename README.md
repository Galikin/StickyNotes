# 🗒️ Doug’s Sticky Notes

A **modern desktop sticky notes application** built with **Python and Tkinter**, featuring **rich text formatting**, **image pasting**, **color customization**, **auto-saving**, and **system tray integration**.  

Doug’s Sticky Notes lets you create, manage, and personalize digital sticky notes directly on your desktop — perfect for jotting down quick reminders, lists, or ideas.

---

## 🚀 Features

### 📝 Note Management
- Create, rename, and delete notes easily.
- Each note opens in its own window.
- Automatically saves content and positions.
- Reopens previously open notes on restart.

### 🎨 Appearance & Formatting
- Customize each note’s background color from a palette.
- Rich text formatting with:
  - **Bold**, *Italic*, and <u>Underline*
  - Adjustable **font sizes**
- **Pasting images** directly into notes (clipboard image support).

### 📁 Organization
- Built-in **search bar** to find notes by title or content.
- Sorts notes by creation date (newest first).
- Persistent note color and style storage.

### 📌 Convenience
- **Pin notes** to stay on top of other windows.
- **System tray integration** — minimize to tray and restore quickly.
- Remembers window size and position for each note.

---

## 🧰 Installation

### Requirements

Make sure you have Python **3.8+** installed.

Then install dependencies:
```bash
pip install pillow pystray
```

### Files
| File | Purpose |
|------|----------|
| `sticky_notes_app.py` | Main application |
| `icon.png` *(optional)* | Tray/Window icon image |

If `icon.png` is missing, the app automatically generates a placeholder.

---

## ▶️ Running the App

Run directly from the terminal or double-click the script:
```bash
python sticky_notes_app.py
```

Upon first launch, it creates a data directory at:
```
~/.sticky_notes/
```
Containing:
- `notes.json` — saved notes and content
- `positions.json` — note window sizes and coordinates
- `state.json` — which notes were open last session
- `images/` — stored pasted images
- `icon.ico` — generated from `icon.png` for window title bars

---

## 💡 Usage Guide

### 🗂️ Manager Window
The main “Sticky Notes Manager” lets you:
- **Create New Notes** (`+ New Note`)
- **Delete Selected Notes**
- **Search Notes** (filter by title or content)
- **Double-click** a note to open it
- **Right-click** for a context menu (Delete, Change Color, Close)

### 🪶 Editing Notes
Each note window includes:
- **Title bar entry** (editable note title)
- **Pin/Unpin** button to keep on top
- **Color** button to change note background
- **Delete** button to remove the note
- **Formatting toolbar**:
  - `A↑` / `A↓` — increase or decrease font size
  - `B`, `I`, `U` — bold, italic, underline

### 🖼️ Pasting Images
- Copy an image (e.g., from a screenshot tool or browser)
- Click inside a note and press **Ctrl + V**
- The image will appear inline and be saved in the `images` folder.

### 🖱️ System Tray
- Minimizing the main manager hides it and shows a **tray icon**.
- Right-click tray icon → **Show** or **Quit**.

---

## 🧩 Keyboard Shortcuts

| Shortcut | Action |
|-----------|--------|
| **Ctrl + Shift + N** | Create a new note (from manager) |
| **Ctrl + B** | Toggle bold |
| **Ctrl + L** | Toggle italic |
| **Ctrl + U** | Toggle underline |
| **Delete** | Delete selected note(s) |
| **Double-click** | Open note |
| **Right-click** | Context menu for selected notes |

---

## ⚙️ Data Storage

All data is stored locally in:
```
%USERPROFILE%\.sticky_notes\   (Windows)
~/.sticky_notes/               (macOS/Linux)
```

Each file has a clear role:
- `notes.json`: note titles, content, formatting, and metadata.
- `positions.json`: window position/size for each note.
- `state.json`: which notes were open last session.
- `images/`: pasted image files.

These allow notes to persist between sessions and maintain visual consistency.

---

## 🧼 Troubleshooting

**Icon not appearing on title bar:**  
Ensure `icon.png` exists in the same directory as the script. It should be a square (64×64 recommended). The app will auto-generate a fallback if missing.

**Tray icon not showing on macOS/Linux:**  
Tray support may depend on your desktop environment. On Linux, make sure your system supports app indicators.

**Notes not saving:**  
Check file write permissions for the `~/.sticky_notes` directory.

---

## 🧑‍💻 Developer Notes

- The app is fully **standalone** — no external services or databases.
- Designed to be **PyInstaller-compatible**:
  ```bash
  pyinstaller --onefile --noconsole sticky_notes_app.py
  ```
- Handles icon embedding automatically for Windows executables.

---

## 🏁 Future Enhancements (Ideas)
- Tagging and categorization system
- Note synchronization across devices
- Markdown support
- Export/Import functionality
- Reminder and notification scheduling

---

## 📜 License

This project is provided “as-is” for personal use.  
All rights reserved © Doug’s Sticky Notes.
