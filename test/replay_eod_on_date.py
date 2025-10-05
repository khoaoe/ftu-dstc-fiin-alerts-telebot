# -*- coding: utf-8 -*-
"""
test/replay_eod_on_date.py
Replay EOD V12 cho một ngày cụ thể rồi gửi Telegram.
- KHÔNG sửa logic chiến lược.
- Tận dụng sẵn các module: fiin_client, strategy_adapter (V12), formatters, notifier.
"""
from __future__ import annotations

import os, sys
from pathlib import Path
import math
import pandas as pd

# Thêm repo root vào sys.path để import "app.*"
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import CFG
from app.fiin_client import get_client
from app.notifier import TelegramNotifier
from app.strategy_adapter import compute_features_v12, apply_v12_on_last_day
from app.formatters.vi_alerts import build_eod_header_vi, build_buy_alert_vi, build_no_pick_vi

# =========================
# CHỈNH NGÀY Ở ĐÂY (ví dụ 05/07/2025)
# =========================
TARGET_DATE = "2025-06-05"  # YYYY-MM-DD
# =========================

def _to_ts(s: str) -> pd.Timestamp:
    return pd.to_datetime(s).tz_localize(None)

def _normalize_datetime_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Trả về (df, series_datetime) chuẩn để filter/snap:
      - Ưu tiên 'date', fallback 'time', cuối cùng 'timestamp' (epoch s/ms).
    """
    cols = {c.lower(): c for c in df.columns}
    if "date" in cols:
        ser = pd.to_datetime(df[cols["date"]])
    elif "time" in cols:
        ser = pd.to_datetime(df[cols["time"]])
    elif "timestamp" in cols:
        ts_raw = df[cols["timestamp"]]
        vmax = pd.to_numeric(ts_raw, errors="coerce").max()
        unit = "ms" if pd.notna(vmax) and vmax > 10**12 else "s"
        ser = pd.to_datetime(ts_raw, unit=unit, errors="coerce")
    else:
        raise RuntimeError("Không tìm thấy cột thời gian ('date'/'time'/'timestamp').")
    return df.copy(), ser.dt.tz_localize(None)

def main():
    target_ts = _to_ts(TARGET_DATE)

    # 1) Lấy dữ liệu EOD y như production
    client = get_client()
    data = client.Fetch_Trading_Data(
        realtime=False,
        tickers=list(CFG.tickers),
        fields=["open","high","low","close","volume","bu","sd","fb","fs","fn"],
        adjusted=True,
        by="1d",
        period=260,
    ).get_data()

    if not isinstance(data, pd.DataFrame):
        try:
            data = pd.DataFrame(data)
        except Exception as e:
            raise RuntimeError(f"Không thể chuyển kết quả get_data() thành DataFrame: {e}")

    # 2) Chuẩn hoá thời gian & cắt tới TARGET_DATE (snap về phiên gần nhất ≤ TARGET_DATE)
    _, ts_all = _normalize_datetime_columns(data)
    data_cut = data.loc[ts_all <= target_ts].copy()
    if data_cut.empty:
        raise RuntimeError(f"Không có dữ liệu trước hoặc bằng {target_ts.date()}.")

    # 3) Tính feature V12 trên phần dữ liệu đã cắt
    feat = compute_features_v12(data_cut)

    # 4) Lấy series thời gian trong feat (date → time → timestamp)
    feat_cols = {c.lower(): c for c in feat.columns}
    if "date" in feat_cols:
        ts_feat = pd.to_datetime(feat[feat_cols["date"]])
    elif "time" in feat_cols:
        ts_feat = pd.to_datetime(feat[feat_cols["time"]])
    elif "timestamp" in feat_cols:
        vmax = pd.to_numeric(feat[feat_cols["timestamp"]], errors="coerce").max()
        unit = "ms" if pd.notna(vmax) and vmax > 10**12 else "s"
        ts_feat = pd.to_datetime(feat[feat_cols["timestamp"]], unit=unit, errors="coerce")
    else:
        TelegramNotifier.send(build_no_pick_vi("EOD"), parse_mode="HTML")
        return
    ts_feat = ts_feat.dt.tz_localize(None)

    # 5) Snap phiên gần nhất ≤ TARGET_DATE
    feat_cut = feat.loc[ts_feat <= target_ts].copy()
    if feat_cut.empty:
        TelegramNotifier.send(build_no_pick_vi("EOD"), parse_mode="HTML")
        return
    last_ts = pd.to_datetime(feat_cut.assign(_ts=ts_feat.loc[feat_cut.index])["_ts"]).max()
    feat_last = feat_cut.loc[ts_feat.loc[feat_cut.index] == last_ts].copy()

    # 6) Picks của ngày đó
    picks = apply_v12_on_last_day(feat_cut) or []

    # 7) Tổng hợp market metrics cho header (lấy giá trị đầu tiên != NaN)
    market_fields = ["market_close","market_MA50","market_MA200","market_rsi","market_adx","market_boll_width"]
    market = {}
    for f in market_fields:
        col = next((c for c in feat_last.columns if c.lower() == f.lower()), None)
        if col:
            val = feat_last[col].dropna()
            market[f] = float(val.iloc[0]) if not val.empty else None
        else:
            market[f] = None

    market_close      = market.get("market_close")
    market_ma50       = market.get("market_MA50")
    market_ma200      = market.get("market_MA200")
    market_rsi        = market.get("market_rsi")
    market_adx        = market.get("market_adx")
    market_boll_width = market.get("market_boll_width")

    is_bull = (
        market_close is not None and market_ma50 is not None and market_ma200 is not None and market_rsi is not None
        and market_close > market_ma50 and market_close > market_ma200 and market_rsi > 55
    )
    is_sideway = (
        market_adx is not None and market_boll_width is not None and market_rsi is not None
        and market_adx < 25 and (market_boll_width or 0) < 0.35 and 35 <= market_rsi <= 60
    )
    regime_label = "bull" if is_bull else ("sideway" if is_sideway else "bear")
    atr_multiplier = 2.0 if is_bull else (1.2 if is_sideway else 2.2)

    header = build_eod_header_vi(
        date_str=str(last_ts.date() if not pd.isna(last_ts) else target_ts.date()),
        market={
            "market_close": market_close,
            "market_rsi": market_rsi,
            "market_adx": market_adx,
            "market_boll_width": market_boll_width,
        },
    )

    # 8) Build alerts cho từng mã
    blocks = [header]
    tkr_col = next((c for c in feat_last.columns if c.lower() == "ticker"), None)

    for tkr in picks:
        entry = tp = sl = 0.0
        if tkr_col:
            m = feat_last[feat_last[tkr_col].astype(str).str.upper() == str(tkr).upper()]
            if not m.empty:
                row = m.iloc[0]
                entry_val = row.get("close_adj", float("nan"))
                if (not isinstance(entry_val, (int, float))) or math.isnan(entry_val):
                    entry_val = row.get("close", 0.0)
                atr_val = row.get("atr_14", 0.0)

                try:
                    entry = float(entry_val)
                except Exception:
                    entry = 0.0
                try:
                    atr = float(atr_val)
                except Exception:
                    atr = 0.0
                if entry > 0 and atr > 0:
                    tp = entry + atr_multiplier * atr
                    sl = max(0.0, entry - atr_multiplier * atr)
                else:
                    tp = entry
                    sl = entry

        blocks.append(build_buy_alert_vi(str(tkr), entry, tp, sl, regime_label))

    # 9) Gửi Telegram
    text = "\n\n".join(blocks)
    notifier = TelegramNotifier()
    if hasattr(notifier, "send_chunks"):
        notifier.send_chunks(text, parse_mode="HTML")
    else:
        try:
            TelegramNotifier.send(text, parse_mode="HTML")
        except Exception:
            notifier._send(text, parse_mode="HTML")

if __name__ == "__main__":
    main()
