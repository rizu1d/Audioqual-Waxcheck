"""Metadata editor window (iTunes-style)."""

import os
from pathlib import Path
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from mutagen import File as MutagenFile
from mutagen.id3 import (
    ID3, TIT2, TPE1, TALB, TCON, TDRC, TRCK, TPOS, TBPM, COMM, ID3NoHeaderError,
)
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.wave import WAVE
from mutagen.aiff import AIFF

from ..utils.constants import THEME_COLORS, FONT_FAMILY, FONT_SIZES
from ..utils.settings import AppSettings

# Common music genres for the combobox dropdown
GENRES = [
    "", "Alternative", "Blues", "Classical", "Country", "Dance",
    "Disco", "Drum & Bass", "Dubstep", "Electronic", "Folk",
    "Funk", "Gospel", "Hip-Hop", "House", "Indie", "Jazz",
    "Latin", "Lo-Fi", "Metal", "New Age", "Opera", "Pop",
    "Punk", "R&B", "Rap", "Reggae", "Reggaeton", "Rock",
    "Soul", "Soundtrack", "Techno", "Trance", "Trip-Hop", "World",
]

# ID3 tag mapping for MP3/AIFF/WAV
ID3_TAG_MAP = {
    "title": "TIT2",
    "artist": "TPE1",
    "album": "TALB",
    "genre": "TCON",
    "year": "TDRC",
    "track_num": "TRCK",
    "disc_num": "TPOS",
    "bpm": "TBPM",
}

# Vorbis comment mapping for FLAC
VORBIS_TAG_MAP = {
    "title": "title",
    "artist": "artist",
    "album": "album",
    "genre": "genre",
    "year": "date",
    "track_num": "tracknumber",
    "track_total": "tracktotal",
    "disc_num": "discnumber",
    "disc_total": "disctotal",
    "compilation": "compilation",
    "bpm": "bpm",
    "comments": "comment",
}


class MetadataEditor(ctk.CTkToplevel):
    """Modal window for editing audio file metadata tags."""

    def __init__(
        self,
        master,
        filepath: str,
        on_save: Optional[Callable[[str, Optional[str]], None]] = None,
    ):
        super().__init__(master)

        self._filepath = filepath
        self._on_save = on_save
        self._format_type: Optional[str] = None  # "id3", "vorbis", or None
        self._fields: Dict[str, ctk.CTkEntry] = {}
        self._genre_combo: Optional[ctk.CTkComboBox] = None
        self._compilation_var = ctk.StringVar(value="0")
        self._comments_textbox: Optional[ctk.CTkTextbox] = None
        self._supported = True

        self._detect_format()
        self._setup_window()
        self._setup_ui()
        self._read_metadata()

        # Make modal
        self.grab_set()
        self.focus_force()
        self.bind("<Escape>", lambda e: self._cancel())

    def _detect_format(self):
        """Detect file format and determine tag type."""
        ext = Path(self._filepath).suffix.lower()
        if ext in (".mp3",):
            self._format_type = "id3"
        elif ext in (".flac",):
            self._format_type = "vorbis"
        elif ext in (".aiff", ".aif"):
            self._format_type = "id3"
        elif ext in (".wav",):
            self._format_type = "id3"
        else:
            # OGG, M4A, etc. — not supported for editing
            self._format_type = None
            self._supported = False

    def _setup_window(self):
        """Configure window size, position, and appearance."""
        w, h = 500, 580
        self.geometry(f"{w}x{h}")
        self.resizable(False, False)
        self.title("Editar metadatos")
        self.configure(fg_color=THEME_COLORS["bg_primary"])

        # Center over parent
        self.update_idletasks()
        parent = self.master
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _setup_ui(self):
        """Build the form layout."""
        # Header
        self._setup_header()

        # Separator
        sep = ctk.CTkFrame(self, height=1, fg_color=THEME_COLORS["primary_dark"])
        sep.pack(fill="x", padx=20, pady=(0, 12))

        # Form fields
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=28, pady=(0, 8))

        if not self._supported:
            unsupported_label = ctk.CTkLabel(
                form,
                text="Este formato no soporta edición de metadatos.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
                text_color=THEME_COLORS["text_secondary"],
            )
            unsupported_label.pack(pady=40)
        else:
            self._setup_fields(form)

        # Buttons
        self._setup_buttons()

    def _setup_header(self):
        """Create header with filename and format info."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))

        filename = Path(self._filepath).name
        ext = Path(self._filepath).suffix.upper().lstrip(".")

        # Get bitrate info
        bitrate_str = ""
        try:
            audio = MutagenFile(self._filepath)
            if audio and hasattr(audio, "info") and hasattr(audio.info, "bitrate"):
                br = audio.info.bitrate
                if br:
                    bitrate_str = f" - {br // 1000} kbps"
        except Exception:
            pass

        ctk.CTkLabel(
            header,
            text=filename,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["heading"], weight="bold"),
            text_color=THEME_COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            header,
            text=f"{ext}{bitrate_str}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

    def _setup_fields(self, parent):
        """Create the form fields."""
        # Helper to create a labeled row
        def make_row(label_text: str, row_idx: int) -> ctk.CTkFrame:
            row = ctk.CTkFrame(parent, fg_color="transparent", height=36)
            row.pack(fill="x", pady=(0, 6))
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row,
                text=label_text,
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
                text_color=THEME_COLORS["text_secondary"],
                anchor="e",
                width=100,
            ).grid(row=0, column=0, sticky="e", padx=(0, 12))
            return row

        entry_kwargs = dict(
            fg_color=THEME_COLORS["bg_elevated"],
            border_color=THEME_COLORS["primary_dark"],
            border_width=1,
            text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            height=32,
        )

        # 1. Título
        row = make_row("título", 0)
        e = ctk.CTkEntry(row, **entry_kwargs)
        e.grid(row=0, column=1, sticky="ew")
        self._fields["title"] = e

        # 2. Artista
        row = make_row("artista", 1)
        e = ctk.CTkEntry(row, **entry_kwargs)
        e.grid(row=0, column=1, sticky="ew")
        self._fields["artist"] = e

        # 3. Álbum
        row = make_row("álbum", 2)
        e = ctk.CTkEntry(row, **entry_kwargs)
        e.grid(row=0, column=1, sticky="ew")
        self._fields["album"] = e

        # 4. Género (ComboBox)
        row = make_row("género", 3)
        self._genre_combo = ctk.CTkComboBox(
            row,
            values=GENRES,
            fg_color=THEME_COLORS["bg_elevated"],
            border_color=THEME_COLORS["primary_dark"],
            border_width=1,
            text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            button_color=THEME_COLORS["primary_dark"],
            button_hover_color=THEME_COLORS["primary"],
            dropdown_fg_color=THEME_COLORS["bg_elevated"],
            dropdown_text_color=THEME_COLORS["text_primary"],
            dropdown_hover_color=THEME_COLORS["primary_dark"],
            height=32,
        )
        self._genre_combo.grid(row=0, column=1, sticky="ew")
        self._genre_combo.set("")

        # 5. Año
        row = make_row("año", 4)
        e = ctk.CTkEntry(row, width=80, **entry_kwargs)
        e.grid(row=0, column=1, sticky="w")
        self._fields["year"] = e

        # 6. Pista (__) de (____)
        row = make_row("pista", 5)
        track_frame = ctk.CTkFrame(row, fg_color="transparent")
        track_frame.grid(row=0, column=1, sticky="w")

        e_num = ctk.CTkEntry(track_frame, width=55, **entry_kwargs)
        e_num.pack(side="left")
        self._fields["track_num"] = e_num

        ctk.CTkLabel(
            track_frame,
            text="de",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_secondary"],
        ).pack(side="left", padx=6)

        e_total = ctk.CTkEntry(track_frame, width=55, **entry_kwargs)
        e_total.pack(side="left")
        self._fields["track_total"] = e_total

        # 7. Nº de disco (__) de (____)
        row = make_row("nº de disco", 6)
        disc_frame = ctk.CTkFrame(row, fg_color="transparent")
        disc_frame.grid(row=0, column=1, sticky="w")

        e_num = ctk.CTkEntry(disc_frame, width=55, **entry_kwargs)
        e_num.pack(side="left")
        self._fields["disc_num"] = e_num

        ctk.CTkLabel(
            disc_frame,
            text="de",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_secondary"],
        ).pack(side="left", padx=6)

        e_total = ctk.CTkEntry(disc_frame, width=55, **entry_kwargs)
        e_total.pack(side="left")
        self._fields["disc_total"] = e_total

        # 8. Recopilación (checkbox)
        row = make_row("recopilación", 7)
        cb = ctk.CTkCheckBox(
            row,
            text="Es una recopilación de varios artistas",
            variable=self._compilation_var,
            onvalue="1",
            offvalue="0",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_secondary"],
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
            border_color=THEME_COLORS["primary_dark"],
            checkmark_color=THEME_COLORS["text_primary"],
        )
        cb.grid(row=0, column=1, sticky="w")
        self._fields["compilation"] = cb

        # 9. BPM
        row = make_row("bpm", 8)
        e = ctk.CTkEntry(row, width=80, **entry_kwargs)
        e.grid(row=0, column=1, sticky="w")
        self._fields["bpm"] = e

        # 10. Comentarios (multiline textbox)
        row = make_row("comentarios", 9)
        self._comments_textbox = ctk.CTkTextbox(
            row,
            fg_color=THEME_COLORS["bg_elevated"],
            border_color=THEME_COLORS["primary_dark"],
            border_width=1,
            text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            height=72,
        )
        self._comments_textbox.grid(row=0, column=1, sticky="ew")

    def _setup_buttons(self):
        """Create Cancel and Save buttons."""
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=28, pady=(4, 20))

        # Right-align buttons
        btn_frame.grid_columnconfigure(0, weight=1)

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancelar",
            command=self._cancel,
            width=100,
            height=36,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=THEME_COLORS["primary_dark"],
            text_color=THEME_COLORS["text_primary"],
            hover_color=THEME_COLORS["bg_elevated"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
        )
        cancel_btn.grid(row=0, column=1, padx=(0, 8))

        save_btn = ctk.CTkButton(
            btn_frame,
            text="Guardar",
            command=self._save_metadata,
            width=100,
            height=36,
            corner_radius=8,
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
            text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"], weight="bold"),
            state="normal" if self._supported else "disabled",
        )
        save_btn.grid(row=0, column=2)

    # ─── Read Metadata ──────────────────────────────────────────────

    def _read_metadata(self):
        """Read metadata from file and populate form fields."""
        if not self._supported:
            return

        try:
            if self._format_type == "id3":
                self._read_id3()
            elif self._format_type == "vorbis":
                self._read_vorbis()
        except Exception:
            pass

    def _read_id3(self):
        """Read ID3 tags (MP3, AIFF, WAV)."""
        try:
            audio = MutagenFile(self._filepath)
            if audio is None:
                return
            tags = audio.tags
            if tags is None:
                return
        except Exception:
            return

        def get_text(frame_id: str) -> str:
            frame = tags.get(frame_id)
            if frame:
                return str(frame.text[0]) if frame.text else ""
            return ""

        self._set_field("title", get_text("TIT2"))
        self._set_field("artist", get_text("TPE1"))
        self._set_field("album", get_text("TALB"))

        # Genre
        genre = get_text("TCON")
        if self._genre_combo:
            self._genre_combo.set(genre)

        self._set_field("year", get_text("TDRC"))

        # Track: "num/total" format
        track_str = get_text("TRCK")
        if "/" in track_str:
            parts = track_str.split("/", 1)
            self._set_field("track_num", parts[0])
            self._set_field("track_total", parts[1])
        else:
            self._set_field("track_num", track_str)

        # Disc: "num/total" format
        disc_str = get_text("TPOS")
        if "/" in disc_str:
            parts = disc_str.split("/", 1)
            self._set_field("disc_num", parts[0])
            self._set_field("disc_total", parts[1])
        else:
            self._set_field("disc_num", disc_str)

        # Compilation (TCMP is an iTunes extension, stored as text "1"/"0")
        tcmp = tags.get("TCMP")
        if tcmp and tcmp.text:
            self._compilation_var.set("1" if str(tcmp.text[0]) == "1" else "0")

        self._set_field("bpm", get_text("TBPM"))

        # Comments — ID3 COMM has language + description keys
        for key in tags:
            if key.startswith("COMM"):
                frame = tags[key]
                if hasattr(frame, "text"):
                    text = str(frame.text[0]) if frame.text else ""
                elif hasattr(frame, "description"):
                    text = str(frame)
                else:
                    text = ""
                if text and self._comments_textbox:
                    self._comments_textbox.insert("1.0", text)
                break

    def _read_vorbis(self):
        """Read Vorbis comments (FLAC)."""
        try:
            audio = FLAC(self._filepath)
        except Exception:
            return

        def get_tag(key: str) -> str:
            vals = audio.get(key, [])
            return vals[0] if vals else ""

        self._set_field("title", get_tag("title"))
        self._set_field("artist", get_tag("artist"))
        self._set_field("album", get_tag("album"))

        genre = get_tag("genre")
        if self._genre_combo:
            self._genre_combo.set(genre)

        self._set_field("year", get_tag("date"))
        self._set_field("track_num", get_tag("tracknumber"))
        self._set_field("track_total", get_tag("tracktotal"))
        self._set_field("disc_num", get_tag("discnumber"))
        self._set_field("disc_total", get_tag("disctotal"))

        comp = get_tag("compilation")
        self._compilation_var.set("1" if comp == "1" else "0")

        self._set_field("bpm", get_tag("bpm"))

        comment = get_tag("comment")
        if comment and self._comments_textbox:
            self._comments_textbox.insert("1.0", comment)

    def _set_field(self, field_id: str, value: str):
        """Set a field value, handling both Entry and CheckBox widgets."""
        widget = self._fields.get(field_id)
        if widget is None:
            return
        if isinstance(widget, ctk.CTkEntry):
            widget.delete(0, "end")
            widget.insert(0, value)
        elif isinstance(widget, ctk.CTkCheckBox):
            self._compilation_var.set(value if value in ("0", "1") else "0")

    def _get_field(self, field_id: str) -> str:
        """Get a field value."""
        widget = self._fields.get(field_id)
        if widget is None:
            return ""
        if isinstance(widget, ctk.CTkEntry):
            return widget.get().strip()
        if isinstance(widget, ctk.CTkCheckBox):
            return self._compilation_var.get()
        return ""

    # ─── Save Metadata ──────────────────────────────────────────────

    def _save_metadata(self):
        """Write metadata to file, optionally rename."""
        if not self._supported:
            return

        try:
            if self._format_type == "id3":
                self._save_id3()
            elif self._format_type == "vorbis":
                self._save_vorbis()
        except Exception as e:
            self._show_error(str(e))
            return

        # Rename file if setting is enabled
        old_filepath = self._filepath
        new_filepath = None
        settings = AppSettings()
        if settings.rename_on_save:
            new_filepath = self._try_rename()

        if self._on_save:
            self._on_save(old_filepath, new_filepath)

        self.destroy()

    def _try_rename(self) -> Optional[str]:
        """Attempt to rename the file to 'Artist - Title.ext'.

        Returns the new filepath if renamed, None otherwise.
        """
        artist = self._get_field("artist")
        title = self._get_field("title")

        if not artist or not title:
            self._show_warning(
                "No se pudo renombrar: faltan artista o título."
            )
            return None

        ext = Path(self._filepath).suffix
        sanitized = self._sanitize_filename(f"{artist} - {title}")
        new_name = f"{sanitized}{ext}"
        parent_dir = Path(self._filepath).parent
        new_path = parent_dir / new_name

        # Don't rename if name is the same
        if new_path == Path(self._filepath):
            return None

        # Don't overwrite an existing different file
        if new_path.exists():
            self._show_warning(
                f"No se pudo renombrar: ya existe un archivo\n\"{new_name}\"."
            )
            return None

        try:
            os.rename(self._filepath, str(new_path))
            self._filepath = str(new_path)
            return str(new_path)
        except OSError as e:
            self._show_warning(f"Error al renombrar: {e}")
            return None

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Remove characters not allowed in filenames."""
        forbidden = r'/\:*?"<>|'
        for ch in forbidden:
            name = name.replace(ch, "")
        # Collapse multiple spaces and strip
        return " ".join(name.split()).strip()

    def _save_id3(self):
        """Write ID3 tags (MP3, AIFF, WAV)."""
        audio = MutagenFile(self._filepath)
        if audio is None:
            raise RuntimeError("No se pudo abrir el archivo")

        # Ensure tags exist
        if audio.tags is None:
            audio.add_tags()
        tags = audio.tags

        title = self._get_field("title")
        if title:
            tags["TIT2"] = TIT2(encoding=3, text=[title])
        elif "TIT2" in tags:
            del tags["TIT2"]

        artist = self._get_field("artist")
        if artist:
            tags["TPE1"] = TPE1(encoding=3, text=[artist])
        elif "TPE1" in tags:
            del tags["TPE1"]

        album = self._get_field("album")
        if album:
            tags["TALB"] = TALB(encoding=3, text=[album])
        elif "TALB" in tags:
            del tags["TALB"]

        genre = self._genre_combo.get().strip() if self._genre_combo else ""
        if genre:
            tags["TCON"] = TCON(encoding=3, text=[genre])
        elif "TCON" in tags:
            del tags["TCON"]

        year = self._get_field("year")
        if year:
            tags["TDRC"] = TDRC(encoding=3, text=[year])
        elif "TDRC" in tags:
            del tags["TDRC"]

        # Track: combine num/total
        track_num = self._get_field("track_num")
        track_total = self._get_field("track_total")
        if track_num:
            track_str = f"{track_num}/{track_total}" if track_total else track_num
            tags["TRCK"] = TRCK(encoding=3, text=[track_str])
        elif "TRCK" in tags:
            del tags["TRCK"]

        # Disc: combine num/total
        disc_num = self._get_field("disc_num")
        disc_total = self._get_field("disc_total")
        if disc_num:
            disc_str = f"{disc_num}/{disc_total}" if disc_total else disc_num
            tags["TPOS"] = TPOS(encoding=3, text=[disc_str])
        elif "TPOS" in tags:
            del tags["TPOS"]

        # Compilation (iTunes TCMP)
        from mutagen.id3 import TCMP
        comp = self._compilation_var.get()
        if comp == "1":
            tags["TCMP"] = TCMP(encoding=3, text=["1"])
        elif "TCMP" in tags:
            del tags["TCMP"]

        bpm = self._get_field("bpm")
        if bpm:
            tags["TBPM"] = TBPM(encoding=3, text=[bpm])
        elif "TBPM" in tags:
            del tags["TBPM"]

        # Comments
        comments = self._comments_textbox.get("1.0", "end-1c").strip() if self._comments_textbox else ""
        # Remove existing COMM frames
        comm_keys = [k for k in tags if k.startswith("COMM")]
        for k in comm_keys:
            del tags[k]
        if comments:
            tags["COMM::eng"] = COMM(encoding=3, lang="eng", desc="", text=[comments])

        audio.save()

    def _save_vorbis(self):
        """Write Vorbis comments (FLAC)."""
        audio = FLAC(self._filepath)

        def set_tag(key: str, value: str):
            if value:
                audio[key] = [value]
            elif key in audio:
                del audio[key]

        set_tag("title", self._get_field("title"))
        set_tag("artist", self._get_field("artist"))
        set_tag("album", self._get_field("album"))
        set_tag("genre", self._genre_combo.get().strip() if self._genre_combo else "")
        set_tag("date", self._get_field("year"))
        set_tag("tracknumber", self._get_field("track_num"))
        set_tag("tracktotal", self._get_field("track_total"))
        set_tag("discnumber", self._get_field("disc_num"))
        set_tag("disctotal", self._get_field("disc_total"))
        set_tag("compilation", self._compilation_var.get() if self._compilation_var.get() == "1" else "")
        set_tag("bpm", self._get_field("bpm"))

        comments = self._comments_textbox.get("1.0", "end-1c").strip() if self._comments_textbox else ""
        set_tag("comment", comments)

        audio.save()

    # ─── UI Helpers ─────────────────────────────────────────────────

    def _show_error(self, message: str):
        """Show an error message in a simple dialog."""
        error_win = ctk.CTkToplevel(self)
        error_win.title("Error")
        error_win.geometry("350x120")
        error_win.resizable(False, False)
        error_win.configure(fg_color=THEME_COLORS["bg_primary"])
        error_win.grab_set()

        ctk.CTkLabel(
            error_win,
            text=f"Error al guardar:\n{message}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=THEME_COLORS["text_primary"],
            wraplength=300,
        ).pack(pady=(16, 8), padx=16)

        ctk.CTkButton(
            error_win,
            text="Aceptar",
            command=error_win.destroy,
            width=80,
            height=32,
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
        ).pack()

    def _show_warning(self, message: str):
        """Show a warning message (non-blocking, auto-closes parent won't wait)."""
        warn_win = ctk.CTkToplevel(self.master)
        warn_win.title("Aviso")
        warn_win.geometry("380x120")
        warn_win.resizable(False, False)
        warn_win.configure(fg_color=THEME_COLORS["bg_primary"])
        warn_win.grab_set()

        ctk.CTkLabel(
            warn_win,
            text=message,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=THEME_COLORS["text_primary"],
            wraplength=340,
        ).pack(pady=(16, 8), padx=16)

        ctk.CTkButton(
            warn_win,
            text="Aceptar",
            command=warn_win.destroy,
            width=80,
            height=32,
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
        ).pack()

    def _cancel(self):
        """Close without saving."""
        self.destroy()
