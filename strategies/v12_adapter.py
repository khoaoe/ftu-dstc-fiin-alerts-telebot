# strategies/v12_adapter.py
from __future__ import annotations
import importlib
from typing import Optional

# --- Robust import: ưu tiên v12 ở repo root; nếu không có thì thử round_2.v12 ---
def _try_import(name: str):
    try:
        return importlib.import_module(name)
    except Exception:
        return None

_v12 = _try_import("v12") 

def _require_v12():
    if not _v12:
        raise ImportError(
            "[v12_adapter] Không tìm thấy module 'v12' (root) hoặc 'round_2.v12'. "
            "Hãy đặt v12.py vào repo root hoặc thêm round_2/__init__.py để import."
        )
    miss = [x for x in (
        "precompute_technical_indicators_vectorized",
        "apply_enhanced_screener_v12",
    ) if not hasattr(_v12, x)]
    if miss:
        raise AttributeError(
            f"[v12_adapter] Thiếu hàm trong v12: {', '.join(miss)}. "
            "Hãy đảm bảo v12.py có đúng các hàm API."
        )

# ============== API CHUẨN DÙNG V12 ==============

def compute_features_v12(df_hist):
    """
    Tính toàn bộ chỉ báo/feature V12 trên HISTORICAL (vd 260 phiên).
    Trả về DataFrame 'feat' (cùng số hàng), có đủ cột V12 yêu cầu.
    """
    _require_v12()
    return _v12.precompute_technical_indicators_vectorized(df_hist)

def apply_v12_on_last_day(feat_df):
    """
    Áp filter V12 trên NGÀY MỚI NHẤT.
    feat_df: DataFrame đã qua compute_features_v12(...)
    """
    _require_v12()
    if "timestamp" not in feat_df.columns:
        raise KeyError("[v12_adapter] Thiếu cột 'timestamp' sau khi tính feature.")
    last_ts = feat_df["timestamp"].max()
    df_last = feat_df[feat_df["timestamp"] == last_ts].copy()
    picks = _v12.apply_enhanced_screener_v12(df_last)
    return list(picks)

def compute_picks_from_history(df_hist):
    """
    Pipeline tiện dụng: (1) tính feature toàn lịch sử -> (2) lọc last-day -> (3) áp V12.
    """
    feat = compute_features_v12(df_hist)
    return apply_v12_on_last_day(feat)

# ============== OPTIONAL: Early signal intraday (không phải V12 đầy đủ) ==============

def early_signal_from_15m_bar(prev_bar_row) -> bool:
    """
    Điều kiện 'V12-lite' intraday (demo) — chỉ cảnh báo sớm.
    Bạn có thể thay bằng tiền đề intraday thật của V12.
    """
    vol = float(prev_bar_row.get("volume", 0))
    bu  = float(prev_bar_row.get("bu", 0))
    sd  = float(prev_bar_row.get("sd", 0))
    return vol > 0 and (bu - sd) > 0 and (bu / max(sd, 1)) > 1.2
