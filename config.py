"""
Configurable constants for double-clap detection and wake-phrase listening.

Clap sensitivity:
  - Higher THRESHOLD_MULTIPLIER / MIN_THRESHOLD => fewer false positives
  - Lower  => easier to trigger

Set DEBUG_NEAR_MISSES = True to print why loud sounds were rejected.
"""

# ---------------------------------------------------------------------------
# Clap detection
# ---------------------------------------------------------------------------

# Microphone sample rate in Hz.
SAMPLE_RATE = 16000

# Frames per audio callback (~32 ms at 16 kHz).
BLOCK_SIZE = 512

# Seconds of ambient noise measured at startup.
CALIBRATION_DURATION = 3.0

# Clap threshold ≈ quiet background * multiplier, then floored/capped.
THRESHOLD_MULTIPLIER = 3.0

# Absolute minimum peak for a clap candidate.
# Current mic levels show real claps around 0.05–0.07.
MIN_THRESHOLD = 0.045

# Cap so a noisy calibration cannot block real claps.
MAX_THRESHOLD = 0.30

# Double-clap timing window (seconds).
MIN_CLAP_INTERVAL = 0.15
MAX_CLAP_INTERVAL = 1.8

# Ignore new claps after a confirmed double clap / wake cycle.
COOLDOWN_DURATION = 3.0

# Max length of one clap transient.
MAX_CLAP_DURATION = 0.40

# Debounce after a counted clap.
CLAP_REFRACTORY = 0.10

# Peak must rise this much vs recent quiet baseline (first clap only).
# Kept low — laptop AGC often leaves an elevated baseline after a clap.
MIN_RISE_RATIO = 1.3

# Crest factor = peak / RMS (impulsive sounds are higher).
MIN_CREST_FACTOR = 1.8

# High-frequency proxy via sample differences / RMS.
MIN_HF_RATIO = 0.10

# Set True while tuning; leave False for normal use.
DEBUG_NEAR_MISSES = True

# ---------------------------------------------------------------------------
# Wake-phrase recognition (Vosk, offline)
# ---------------------------------------------------------------------------

# Folder containing the extracted Vosk model (see models/README.md).
VOSK_MODEL_PATH = "models/vosk-model-small-en-us-0.15"

# Canonical wake phrase (matching is normalized; variants are accepted).
WAKE_PHRASE = "wake up jarvis"

# Seconds allowed to speak the wake phrase after a double clap.
WAKE_LISTEN_TIMEOUT = 7.0

# Delay after double clap before opening the speech mic (avoids clap-as-speech).
WAKE_START_DELAY = 0.3

# Sample rate for Vosk (must match the model; small en-us models use 16 kHz).
SPEECH_SAMPLE_RATE = 16000

# Audio block size for the wake-phrase stream (frames).
SPEECH_BLOCK_SIZE = 4000

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FILE = "logs/jarvis.log"
