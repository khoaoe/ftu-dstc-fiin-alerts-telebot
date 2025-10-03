# strategies/v12_adapter.py
from __future__ import annotations
import importlib
from typing import Optional
import pandas as pd

# --- Robust import: uu tien v12 o repo root; neu khong co thi thu round_2.v12 ---
_import_errors = []

def _try_import(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:
        _import_errors.append((name, exc))
        return None

_v12 = _try_import("v12") or _try_import("round_2.v12")

def _require_v12():
    if not _v12:
        context = ""
        if _import_errors:
            details = "; ".join(f"{name}: {exc}" for name, exc in _import_errors)
            context = f" (import detail: {details})"
        raise ImportError(
            "[v12_adapter] Khong tim thay module 'v12' (root) hoac 'round_2.v12'. "
            "Hay dat v12.py vao repo root hoac them round_2/__init__.py de import."
            + context
        )
    miss = [x for x in (
        "precompute_technical_indicators_vectorized",
        "apply_enhanced_screener_v12",
    ) if not hasattr(_v12, x)]
    if miss:
        raise AttributeError(
            f"[v12_adapter] Thieu ham trong v12: {', '.join(miss)}. "
            "Hay dam bao v12.py co du day cac ham API."
        )

# ============== API CHUẨN DÙNG V12 ==============

def _find_level(names, candidates) -> Optional[int]:
    if names is None:
        return None
    low = [ (str(n) if n is not None else "").lower() for n in names ]
    for i, n in enumerate(low):
        if n in candidates:
            return i
    return None

def _ensure_market_close(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tạo cột 'market_close' theo *ngày* để V12 dùng groupby(level=0).first().
    Ưu tiên lấy close của VNINDEX; nếu không có, dùng mean close theo ngày.
    Không làm thay đổi logic sàng lọc của V12.
    """
    if 'market_close' in df.columns:
        return df

    out = df.copy()
    idx = out.index

    # tìm level ngày/mã trong MultiIndex (nếu có)
    is_mi = isinstance(idx, pd.MultiIndex)
    names = getattr(idx, "names", None)
    lvl_date = _find_level(names, {"date", "trading_date", "time"})
    lvl_sym  = _find_level(names, {"ticker", "symbol", "code"})

    # chọn tên cột giá đóng cửa
    close_col = None
    for c in ["close", "adj_close", "close_price", "Close"]:
        if c in out.columns:
            close_col = c
            break
    if close_col is None:
        # thiếu dữ liệu nền tảng → để nổ sớm với thông điệp rõ ràng
        raise KeyError("[v12_adapter] Không tìm thấy cột giá đóng cửa (close/adj_close/close_price).")

    # --- TH1: MultiIndex & có level mã → thử lấy VNINDEX/VN30 làm benchmark ---
    if is_mi and lvl_sym is not None:
        syms = idx.get_level_values(lvl_sym).astype(str).str.upper()
        aliases = ['^VNINDEX', 'VNINDEX', '^VNI', 'VNI', '^VN30', 'VN30']
        found_alias = None
        for a in aliases:
            if (syms == a).any():
                found_alias = a
                break

        if found_alias is not None:
            # chuỗi benchmark theo *ngày*
            bench = out.loc[syms == found_alias, close_col]
            # bỏ level mã để còn trục ngày
            bench = bench.droplevel(lvl_sym) if isinstance(bench.index, pd.MultiIndex) else bench

            # xác định level ngày (V12 coi level=0 là ngày → ta broadcast theo level ngày thực)
            if lvl_date is None:
                lvl_date = 0  # mặc định đoán level 0 là ngày

            # align theo ngày: map từng dòng về giá market của đúng ngày
            days = idx.get_level_values(lvl_date)
            out['market_close'] = bench.reindex(days).to_numpy()
            return out

    # --- TH2: Không có VNINDEX → proxy = mean close theo ngày ---
    if is_mi and (lvl_date is not None):
        days = idx.get_level_values(lvl_date)
        daily = out[close_col].groupby(level=lvl_date).mean()
        out['market_close'] = daily.reindex(days).to_numpy()
        return out

    # --- TH3: DataFrame 1 cấp chỉ số → group theo cột date nếu có ---
    if not is_mi:
        # Nếu chưa có 'date' thì suy ra từ 'timestamp' hoặc 'time'
        if 'date' not in out.columns:
            ts_col = None
            for c in ['timestamp', 'time', 'Date', 'datetime', 'Datetime']:
                if c in out.columns:
                    ts_col = c
                    break
            if ts_col is not None:
                out['date'] = pd.to_datetime(out[ts_col]).dt.date

        if 'date' in out.columns:
            daily = out.groupby('date')[close_col].mean()
            out['market_close'] = out['date'].map(daily)
            return out

    # Không thể suy ra benchmark → để nổ sớm, kèm gợi ý cấu trúc
    raise KeyError(
        "[v12_adapter] Không thể tạo 'market_close'. "
        "Yêu cầu: DataFrame có MultiIndex (ngày, mã) hoặc có cột 'date', và có cột giá đóng cửa."
    )

def compute_features_v12(df_hist):
    """
    Tính toàn bộ chỉ báo/feature V12 trên HISTORICAL (vd 260 phiên).
    Trả về DataFrame 'feat' (cùng số hàng), có đủ cột V12 yêu cầu.
    """
    _require_v12()
    df_hist = _ensure_market_close(df_hist) 
    return _v12.precompute_technical_indicators_vectorized(df_hist)

def apply_v12_on_last_day(feat_df):
    """
    Áp filter V12 trên NGÀY MỚI NHẤT.
    feat_df: DataFrame đã qua compute_features_v12(...)
    """
    _require_v12()
    # Hỗ trợ cả 'timestamp' và 'time' (v12.py dùng 'time')
    ts_col = 'timestamp' if 'timestamp' in feat_df.columns else ('time' if 'time' in feat_df.columns else None)
    if ts_col is None:
        raise KeyError("[v12_adapter] Thiếu cột 'timestamp' hoặc 'time' sau khi tính feature.")
    last_ts = feat_df[ts_col].max()
    df_last = feat_df[feat_df[ts_col] == last_ts].copy()
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
