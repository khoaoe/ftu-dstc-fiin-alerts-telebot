# -*- coding: utf-8 -*-
"""
alerts_on_date.py — Re-run V12 alerts for a specific DATE (EOD-only)

Chức năng:
- Nhận --date (YYYY-MM-DD) từ CLI; nếu không có thì dùng DEFAULT_DATE.
- Lấy dữ liệu EOD, tính feature V12 đến hết DATE, chạy screener để ra "cảnh báo MUA" cho DATE.
- Đọc positions (mua trước DATE) từ state.json -> áp logic thoát lệnh V12 trên nến DATE để tạo "cảnh báo BÁN".
- Gửi tất cả cảnh báo qua Telegram (HTML).

Yêu cầu ENV (đã có sẵn trong repo):
- FIIN_USER, FIIN_PASS (nếu dùng FiinQuantX)
- BOT_TOKEN, CHAT_ID, THREAD_ID? (tuỳ nếu chat theo topic)
- STATE_FILE (mặc định: state.json)
- DATA_FILE_PATH (nếu muốn đọc dữ liệu EOD từ file thay vì Fiin)

Chạy:
    python -m app.jobs.alerts_on_date --date 2025-07-30
    # hoặc:
    python app/jobs/alerts_on_date.py --date 2025-07-30
"""

from __future__ import annotations
import os, sys, json, time, math, argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import numpy as np

# ---- Import từ repo sẵn có ----
from app.config import CFG
from app.fiin_client import get_client
from app.strategy_adapter import compute_features_v12, apply_v12_on_last_day
from app.formatters.vi_alerts import build_eod_header_vi, build_buy_alert_vi, fmt_money, fmt_pct, fmt_num
from app.notifier import TelegramNotifier
from app.state import load_state, save_state

# ---- Tham số mặc định (KHỚP VỚI BACKTEST V12) ----
DEFAULT_DATE = "2025-07-30"  # khi không truyền --date
ATR_MULTIPLIER = 1.5
TRAILING_STOP_PCT = 0.05
PARTIAL_PROFIT_PCT = 0.4
MIN_HOLDING_DAYS = 3

STATE_KEY = "positions"  # trong state.json

# =======================
# Tiện ích IO dữ liệu
# =======================

def _load_eod_data_until_date(target_date: pd.Timestamp) -> pd.DataFrame:
    """
    Load dữ liệu EOD cho CFG.tickers (bao gồm VNINDEX) đến hết target_date.
    - Nếu có DATA_FILE_PATH trong .env -> đọc file (parquet/csv).
    - Ngược lại dùng FiinQuantX client Fetch_Trading_Data(by='1d', period đủ dài).
    Output: DataFrame columns ~ ['time','ticker','open','high','low','close','volume', ...]
    """
    data_path = os.getenv("DATA_FILE_PATH", "").strip()
    if data_path:
        path = Path(data_path)
        if not path.exists():
            raise FileNotFoundError(f"Không thấy file dữ liệu: {path}")
        ext = path.suffix.lower()
        if ext == ".parquet":
            df = pd.read_parquet(path)
        elif ext == ".csv":
            df = pd.read_csv(path)
        else:
            try:
                df = pd.read_parquet(path)
            except Exception:
                df = pd.read_csv(path)
        # Chuẩn hoá
        if "time" not in df.columns:
            if "timestamp" in df.columns:
                df = df.rename(columns={"timestamp": "time"})
            else:
                raise KeyError("Thiếu cột thời gian: cần 'time' hoặc 'timestamp'.")
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values(["time","ticker"])
        df = df[df["time"] <= target_date].copy()
        # Nếu muốn chỉ giữ các tickers trong CFG:
        tickers = set(CFG.tickers) if getattr(CFG, "tickers", None) else None
        if tickers:
            df = df[df["ticker"].isin(tickers | {"VNINDEX"})].copy()
        return df

    # --- FiinQuantX ---
    client = get_client()
    # Lấy 400 phiên gần nhất để đủ SMA200/ATR14
    raw = client.Fetch_Trading_Data(
        realtime=False,
        tickers=list(CFG.tickers),
        fields=['open','high','low','close','volume','bu','sd','fb','fs','fn'],
        adjusted=True,
        by='1d',
        period=400
    ).get_data()
    df = raw.copy()
    # Chuẩn hoá kiểu thời gian
    if "time" not in df.columns:
        if "timestamp" in df.columns:
            df = df.rename(columns={"timestamp": "time"})
        else:
            raise KeyError("Thiếu cột thời gian: cần 'time' hoặc 'timestamp'.")
    df["time"] = pd.to_datetime(df["time"])
    df = df[df["time"] <= target_date].copy()
    return df


# =======================
# Logic BUY (EOD @ DATE)
# =======================

def pick_buys_on_date(feat: pd.DataFrame, target_date: pd.Timestamp) -> Tuple[List[str], pd.DataFrame, Dict[str, Any]]:
    """
    Truncate features <= target_date rồi dùng apply_v12_on_last_day(feat_trunc) để lấy picks.
    Trả về (list mã, df_lastday, market_metrics_dict)
    """
    # Ưu tiên 'date' (adapter chuẩn hóa), fallback sang 'time'/'timestamp'
    if 'date' in feat.columns:
        ts = pd.to_datetime(feat['date'])
    elif 'time' in feat.columns:
        ts = pd.to_datetime(feat['time'])
    elif 'timestamp' in feat.columns:
        ts = pd.to_datetime(feat['timestamp'])
    else:
        return [], pd.DataFrame(), {}

    feat_trunc = feat[ts <= target_date].copy()
    if feat_trunc.empty:
        return [], pd.DataFrame(), {}

    # Lấy hàng của đúng ngày target
    last_ts = pd.to_datetime(target_date)
    feat_last = feat_trunc[(pd.to_datetime(feat_trunc.get('date', feat_trunc.get('time', feat_trunc.get('timestamp')))) == last_ts)].copy()

    picks = apply_v12_on_last_day(feat_trunc)  # "last day" = target_date
    # Loại trừ nếu có exclude_tickers
    if getattr(CFG, "exclude_tickers", None):
        exclude = {t.strip().upper() for t in CFG.exclude_tickers if isinstance(t, str)}
        picks = [p for p in picks if p.upper() not in exclude]

    # Market metrics để render header
    metrics_row = feat_last.iloc[0].to_dict() if not feat_last.empty else {}
    def _as_float(x):
        try:
            return float(x)
        except Exception:
            return None
    market = {
        "market_close": _as_float(metrics_row.get("market_close")),
        "market_MA50": _as_float(metrics_row.get("market_MA50")),
        "market_MA200": _as_float(metrics_row.get("market_MA200")),
        "market_rsi": _as_float(metrics_row.get("market_rsi")),
        "market_adx": _as_float(metrics_row.get("market_adx")),
        "market_boll_width": _as_float(metrics_row.get("market_boll_width")),
    }
    return picks, feat_last, market


def compute_entry_tp_sl(row: pd.Series) -> Tuple[float, float, float]:
    """
    Entry/TP/SL theo đúng tham số backtest V12 (entry_mode='close', ATR_MULTIPLIER, TRAILING_STOP_PCT).
    """
    entry = float(row.get("close") or row.get("close_adj"))
    atr14 = float(row.get("atr_14", np.nan))
    tp = entry + ATR_MULTIPLIER * atr14
    sl = entry - ATR_MULTIPLIER * atr14
    return entry, tp, sl


def infer_regime_badge(market: Dict[str, Any]) -> str:
    """
    Badge bull/sideway/bear — cùng tiêu chí như trong adapter/eod_scan.
    """
    c = market.get("market_close"); ma50 = market.get("market_MA50"); ma200 = market.get("market_MA200")
    rsi = market.get("market_rsi"); adx = market.get("market_adx"); bw = market.get("market_boll_width")
    is_bull = all(v is not None for v in (c, ma50, ma200, rsi)) and c > ma50 and c > ma200 and rsi > 55
    is_side = all(v is not None for v in (adx, bw, rsi)) and adx < 25 and (bw or 0) < 0.3 and 40 < rsi < 60
    if is_bull: return "bull"
    if is_side: return "sideway"
    return "bear"


# =======================
# Logic SELL (theo V12)
# =======================

@dataclass
class Position:
    ticker: str
    entry_date: str        # 'YYYY-MM-DD'
    entry_price: float
    tp: float
    sl: float
    highest: float
    partial_taken: bool    # đã chốt lời 1 phần (lần 1) hay chưa
    trailing_sl: float     # trailing = highest * (1 - TRAILING_STOP_PCT)
    shares: int            # tuỳ ý; không cần chính xác để gửi alert

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Position":
        return Position(
            ticker=d["ticker"],
            entry_date=d["entry_date"],
            entry_price=float(d["entry_price"]),
            tp=float(d["tp"]),
            sl=float(d["sl"]),
            highest=float(d.get("highest", d["entry_price"])),
            partial_taken=bool(d.get("partial_taken", False)),
            trailing_sl=float(d.get("trailing_sl", d["entry_price"] * (1 - TRAILING_STOP_PCT))),
            shares=int(d.get("shares", 0))
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "entry_date": self.entry_date,
            "entry_price": self.entry_price,
            "tp": self.tp,
            "sl": self.sl,
            "highest": self.highest,
            "partial_taken": self.partial_taken,
            "trailing_sl": self.trailing_sl,
            "shares": self.shares,
        }


def _check_intraday_tp_sl(high_val: float, low_val: float, tp_val: float, sl_val: float) -> Tuple[bool, bool]:
    # Bám theo logic kiểm tra nội phiên: vượt TP hoặc thủng SL (đơn giản hoá chuẩn với V12)
    trigger_tp = high_val >= tp_val
    trigger_sl = low_val <= sl_val
    return trigger_tp, trigger_sl


def evaluate_sell_signal_for_bar(pos: Position, bar: pd.Series, date_str: str) -> Optional[Dict[str, Any]]:
    """
    Sinh sell-signal cho 1 position trên cây nến DATE, áp cơ bản:
      1) Gap qua TP/SL tại open -> thoát tại open (ưu tiên).
      2) Nội phiên chạm TP/SL:
           - Nếu chưa partial: BÁN MỘT PHẦN tại TP; cập nhật vị thế (partial_taken=True, nâng trailing).
           - Nếu đã partial: BÁN HẾT khi chạm TP lần 2 (đơn giản hoá hợp lý).
      3) Trailing stop: nếu Close < trailing_sl -> BÁN HẾT tại Close.
    Trả về dict {type, price, reason, realized_pct} hoặc None.
    """
    o = float(bar["open"]); h = float(bar["high"]); l = float(bar["low"]); c = float(bar["close"])

    # Cập nhật highest/trailing trước (để trailing nhạy hơn)
    if h > pos.highest:
        pos.highest = h
        pos.trailing_sl = pos.highest * (1 - TRAILING_STOP_PCT)

    # 1) Gap qua mức tại open
    if o >= pos.tp:
        ret = (o - pos.entry_price) / pos.entry_price
        action = "BÁN CHỐT LỜI" if pos.partial_taken else "BÁN CHỐT LỜI (LẦN 1)"
        return {"type": "TP_GAP", "price": o, "reason": action, "realized_pct": ret}
    if o <= pos.sl:
        ret = (o - pos.entry_price) / pos.entry_price
        return {"type": "SL_GAP", "price": o, "reason": "BÁN CẮT LỖ", "realized_pct": ret}

    # 2) Nội phiên TP/SL
    hit_tp, hit_sl = _check_intraday_tp_sl(h, l, pos.tp, pos.sl)
    if hit_sl:
        ret = (pos.sl - pos.entry_price) / pos.entry_price
        return {"type": "SL", "price": pos.sl, "reason": "BÁN CẮT LỖ", "realized_pct": ret}

    if hit_tp:
        if not pos.partial_taken:
            # Bán một phần lần 1 theo partial_profit_pct
            ret = (pos.tp - pos.entry_price) / pos.entry_price
            # Sau chốt 1 phần -> nâng mục tiêu (mô phỏng “profit staircase” đơn giản)
            next_tp = pos.tp * (1.0 + 0.15)  # xấp xỉ tăng mục tiêu ~15% từ mức TP hiện tại
            pos.partial_taken = True
            pos.tp = next_tp
            pos.sl = max(pos.sl, pos.entry_price)  # bảo toàn vốn tối thiểu
            return {"type": "TP_PARTIAL", "price": pos.tp / 1.15, "reason": "BÁN CHỐT LỜI (MỘT PHẦN)", "realized_pct": ret}
        else:
            ret = (pos.tp - pos.entry_price) / pos.entry_price
            return {"type": "TP_FULL", "price": pos.tp, "reason": "BÁN CHỐT LỜI (PHẦN CÒN LẠI)", "realized_pct": ret}

    # 3) Trailing stop (đánh giá cuối phiên)
    if c <= pos.trailing_sl:
        ret = (c - pos.entry_price) / pos.entry_price
        return {"type": "TRAIL", "price": c, "reason": "BÁN THEO TRAILING", "realized_pct": ret}

    # Không có tín hiệu bán
    return None


def build_sell_alert_vi(date_str: str, pos: Position, signal: Dict[str, Any]) -> str:
    """Format cảnh báo BÁN (HTML) — giữ style gần với buy-alert trong repo."""
    price = signal["price"]; reason = signal["reason"]; realized = signal["realized_pct"]
    rr = None
    try:
        # RR dựa trên “khoảng risk” ban đầu
        risk = max(1e-9, pos.entry_price - pos.sl)
        reward = max(0.0, pos.tp - pos.entry_price)
        rr = reward / risk if risk > 0 else None
    except Exception:
        rr = None

    up_pct = (price - pos.entry_price) / pos.entry_price if pos.entry_price else 0.0
    lines = [
        "🔴",
        f"<b>[{date_str}] Cảnh báo BÁN: {pos.ticker}</b>",
        f"• Lý do: <b>{reason}</b>",
        f"• Giá thoát (tham khảo): <b>{fmt_money(price)} VNĐ</b>  (≈ {fmt_pct(up_pct, 2)})",
        f"• Giá vào lệnh: {fmt_money(pos.entry_price)} VNĐ",
        f"• Trailing SL hiện tại: {fmt_money(pos.trailing_sl)} VNĐ",
    ]
    if rr is not None and rr > 0:
        lines.append(f"• Tỷ lệ R/R (ước lượng): <b>{fmt_num(rr, 2)}</b>")
    return "\n".join(lines)


# =======================
# Main flow
# =======================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", "-d", type=str, default=None, help="Ngày định dạng YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or DEFAULT_DATE
    target_date = pd.to_datetime(date_str).normalize()

    # 1) Load dữ liệu đến hết DATE
    data = _load_eod_data_until_date(target_date)

    # 2) Tính feature V12
    feat = compute_features_v12(data)

    # 3) Picks MUA đúng ngày DATE
    picks, feat_last, market = pick_buys_on_date(feat, target_date)
    header_text = build_eod_header_vi(date_str=date_str, market=market)
    TelegramNotifier.send(header_text, parse_mode="HTML")

    if not picks:
        from app.formatters.vi_alerts import build_no_pick_vi
        TelegramNotifier.send(build_no_pick_vi("EOD"), parse_mode="HTML")
    else:
        # Render buy-alert cho từng mã
        badge = infer_regime_badge(market)
        # Map để lấy ATR và close cho từng ticker ở DATE
        df_day = feat_last.set_index("ticker") if "ticker" in feat_last.columns else pd.DataFrame()
        for t in picks:
            row = df_day.loc[t] if not df_day.empty and t in df_day.index else None
            if row is None or row.empty:
                # fallback tìm trong data gốc
                row = data[(data["ticker"] == t) & (data["time"] == target_date)]
                if not row.empty:
                    row = row.iloc[0]
            entry, tp, sl = compute_entry_tp_sl(row)
            atr_val = float(row.get("atr_14", np.nan)) if row is not None else None
            # RR
            rr = (tp - entry) / max(1e-9, entry - sl)
            # Gửi BUY alert
            msg = build_buy_alert_vi(
                ts=date_str,       # timestamp string
                t=t,               # ticker
                badge=badge,       # bull/sideway/bear
                entry=entry,
                tp=tp,
                sl=sl,
                atr=atr_val,
                rr=rr,
                score=float(row.get("score", np.nan)) if row is not None and "score" in row else None
            )
            TelegramNotifier.send(msg, parse_mode="HTML")

    # 4) SELL alerts cho các vị thế mở trước DATE
    state = load_state()
    positions_raw = state.get(STATE_KEY, {})
    positions: Dict[str, Position] = {}
    for k, v in positions_raw.items():
        try:
            p = Position.from_dict(v)
            # chỉ xét các lệnh có entry_date < DATE
            if pd.to_datetime(p.entry_date) < target_date:
                positions[p.ticker] = p
        except Exception:
            continue

    # Build OHLC map của DATE để check nhanh
    day_bars = (
        data[data["time"] == target_date]
        .set_index("ticker")[["open","high","low","close"]]
        .to_dict(orient="index")
    )

    to_remove = []
    to_update = {}
    for t, pos in positions.items():
        bar = day_bars.get(t)
        if not bar:
            continue
        bar_s = pd.Series(bar)
        signal = evaluate_sell_signal_for_bar(pos, bar_s, date_str)
        if signal:
            # Gửi SELL alert
            sell_msg = build_sell_alert_vi(date_str, pos, signal)
            TelegramNotifier.send(sell_msg, parse_mode="HTML")

            # Cập nhật/đóng vị thế
            if signal["type"] in ("SL_GAP", "SL", "TP_FULL", "TRAIL"):
                # đóng toàn bộ
                to_remove.append(t)
            elif signal["type"] in ("TP_GAP", "TP_PARTIAL"):
                # giữ lại vị thế đã cập nhật (đánh dấu partial, nâng TP/SL/trailing)
                to_update[t] = pos.to_dict()

    # 5) MUA mới trong ngày: lưu thêm vào state để ngày sau có thể đánh giá SELL
    #    (chỉ thêm nếu chưa có trong positions)
    for t in picks:
        if t in positions_raw:
            continue
        # ghi vị thế ban đầu
        row = day_bars.get(t)
        if not row:
            # fallback từ feat_last
            if not feat_last.empty and t in feat_last["ticker"].values:
                r = feat_last[feat_last["ticker"] == t].iloc[0]
                entry, tp, sl = compute_entry_tp_sl(r)
                ohlc_close = float(r.get("close", entry))
            else:
                continue
        else:
            r = pd.Series(row)
            # dùng close để set entry nhất quán với backtest (entry_mode='close')
            # atr lấy từ feat_last (nếu có)
            fr = feat_last.set_index("ticker").loc[t] if "ticker" in feat_last.columns and t in feat_last["ticker"].values else None
            entry, tp, sl = compute_entry_tp_sl(fr if fr is not None else r)
            ohlc_close = float(r.get("close", entry))

        new_pos = Position(
            ticker=t,
            entry_date=date_str,
            entry_price=float(ohlc_close),
            tp=float(tp),
            sl=float(sl),
            highest=float(ohlc_close),
            partial_taken=False,
            trailing_sl=float(ohlc_close * (1 - TRAILING_STOP_PCT)),
            shares=0,
        )
        to_update[t] = new_pos.to_dict()

    # 6) Ghi state
    # refresh dict
    final_state = positions_raw.copy()
    for t in to_remove:
        final_state.pop(t, None)
    for t, d in to_update.items():
        final_state[t] = d
    state[STATE_KEY] = final_state
    save_state(state)

    print(f"[DONE] Alerts generated for {date_str}. Open positions now: {len(final_state)}")


if __name__ == "__main__":
    main()
