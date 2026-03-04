# 🎸 Essentia Music Tagger — GUI

A graphical front-end for [WB2024/Essentia-to-Metadata](https://github.com/WB2024/Essentia-to-Metadata) with GPU acceleration, library browser, tag viewer, and mood tagging support.

> ⚠️ **This repo contains only `essentia_gui.py`.**  
> You need the original repo for `tag_music.py`, `download_models.sh`, and everything else.  
> **[→ Get the original project here](https://github.com/WB2024/Essentia-to-Metadata)**

---

## ✨ What the GUI adds

- Visual library browser (Artist → Album → Track)
- Live tag inspector (genre + mood highlighted)
- One-click model downloader
- GPU / CPU selector with auto-detection
- Dry run / Normal / Overwrite radio modes
- Progress bar and live output log
- Session logs saved automatically next to the script

---

## 🖥️ Platform support

| Platform | Status |
|---|---|
| Linux (any distro) | ✅ Fully supported |
| macOS | ⚠️ CPU only, untested |
| Windows | ❌ `essentia-tensorflow` has no Windows wheels — use WSL2 |

---

## 📋 Requirements

- Python 3.8+
- NVIDIA GPU + drivers (for GPU mode — CPU works fine without)
- `tkinter` (usually ships with Python — see below if missing)
- `git`

---

## 🚀 Installation

### 1. Clone the repo

```bash
git clone https://github.com/WB2024/Essentia-to-Metadata.git
cd Essentia-to-Metadata
```

### 2. Create a virtual environment

```bash
# bash/zsh
python3 -m venv .venv --system-site-packages
source .venv/bin/activate

# fish shell
python3 -m venv .venv --system-site-packages
source .venv/bin/activate.fish
```

> `--system-site-packages` is recommended so the venv can see system tkinter.

### 3. Install Python dependencies

```bash
pip install essentia-tensorflow mutagen numpy
```

### 4. Download ML models

Either click **Download Models** inside the GUI, or run:

```bash
bash download_models.sh
```

Models are saved to `models/` next to the script (~25 MB total).

### 5. Run the GUI

```bash
python essentia_gui.py
```

---

## ⚡ GPU Setup (CUDA 11)

`essentia-tensorflow` bundles TensorFlow 2.x which requires **CUDA 11** libraries.  
Most modern Linux systems ship with CUDA 12+, so you need to install the CUDA 11 compatibility libraries via pip — **no system CUDA downgrade needed**.

### Install CUDA 11 libs into your venv

```bash
pip install \
  nvidia-cuda-runtime-cu11 \
  nvidia-cudnn-cu11==8.9.2.26 \
  nvidia-cublas-cu11 \
  nvidia-cufft-cu11 \
  nvidia-curand-cu11 \
  nvidia-cusolver-cu11 \
  nvidia-cusparse-cu11
```

### Set LD_LIBRARY_PATH (for running outside the GUI)

The GUI sets this automatically when launching the tagger. For manual CLI runs, add this to your shell config.

Replace `/path/to/Essentia-to-Metadata` with your actual clone path.

**bash** — add to `~/.bashrc`:
```bash
export LD_LIBRARY_PATH=$(find ~/path/to/Essentia-to-Metadata/.venv/lib/python3.*/site-packages/nvidia -name "lib" -type d | tr '\n' ':')$LD_LIBRARY_PATH
```

**zsh** — add to `~/.zshrc`:
```zsh
export LD_LIBRARY_PATH=$(find ~/path/to/Essentia-to-Metadata/.venv/lib/python3.*/site-packages/nvidia -name "lib" -type d | tr '\n' ':')$LD_LIBRARY_PATH
```

**fish** — add to `~/.config/fish/config.fish`:
```fish
set -x LD_LIBRARY_PATH (find ~/path/to/Essentia-to-Metadata/.venv/lib/python3.*/site-packages/nvidia -name "lib" -type d | string join ":") $LD_LIBRARY_PATH
```

After editing, reload your config:
```bash
source ~/.bashrc   # bash
source ~/.zshrc    # zsh
source ~/.config/fish/config.fish  # fish
```

### Test CUDA is working (before running the GUI)

Run this one-liner to verify all CUDA 11 libs are found and the GPU is detected:

```bash
# Set the path for this session first
export LD_LIBRARY_PATH=$(find .venv/lib/python3.*/site-packages/nvidia -name "lib" -type d | tr '\n' ':')$LD_LIBRARY_PATH

# Then test
python3 -c "
import essentia.standard as es
m = es.TensorflowPredictEffnetDiscogs(
    graphFilename='models/discogs-effnet-bs64-1.pb',
    output='PartitionedCall:1')
print('done')
" 2>&1 | grep -i 'cuda\|gpu\|success\|error\|fail' | head -20
```

Expected successful output — every library should say **Successfully opened**:
```
Successfully opened dynamic library libcudart.so.11.0
Successfully opened dynamic library libcuda.so.1
Successfully opened dynamic library libcublas.so.11
Successfully opened dynamic library libcublasLt.so.11
Successfully opened dynamic library libcufft.so.10
Successfully opened dynamic library libcurand.so.10
Successfully opened dynamic library libcusolver.so.11
Successfully opened dynamic library libcusparse.so.11
Successfully opened dynamic library libcudnn.so.8
Adding visible gpu devices: 0
```

> The "NUMA node negative value" warning is harmless — safe to ignore.

### Verify GPU in the GUI

Click **Detect GPUs** — it should show your GPU name and VRAM.  
The output log will confirm at run time:

```
⚡ GPU mode — CUDA_VISIBLE_DEVICES=0 (NVIDIA GeForce RTX 4090)
✅ GPU confirmed via nvidia-smi: NVIDIA GeForce RTX 4090, 24564 MiB
✅ libcudart.so.11.0 loaded — CUDA active
```

---

## 🔧 tkinter missing?

If you get `ModuleNotFoundError: No module named 'tkinter'`:

```bash
# Debian/Ubuntu
sudo apt install python3-tk

# Arch/CachyOS/Manjaro
sudo pacman -S tk

# Fedora
sudo dnf install python3-tkinter
```

---

## 📁 File structure

After setup your folder should look like this:

```
Essentia-to-Metadata/
├── essentia_gui.py       ← the GUI (this file)
├── tag_music.py          ← the CLI tagger (from original repo)
├── download_models.sh    ← model downloader (from original repo)
├── models/               ← ML model files (auto-created)
│   ├── discogs-effnet-bs64-1.pb
│   ├── genre_discogs400-discogs-effnet-1.pb
│   ├── genre_discogs400-discogs-effnet-1.json
│   ├── mtg_jamendo_moodtheme-discogs-effnet-1.pb
│   └── mtg_jamendo_moodtheme-discogs-effnet-1.json
└── logs/                 ← auto-created on first run
    ├── tagger/           ← essentia_tagger_*.log files
    └── gui/              ← gui_session_*.log files
```

---

## 🎛️ GUI walkthrough

### Library Browser tab
Browse your music collection by Artist → Album → Track. Click any track to inspect its tags in the panel on the right. Genre and mood tags are highlighted in purple.

The library browser **auto-detects your folder structure** — it works with:

| Structure | Example |
|---|---|
| Artist / Album / Track | `/Music/2Pac/All Eyez On Me/track.mp3` |
| Artist / Track | `/Music/2Pac/track.mp3` |
| Combined folder | `/Music/2Pac - All Eyez On Me/track.mp3` |
| Flat | `/Music/track.mp3` |

If your files have no tags yet (you're about to tag them), the browser falls back to parsing folder names to populate Artist and Album. After tagging, hit **Refresh** and it will update from the written tags.

> ⚠️ **Known limitation:** If your files are flat (no subfolders) and untagged, with artist/album info only in the filename (e.g. `2pac-better-dayz-01-intro.mp3`), the library browser cannot parse this and will group everything under `(unknown artist)`. The tagger will still process and tag all files correctly — after tagging, hit Refresh and the browser will populate from the written tags.

### Tagger tab

| Setting | Description |
|---|---|
| tag_music.py script | Path to `tag_music.py` — auto-detected if in same folder |
| Music folder | Root of your music library |
| Whole folder / Single file | Tag everything or just one file |
| Genres to write | How many genre tags per track (1–10) |
| Genre threshold | Min ML confidence % to write a genre tag |
| Genre format | How genre names are formatted (see below) |
| Mood threshold | Min confidence % for mood tags (0.1–10%) |
| Dry run | Preview only — nothing is written |
| Normal | Write tags, skip already-tagged files |
| Overwrite | Write tags, replace existing ones |
| GPU / CPU | Which compute device to use |

### Genre formats

| Format | Example output |
|---|---|
| `parent_child` | `Hip Hop - Gangsta` |
| `child_parent` | `Gangsta - Hip Hop` |
| `child_only` | `Gangsta` ← recommended for Navidrome/Symfonium |
| `raw` | `Hip-Hop---Gangsta` |

---

## 💡 Recommended workflow

1. **Run dry run first** on a single album to preview results
2. Switch to **Normal mode** and run on your full library — this writes tags only to untagged files, preserving any existing genres from MusicBrainz Picard
3. If you only want mood tags (and already have genres from Picard), set **Genre threshold to 100%** — nothing will ever score 100% so genres are skipped, but moods still get written
4. Use **Overwrite mode** only if you want to replace all existing genre/mood tags

---

## 🎵 Music server compatibility

| Server/Player | Genre | Mood |
|---|---|---|
| Navidrome | ✅ | ❌ no mood field |
| Symfonium | ✅ | ✅ reads MOOD tag natively |
| Jellyfin | ✅ | ❌ |
| foobar2000 | ✅ | ✅ |
| Strawberry | ✅ | ✅ |

For Navidrome + Symfonium stacks: Navidrome serves the genres, Symfonium reads the MOOD tag directly from the file.

---

## ⚠️ Known issues

- **Qt SVG warnings** when using `kdialog` for file browsing — harmless, suppress with `python essentia_gui.py 2>/dev/null`
- **AudioLoader: invalid frame** warnings in the log — harmless, Essentia skips malformed frames automatically
- **"No network created"** log messages — suppressed automatically by the GUI

---

## 🙏 Credits

- [WB2024/Essentia-to-Metadata](https://github.com/WB2024/Essentia-to-Metadata) — original CLI tagger
- [Essentia](https://essentia.upf.edu/) by Music Technology Group, Universitat Pompeu Fabra
- ML models trained on Discogs and MTG-Jamendo datasets
