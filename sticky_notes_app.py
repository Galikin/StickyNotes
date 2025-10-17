import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext, font
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageGrab
import pystray
from threading import Thread

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class StickyNotesApp:
    def __init__(self):
        self.data_dir = Path.home() / ".sticky_notes"
        self.data_dir.mkdir(exist_ok=True)
        self.images_dir = self.data_dir / "images"
        self.images_dir.mkdir(exist_ok=True)
        self.notes_file = self.data_dir / "notes.json"
        self.state_file = self.data_dir / "state.json"
        self.positions_file = self.data_dir / "positions.json"
        
        # Handle icon conversion for window title bars
        self.icon_ico_path = self.data_dir / "icon.ico"
        if not self.icon_ico_path.exists():
            try:
                icon_png_path = resource_path("icon.png")
                img = Image.open(icon_png_path)
                img.save(self.icon_ico_path, format='ICO', sizes=[(32, 32)])
            except Exception as e:
                print(f"Could not create icon for windows: {e}")

        self.notes = {}
        self.open_windows = {}
        self.tray_thread = None
        self.search_query = ""
        self.load_notes()
        self.create_manager_window()
        self.restore_open_notes()

    def load_notes(self):
        """Load notes from file"""
        if self.notes_file.exists():
            try:
                with open(self.notes_file, 'r') as f:
                    self.notes = json.load(f)
                    print(f"[LOAD_NOTES] Loaded notes: {list(self.notes.keys())}")
                    for note_id, note in self.notes.items():
                        print(f"  - {note_id}: is_new={note.get('is_new', False)}")
            except:
                self.notes = {}
                print("[LOAD_NOTES] Failed to load notes")
        else:
            self.notes = {}
            print("[LOAD_NOTES] Notes file does not exist")

    def save_notes(self):
        """Save notes to file"""
        print(f"[SAVE_NOTES] Saving {len(self.notes)} notes")
        for note_id, note in self.notes.items():
            print(f"  - {note_id}: is_new={note.get('is_new', False)}")
        with open(self.notes_file, 'w') as f:
            json.dump(self.notes, f, indent=2)

    def load_state(self):
        """Load which notes were open"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                return {"open_notes": []}
        return {"open_notes": []}

    def save_state(self):
        """Save which notes are currently open"""
        state = {
            "open_notes": list(self.open_windows.keys())
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def load_positions(self):
        """Load saved note positions"""
        if self.positions_file.exists():
            try:
                with open(self.positions_file, 'r') as f:
                    positions = json.load(f)
                    print(f"[LOAD_POSITIONS] Loaded positions for: {list(positions.keys())}")
                    return positions
            except:
                print("[LOAD_POSITIONS] Failed to load positions")
                return {}
        print("[LOAD_POSITIONS] Positions file does not exist")
        return {}

    def save_positions(self):
        """Save note positions"""
        positions = self.load_positions()
        print(f"[SAVE_POSITIONS] Checking {len(self.open_windows)} open windows")
        for note_id, window in list(self.open_windows.items()):
            if note_id not in self.notes:
                continue
            is_new = self.notes[note_id].get("is_new", False)
            print(f"  - {note_id}: is_new={is_new}, exists={window.winfo_exists()}")
            if window.winfo_exists() and not is_new:
                positions[note_id] = {
                    "x": window.winfo_x(),
                    "y": window.winfo_y(),
                    "width": window.winfo_width(),
                    "height": window.winfo_height()
                }
                print(f"    -> SAVING position: {positions[note_id]}")
            else:
                print(f"    -> SKIPPING (is_new={is_new}, exists={window.winfo_exists()})")
        print(f"[SAVE_POSITIONS] Final saved positions: {list(positions.keys())}")
        with open(self.positions_file, 'w') as f:
            json.dump(positions, f, indent=2)

    def create_manager_window(self):
        """Create the sticky notes manager window"""
        self.manager = tk.Tk()
        if self.icon_ico_path.exists():
            self.manager.iconbitmap(self.icon_ico_path)
        self.manager.title("Doug's Sticky Notes Manager")
        self.manager.geometry("400x500")
        self.manager.configure(bg="#f0f0f0")
        
        # Center manager window on screen
        self.manager.update_idletasks()
        screen_width = self.manager.winfo_screenwidth()
        screen_height = self.manager.winfo_screenheight()
        x = (screen_width - 400) // 2
        y = (screen_height - 500) // 2
        self.manager.geometry(f"400x500+{x}+{y}")

        # Header
        header = tk.Frame(self.manager, bg="#333", height=60)
        header.pack(fill=tk.X)
        title = tk.Label(header, text="Doug's Sticky Notes", font=("Arial", 16, "bold"), bg="#333", fg="white")
        title.pack(pady=10)

        # Buttons frame
        btn_frame = tk.Frame(self.manager, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(btn_frame, text="+ New Note", command=self.create_new_note, bg="#4CAF50", fg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Delete Note", command=self.delete_selected_note_btn, bg="#f44336", fg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)

        # Search frame
        search_frame = tk.Frame(self.manager, bg="#f0f0f0")
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Label(search_frame, text="Search:", bg="#f0f0f0", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_search_change)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=("Arial", 10), relief=tk.FLAT, bd=1)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Notes list
        list_frame = tk.Frame(self.manager, bg="white")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.notes_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Arial", 10), height=15, selectmode=tk.EXTENDED)
        self.notes_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.notes_listbox.bind('<Double-Button-1>', self.on_note_double_click)
        self.notes_listbox.bind('<Button-3>', self.on_right_click)
        self.notes_listbox.bind('<Delete>', self.delete_selected_note)
        scrollbar.config(command=self.notes_listbox.yview)

        self.refresh_list()
        self.manager.protocol("WM_DELETE_WINDOW", self.on_manager_close)
        self.manager.bind("<Unmap>", self.on_minimize)
        self.manager.bind("<Control-Shift-N>", lambda e: self.create_new_note())

    def on_search_change(self, *args):
        """Handle search input changes"""
        self.search_query = self.search_var.get().lower()
        self.refresh_list()

    def create_tray_icon(self):
        """Create the system tray icon"""
        if hasattr(self, 'tray_thread') and self.tray_thread and self.tray_thread.is_alive():
            return

        icon_path = resource_path("icon.png")
        # Create a default icon if not found
        if not os.path.exists(icon_path):
            img = Image.new('RGB', (64, 64), color = 'black')
            d = ImageDraw.Draw(img)
            d.text((10,10), "SN", fill='white')
            img.save("icon.png")

        image = Image.open(icon_path)
        menu = (pystray.MenuItem('Show', self.show_window, default=True),
                pystray.MenuItem('Quit', self.quit_app))
        self.tray_icon = pystray.Icon("sticky_notes", image, "Sticky Notes", menu)
        
        # Run in a separate thread
        self.tray_thread = Thread(target=self.tray_icon.run)
        self.tray_thread.daemon = True
        self.tray_thread.start()

    def on_minimize(self, event):
        """Handle manager window minimization"""
        if self.manager.state() == 'iconic':
            self.hide_window()
            self.create_tray_icon()

    def hide_window(self):
        """Hide the main window"""
        self.manager.withdraw()

    def show_window(self):
        """Show the main window"""
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.stop()
            self.tray_thread = None
        self.manager.deiconify()

    def quit_app(self):
        """Quit the application"""
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.stop()
        self.on_manager_close()

    def refresh_list(self):
        """Refresh the notes list display"""
        self.notes_listbox.delete(0, tk.END)
        for note_id, note in sorted(self.notes.items(), key=lambda x: x[1].get("created", ""), reverse=True):
            title = note.get("title", "Note")
            content = note.get("content_text", note.get("content", ""))
            
            # Filter based on search query
            if self.search_query:
                if self.search_query not in title.lower() and self.search_query not in content.lower():
                    continue
            
            self.notes_listbox.insert(tk.END, title)
            self.notes_listbox.itemconfig(tk.END, {"bg": note.get("color", "#FFFF99")})

    def create_new_note(self):
        """Create a new sticky note"""
        note_id = str(int(datetime.now().timestamp() * 1000))
        print(f"[CREATE_NEW_NOTE] Creating note {note_id} with is_new=True")
        self.notes[note_id] = {
            "title": "Title",
            "content_text": "",
            "content_tags": [],
            "created": datetime.now().isoformat(),
            "color": "#FFFF99",
            "is_new": True,
            "pinned": False
        }
        self.save_notes()
        self.refresh_list()
        self.open_note(note_id)

    def on_note_double_click(self, event):
        """Handle double-click on note in list"""
        selection = self.notes_listbox.curselection()
        if selection:
            # Get the displayed items after filtering
            displayed_ids = []
            for note_id, note in sorted(self.notes.items(), key=lambda x: x[1].get("created", ""), reverse=True):
                title = note.get("title", "Note")
                content = note.get("content_text", note.get("content", ""))
                
                if self.search_query:
                    if self.search_query not in title.lower() and self.search_query not in content.lower():
                        continue
                
                displayed_ids.append(note_id)
            
            if selection[0] < len(displayed_ids):
                note_id = displayed_ids[selection[0]]
                self.open_note(note_id)

    def open_note(self, note_id, skip_save=False):
        """Open a note in a new window"""
        print(f"[OPEN_NOTE] Opening note {note_id} (skip_save={skip_save})")
        if note_id in self.open_windows and self.open_windows[note_id].winfo_exists():
            print(f"[OPEN_NOTE] Note already open, lifting window")
            self.open_windows[note_id].lift()
            return

        note = self.notes[note_id]
        print(f"[OPEN_NOTE] Note data: is_new={note.get('is_new', False)}")
        window = tk.Toplevel(self.manager)
        if self.icon_ico_path.exists():
            window.iconbitmap(self.icon_ico_path)
        window.title(note.get("title", "Note"))
        window.configure(bg=note.get("color", "#FFFF99"))
        
        # Check if we should restore position or set default
        positions = self.load_positions()
        print(f"[OPEN_NOTE] Positions available: {list(positions.keys())}")
        if note_id in positions:
            pos = positions[note_id]
            print(f"[OPEN_NOTE] RESTORING {note_id} to saved position: {pos}")
            window.geometry(f"{pos['width']}x{pos['height']}+{pos['x']}+{pos['y']}")
        else:
            # Set default size and center on manager
            print(f"[OPEN_NOTE] NO saved position for {note_id}, centering")
            self.manager.update_idletasks()
            manager_x = self.manager.winfo_x()
            manager_y = self.manager.winfo_y()
            manager_width = self.manager.winfo_width()
            manager_height = self.manager.winfo_height()
            x = manager_x + (manager_width - 200) // 2
            y = manager_y + (manager_height - 200) // 2
            print(f"[OPEN_NOTE] Centering at: {x}, {y}")
            window.geometry(f"270x270+{x}+{y}")
        
        # Mark as no longer new after opening
        print(f"[OPEN_NOTE] Setting is_new=False for {note_id}")
        self.notes[note_id]["is_new"] = False
        self.save_notes()
        
        window.update_idletasks()

        # Top controls
        control_frame = tk.Frame(window, bg=note.get("color", "#FFFF99"))
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Title Entry
        title_var = tk.StringVar(value=note.get("title", "Note"))
        title_entry = tk.Entry(control_frame, textvariable=title_var, font=("Arial", 10, "bold"), relief=tk.FLAT, bg=note.get("color", "#FFFF99"))
        title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # --- Pinning Logic ---
        is_pinned = [note.get("pinned", False)]  # Use list to be mutable in nested scope
        
        def toggle_pin():
            is_pinned[0] = not is_pinned[0]
            window.attributes("-topmost", is_pinned[0])
            pin_button.config(text="Unpin" if is_pinned[0] else "Pin")
            self.notes[note_id]["pinned"] = is_pinned[0]
            save_note()

        # Set initial state
        window.attributes("-topmost", is_pinned[0])

        pin_button = tk.Button(control_frame, text="Unpin" if is_pinned[0] else "Pin", command=toggle_pin, bg="#007bff", fg="white", font=("Arial", 8))
        pin_button.pack(side=tk.LEFT, padx=2)

        # Transparency control (blended into note)
        transparency_frame = tk.Frame(window, bg=note.get("color", "#FFFF99"), height=25)
        transparency_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        # Transparency slider that blends in
        current_alpha = note.get("transparency", 1.0)
        transparency_var = tk.DoubleVar(value=current_alpha)
        
        # Label with subtle styling
        transparency_label_min = tk.Label(transparency_frame, text="○", font=("Arial", 8), bg=note.get("color", "#FFFF99"), fg="#888")
        transparency_label_min.pack(side=tk.LEFT, padx=(0, 5))
        
        transparency_slider = tk.Scale(
            transparency_frame, 
            from_=0.3, 
            to=1.0, 
            resolution=0.05,
            orient=tk.HORIZONTAL,
            variable=transparency_var,
            showvalue=False,
            bg=note.get("color", "#FFFF99"),
            highlightthickness=0,
            borderwidth=0,
            troughcolor="#d3d3d3",  # Subtle trough
            sliderrelief=tk.FLAT,
            width=10,
            length=120
        )
        transparency_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        transparency_label_max = tk.Label(transparency_frame, text="●", font=("Arial", 8), bg=note.get("color", "#FFFF99"), fg="#888")
        transparency_label_max.pack(side=tk.LEFT, padx=(5, 0))
        
        def update_transparency(val):
            alpha = float(val)
            window.attributes("-alpha", alpha)
            self.notes[note_id]["transparency"] = alpha
            save_note()
        
        transparency_slider.config(command=update_transparency)
        window.attributes("-alpha", current_alpha)

        # Formatting Toolbar
        formatting_frame = tk.Frame(window, bg=note.get("color", "#FFFF99"))
        formatting_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        # Text Widget with Scrollbar
        text_frame = tk.Frame(window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        text_widget = tk.Text(text_frame, font=("Arial", 10), wrap=tk.WORD, bg=note.get("color", "#FFFF99"), relief=tk.FLAT, bd=0, undo=True)
        scrollbar = tk.Scrollbar(text_frame, command=text_widget.yview)
        text_widget.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def handle_paste(event):
            try:
                img = ImageGrab.grabclipboard()
                if isinstance(img, Image.Image):
                    image_id = f"{note_id}_{int(datetime.now().timestamp() * 1000)}.png"
                    image_path = self.images_dir / image_id
                    img.save(image_path)
                    
                    image_name = str(image_path)
                    photo = tk.PhotoImage(name=image_name, file=image_path)
                    
                    if not hasattr(text_widget, 'images'):
                        text_widget.images = []
                    text_widget.images.append(photo)

                    text_widget.image_create(tk.INSERT, image=photo)
                    
                    save_note()
                    return "break"
            except Exception as e:
                print(f"Paste error: {e}")
            return None

        text_widget.bind("<<Paste>>", handle_paste)

        # --- Font and Tag Configuration ---
        current_font_size = [10]  # Use list to allow modification in nested function
        fonts = {}
        
        def get_font_config(size, is_bold=False, is_italic=False, is_underline=False):
            key = (size, is_bold, is_italic, is_underline)
            if key not in fonts:
                f = font.Font(family="Arial", size=size)
                if is_bold: f.configure(weight="bold")
                if is_italic: f.configure(slant="italic")
                if is_underline: f.configure(underline=True)
                fonts[key] = f
            return fonts[key]

        def _apply_styles(sel_start, sel_end, is_bold, is_italic, is_underline, size):
            """A centralized function to apply a full set of styles to a selection."""
            # 1. Define a unique tag for this specific combination of styles
            combo_tag = f"style_{size}_{is_bold}_{is_italic}_{is_underline}"

            # 2. Configure the tag with the correct font if it doesn't exist yet
            if combo_tag not in text_widget.tag_names():
                combo_font = get_font_config(size, is_bold, is_italic, is_underline)
                text_widget.tag_configure(combo_tag, font=combo_font)

            # 3. Remove all other style tags from the selection
            for tag in text_widget.tag_names(sel_start):
                if tag.startswith("style_"):
                    text_widget.tag_remove(tag, sel_start, sel_end)
            
            # 4. Apply the new combination tag
            text_widget.tag_add(combo_tag, sel_start, sel_end)

        def _handle_style_change(toggle_style=None, size_change=0):
            try:
                sel_start = text_widget.index("sel.first")
                sel_end = text_widget.index("sel.last")
            except tk.TclError:
                return  # No selection

            # Get the style from the first character to use as a base
            tags_at_start = text_widget.tag_names(sel_start)
            
            # Defaults
            is_bold, is_italic, is_underline = False, False, False
            size = current_font_size[0]

            # Find the combined style tag and parse it
            for tag in tags_at_start:
                if tag.startswith("style_"):
                    parts = tag.split('_')
                    # style_{size}_{is_bold}_{is_italic}_{is_underline}
                    if len(parts) == 5:
                        size = int(parts[1])
                        is_bold = parts[2] == 'True'
                        is_italic = parts[3] == 'True'
                        is_underline = parts[4] == 'True'
                    break
            
            # Apply the requested change
            if toggle_style == "bold": is_bold = not is_bold
            if toggle_style == "italic": is_italic = not is_italic
            if toggle_style == "underline": is_underline = not is_underline
            
            new_size = max(8, min(size + size_change, 32))

            _apply_styles(sel_start, sel_end, is_bold, is_italic, is_underline, new_size)
            save_note()

        def toggle_style(style):
            _handle_style_change(toggle_style=style)

        def increase_font_size():
            _handle_style_change(size_change=1)

        def decrease_font_size():
            _handle_style_change(size_change=-1)


        tk.Button(formatting_frame, text="A↑", font=("Arial", 10, "bold"), command=increase_font_size, width=3).pack(side=tk.LEFT)
        tk.Button(formatting_frame, text="A↓", font=("Arial", 10, "bold"), command=decrease_font_size, width=3).pack(side=tk.LEFT)
        tk.Button(formatting_frame, text="B", font=("Arial", 10, "bold"), command=lambda: toggle_style("bold"), width=3).pack(side=tk.LEFT)
        tk.Button(formatting_frame, text="I", font=("Arial", 10, "italic"), command=lambda: toggle_style("italic"), width=3).pack(side=tk.LEFT)
        tk.Button(formatting_frame, text="U", font=("Arial", 10, "underline"), command=lambda: toggle_style("underline"), width=3).pack(side=tk.LEFT)

        def apply_color_to_widgets(color):
            window.configure(bg=color)
            text_widget.configure(bg=color)
            control_frame.configure(bg=color)
            title_entry.configure(bg=color)
            formatting_frame.configure(bg=color)
            transparency_frame.configure(bg=color)
            transparency_label_min.configure(bg=color)
            transparency_slider.configure(bg=color)
            transparency_label_max.configure(bg=color)

        tk.Button(control_frame, text="Color", command=lambda: self._show_color_chooser(window, [note_id], apply_color_to_widgets), bg="#666", fg="white", font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(control_frame, text="Delete", command=lambda: delete_note(note_id, window), bg="#f44336", fg="white", font=("Arial", 8)).pack(side=tk.LEFT, padx=2)

        # Load content
        if not hasattr(text_widget, 'images'):
            text_widget.images = []

        if "content_dump" in note:
            content_dump = note["content_dump"]
            for key, value, index in content_dump:
                if key == "text":
                    text_widget.insert(index, value)
                elif key == "tagon":
                    # Ensure tag is configured before applying
                    if value.startswith("style_"):
                        try:
                            parts = value.split('_')
                            if len(parts) == 5:
                                size = int(parts[1])
                                is_bold = parts[2] == 'True'
                                is_italic = parts[3] == 'True'
                                is_underline = parts[4] == 'True'
                                font_config = get_font_config(size, is_bold, is_italic, is_underline)
                                text_widget.tag_configure(value, font=font_config)
                        except Exception:
                            pass # Skip malformed tag
                    text_widget.tag_add(value, index)
                elif key == "tagoff":
                    text_widget.tag_remove(value, index)
                elif key == "image":
                    image_path = Path(value)
                    if image_path.exists():
                        try:
                            photo = tk.PhotoImage(name=value, file=image_path)
                            text_widget.images.append(photo)
                            text_widget.image_create(index, image=photo)
                        except Exception as e:
                            print(f"Failed to load image {image_path}: {e}")
                    else:
                        text_widget.insert(index, f"\n[Image not found: {value}]\n")
        else:
            # Legacy loading for old notes
            text_widget.insert("1.0", note.get("content_text", note.get("content", "")))
            tags = note.get("content_tags", [])
            for tag_info in tags:
                if len(tag_info) == 3:
                    tag_name, start, end = tag_info
                    if tag_name.startswith("style_"):
                        try:
                            parts = tag_name.split('_')
                            if len(parts) == 5:
                                size = int(parts[1])
                                is_bold = parts[2] == 'True'
                                is_italic = parts[3] == 'True'
                                is_underline = parts[4] == 'True'
                                font_config = get_font_config(size, is_bold, is_italic, is_underline)
                                text_widget.tag_configure(tag_name, font=font_config)
                        except Exception: continue
                    text_widget.tag_add(tag_name, start, end)

        # Save on any modification
        def save_note(*args):
            self.notes[note_id]["title"] = title_var.get()
            
            # Use dump to serialize content including images and formatting
            self.notes[note_id]["content_dump"] = text_widget.dump("1.0", tk.END, all=True)
            
            # Keep a plain text version for search
            self.notes[note_id]["content_text"] = text_widget.get("1.0", tk.END).strip()

            # Remove legacy fields
            self.notes[note_id].pop("content_tags", None)
            self.notes[note_id].pop("content", None) # Handle legacy notes

            window.title(title_var.get())
            self.save_notes()
            self.refresh_list()

        text_widget.bind("<KeyRelease>", save_note)
        title_entry.bind("<KeyRelease>", save_note)
        text_widget.bind("<Control-b>", lambda e: toggle_style("bold"))
        text_widget.bind("<Control-l>", lambda e: toggle_style("italic"))
        text_widget.bind("<Control-u>", lambda e: toggle_style("underline"))

        def delete_note(nid, win):
            if messagebox.askyesno("Delete", "Delete this note?"):
                del self.notes[nid]
                self.save_notes()
                self.refresh_list()
                win.destroy()
                if nid in self.open_windows:
                    del self.open_windows[nid]

        def on_close():
            # If note is deleted, don't save, just clean up
            if note_id in self.notes:
                save_note() # Save content and tags

                # Save the position of the window being closed
                positions = self.load_positions()
                positions[note_id] = {
                    "x": window.winfo_x(),
                    "y": window.winfo_y(),
                    "width": window.winfo_width(),
                    "height": window.winfo_height()
                }
                with open(self.positions_file, 'w') as f:
                    json.dump(positions, f, indent=2)

            if note_id in self.open_windows:
                del self.open_windows[note_id]
            self.save_state()
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", on_close)
        self.open_windows[note_id] = window
        print(f"[OPEN_NOTE] Window added to open_windows, total now: {len(self.open_windows)}")
        # Only save state, never save positions during note opening
        self.save_state()
        print(f"[OPEN_NOTE] Saved state only (skip_save={skip_save})")

    def restore_open_notes(self):
        """Restore previously open notes"""
        state = self.load_state()
        for note_id in state["open_notes"]:
            if note_id in self.notes:
                self.open_note(note_id)

    def delete_selected_note(self, event):
        """Delete selected note from list"""
        self.delete_selected_note_btn()

    def delete_selected_note_btn(self):
        """Delete button handler"""
        selection = self.notes_listbox.curselection()
        if not selection:
            messagebox.showwarning("Select Note", "Please select one or more notes to delete")
            return

        # Get the displayed items after filtering
        displayed_ids = []
        for note_id, note in sorted(self.notes.items(), key=lambda x: x[1].get("created", ""), reverse=True):
            title = note.get("title", "Note")
            content = note.get("content_text", note.get("content", ""))
            
            if self.search_query:
                if self.search_query not in title.lower() and self.search_query not in content.lower():
                    continue
            
            displayed_ids.append(note_id)
        
        note_ids_to_delete = [displayed_ids[i] for i in selection if i < len(displayed_ids)]

        if not note_ids_to_delete:
            return

        if messagebox.askyesno("Delete", f"Delete {len(note_ids_to_delete)} selected notes?"):
            for note_id in note_ids_to_delete:
                if note_id in self.notes:
                    del self.notes[note_id]
                if note_id in self.open_windows and self.open_windows[note_id].winfo_exists():
                    self.open_windows[note_id].destroy()
            self.save_notes()
            self.refresh_list()

    def close_selected_notes(self):
        """Close selected notes from the listbox."""
        selection = self.notes_listbox.curselection()
        if not selection:
            return

        displayed_ids = []
        for note_id, note in sorted(self.notes.items(), key=lambda x: x[1].get("created", ""), reverse=True):
            title = note.get("title", "Note")
            content = note.get("content_text", note.get("content", ""))
            if self.search_query:
                if self.search_query not in title.lower() and self.search_query not in content.lower():
                    continue
            displayed_ids.append(note_id)
        
        selected_note_ids = [displayed_ids[i] for i in selection if i < len(displayed_ids)]

        for note_id in selected_note_ids:
            if note_id in self.open_windows and self.open_windows[note_id].winfo_exists():
                # The on_close protocol will handle saving and cleanup
                self.open_windows[note_id].destroy()

    def on_right_click(self, event):
        """Handle right-click on note"""
        selection = self.notes_listbox.curselection()
        clicked_index = self.notes_listbox.nearest(event.y)

        # if right-clicking on an item not in the selection, change selection to that item
        if clicked_index not in selection:
            self.notes_listbox.selection_clear(0, tk.END)
            self.notes_listbox.selection_set(clicked_index)
            selection = (clicked_index,)

        if not selection:
            return

        # Get the displayed items after filtering
        displayed_ids = []
        for note_id, note in sorted(self.notes.items(), key=lambda x: x[1].get("created", ""), reverse=True):
            title = note.get("title", "Note")
            content = note.get("content_text", note.get("content", ""))
            
            if self.search_query:
                if self.search_query not in title.lower() and self.search_query not in content.lower():
                    continue
            
            displayed_ids.append(note_id)
        
        selected_note_ids = [displayed_ids[i] for i in selection if i < len(displayed_ids)]

        if not selected_note_ids:
            return

        menu = tk.Menu(self.notes_listbox, tearoff=0)
        delete_label = f"Delete {len(selected_note_ids)} Notes" if len(selected_note_ids) > 1 else "Delete Note"
        color_label = f"Change Color for {len(selected_note_ids)} Notes" if len(selected_note_ids) > 1 else "Change Color"
        
        open_notes_in_selection = [nid for nid in selected_note_ids if nid in self.open_windows and self.open_windows[nid].winfo_exists()]
        if open_notes_in_selection:
            close_label = f"Close {len(open_notes_in_selection)} Notes" if len(open_notes_in_selection) > 1 else "Close Note"
            menu.add_command(label=close_label, command=self.close_selected_notes)
            menu.add_separator()

        menu.add_command(label=delete_label, command=self.delete_selected_note_btn)
        menu.add_command(label=color_label, command=lambda: self._show_color_chooser(self.manager, selected_note_ids))
        menu.post(event.x_root, event.y_root)

    def on_manager_close(self):
        """Handle manager window close"""
        self.save_state()
        self.save_positions()
        self.manager.destroy()

    def _show_color_chooser(self, parent, note_ids, on_color_selected_callback=None):
        """Shows a color chooser dialog."""
        colors = {
            "Yellow": "#FFFF99", "Blue": "#99CCFF", "Green": "#99FF99",
            "Pink": "#FFB6C1", "Orange": "#FFCC99", "Purple": "#CC99FF",
            "Red": "#FF9999", "Cyan": "#99FFFF", "Lime": "#CCFF99",
            "Salmon": "#FFA07A", "Lavender": "#E6CCFF", "Peach": "#FFCCB3",
            "Mint": "#B3FFCC", "Sky": "#B3DDFF", "Gold": "#FFE699",
            "Rose": "#FFB3D9", "Teal": "#99CCCC", "Plum": "#DD99FF",
            "Coral": "#FF9999", "Khaki": "#FFFF99", "Apricot": "#FFCC99",
            "Powder Blue": "#B0E0E6", "Honeydew": "#F0FFF0", "Thistle": "#D8BFD8",
            "Wheat": "#F5DEB3", "Beige": "#F5F5DC", "Cornsilk": "#FFF8DC",
            "Linen": "#FAF0E6", "Misty Rose": "#FFE4E1", "Floral White": "#FFFAF0",
            "Seashell": "#FFF5EE", "Antique White": "#FAEBD7", "Cream": "#FFFDD0",
            "Light Yellow": "#FFFFE0", "Light Green": "#90EE90", "Light Blue": "#ADD8E6",
            "Light Pink": "#FFB6C1", "Light Gray": "#D3D3D3", "Dark Salmon": "#E9967A",
            "Light Salmon": "#FFA07A", "Light Sea Green": "#20B2AA"
        }
        color_window = tk.Toplevel(parent)
        color_window.title("Choose Color")
        color_window.geometry("200x250")

        frame = tk.Frame(color_window)
        frame.pack(fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(frame, yscrollcommand=scrollbar.set, highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        button_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=button_frame, anchor="nw")


        def apply_color(color):
            note_id_list = note_ids if isinstance(note_ids, list) else [note_ids]
            for note_id in note_id_list:
                self.notes[note_id]["color"] = color
                
                # If a single callback is provided, it's for a single open note window
                if on_color_selected_callback and len(note_id_list) == 1:
                    on_color_selected_callback(color)
                
                # If the note window is open, update its colors too
                if note_id in self.open_windows:
                    open_window = self.open_windows[note_id]
                    # Only update specific widgets, not all buttons
                    for widget in open_window.winfo_children():
                        if isinstance(widget, tk.Frame):
                            widget.configure(bg=color)
                            for sub_widget in widget.winfo_children():
                                # Skip Color, Delete, and formatting buttons
                                if isinstance(sub_widget, tk.Button):
                                    button_text = sub_widget.cget("text")
                                    if button_text not in ["Color", "Delete", "B", "I", "U", "Pin", "Unpin"] and not button_text.startswith("A"):
                                        sub_widget.configure(bg=color)
                                elif isinstance(sub_widget, (tk.Entry, tk.Label, tk.Scale)):
                                    sub_widget.configure(bg=color)
                        elif isinstance(widget, tk.Text):
                            widget.configure(bg=color)
                    open_window.configure(bg=color)

            self.save_notes()
            self.refresh_list()
            color_window.destroy()

        for name, code in colors.items():
            btn = tk.Button(button_frame, text=name, bg=code, command=lambda c=code: apply_color(c), width=20)
            btn.pack(fill=tk.X, padx=5, pady=2)
        
        button_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

if __name__ == "__main__":
    app = StickyNotesApp()
    app.manager.mainloop()