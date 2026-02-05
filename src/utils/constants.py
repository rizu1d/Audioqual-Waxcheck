"""Constants and thresholds for audio quality analysis."""

# Frequency cutoff thresholds (in kHz) for bitrate classification
# Based on typical MP3 encoder low-pass filter frequencies
BITRATE_THRESHOLDS = {
    "lossless": {"min_freq": 20.5, "max_freq": 22.5},
    "320kbps": {"min_freq": 19.5, "max_freq": 20.5},
    "256kbps": {"min_freq": 18.5, "max_freq": 19.5},
    "192kbps": {"min_freq": 17.0, "max_freq": 18.5},
    "160kbps": {"min_freq": 16.0, "max_freq": 17.0},
    "128kbps": {"min_freq": 15.0, "max_freq": 16.0},
    "96kbps": {"min_freq": 13.0, "max_freq": 15.0},
    "low": {"min_freq": 0, "max_freq": 13.0},
}

# Analysis status
STATUS_OK = "OK"
STATUS_TRANSCODE = "Transcode detectado"
STATUS_LOSSLESS = "Lossless"
STATUS_LOW_QUALITY = "Baja calidad"
STATUS_ERROR = "Error"
STATUS_PENDING = "Pendiente"
STATUS_ANALYZING = "Analizando..."
STATUS_UNCERTAIN = "Incierto"
STATUS_VARIABLE = "Calidad variable"

# Confidence thresholds
CONFIDENCE_HIGH = 0.7      # Above this = certain result
CONFIDENCE_LOW = 0.5       # Below this = uncertain result

# FFT parameters for spectral analysis
FFT_SIZE = 4096
HOP_LENGTH = 512
SAMPLE_RATE = 44100

# Noise floor threshold in dB
NOISE_FLOOR_DB = -60

# Gradient threshold for detecting abrupt cutoff
GRADIENT_THRESHOLD = -5.0

# Shelf detection parameters (for brick-wall filter detection)
SHELF_WINDOW_HZ = 500.0      # Window width for smoothing (Hz)
SHELF_DROP_DB = 20.0         # Minimum drop to consider a cutoff (dB)
SHELF_SUSTAIN_DB = 10.0      # Maximum variation allowed post-cutoff (dB)
SHELF_REFERENCE_LOW_KHZ = 1.0   # Lower bound for reference signal (kHz)
SHELF_REFERENCE_HIGH_KHZ = 8.0  # Upper bound for reference signal (kHz)
SHELF_NOISE_LOW_KHZ = 20.0      # Lower bound for noise floor estimation (kHz)
SHELF_NOISE_HIGH_KHZ = 22.0     # Upper bound for noise floor estimation (kHz)
SHELF_SEARCH_START_KHZ = 21.0   # Start searching from this frequency (kHz)
SHELF_SEARCH_END_KHZ = 10.0     # Stop searching at this frequency (kHz)

# Relative energy detection parameters (improved algorithm for transcode detection)
# This algorithm distinguishes musical content (variable energy) from noise (constant energy)
RELATIVE_REFERENCE_LOW_KHZ = 2.0      # Reference band lower bound (kHz)
RELATIVE_REFERENCE_HIGH_KHZ = 8.0     # Reference band upper bound (kHz)
RELATIVE_DROP_DB = -20.0              # Threshold: energy drop from reference to consider noise (dB) - más estricto
RELATIVE_VARIANCE_THRESHOLD = 0.25    # Normalized variance threshold (music > 0.25, noise < 0.25)
RELATIVE_STRICT_VARIANCE_THRESHOLD = 0.7  # For low-energy bands, require 70% of reference variance - más estricto
RELATIVE_BAND_WIDTH_KHZ = 1.0         # Width of analysis bands (kHz)
RELATIVE_SEARCH_START_KHZ = 20.0      # Start searching from this frequency (kHz)
RELATIVE_SEARCH_END_KHZ = 10.0        # Stop searching at this frequency (kHz)
RELATIVE_MIN_ACTIVE_RATIO = 0.3       # Minimum ratio of non-silent frames required

# Segment-based percentile analysis parameters
SEGMENT_COUNT = 50                    # Number of segments to analyze
PREDOMINANT_PERCENTILE = 85.0         # Use 85th percentile (ignore top 15% peaks)
OUTLIER_THRESHOLD_KHZ = 3.0           # >3kHz difference between max and percentile = has outliers

# Transition-based detection parameters (primary algorithm for detecting codec cutoff)
# Detects the "brick wall" by finding where energy DROPS significantly between adjacent bands
TRANSITION_MIN_DROP_DB = 8.0          # Minimum energy drop to consider a cutoff (dB) - reduced from 10.0
TRANSITION_BAND_WIDTH_HZ = 500        # Width of analysis bands (Hz) - smaller for precision
TRANSITION_SEARCH_START_HZ = 10000    # Start analyzing from this frequency (Hz)
TRANSITION_SEARCH_END_HZ = 21000      # End analyzing at this frequency (Hz)
TRANSITION_MIN_ENERGY_DB = -40.0      # Minimum energy to consider band as having content (dB)
TRANSITION_CONFIRMATION_BANDS = 2     # Number of bands after drop that must stay low

# Variance thresholds for transition detection (v2 - uses RELATIVE variance drop)
# Instead of absolute thresholds, we check if variance DROPS significantly between bands
TRANSITION_VARIANCE_DROP_RATIO = 0.30 # Variance must drop by at least 30% between bands
TRANSITION_RECOVERY_THRESHOLD_DB = 3.0  # If energy rises >3dB after drop, it's not a real cutoff
TRANSITION_MIN_PRE_VARIANCE = 0.4     # Pre-transition band must have at least 40% of reference variance (musical content)

# Frequency-dependent variance threshold interpolation range (Layer 2)
# At lower frequencies, musical content has higher variance; at higher frequencies
# (near codec cutoff), even real content has lower variance (especially acapellas).
# Interpolate TRANSITION_MIN_PRE_VARIANCE from base value at low freq to reduced value at high freq.
TRANSITION_VARIANCE_FREQ_LOW_HZ = 14000   # Below this: use full TRANSITION_MIN_PRE_VARIANCE
TRANSITION_VARIANCE_FREQ_HIGH_HZ = 20000  # Above this: use reduced minimum variance
TRANSITION_MIN_PRE_VARIANCE_HIGH_FREQ = 0.25  # Reduced variance threshold at high frequencies

# Cumulative drop detection (Layer 2): detect gradual codec rolloff
# If N consecutive bands sum > threshold in total drop, treat as cutoff
TRANSITION_CUMULATIVE_BANDS = 3           # Number of consecutive bands to sum
TRANSITION_CUMULATIVE_DROP_DB = 12.0      # Total dB drop across those bands

# Anti-sibilance recovery check (Layer 2)
# Require multiple consecutive bands with energy AND variance to consider "recovery"
TRANSITION_RECOVERY_CONSECUTIVE_BANDS = 2  # Must have 2 consecutive bands with real content
TRANSITION_RECOVERY_MIN_VARIANCE = 0.3     # Each recovery band must have variance >= this

# MP3 bitrate → maximum physically possible cutoff frequency (kHz)
# Based on LAME and other MP3 encoder low-pass filter behavior.
# Used as a safety net: if detected cutoff exceeds this, it's physically impossible.
MP3_BITRATE_MAX_CUTOFF_KHZ = {
    (0, 95):     15.0,   # <96kbps
    (96, 127):   16.0,   # 96kbps
    (128, 159):  17.0,   # 128kbps (real ~16kHz + 1kHz margin)
    (160, 191):  18.0,   # 160kbps
    (192, 255):  19.5,   # 192kbps
    (256, 279):  20.5,   # 256kbps
    (280, 320):  21.0,   # 320kbps
}

# Supported audio formats
SUPPORTED_FORMATS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma", ".aiff", ".aif"}

# GUI constants
WINDOW_WIDTH = 900           # Main window only (when panel closed)
PANEL_WIDTH = 450            # Spectrogram panel width
WINDOW_HEIGHT = 800
MIN_WINDOW_WIDTH = 900
MIN_WINDOW_HEIGHT = 600

# Panel resize constraints (draggable divider)
MIN_MAIN_WIDTH = 500         # Ancho mínimo del panel principal (selector de archivos)
MIN_SPECTRUM_WIDTH = 300     # Ancho mínimo del panel de espectrogramas
DIVIDER_WIDTH = 6            # Ancho del divisor arrastrable (px)

# Theme colors - Premium purple/gold/black palette (refined)
THEME_COLORS = {
    # Violeta refinado
    "primary": "#8B7EC8",           # Violeta más luminoso
    "primary_dark": "#5D5478",      # Violeta para hover/bordes
    "primary_muted": "#3D3650",     # Violeta muy suave para fondos

    # Acento
    "accent": "#F5C842",            # Dorado

    # Texto
    "text_primary": "#F5F3E8",      # Crema cálido
    "text_secondary": "#9A9A9A",    # Gris medio para subtítulos
    "text_muted": "#666666",        # Gris suave para headers tabla

    # Fondos (NO negro puro)
    "bg_primary": "#121214",        # Gris muy oscuro (base)
    "bg_secondary": "#18181C",      # Gris para tabla
    "bg_tertiary": "#1E1E24",       # Gris para drop zone
    "bg_elevated": "#252530",       # Gris para elementos elevados
    "bg_frame": "#1A1A20",          # Frames

    # Scrollbar
    "scrollbar_track": "#1E1E24",
    "scrollbar_thumb": "#5D5478",
    "scrollbar_thumb_hover": "#8B7EC8",

    # Filas
    "row_selected": "#2D2D38",
    "row_hover": "#222228",
}

# Colors for status - softened premium palette
STATUS_COLORS = {
    STATUS_OK: "#5DB88C",           # Esmeralda suave (no neón)
    STATUS_LOSSLESS: "#8B7EC8",     # Violeta principal
    STATUS_TRANSCODE: "#E05555",    # Coral/bermellón
    STATUS_LOW_QUALITY: "#E09650",  # Naranja cálido
    STATUS_ERROR: "#7A7A7A",        # Gris
    STATUS_PENDING: "#555555",      # Gris medio
    STATUS_ANALYZING: "#F5C842",    # Dorado
    STATUS_UNCERTAIN: "#D4B84A",    # Amarillo suave
    STATUS_VARIABLE: "#D08A45",     # Naranja terroso
}

# Typography (Inter - fuente geométrica moderna)
FONT_FAMILY = "Inter"
FONT_SIZES = {
    "title": 28,
    "heading": 18,
    "body": 14,
    "caption": 12,
    "small": 11,
}
FONT_WEIGHTS = {
    "bold": "bold",
    "medium": "normal",  # CTkFont no soporta "medium"
    "regular": "normal",
}
