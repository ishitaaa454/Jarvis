"""
Configurable constants for double-clap detection.

Tune THRESHOLD_MULTIPLIER / MIN_THRESHOLD for sensitivity:
  - Higher  => fewer false positives
  - Lower   => easier to trigger

Set DEBUG_NEAR_MISSES = True to print why loud sounds were rejected
(useful while tuning; turn off afterward).
"""

# Microphone sample rate in Hz.
SAMPLE_RATE = 16000

# Frames per audio callback (~32 ms at 16 kHz).
BLOCK_SIZE = 512

# Seconds of ambient noise measured at startup.
CALIBRATION_DURATION = 3.0

# Clap threshold ≈ quiet background * multiplier, then floored/capped.
THRESHOLD_MULTIPLIER = 3.5

# Absolute minimum peak for a clap candidate.
# Your claps often measure ~0.10–0.21.
MIN_THRESHOLD = 0.10

# Cap so a noisy calibration cannot block real claps.
MAX_THRESHOLD = 0.35

# Double-clap timing window (seconds).
MIN_CLAP_INTERVAL = 0.18
MAX_CLAP_INTERVAL = 1.5

# Ignore new claps after a confirmed double clap.
COOLDOWN_DURATION = 3.0

# Max length of one clap transient.
MAX_CLAP_DURATION = 0.35

# Debounce after a counted clap.
CLAP_REFRACTORY = 0.12

# Peak must rise this much vs recent quiet baseline (first clap only).
# Second clap skips this check — baseline is often still elevated.
MIN_RISE_RATIO = 1.8

# Crest factor = peak / RMS (impulsive sounds are higher).
MIN_CREST_FACTOR = 2.0

# High-frequency proxy via sample differences / RMS.
MIN_HF_RATIO = 0.15

# Set True while tuning; leave False for normal use.
DEBUG_NEAR_MISSES = False

# Log file relative to the project root.
LOG_FILE = "logs/jarvis.log"
