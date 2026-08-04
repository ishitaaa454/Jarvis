# Vosk models

Jarvis Phase 2 uses a **small English Vosk model** for offline wake-phrase detection.
The backend does **not** download models automatically.

## 1. Obtain a model

Download the small US English model from the official Vosk models page:

https://alphacephei.com/vosk/models

Recommended archive:

- `vosk-model-small-en-us-0.15.zip` (or the current small `en-us` package)

## 2. Extract location

Extract so the model directory sits here:

```text
backend/models/vosk-model-small-en-us/
```

Example PowerShell (from the `backend` folder):

```powershell
New-Item -ItemType Directory -Force -Path models | Out-Null
# After downloading the zip to Downloads:
Expand-Archive -Path "$env:USERPROFILE\Downloads\vosk-model-small-en-us-0.15.zip" -DestinationPath models
# Rename the extracted folder if needed:
Rename-Item models\vosk-model-small-en-us-0.15 models\vosk-model-small-en-us
```

## 3. Expected folder structure

The extracted directory must contain Vosk model markers such as:

```text
backend/models/vosk-model-small-en-us/
  am/
  conf/
  graph/
  ivector/   (optional depending on model)
  ...
```

Jarvis validates that `am`, `conf`, and `graph` exist before loading.

## 4. Configure `VOSK_MODEL_PATH`

In `backend/.env`:

```env
VOSK_MODEL_PATH=models/vosk-model-small-en-us
```

Relative paths resolve against the `backend/` directory. Absolute paths are also accepted.

## 5. Verify the path

```powershell
cd backend
Test-Path .\models\vosk-model-small-en-us\am
Test-Path .\models\vosk-model-small-en-us\conf
Test-Path .\models\vosk-model-small-en-us\graph
```

All three should return `True`. Then start the backend and check:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/voice/status
```

`model_loaded` should be `true` when the listener can start.

## 6. Do not commit model files

Model binaries are large and must stay out of Git. They are ignored via `.gitignore`.
Only `backend/models/README.md` (and `.gitkeep`) belong in the repository.
