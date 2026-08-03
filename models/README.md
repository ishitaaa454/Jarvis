# Vosk speech models

This folder holds the offline Vosk model used for wake-phrase recognition.

## Required model

Download **vosk-model-small-en-us-0.15** (small English US model):

- Model page: https://alphacephei.com/vosk/models
- Direct zip: https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip

## Exact placement

After download, extract so the folder layout is:

```text
jarvis-workspace/
└── models/
    ├── README.md
    └── vosk-model-small-en-us-0.15/
        ├── am/
        ├── conf/
        ├── graph/
        └── ...
```

`config.VOSK_MODEL_PATH` must point to that extracted folder:

```text
models/vosk-model-small-en-us-0.15
```

## Windows PowerShell extract example

```powershell
cd "C:\Users\Ishita Joshi\Desktop\Projects\Jarvis\jarvis-workspace\models"
# After downloading vosk-model-small-en-us-0.15.zip into this folder:
Expand-Archive -Path ".\vosk-model-small-en-us-0.15.zip" -DestinationPath "." -Force
```

Confirm:

```powershell
Test-Path ".\vosk-model-small-en-us-0.15\am"
```

It should return `True`.

Do **not** commit the large model files to git (they are ignored).
