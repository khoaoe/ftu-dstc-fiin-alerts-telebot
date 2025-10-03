# -*- coding: utf-8 -*-
from html import escape


_BULLET = chr(0x1F7E2)


def fmt_money(v: float) -> str:
    """Format so theo style VN: dung "." cho nghin va "," cho thap phan (2 chu so)."""
    try:
        return f"{v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    except Exception:
        return f"{v}"


def build_buy_alert_vi(ticker: str, entry: float, tp: float, sl: float, regime: str = "bull") -> str:
    """Block canh bao MUA theo dinh dang tieng Viet."""
    t = escape(str(ticker))
    regime_txt = escape(str(regime))
    lines = [
        _BULLET,
        f"<b>Thiet lap Canh bao MUA co phieu {t}</b>",
        f"- Dieu kien Mua: Co phieu vuot qua bo loc v12 trong thi truong '{regime_txt}'.",
        f"- Gia vao lenh (tham khao): {fmt_money(entry)}",
        f"- Chot loi (TP) ban dau: {fmt_money(tp)}",
        f"- Cat lo (SL) ban dau: {fmt_money(sl)}",
    ]
    return "\n".join(lines)


def build_eod_header_vi() -> str:
    return "<b>[EOD] V12 picks</b>"


def build_no_pick_vi(scope: str = "EOD") -> str:
    tag = "EOD" if (scope or "").upper() == "EOD" else "Realtime"
    return f"<b>[{tag}]</b> Khong co ma dat filter."
