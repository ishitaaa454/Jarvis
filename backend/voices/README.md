# Piper voices

Jarvis Phase 3 uses **Piper** with the British male voice **`en_GB-alan-medium`**.
The backend does **not** download Piper or voice models during startup.

## 1. Install Piper on Windows

1. Download `piper_windows_amd64.zip` from the Piper releases:  
   https://github.com/rhasspy/piper/releases  
   (release `2023.11.14-2` / `v1.2.0` style Windows zip is fine)
2. Extract somewhere stable, for example:

```text
C:\Tools\piper\
  piper.exe
  espeak-ng-data\
  *.dll
```

3. Set in `backend/.env`:

```env
PIPER_EXECUTABLE_PATH=C:\Tools\piper\piper.exe
```

Or add the folder containing `piper.exe` to your PATH and leave `PIPER_EXECUTABLE_PATH` blank.

Verify:

```powershell
& "C:\Tools\piper\piper.exe" --help
```

## 2. Download `en_GB-alan-medium`

From Hugging Face Piper voices:

https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_GB/alan/medium

Download **both**:

- `en_GB-alan-medium.onnx`
- `en_GB-alan-medium.onnx.json`

## 3. Place files here

```text
backend/voices/en_GB-alan-medium/
  en_GB-alan-medium.onnx
  en_GB-alan-medium.onnx.json
```

## 4. Configure paths

```env
PIPER_VOICE_MODEL_PATH=voices/en_GB-alan-medium/en_GB-alan-medium.onnx
PIPER_VOICE_CONFIG_PATH=voices/en_GB-alan-medium/en_GB-alan-medium.onnx.json
```

Relative paths resolve from the `backend/` directory.

## 5. Verify

```powershell
cd backend
Test-Path .\voices\en_GB-alan-medium\en_GB-alan-medium.onnx
Test-Path .\voices\en_GB-alan-medium\en_GB-alan-medium.onnx.json
.\.venv\Scripts\Activate.ps1
python tools\test_tts.py --welcome
```

Or via API after starting the backend:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/tts/status
```

`model_loaded` should be `true` and `status` should be `READY` when Piper and the voice files are present.

## 6. Do not commit voice binaries

`.onnx` models and generated `.wav` files are large and must stay out of Git.
Only `backend/voices/README.md` (and `.gitkeep`) belong in the repository.
