# -*- coding: utf-8 -*-
"""
vi_alerts.py — Vietnamese Telegram alert formatters (HTML parse_mode)
- Giữ nguyên API cũ: build_buy_alert_vi(), build_eod_header_vi(), build_no_pick_vi()
- Nâng cấp:
  * Escape HTML an toàn hơn
  * Format số/tiền tệ robust (None → '—')
  * Thêm % so với entry + Risk/Reward (RR)
  * Badge theo regime (bull/sideway/bear)
  * Header EOD có thể nhúng tóm tắt thị trường (opt.)
"""
from __future__ import annotations

from html import escape
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any


# ---------- Utils: formatting ----------

def _safe_decimal(x: Any) -> Optional[Decimal]:
    if x is None:
        return None
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError, TypeError):
        return None

def fmt_money(v: Any, digits: int = 2) -> str:
    """
    Format số theo style VN: dùng '.' cho nghìn và ',' cho phần thập phân.
    Hỗ trợ None → '—'
    """
    dv = _safe_decimal(v)
    if dv is None:
        return "—"
    q = Decimal(10) ** -digits
    dv = dv.quantize(q)
    s = f"{dv:,.{digits}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")

def fmt_num(v: Any, digits: int = 2) -> str:
    dv = _safe_decimal(v)
    if dv is None:
        return "—"
    q = Decimal(10) ** -digits
    dv = dv.quantize(q)
    s = f"{dv:.{digits}f}"
    return s.replace(".", ",")

def fmt_pct(v: Any, digits: int = 2) -> str:
    dv = _safe_decimal(v)
    if dv is None:
        return "—"
    dv = dv * Decimal("100")
    q = Decimal(10) ** -digits
    dv = dv.quantize(q)
    s = f"{dv:.{digits}f}%"
    return s.replace(".", ",")


# ---------- Regime badges ----------

_REGIME_BADGE = {
    "bull":    "🟢 BULL",
    "sideway": "🟡 SIDEWAY",
    "bear":    "🔴 BEAR",
}
def _regime_badge(regime: str) -> str:
    return _REGIME_BADGE.get(str(regime).lower(), escape(str(regime)).upper())


# ---------- Public API (backward compatible) ----------

def build_buy_alert_vi(
    ticker: str,
    entry: float,
    tp: float,
    sl: float,
    regime: str = "bull",
    *,
    # Tuỳ chọn bổ sung (không bắt buộc):
    note: Optional[str] = None,          # ghi chú ngắn
    score: Optional[float] = None,       # điểm tín hiệu (nếu bạn có)
    atr: Optional[float] = None,         # ATR hiện hành (nếu muốn show)
    extras: Optional[Dict[str, Any]] = None,  # key/value bổ sung
) -> str:
    """
    Block cảnh báo MUA (HTML). Giữ nguyên 4 tham số đầu để tương thích.
    Bổ sung: note/score/atr/extras (optional).
    """
    t = escape(str(ticker))
    badge = _regime_badge(regime)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Tính % so với entry + RR
    entry_d = _safe_decimal(entry) or Decimal("0")
    tp_d    = _safe_decimal(tp)    or Decimal("0")
    sl_d    = _safe_decimal(sl)    or Decimal("0")

    up_pct = ((tp_d - entry_d) / entry_d) if entry_d != 0 else None
    dn_pct = ((entry_d - sl_d) / entry_d) if entry_d != 0 else None
    rr     = ((tp_d - entry_d) / (entry_d - sl_d)) if (entry_d - sl_d) != 0 else None

    up_pct_s = fmt_pct(up_pct) if up_pct is not None else "—"
    dn_pct_s = fmt_pct(dn_pct) if dn_pct is not None else "—"
    rr_s     = fmt_num(rr, 2)   if rr     is not None else "—"

    lines = [
        "🟢",
        f"<b>[{ts}] Cảnh báo MUA: {t}</b>",
        f"• Regime thị trường: <b>{escape(badge)}</b>",
        f"• Giá vào lệnh (tham khảo): <b>{fmt_money(entry)} VNĐ</b>",
        f"• Chốt lời (TP): {fmt_money(tp)} VNĐ  (≈ {up_pct_s})",
        f"• Cắt lỗ (SL): {fmt_money(sl)} VNĐ  (≈ {dn_pct_s})",
        f"• Tỷ lệ R/R: <b>{rr_s}</b>",
    ]

    if atr is not None:
        lines.append(f"• ATR(14): {fmt_money(atr)}")

    if score is not None:
        lines.append(f"• Điểm tín hiệu: {fmt_num(score, 2)}")

    # Extras: in theo dạng "• key: value"
    if extras:
        for k, v in extras.items():
            k_s = escape(str(k)).strip()
            v_s = escape(str(v)).strip()
            if k_s and v_s:
                lines.append(f"• {k_s}: {v_s}")

    if note:
        lines.append(f"📝 {escape(note)}")

    lines += [
        "",
        "⚠️ <i>Lưu ý: Đây là cảnh báo tham khảo, không phải lời khuyên đầu tư.</i>",
    ]
    return "\n".join(lines)


def build_eod_header_vi(
    *,
    market: Optional[Dict[str, Any]] = None,   # ví dụ: {"Close": 1245, "RSI": 58.3, ...}
    date_str: Optional[str] = None,            # nếu muốn chủ động truyền ngày
) -> str:
    """
    Header cho EOD. Có thể nhúng tóm tắt thị trường (optional).
    market: dict các chỉ số market_* sẽ được render gọn phía dưới.
    """
    ts = date_str or datetime.now().strftime("%Y-%m-%d")
    header = [f"<b>📊 [EOD {ts}] V12 Picks</b>"]

    if market:
        # Render gọn các chỉ số chính (nếu có)
        mk = []
        def add(label: str, key: str, digits=2, suffix=""):
            val = market.get(key)
            if val is not None:
                if suffix == "%":
                    mk.append(f"{label}: {fmt_pct(val, digits)}")
                else:
                    mk.append(f"{label}: {fmt_num(val, digits)}")
        # Gợi ý: truyền vào market_close, market_rsi, market_adx, market_boll_width
        add("Close", "market_close", 2, "")      # số điểm
        add("RSI", "market_rsi", 2, "")          # 0-100
        add("ADX", "market_adx", 2, "")          # 0-100
        add("BW", "market_boll_width", 2, "")    # tuỳ thang của bạn
        if mk:
            header.append("• " + " | ".join(mk))
    return "\n".join(header)


def build_no_pick_vi(scope: str = "EOD") -> str:
    tag = "EOD" if (scope or "").upper() == "EOD" else "Realtime"
    ts = datetime.now().strftime("%Y-%m-%d")
    return f"<b>📈 [{tag} {ts}]</b> Không có mã nào đạt filter trong phiên này."