from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


def _load_v12():
    """Attempt to load the user-provided V12 module from common drop-in locations."""
    candidate_modules = (
        "v12",
        "strategies.v12",
        "round_2.v12",
    )

    for name in candidate_modules:
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        except Exception:
            return None

    base_dir = Path(__file__).resolve().parent.parent
    candidate_files = (
        base_dir / "v12.py",
        base_dir / "round_2" / "v12.py",
    )

    for file_path in candidate_files:
        if file_path.exists():
            spec = importlib.util.spec_from_file_location("v12_user", file_path)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules.setdefault("v12_user", module)
            try:
                spec.loader.exec_module(module)  # type: ignore[union-attr]
            except Exception:
                continue
            return module
    return None


_v12 = _load_v12()


def compute_picks_from_daily_df(df_last_day) -> list[str]:
    """
    Input: DataFrame (last day per ticker) with OHLCV (+ any extra fields V12 needs).
    Output: list of tickers that pass V12 filter.
    """
    if _v12 and hasattr(_v12, "precompute_technical_indicators_vectorized") and hasattr(_v12, "apply_enhanced_screener_v12"):
        feat = _v12.precompute_technical_indicators_vectorized(df_last_day)
        return list(_v12.apply_enhanced_screener_v12(feat))

    # Fallback (demo only): simple MA condition so repo runs without real V12
    import numpy as np

    picks = []
    for tk, g in df_last_day.groupby("ticker"):
        if len(g) < 50:
            continue
        c = g["close"].to_numpy()
        ma20 = c[-20:].mean()
        ma50 = c[-50:].mean()
        if c[-1] > ma20 > ma50:
            picks.append(tk)
    return picks


def early_signal_from_15m_bar(prev_bar_row) -> bool:
    """Intraday early condition (demo). Replace by your real V12 intraday premises."""
    vol = float(prev_bar_row.get("volume", 0))
    bu = float(prev_bar_row.get("bu", 0))
    sd = float(prev_bar_row.get("sd", 0))
    return vol > 0 and (bu - sd) > 0 and (bu / max(sd, 1)) > 1.2
