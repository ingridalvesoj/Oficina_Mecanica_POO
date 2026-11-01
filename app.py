"""Ponto de entrada: python -m streamlit run app.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from oficina.ui.main import main  # noqa: E402

main()
