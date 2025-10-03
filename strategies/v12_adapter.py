# strategies/v12_adapter.py
from __future__ import annotations
import importlib
from typing import Optional
import pandas as pd
import numpy as np

# ====== Helpers tính chỉ báo kỹ thuật (không phụ thuộc thư viện ngoài) ======
def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()

def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()

def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = (-delta).clip(lower=0.0)
    roll_up = up.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    roll_down = down.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    rs = roll_up / (roll_down.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi

def _macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series]:
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return macd, macd_signal

def _bb_width(close: pd.Series, n: int = 20, nstd: float = 2.0) -> pd.Series:
    ma = close.rolling(n, min_periods=n).mean()
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    upper = ma + nstd * sd
    lower = ma - nstd * sd
    width = (upper - lower) / ma
    return width

def _atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = np.maximum.reduce([
        (high - low).abs().values,
        (high - prev_close).abs().values,
        (low - prev_close).abs().values
    ])
    tr = pd.Series(tr, index=close.index)
    atr = tr.rolling(n, min_periods=n).mean()
    return atr


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    # Wilder's ADX — tối giản cho EOD
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = ((up_move > down_move) & (up_move > 0)).astype(float) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0)).astype(float) * down_move
    tr1 = (high - low).abs()
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low  - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(n, min_periods=n).mean()
    plus_di  = 100 * (plus_dm.rolling(n, min_periods=n).mean()  / atr)
    minus_di = 100 * (minus_dm.rolling(n, min_periods=n).mean() / atr)
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx = dx.rolling(n, min_periods=n).mean()
    return adx

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
        # Chuẩn hóa 'date' từ timestamp/time nếu cần
        if 'date' not in out.columns:
            ts_col = next((c for c in ['timestamp', 'time', 'Date', 'datetime', 'Datetime'] if c in out.columns), None)
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
    

def compute_features_v12(df_hist: pd.DataFrame) -> pd.DataFrame:
    """
    Sinh đầy đủ cột kỹ thuật mà chiến lược V12 yêu cầu:
    ['market_MA200','market_rsi','sma_50','sma_200','rsi_14','volume_spike','macd','macd_signal','boll_width','atr_14']
    - Tự tạo 'date' từ ['timestamp'/'time'/...] nếu thiếu.
    - Tính theo từng 'ticker', sau đó merge 'market_*' từ VNINDEX theo 'date'.
    """
    if df_hist is None or len(df_hist) == 0:
        return df_hist

    df = df_hist.copy()
    # Bắt buộc có 'date' để group/merge
    if 'date' not in df.columns:
        ts_col = next((c for c in ['timestamp', 'time', 'Date', 'datetime', 'Datetime'] if c in df.columns), None)
        if ts_col is None:
            raise KeyError("[v12_adapter] Thiếu cột thời gian ('timestamp'/'time') để tạo 'date'.")
        df['date'] = pd.to_datetime(df[ts_col]).dt.date

    # Sắp xếp và tính theo từng mã
    df = df.sort_values(['ticker', 'date'])
    def _per_ticker(g: pd.DataFrame) -> pd.DataFrame:
        out = g.copy()
        out['sma_50']  = _sma(out['close'], 50)
        out['sma_200'] = _sma(out['close'], 200)
        out['rsi_14']  = _rsi(out['close'], 14)
        macd, macd_signal = _macd(out['close'], 12, 26, 9)
        out['macd']        = macd
        out['macd_signal'] = macd_signal
        out['boll_width']  = _bb_width(out['close'], 20, 2.0)
        out['atr_14']      = _atr(out['high'], out['low'], out['close'], 14)
        # volume_spike = volume / SMA20(volume)
        vma20 = out['volume'].rolling(20, min_periods=20).mean()
        out['volume_spike'] = out['volume'] / vma20
        return out

    df = df.groupby('ticker', group_keys=False).apply(_per_ticker)

    # Market features từ VNINDEX (OHLC) — phục vụ filter V12 EOD
    mkt = df[df['ticker'].eq('VNINDEX')][['date', 'open', 'high', 'low', 'close']].copy()
    mkt = mkt.sort_values('date').drop_duplicates('date', keep='last')
    m_close = mkt['close']
    mkt['market_close']      = m_close
    mkt['market_MA50']       = _sma(m_close, 50)
    mkt['market_MA200']      = _sma(m_close, 200)
    mkt['market_rsi']        = _rsi(m_close, 14)
    mkt['market_boll_width'] = _bb_width(m_close, 20, 2.0)
    mkt['market_adx']        = _adx(mkt['high'], mkt['low'], m_close, 14)
    df = df.merge(
        mkt[['date','market_close','market_MA50','market_MA200','market_rsi','market_boll_width','market_adx']],
        on='date', how='left'
    )

    # Loại bỏ phiên chưa đủ dữ liệu cho các chỉ báo bắt buộc
    req_cols = [
        'market_close','market_MA50','market_MA200','market_rsi','market_boll_width','market_adx',
        'sma_50','sma_200','rsi_14','volume_spike','macd','macd_signal','boll_width','atr_14'
    ]
    df = df.dropna(subset=req_cols)
    return df


def apply_v12_on_last_day(feat_df):
    """
    Áp filter V12 trên NGÀY MỚI NHẤT.
    feat_df: DataFrame đã qua compute_features_v12(...)
    """
    _require_v12()
    # Hỗ trợ cả 'timestamp' và 'time' (v12.py dùng 'time')
    ts_col = 'timestamp' if 'timestamp' in feat_df.columns else ('time' if 'time' in feat_df.columns else None)
    if ts_col is None:
        # fallback theo 'date' nếu không có timestamp/time
        ts_col = 'date'
    if ts_col not in feat_df.columns:
        raise KeyError("[v12_adapter] Thiếu cột 'timestamp'/'time'/'date' để lấy phiên cuối.")
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
