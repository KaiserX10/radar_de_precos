# Entrada da Vercel: expõe o mesmo app FastAPI do modo local.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar.servidor import app  # noqa: E402,F401
