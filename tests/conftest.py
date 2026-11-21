"""The package is installed (pip install -e .), so the modules are imported
as ovos_skill_music_teacher.*; sounds.py makes the sound the tests play."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
