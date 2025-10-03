# app/jobs/eod_scan.py
from ..fiin_client import get_client
from ..config import CFG
from ..notifier import TelegramNotifier
from ..strategy_adapter import compute_features_v12, apply_v12_on_last_day
from ..formatters.vi_alerts import build_eod_header_vi, build_buy_alert_vi, build_no_pick_vi

import pandas as pd


def run_eod_scan():
    client = get_client()
    data = client.Fetch_Trading_Data(
        realtime=False,
        tickers=list(CFG.tickers),
        fields=['open','high','low','close','volume','bu','sd','fb','fs','fn'],
        adjusted=True,
        by='1d',
        period=260
    ).get_data()
    
    feat = compute_features_v12(data)

    # Ưu tiên 'date' (adapter đã chuẩn hoá). Fallback sang 'time'/'timestamp' nếu cần.
    if 'date' in feat.columns:
        ts_series = pd.to_datetime(feat['date'])
    elif 'time' in feat.columns:
        ts_series = pd.to_datetime(feat['time'])
    elif 'timestamp' in feat.columns:
        ts_series = pd.to_datetime(feat['timestamp'])
    else:
        TelegramNotifier.send(build_no_pick_vi('EOD'), parse_mode="HTML")
        return
    last_ts = ts_series.max()
    feat_last = feat[ts_series == last_ts].copy()

    picks = apply_v12_on_last_day(feat)
    if getattr(CFG, "exclude_tickers", None):
        exclude = {t.strip().upper() for t in CFG.exclude_tickers if isinstance(t, str)}
        picks = [p for p in picks if p.upper() not in exclude]

    if not picks:
        TelegramNotifier.send(build_no_pick_vi('EOD'), parse_mode="HTML")
        return

    metrics_row = feat_last.iloc[0] if not feat_last.empty else {}

    def _as_float(value):
        try:
            return float(value)
        except Exception:
            return None

    def _metric(key):
        if isinstance(metrics_row, dict):
            value = metrics_row.get(key)
        else:
            value = metrics_row.get(key, None)
        return _as_float(value)

    market_close = _metric('market_close') if 'market_close' in feat_last.columns else None
    market_ma50 = _metric('market_MA50') if 'market_MA50' in feat_last.columns else None
    market_ma200 = _metric('market_MA200') if 'market_MA200' in feat_last.columns else None
    market_rsi = _metric('market_rsi') if 'market_rsi' in feat_last.columns else None
    market_adx = _metric('market_adx') if 'market_adx' in feat_last.columns else None
    market_boll_width = _metric('market_boll_width') if 'market_boll_width' in feat_last.columns else None

    is_bull = all(v is not None for v in (market_close, market_ma50, market_ma200, market_rsi)) and market_close > market_ma50 and market_close > market_ma200 and market_rsi > 55
    is_sideway = all(v is not None for v in (market_adx, market_boll_width, market_rsi)) and market_adx < 25 and market_boll_width < 0.35 and 35 <= market_rsi <= 60
    regime_label = 'bull' if is_bull else ('sideway' if is_sideway else 'bear')
    atr_multiplier = 2.0 if is_bull else (1.2 if is_sideway else 2.2)

    ticker_col = 'ticker' if 'ticker' in feat_last.columns else None

    blocks = [build_eod_header_vi()]
    for ticker in picks:
        entry = 0.0
        tp = 0.0
        sl = 0.0
        if ticker_col:
            match = feat_last[feat_last[ticker_col].astype(str).str.upper() == ticker.upper()]
            if not match.empty:
                row = match.iloc[0]
                # Ưu tiên giá đã điều chỉnh
                entry_val = row.get('close_adj') or row.get('close') or 0.0
                atr_val = row.get('atr_14') or 0.0
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
        blocks.append(build_buy_alert_vi(ticker, entry, tp, sl, regime_label))

    # Gửi theo từng đoạn để an toàn giới hạn 4096 ký tự của Telegram
    TelegramNotifier().send_chunks("\n\n".join(blocks), parse_mode="HTML")
