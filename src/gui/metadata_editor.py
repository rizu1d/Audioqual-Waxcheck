"""Metadata editor window (iTunes-style)."""

import datetime
import io
import os
from pathlib import Path
from tkinter import filedialog
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

import customtkinter as ctk
from PIL import Image

from mutagen import File as MutagenFile
from mutagen.id3 import (
    ID3, TIT2, TPE1, TALB, TCON, TDRC, TRCK, TPOS, TBPM, COMM, APIC, ID3NoHeaderError,
)
from mutagen.mp3 import MP3
from mutagen.flac import FLAC, Picture
from mutagen.wave import WAVE
from mutagen.aiff import AIFF

from ..utils.constants import (
    THEME_COLORS, FONT_FAMILY, FONT_FAMILY_MONO, FONT_SIZES,
    QUALITY_LEVELS, STATUS_TRANSCODE, STATUS_LOSSLESS, get_quality_level,
)
from ..utils.file_utils import format_duration
from ..utils.settings import AppSettings

if TYPE_CHECKING:
    from ..core.analyzer import AnalysisResult

# Common music genres for the combobox dropdown
# Electronic subgenres sourced from https://en.wikipedia.org/wiki/List_of_electronic_music_genres
GENRES = [
    "",
    "2-step garage", "Acid breaks", "Acid house", "Acid techno", "Acid trance",
    "Afro house", "Afro tech", "Afro trap", "Afrobeats", "Afroswing",
    "Aggrotech", "Algorave", "Alternative", "Alternative dance", "Alternative hip-hop",
    "Alternative R&B", "Amapiano", "Ambient", "Ambient dub", "Ambient house",
    "Ambient industrial", "Ambient techno", "Asian Underground",
    "Atmospheric drum and bass", "Azonto",
    "Baggy", "Balearic beat", "Balearic trance", "Ballroom", "Baltimore club",
    "Bass house", "Bassline", "Berlin School", "Big beat", "Big room house",
    "Birmingham sound", "Bitpop", "Black MIDI", "Bleep techno", "Blog house",
    "Blues", "Boogie", "Bouncy techno", "Brazilian bass", "Brazilian phonk",
    "Breakbeat", "Breakbeat hardcore", "Breakcore", "Breakstep", "Broken beat",
    "Brooklyn drill", "Brostep", "Budots",
    "Changa tuki", "Chicago hard house", "Chicago house", "Chill-out", "Chillwave",
    "Chiptune", "Chopped and screwed", "City pop", "Classical", "Cloud rap",
    "Cold wave", "Complextro", "Contemporary R&B", "Country", "Coupé-décalé",
    "Crunk", "Crunkcore", "Cyber metal",
    "Dance", "Dance-pop", "Dance-punk", "Dance-rock", "Dancehall pop",
    "Dark ambient", "Dark electro", "Dark psytrance", "Dark wave",
    "Darkcore", "Darkstep", "Darksynth", "Death industrial", "Deconstructed club",
    "Deep house", "Detroit techno", "Digital hardcore", "Disco", "Disco edits",
    "Disco house", "Disco polo", "Diva house", "Downtempo", "Dream trance",
    "Dreampunk", "Drift phonk", "Drill", "Drill 'n' bass", "Drone",
    "Drum & Bass", "Drumfunk", "Drumstep", "Dub", "Dub poetry", "Dub techno",
    "Dubstep", "Dubstyle", "Dungeon synth", "Dutch house",
    "Early hardcore", "Electro", "Electro hop", "Electro house", "Electro swing",
    "Electro-disco", "Electro-industrial", "Electroacoustic improvisation",
    "Electroclash", "Electrogrind", "Electronic", "Electropop", "Emo rap",
    "Ethereal wave", "Euphoric frenchcore", "Euphoric hardstyle", "Eurobeat",
    "Eurodance", "Eurodisco", "Eurohouse", "Eurotrance", "Extratone",
    "Fidget house", "Flashcore", "Florida breaks", "FM synthesis", "Folk",
    "Folktronica", "Footwork", "Free tekno", "Freestyle", "French house",
    "Frenchcore", "Full-on", "Funk", "Funk carioca", "Funk melody",
    "Funk ostentação", "Funkstep", "Funktronica", "Funky house",
    "Future bass", "Future funk", "Future garage", "Future house", "Future rave",
    "Futurepop",
    "Gabber", "Garage house", "Ghetto house", "Ghettotech", "Glitch",
    "Glitch hop", "Goa trance", "Gospel", "Gqom", "Grime", "Grindie",
    "Guaracha",
    "Hands up", "Happy hardcore", "Hard dance", "Hard NRG", "Hard techno",
    "Hard trance", "Hardbag", "Hardbass", "Hardcore", "Hardcore breaks",
    "Hardstep", "Hardstyle", "Hardvapour", "Hardwave", "Harsh noise",
    "Harsh noise wall", "Hauntology", "Hi-NRG", "Hip house", "Hip-Hop",
    "Hipster hop", "House", "Hyperpop", "Hypnagogic pop",
    "Illbient", "Indie", "Indietronica", "Industrial", "Industrial hardcore",
    "Industrial hip-hop", "Industrial metal", "Industrial rock", "Industrial techno",
    "Instrumental hip-hop", "Intelligent drum and bass", "Isolationism",
    "Italo dance", "Italo disco", "Italo house",
    "J-core", "Jackin house", "Japanoise", "Jazz", "Jazz house", "Jazzstep",
    "Jerk", "Jersey club", "Juke house", "Jump-up", "Jumpstyle", "Jungle",
    "Jungle terror", "Jungletek",
    "Kawaii future bass", "Kidandali", "Kosmische musik", "Krautrock", "Kuduro",
    "Kwaito",
    "Laptronica", "Latin", "Latin house", "Latin trap", "Lento violento",
    "Liquid funk", "Lo-Fi", "Lo-fi house", "Lofi hip-hop", "Lowercase",
    "Mahraganat", "Mainstream hardcore", "Mallsoft", "Manila sound",
    "Martial industrial", "Melbourne bounce", "Melodic house", "Merenhouse",
    "Metal", "Miami bass", "Microhouse", "Microsound", "Midtempo bass",
    "Minimal psytrance", "Minimal techno", "Minimal wave", "Moombahcore",
    "Moombahsoul", "Moombahton", "Mumble rap", "Musique concrète", "Mákina",
    "Neo soul", "Neoclassical dark wave", "Neoclassical new-age",
    "Neue Deutsche Härte", "Neue Deutsche Todeskunst", "Neue Deutsche Welle",
    "Neurofunk", "New Age", "New beat", "New jack swing", "New Jersey sound",
    "New rave", "New romantic", "New wave", "Nightcore", "Nintendocore",
    "Nitzhonot", "Nortec", "Nu jazz", "Nu skool breaks", "Nu-disco", "Nu-gaze",
    "Nueva Iberica",
    "Onkyokei", "Opera", "Outsider house",
    "Philly club", "Phonk", "Plugg", "Plunderphonics", "Pop", "Pop kreatif",
    "Post-disco", "Post-dubstep", "Post-Industrial", "Post-rock", "Power noise",
    "Progressive breaks", "Progressive house", "Progressive psytrance",
    "Progressive trance", "Proibidão", "Psybient", "Psychedelic trance", "Psydub",
    "Pumping house", "Punk",
    "R&B", "Rabòday", "Ragga jungle", "Raggacore", "Raggatek", "Rap",
    "Rara tech", "Rasteirinha", "Rawstyle", "Reductionism", "Reggae",
    "Reggaestep", "Reggaeton", "Riddim", "Rock",
    "Sambass", "Sampledelia", "Schaffel", "Scouse house", "Shamstep",
    "Shangaan electro", "Skweee", "Slap house", "Sophisti-pop", "Soul",
    "Soulful house", "Soundscape", "Soundtrack", "Sovietwave", "Space disco",
    "Space rock", "Spacesynth", "Speed garage", "Speedcore", "Splittercore",
    "Stadium house", "Suomisaundi", "Synth-funk", "Synth-metal", "Synth-pop",
    "Synth-punk", "Synthwave",
    "Tech house", "Tech trance", "Techno", "Techstep", "Tecno brega",
    "Tecnocumbia", "Toytown techno", "Trance", "Trap", "Trap (EDM)", "Trapstyle",
    "Tribal guarachero", "Tribal house", "Trip rock", "Trip-Hop",
    "Tropical house", "Trouse",
    "UK bass", "UK drill", "UK funky", "UK garage", "UK hard house",
    "UK hardcore", "UK trap", "Uplifting trance",
    "Vaporwave", "Vocal trance",
    "Wave", "Weird SoundCloud", "Witch house", "Wonky", "Wonky pop", "World",
    "Worldbeat",
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
        analysis_result: "Optional[AnalysisResult]" = None,
        on_navigate: Optional[Callable[[int], "Optional[AnalysisResult]"]] = None,
    ):
        super().__init__(master)
        self.withdraw()  # Hide until positioned

        self._filepath = filepath
        self._on_save = on_save
        self._analysis_result = analysis_result
        self._on_navigate = on_navigate  # callback(direction) -> AnalysisResult or None
        self._format_type: Optional[str] = None  # "id3", "vorbis", or None
        self._fields: Dict[str, ctk.CTkEntry] = {}
        self._genre_combo: Optional[ctk.CTkComboBox] = None
        self._compilation_var = ctk.StringVar(value="0")
        self._comments_textbox: Optional[ctk.CTkTextbox] = None
        self._supported = True

        # Tab system
        self._current_tab: str = "detalles"
        self._detalles_tab_btn: Optional[ctk.CTkButton] = None
        self._ilustracion_tab_btn: Optional[ctk.CTkButton] = None
        self._archivo_tab_btn: Optional[ctk.CTkButton] = None
        self._content_frame: Optional[ctk.CTkFrame] = None
        self._detalles_content: Optional[ctk.CTkFrame] = None
        self._ilustracion_content: Optional[ctk.CTkFrame] = None
        self._archivo_content: Optional[ctk.CTkFrame] = None

        # Artwork state
        self._artwork_data: Optional[bytes] = None
        self._artwork_mime: Optional[str] = None
        self._artwork_modified: bool = False
        self._artwork_display_label: Optional[ctk.CTkLabel] = None
        self._artwork_ctk_image: Optional[ctk.CTkImage] = None
        self._empty_state_label: Optional[ctk.CTkLabel] = None
        self._add_artwork_btn: Optional[ctk.CTkButton] = None
        self._remove_artwork_btn: Optional[ctk.CTkButton] = None

        self._detect_format()
        self._read_header_info()  # Read artwork + title/artist before building UI
        self._setup_window()
        self._setup_ui()
        self._read_metadata()

        # Show and make modal
        self.deiconify()  # Show at correct position
        self.lift()
        self.grab_set()
        self.focus_force()
        self.after(50, self.focus_force)
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

    def _read_header_info(self):
        """Read artwork, title, and artist for the header display (before UI setup)."""
        self._header_title = Path(self._filepath).stem
        self._header_artist = ""
        self._header_artwork_data: Optional[bytes] = None

        try:
            audio = MutagenFile(self._filepath)
            if audio is None:
                return

            # Read title and artist
            ext = Path(self._filepath).suffix.lower()
            if ext in (".mp3", ".aiff", ".aif", ".wav"):
                if audio.tags:
                    title_frame = audio.tags.get("TIT2")
                    if title_frame and title_frame.text:
                        t = str(title_frame.text[0]).strip()
                        if t:
                            self._header_title = t
                    artist_frame = audio.tags.get("TPE1")
                    if artist_frame and artist_frame.text:
                        self._header_artist = str(artist_frame.text[0]).strip()
                    # Read artwork
                    for key in audio.tags:
                        if key.startswith("APIC"):
                            frame = audio.tags[key]
                            if hasattr(frame, "data") and frame.data:
                                self._header_artwork_data = frame.data
                                break
            elif ext == ".flac":
                flac = FLAC(self._filepath)
                vals = flac.get("title", [])
                if vals and vals[0].strip():
                    self._header_title = vals[0].strip()
                artist_vals = flac.get("artist", [])
                if artist_vals:
                    self._header_artist = artist_vals[0].strip()
                if flac.pictures:
                    self._header_artwork_data = flac.pictures[0].data
        except Exception:
            pass

    def _setup_window(self):
        """Configure window size, position, and appearance."""
        w, h = 500, 640
        self.geometry(f"{w}x{h}")
        self.minsize(500, 500)
        self.resizable(False, True)
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
        sep.pack(fill="x", padx=20, pady=(0, 8))

        if not self._supported:
            form = ctk.CTkFrame(self, fg_color="transparent")
            form.pack(fill="both", expand=True, padx=28, pady=(0, 8))
            ctk.CTkLabel(
                form,
                text="Este formato no soporta edición de metadatos.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
                text_color=THEME_COLORS["text_secondary"],
            ).pack(pady=40)
        else:
            # Tab bar
            self._setup_tab_bar()

            # Content frame (holds both tabs)
            self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
            self._content_frame.pack(fill="both", expand=True, padx=28, pady=(0, 8))

            # Detalles tab content
            self._detalles_content = ctk.CTkFrame(self._content_frame, fg_color="transparent")
            self._detalles_content.pack(fill="both", expand=True)
            self._setup_fields(self._detalles_content)

            # Ilustración tab content
            self._ilustracion_content = ctk.CTkFrame(self._content_frame, fg_color="transparent")
            self._setup_ilustracion_tab()
            # Initially hidden (detalles is default)

            # Archivo tab content
            self._archivo_content = ctk.CTkFrame(self._content_frame, fg_color="transparent")
            self._setup_archivo_tab()

        # Buttons
        self._setup_buttons()

    def _setup_header(self):
        """Create header with artwork thumbnail, title, and artist (iTunes-style)."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))

        # Artwork thumbnail (left)
        thumb_size = 60
        artwork_img = self._make_header_thumbnail(thumb_size)
        self._header_ctk_image = ctk.CTkImage(
            light_image=artwork_img, dark_image=artwork_img,
            size=(thumb_size, thumb_size),
        )
        ctk.CTkLabel(
            header, image=self._header_ctk_image, text="",
        ).pack(side="left", padx=(0, 14))

        # Text block (right of artwork)
        text_frame = ctk.CTkFrame(header, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            text_frame,
            text=self._header_title,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["heading"], weight="bold"),
            text_color=THEME_COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", pady=(6, 0))

        if self._header_artist:
            ctk.CTkLabel(
                text_frame,
                text=self._header_artist,
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
                text_color=THEME_COLORS["text_secondary"],
                anchor="w",
            ).pack(fill="x", pady=(2, 0))

    def _make_header_thumbnail(self, size: int) -> Image.Image:
        """Create the header thumbnail from artwork data, or the custom placeholder."""
        pixel_size = size * 2
        if self._header_artwork_data:
            try:
                img = Image.open(io.BytesIO(self._header_artwork_data))
                img = img.convert("RGB")
                img = img.resize((pixel_size, pixel_size), Image.LANCZOS)
                img = self._round_corners(img, 12)
                return img
            except Exception:
                pass
        # Use custom placeholder asset
        placeholder_path = Path(__file__).parent.parent / "assets" / "waxcheck-empty-cover-small.png"
        try:
            img = Image.open(placeholder_path)
            img = img.resize((pixel_size, pixel_size), Image.LANCZOS)
            return img
        except Exception:
            # Last resort: solid dark square
            return Image.new("RGBA", (pixel_size, pixel_size), (40, 38, 56, 255))

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
        self._setup_genre_autocomplete()

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

    def _setup_genre_autocomplete(self):
        """Bind inline autocomplete to the genre combobox entry."""
        entry = self._genre_combo._entry
        self._genre_ac_skip = False

        def on_key(event):
            # Ignore navigation / modifier keys
            if event.keysym in (
                "BackSpace", "Delete", "Left", "Right", "Home", "End",
                "Shift_L", "Shift_R", "Control_L", "Control_R",
                "Meta_L", "Meta_R", "Alt_L", "Alt_R", "Tab", "Return",
                "Escape", "Up", "Down",
            ):
                return

            typed = entry.get()
            if not typed:
                return

            cursor = entry.index("insert")
            prefix = typed[:cursor].lower()
            if not prefix:
                return

            for genre in GENRES:
                if genre and genre.lower().startswith(prefix):
                    # Complete the text and select the suggested suffix
                    entry.delete(0, "end")
                    entry.insert(0, genre)
                    entry.select_range(cursor, len(genre))
                    entry.icursor(cursor)
                    return

        entry.bind("<KeyRelease>", on_key)

    def _setup_tab_bar(self):
        """Create the tab bar with Detalles and Ilustración buttons."""
        tab_bar = ctk.CTkFrame(self, fg_color="transparent")
        tab_bar.pack(fill="x", padx=28, pady=(0, 8))

        btn_kwargs = dict(
            height=30,
            corner_radius=6,
            border_width=0,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
        )

        self._detalles_tab_btn = ctk.CTkButton(
            tab_bar,
            text="Detalles",
            command=lambda: self._switch_tab("detalles"),
            fg_color=THEME_COLORS["primary"],
            text_color=THEME_COLORS["text_primary"],
            hover_color=THEME_COLORS["primary_dark"],
            **btn_kwargs,
        )
        self._detalles_tab_btn.pack(side="left", padx=(0, 4))

        self._ilustracion_tab_btn = ctk.CTkButton(
            tab_bar,
            text="Ilustración",
            command=lambda: self._switch_tab("ilustracion"),
            fg_color="transparent",
            text_color=THEME_COLORS["text_secondary"],
            hover_color=THEME_COLORS["bg_elevated"],
            **btn_kwargs,
        )
        self._ilustracion_tab_btn.pack(side="left", padx=(0, 4))

        self._archivo_tab_btn = ctk.CTkButton(
            tab_bar,
            text="Archivo",
            command=lambda: self._switch_tab("archivo"),
            fg_color="transparent",
            text_color=THEME_COLORS["text_secondary"],
            hover_color=THEME_COLORS["bg_elevated"],
            **btn_kwargs,
        )
        self._archivo_tab_btn.pack(side="left")

    def _switch_tab(self, tab_name: str):
        """Switch between Detalles, Ilustración, and Archivo tabs."""
        if tab_name == self._current_tab:
            return

        self._current_tab = tab_name

        tabs = {
            "detalles": (self._detalles_tab_btn, self._detalles_content),
            "ilustracion": (self._ilustracion_tab_btn, self._ilustracion_content),
            "archivo": (self._archivo_tab_btn, self._archivo_content),
        }

        active_font = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"], weight="bold")
        inactive_font = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"])

        for name, (btn, content) in tabs.items():
            if name == tab_name:
                content.pack(fill="both", expand=True)
                btn.configure(
                    fg_color=THEME_COLORS["primary"],
                    text_color=THEME_COLORS["text_primary"],
                    font=active_font,
                )
            else:
                content.pack_forget()
                btn.configure(
                    fg_color="transparent",
                    text_color=THEME_COLORS["text_secondary"],
                    font=inactive_font,
                )

        # Re-render artwork at correct size now that frame is visible
        if tab_name == "ilustracion" and self._artwork_data:
            self.after(50, self._update_artwork_display)

    def _setup_ilustracion_tab(self):
        """Create the artwork display tab content."""
        parent = self._ilustracion_content

        # Subtitle
        ctk.CTkLabel(
            parent,
            text="Ilustración del álbum",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x", pady=(4, 8))

        # Artwork display frame (expands to fill available space)
        self._artwork_frame = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            corner_radius=0,
        )
        self._artwork_frame.pack(fill="both", expand=True)

        # Re-render artwork when frame is resized
        self._artwork_resize_after_id = None
        self._artwork_frame.bind("<Configure>", self._on_artwork_frame_resize)

        # Empty state label (centered in frame)
        self._empty_state_label = ctk.CTkLabel(
            self._artwork_frame,
            text="No hay ilustración cargada",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=THEME_COLORS["text_secondary"],
        )
        self._empty_state_label.place(relx=0.5, rely=0.5, anchor="center")

        # Artwork image label (hidden initially)
        self._artwork_display_label = ctk.CTkLabel(
            self._artwork_frame,
            text="",
        )

        # Button row
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(12, 0))

        self._add_artwork_btn = ctk.CTkButton(
            btn_frame,
            text="Añadir ilustración",
            command=self._on_add_artwork,
            width=140,
            height=32,
            corner_radius=8,
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
            text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
        )
        self._add_artwork_btn.pack(side="left", padx=(0, 8))

        self._remove_artwork_btn = ctk.CTkButton(
            btn_frame,
            text="Eliminar",
            command=self._on_remove_artwork,
            width=80,
            height=32,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=THEME_COLORS["primary_dark"],
            hover_color=THEME_COLORS["bg_elevated"],
            text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
        )
        # Initially hidden (shown only when artwork exists)

    # ─── Archivo Tab ────────────────────────────────────────────────

    def _setup_archivo_tab(self):
        """Create the read-only file information tab."""
        parent = self._archivo_content

        scroll = ctk.CTkScrollableFrame(
            parent,
            fg_color="transparent",
            scrollbar_button_color=THEME_COLORS["scrollbar_thumb"],
            scrollbar_button_hover_color=THEME_COLORS["scrollbar_thumb_hover"],
        )
        scroll.pack(fill="both", expand=True)

        # Use grid on the scroll frame so all rows share column alignment
        scroll.grid_columnconfigure(0, minsize=130)  # Fixed label column
        scroll.grid_columnconfigure(1, weight=1)      # Value column expands

        rows = self._gather_file_info()
        for idx, (label, value, kwargs) in enumerate(rows):
            self._build_info_row(scroll, idx, label, value, **kwargs)

    def _gather_file_info(self) -> list:
        """Collect file info from os, mutagen, and analysis result.

        Returns list of (label, value, kwargs_dict) tuples.
        """
        rows = []
        ext = Path(self._filepath).suffix.lower()
        result = self._analysis_result

        # Open file with mutagen once
        try:
            audio = MutagenFile(self._filepath)
        except Exception:
            audio = None

        # 1. Formato (first position — replaces old "tipo")
        fmt_str = self._get_format_description(audio, ext)
        if fmt_str:
            rows.append(("formato", fmt_str, {}))

        # 2. Duración
        duration = None
        if result and result.duration:
            duration = result.duration
        elif audio and hasattr(audio, "info") and hasattr(audio.info, "length"):
            duration = audio.info.length
        if duration:
            rows.append(("duración", format_duration(duration), {"mono": True}))

        # 3. Tamaño
        try:
            size_bytes = os.path.getsize(self._filepath)
            rows.append(("tamaño", self._format_size(size_bytes), {"mono": True}))
        except OSError:
            pass

        # 4. Velocidad de bits (conditional on transcode)
        is_transcode = result and result.status == STATUS_TRANSCODE
        if is_transcode:
            # Declared bitrate
            declared = None
            if result and result.declared_bitrate:
                declared = result.declared_bitrate
            elif audio and hasattr(audio, "info") and hasattr(audio.info, "bitrate"):
                declared = audio.info.bitrate // 1000 if audio.info.bitrate else None
            if declared:
                rows.append(("velocidad de bits declarada", f"{declared} kbps", {"mono": True}))
            # Detected (real) bitrate
            if result and result.detected_quality:
                fmt = self._format_detected_quality(result.detected_quality)
                rows.append(("velocidad de bits real", fmt, {"mono": True, "color": "#E05555"}))
        else:
            bitrate = None
            if result and result.declared_bitrate:
                bitrate = result.declared_bitrate
            elif audio and hasattr(audio, "info") and hasattr(audio.info, "bitrate"):
                bitrate = audio.info.bitrate // 1000 if audio.info.bitrate else None
            if bitrate:
                rows.append(("velocidad de bits", f"{bitrate} kbps", {"mono": True}))

        # 5. Frecuencia de muestreo
        if audio and hasattr(audio, "info") and hasattr(audio.info, "sample_rate"):
            sr = audio.info.sample_rate
            if sr:
                rows.append(("frecuencia de muestreo", f"{sr:,} Hz".replace(",", "."), {"mono": True}))

        # 6. Canales
        if audio and hasattr(audio, "info") and hasattr(audio.info, "channels"):
            ch = audio.info.channels
            if ch:
                ch_str = "Mono" if ch == 1 else "Estéreo" if ch == 2 else f"{ch} canales"
                rows.append(("canales", ch_str, {}))

        # 7. Volumen (ReplayGain)
        vol = self._get_volume_info(audio, ext)
        if vol:
            rows.append(("volumen", vol, {"mono": True}))

        # 8. Etiqueta ID3 / Vorbis
        tag_info = self._get_tag_info(audio, ext)
        if tag_info:
            rows.append(("etiqueta id3", tag_info, {}))

        # 9. Codificado con
        encoder = self._get_encoder_info(audio, ext)
        if encoder:
            rows.append(("codificado con", encoder, {}))

        # 10. Calidad (from analysis)
        if result and result.cutoff_frequency_khz:
            level = get_quality_level(result.cutoff_frequency_khz, result.status)
            level_labels = {
                "bajo": "Baja",
                "bueno": "Buena",
                "excelente": "Excelente",
            }
            label_text = level_labels.get(level, level.capitalize())
            color = QUALITY_LEVELS.get(level, {}).get("text", THEME_COLORS["text_primary"])
            rows.append(("calidad", label_text, {"color": color}))

        # 11. Fecha de modificación
        try:
            mtime = os.path.getmtime(self._filepath)
            dt = datetime.datetime.fromtimestamp(mtime)
            rows.append(("fecha de modificación", dt.strftime("%d/%m/%Y, %H:%M"), {"mono": True}))
        except OSError:
            pass

        # 12. Ubicación
        rows.append(("ubicación", self._filepath, {"wrap": True, "clickable_path": self._filepath}))

        return rows

    def _build_info_row(self, parent, row_idx: int, label: str, value: str, *,
                        mono: bool = False, color: str = None, wrap: bool = False,
                        clickable_path: str = None):
        """Build a single label-value row in the file info grid."""
        # Label (right-aligned, fixed column)
        ctk.CTkLabel(
            parent,
            text=label,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_secondary"],
            anchor="e",
        ).grid(row=row_idx, column=0, sticky="ne", padx=(0, 8), pady=(3, 3))

        # Value (left-aligned, expands)
        value_color = color or THEME_COLORS["text_primary"]
        value_font = ctk.CTkFont(
            family=FONT_FAMILY_MONO if mono else FONT_FAMILY,
            size=FONT_SIZES["caption"],
        )

        val_label = ctk.CTkLabel(
            parent,
            text=value,
            font=value_font,
            text_color=value_color,
            anchor="w",
            wraplength=260 if wrap else 0,
            justify="left",
        )
        val_label.grid(row=row_idx, column=1, sticky="nw", pady=(3, 3))

        if clickable_path:
            val_label.configure(
                cursor="hand2",
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"], underline=True),
            )
            val_label.bind("<Button-1>", lambda e: self._reveal_in_file_manager(clickable_path))

    @staticmethod
    def _reveal_in_file_manager(filepath: str):
        """Open the system file manager and select the file."""
        import subprocess
        import sys
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", filepath])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", os.path.normpath(filepath)])
            else:
                # Linux: open the containing folder
                subprocess.Popen(["xdg-open", os.path.dirname(filepath)])
        except Exception:
            pass

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format file size as human-readable string (e.g., '3,3 MB')."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB".replace(".", ",")
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB".replace(".", ",")
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB".replace(".", ",")

    @staticmethod
    def _format_detected_quality(quality_str: str) -> str:
        """Format detected quality string (e.g., '128kbps' -> '128 kbps')."""
        s = quality_str.strip()
        if s.lower().endswith("kbps"):
            num = s[:-4].strip()
            return f"{num} kbps"
        return s

    @staticmethod
    def _get_volume_info(audio, ext: str) -> Optional[str]:
        """Extract ReplayGain volume from tags if present."""
        if audio is None or audio.tags is None:
            return None
        try:
            if ext in (".mp3", ".aiff", ".aif", ".wav"):
                # ID3: look for TXXX:replaygain_track_gain
                for key in audio.tags:
                    if key.startswith("TXXX") and "replaygain_track_gain" in key.lower():
                        val = str(audio.tags[key].text[0]) if audio.tags[key].text else ""
                        if val:
                            return val
            elif ext == ".flac":
                vals = audio.get("replaygain_track_gain", [])
                if vals:
                    return vals[0]
        except Exception:
            pass
        return None

    @staticmethod
    def _get_tag_info(audio, ext: str) -> Optional[str]:
        """Get tag format version info."""
        if audio is None or audio.tags is None:
            return None
        try:
            if ext in (".mp3", ".aiff", ".aif", ".wav"):
                tags = audio.tags
                if hasattr(tags, "version"):
                    v = tags.version
                    if isinstance(v, tuple) and len(v) >= 2:
                        return f"v{v[0]}.{v[1]}"
                return None
            elif ext == ".flac":
                return "Vorbis Comments"
        except Exception:
            pass
        return None

    @staticmethod
    def _get_encoder_info(audio, ext: str) -> Optional[str]:
        """Get encoder info if available (e.g., LAME version).

        For MP3 files, always returns a value ('Desconocido' as fallback).
        For other formats, returns None if no encoder info is found.
        """
        if audio is None:
            return "Desconocido" if ext == ".mp3" else None
        try:
            if hasattr(audio, "info") and hasattr(audio.info, "encoder_info"):
                enc = audio.info.encoder_info
                if enc:
                    return enc
        except Exception:
            pass
        return "Desconocido" if ext == ".mp3" else None

    @staticmethod
    def _get_format_description(audio, ext: str) -> Optional[str]:
        """Get detailed format description (e.g., 'MPEG-1, Capa 3', 'FLAC (24-bit)')."""
        try:
            if ext == ".mp3":
                if audio and hasattr(audio, "info"):
                    info = audio.info
                    version = getattr(info, "version", None)
                    layer = getattr(info, "layer", None)
                    if version is not None and layer is not None:
                        return f"MPEG-{version}, Capa {layer}"
                return "MP3"
            elif ext == ".flac":
                if audio and hasattr(audio, "info"):
                    bps = getattr(audio.info, "bits_per_sample", None)
                    if bps:
                        return f"FLAC ({bps}-bit)"
                return "FLAC"
            elif ext in (".wav",):
                if audio and hasattr(audio, "info"):
                    bps = getattr(audio.info, "bits_per_sample", None)
                    if bps:
                        return f"WAV ({bps}-bit)"
                return "WAV"
            elif ext in (".aiff", ".aif"):
                if audio and hasattr(audio, "info"):
                    bps = getattr(audio.info, "bits_per_sample", None) or getattr(audio.info, "sample_size", None)
                    if bps:
                        return f"AIFF ({bps}-bit)"
                return "AIFF"
            else:
                return ext.upper().lstrip(".")
        except Exception:
            return ext.upper().lstrip(".")

    def _on_artwork_frame_resize(self, event=None):
        """Debounced handler: re-render artwork when frame is resized."""
        if not self._artwork_data:
            return
        if self._artwork_resize_after_id is not None:
            self.after_cancel(self._artwork_resize_after_id)
        self._artwork_resize_after_id = self.after(100, self._update_artwork_display)

    @staticmethod
    def _round_corners(img: Image.Image, radius: int) -> Image.Image:
        """Apply rounded corners to a PIL image using an alpha mask."""
        img = img.convert("RGBA")
        mask = Image.new("L", img.size, 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, img.width, img.height], radius=radius, fill=255)
        img.putalpha(mask)
        return img

    def _update_artwork_display(self):
        """Update the artwork display based on current artwork data."""
        if self._artwork_data:
            try:
                img = Image.open(io.BytesIO(self._artwork_data))
                # Determine available space; fallback to 420 if frame not mapped yet
                fw = self._artwork_frame.winfo_width()
                fh = self._artwork_frame.winfo_height()
                if fw < 50 or fh < 50:
                    fw, fh = 420, 420
                img.thumbnail((fw, fh), Image.LANCZOS)
                img = self._round_corners(img, 12)
                self._artwork_ctk_image = ctk.CTkImage(
                    light_image=img, dark_image=img,
                    size=(img.width, img.height),
                )
                self._artwork_display_label.configure(image=self._artwork_ctk_image)
                self._artwork_display_label.place(relx=0.5, rely=0.5, anchor="center")
                self._empty_state_label.place_forget()
                self._remove_artwork_btn.pack(side="left", padx=(0, 8))
            except Exception:
                # Corrupted image data — show empty state
                self._artwork_data = None
                self._update_artwork_display()
        else:
            self._artwork_ctk_image = None
            self._artwork_display_label.configure(image=None)
            self._artwork_display_label.place_forget()
            self._empty_state_label.place(relx=0.5, rely=0.5, anchor="center")
            self._remove_artwork_btn.pack_forget()

    def _on_add_artwork(self):
        """Open file dialog to select artwork image."""
        filepath = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar ilustración",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.PNG *.JPG *.JPEG")],
        )
        if not filepath:
            return

        try:
            with open(filepath, "rb") as f:
                self._artwork_data = f.read()

            ext = Path(filepath).suffix.lower()
            if ext == ".png":
                self._artwork_mime = "image/png"
            else:
                self._artwork_mime = "image/jpeg"

            self._artwork_modified = True
            self._update_artwork_display()
        except Exception:
            pass

    def _on_remove_artwork(self):
        """Remove the current artwork."""
        self._artwork_data = None
        self._artwork_mime = None
        self._artwork_modified = True
        self._update_artwork_display()

    # ─── Artwork Read ────────────────────────────────────────────────

    def _read_artwork(self):
        """Read embedded artwork from the audio file."""
        try:
            if self._format_type == "id3":
                self._read_artwork_id3()
            elif self._format_type == "vorbis":
                self._read_artwork_flac()
        except Exception:
            pass
        self._update_artwork_display()

    def _read_artwork_id3(self):
        """Read artwork from ID3 tags (MP3/AIFF/WAV)."""
        audio = MutagenFile(self._filepath)
        if audio is None or audio.tags is None:
            return
        for key in audio.tags:
            if key.startswith("APIC"):
                frame = audio.tags[key]
                if hasattr(frame, "data") and frame.data:
                    self._artwork_data = frame.data
                    self._artwork_mime = getattr(frame, "mime", "image/jpeg")
                    return

    def _read_artwork_flac(self):
        """Read artwork from FLAC pictures."""
        audio = FLAC(self._filepath)
        if audio.pictures:
            pic = audio.pictures[0]
            self._artwork_data = pic.data
            self._artwork_mime = pic.mime or "image/jpeg"

    # ─── Artwork Save ────────────────────────────────────────────────

    def _save_artwork_id3(self, audio):
        """Save artwork to ID3 tags."""
        tags = audio.tags
        # Remove existing APIC frames
        apic_keys = [k for k in tags if k.startswith("APIC")]
        for k in apic_keys:
            del tags[k]
        # Add new artwork if present
        if self._artwork_data:
            tags["APIC:"] = APIC(
                encoding=3,
                mime=self._artwork_mime or "image/jpeg",
                type=3,  # Cover (front)
                desc="",
                data=self._artwork_data,
            )

    def _save_artwork_flac(self, audio):
        """Save artwork to FLAC pictures."""
        audio.clear_pictures()
        if self._artwork_data:
            pic = Picture()
            pic.type = 3  # Cover (front)
            pic.mime = self._artwork_mime or "image/jpeg"
            pic.data = self._artwork_data
            # Set dimensions from actual image
            try:
                img = Image.open(io.BytesIO(self._artwork_data))
                pic.width, pic.height = img.size
                pic.depth = 24
            except Exception:
                pass
            audio.add_picture(pic)

    def _setup_buttons(self):
        """Create navigation arrows, Cancel and Save buttons."""
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=28, pady=(4, 20))

        # Left: nav arrows | Right: cancel + save
        btn_frame.grid_columnconfigure(1, weight=1)

        # Navigation arrows (left side)
        if self._on_navigate:
            nav_kwargs = dict(
                width=32,
                height=36,
                corner_radius=8,
                fg_color="transparent",
                border_width=0,
                text_color=THEME_COLORS["text_secondary"],
                hover_color=THEME_COLORS["bg_elevated"],
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            )
            prev_btn = ctk.CTkButton(
                btn_frame, text="\u276E", command=lambda: self._navigate(-1), **nav_kwargs,
            )
            prev_btn.grid(row=0, column=0, padx=(0, 4))

            next_btn = ctk.CTkButton(
                btn_frame, text="\u276F", command=lambda: self._navigate(1), **nav_kwargs,
            )
            next_btn.grid(row=0, column=1, sticky="w")

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
        cancel_btn.grid(row=0, column=2, padx=(0, 8))

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
        save_btn.grid(row=0, column=3)

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

        self._read_artwork()

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

        self._close()

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

        if self._artwork_modified:
            self._save_artwork_id3(audio)

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

        if self._artwork_modified:
            self._save_artwork_flac(audio)

        audio.save()

    # ─── UI Helpers ─────────────────────────────────────────────────

    def _show_error(self, message: str):
        """Show an error message in a simple dialog."""
        error_win = ctk.CTkToplevel(self)
        error_win.withdraw()  # Hide until positioned
        error_win.title("Error")
        w, h = 350, 120
        error_win.geometry(f"{w}x{h}")
        error_win.resizable(False, False)
        error_win.configure(fg_color=THEME_COLORS["bg_primary"])
        # Center over parent
        error_win.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - w) // 2
        py = self.winfo_rooty() + (self.winfo_height() - h) // 2
        error_win.geometry(f"{w}x{h}+{px}+{py}")
        error_win.deiconify()  # Show at correct position
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
        warn_win.withdraw()  # Hide until positioned
        warn_win.title("Aviso")
        w, h = 380, 120
        warn_win.geometry(f"{w}x{h}")
        warn_win.resizable(False, False)
        warn_win.configure(fg_color=THEME_COLORS["bg_primary"])
        # Center over parent
        warn_win.update_idletasks()
        parent = self.master
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        warn_win.geometry(f"{w}x{h}+{px}+{py}")
        warn_win.deiconify()  # Show at correct position
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

    def _navigate(self, direction: int):
        """Navigate to prev (-1) or next (+1) file, reopening the editor."""
        if not self._on_navigate:
            return
        new_result = self._on_navigate(direction)
        if new_result is None:
            return
        # Close this editor and open a new one for the new file
        master = self.master
        on_save = self._on_save
        on_navigate = self._on_navigate
        self.grab_release()
        self.destroy()
        MetadataEditor(
            master,
            filepath=new_result.filepath,
            on_save=on_save,
            analysis_result=new_result,
            on_navigate=on_navigate,
        )

    def _cancel(self):
        """Close without saving."""
        self._close()

    def _close(self):
        """Close editor and restore focus to parent."""
        master = self.master
        self.grab_release()
        self.destroy()
        # Delayed focus restoration — let destroy propagate through
        # the Cocoa event loop before forcing focus back to parent.
        master.after(50, lambda: master.focus_force())
