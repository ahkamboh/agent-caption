#!/usr/bin/env python3
"""local-caption — cross-platform setup (Windows / macOS / Linux).

    python setup.py        (or: python3 setup.py)

Creates ./.venv-whisperx and installs every dependency into it (single venv).
Run all the caption scripts with that venv's python afterwards.
"""
import os
import sys
import shutil
import subprocess
import venv
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(HERE, ".venv-whisperx")


def venv_python():
    if os.name == "nt":
        return os.path.join(VENV, "Scripts", "python.exe")
    return os.path.join(VENV, "bin", "python")


def main():
    ap = argparse.ArgumentParser(description="local-caption setup")
    ap.add_argument("--small", action="store_true",
                    help="also pre-download the small model (~460MB) for --fast speed mode")
    ap.add_argument("--grammar", action="store_true",
                    help="also install the offline homophone/grammar fixer (language_tool_python; needs Java)")
    args = ap.parse_args()
    print("== local-caption setup ==")

    v = sys.version_info
    print(f"python {v.major}.{v.minor}.{v.micro}  ({sys.platform})")
    if v < (3, 9):
        sys.exit("!! Python 3.9+ required.")
    if v >= (3, 14):
        print("note: very new Python. torch ships wheels for it; if whisperx (or another dep) has")
        print("      no wheel yet, fall back to Python 3.11-3.12 and re-run.")

    if shutil.which("ffmpeg") is None:
        print("!!  ffmpeg not found. Install it, then re-run:")
        print("    macOS: brew install ffmpeg | Ubuntu: sudo apt install ffmpeg | Windows: winget install ffmpeg")
    else:
        print("ok: ffmpeg present")

    py = venv_python()
    if not os.path.exists(py):
        print("-- creating ./.venv-whisperx --")
        venv.EnvBuilder(with_pip=True).create(VENV)
    else:
        print("ok: ./.venv-whisperx already exists")

    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip"], check=False)
    print("-- installing requirements (heavy: torch + whisperx, a few minutes) --")
    r = subprocess.run([py, "-m", "pip", "install", "-r", os.path.join(HERE, "requirements.txt")])
    if r.returncode != 0:
        print("\n!! dependency install failed.")
        print("   Most often this is torch for your platform. Install the right build from")
        print("   https://pytorch.org/get-started/locally/ into ./.venv-whisperx, then re-run setup.")
        sys.exit(r.returncode)

    # Pre-fetch the DEFAULT model (large-v3) so the first caption is instant AND max accuracy.
    print("-- downloading the default model: Whisper large-v3 (~1.5 GB, one-time, best accuracy) --")
    if subprocess.run([py, "-c", "from faster_whisper import WhisperModel; "
                       "WhisperModel('large-v3', device='cpu', compute_type='int8')"]).returncode == 0:
        print("ok: large-v3 ready (the default — no flag needed)")
    else:
        print("   (couldn't pre-fetch large-v3; it will auto-download on your first caption instead)")

    if args.small:
        print("-- also downloading the small model (~460 MB, for --fast) --")
        subprocess.run([py, "-c", "import whisper; whisper.load_model('small')"])

    if args.grammar:
        print("-- installing language_tool_python (offline homophone/grammar fix, for --grammar) --")
        subprocess.run([py, "-m", "pip", "install", "language_tool_python"])
        if shutil.which("java") is None:
            print("   note: Java not found — --grammar needs a JRE 8+.")
            print("         macOS: brew install openjdk | Ubuntu: sudo apt install default-jre | Windows: winget install Microsoft.OpenJDK.21")

    rel = r".venv-whisperx\Scripts\python" if os.name == "nt" else "./.venv-whisperx/bin/python"
    print("\n== done ==  engine + model + fonts ready.\n")
    print("Caption a video — one command:")
    print(f"  {rel} caption.py your_video.mp4")
    print(f"  {rel} caption.py your_video.mp4 --style hormozi       # pick a famous look")
    print(f"  {rel} caption.py your_song.mp4 --content music        # songs: isolate vocals (demucs) first")
    print("Styles: clean bold hormozi green beast impact bebas tiktok pill boxed yellow neon gradient minimal subtitle")
    print("(Demucs' htdemucs model auto-downloads ~80MB on your first --content music job.)")


if __name__ == "__main__":
    main()
