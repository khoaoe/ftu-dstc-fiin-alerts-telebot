# FinLab — Telegram EOD Alert Bot

> Biến chiến lược V12 thành **hệ thống cảnh báo MUA/BÁN** tự động qua Telegram, chạy theo **EOD (End-of-Day)**.

---

## 1) Tính năng chính

* **Cảnh báo MUA (EOD):** lọc cổ phiếu theo **screener V12** đúng ngày giao dịch (chỉ số thị trường, khối lượng, động lượng, MACD…).
* **Cảnh báo BÁN (EOD):** áp logic thoát lệnh **đồng nhất với backtest V12**:
  TP/SL, trailing stop, chốt lời một phần, tối thiểu số ngày nắm giữ (T+2).
* **Gửi Telegram**: thông điệp HTML, định dạng rõ ràng; có tiêu đề phiên, bối cảnh thị trường, R/R, TP/SL tham khảo.
* **Replay theo ngày**: chỉ định `DATE` để “phát lại” cảnh báo MUA/BÁN như tại ngày đó (phục vụ kiểm thử).
* **Backtest có sẵn**: chạy nhanh với `v12.py` để đối chiếu hiệu năng chiến lược.

> **Hiện trạng**: bản triển khai này **EOD-only** (không bật intraday/15’). Có thể mở rộng intraday sau.

---

## 2) Kiến trúc (rút gọn)

```
repo/
├─ app/
│  ├─ jobs/
│  │  ├─ eod_scan.py           # Quét EOD, gửi cảnh báo MUA trong ngày
│  │  └─ alerts_on_date.py     # Replay cảnh báo theo một DATE (MUA/BÁN)
│  ├─ formatters/vi_alerts.py  # Hàm dựng nội dung tin nhắn (HTML)
│  ├─ notifier.py              # TelegramNotifier (gửi message)
│  ├─ state.py                 # Lưu/đọc trạng thái các vị thế đang mở (state.json)
│  └─ fiin_client.py           # Kết nối FiinQuantX hoặc đọc file EOD
├─ data/                       # (tuỳ chọn) EOD .parquet/.csv nếu không gọi API
├─ v12.py                      # Chiến lược V12 + backtest engine
├─ requirements.txt
└─ README.md
```

> Tên file có thể khác nhẹ tùy repo của bạn, nhưng **vai trò các thành phần** vẫn như trên.

---

## 3) Cách cài đặt

### 3.1. Yêu cầu

* Python **3.10+** (khuyến nghị)
* Môi trường 64-bit, pip/venv sẵn sàng

### 3.2. Cài thư viện

```bash
pip install -r requirements.txt
```

### 3.3. Biến môi trường (ENV)

Tạo file `.env` (hoặc export trực tiếp) với các khóa sau:

```dotenv
# FiinQuantX (nếu dùng API trực tiếp)
FIIN_USER=your_email_or_user
FIIN_PASS=your_password

# Telegram
BOT_TOKEN=1234567890:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CHAT_ID=-100xxxxxxxxxx              # Chat/group/channel id
THREAD_ID=0                         # (tuỳ chọn) id topic/thread

# Dữ liệu EOD từ file (nếu KHÔNG gọi API)
DATA_FILE_PATH=/path/to/eod.parquet
```

> **Chỉ cần một nguồn dữ liệu**: hoặc `FIIN_USER/FIIN_PASS` (API), **hoặc** `DATA_FILE_PATH` (file EOD).

---

## 4) Chạy nhanh

### 4.1. Backtest chiến lược (đối chiếu)

```bash
python v12.py
```

Sinh các file log như `portfolio_log.csv`, `trades_log.csv`, `drawdown_log.csv` để tham khảo hiệu năng.

### 4.2. Quét & gửi cảnh báo **EOD hôm nay**

```bash
python app/jobs/eod_scan.py
```

* Lấy dữ liệu EOD mới nhất → tính feature → lọc **picks** theo V12 → **gửi Telegram** 1 tin header (bối cảnh thị trường) + N tin MUA.

### 4.3. Replay cảnh báo theo **một ngày bất kỳ**

```bash
# DATE dạng YYYY-MM-DD; nếu bỏ qua --date, script dùng DEFAULT_DATE trong file
python app/jobs/alerts_on_date.py --date 2025-07-30
```

* **MUA**: chạy screener đúng ngày `DATE`.
* **BÁN**: xét các vị thế đã mua **trước `DATE`** từ `state.json`, áp logic thoát V12 (TP/SL, trailing, partial).

---

## 5) Định dạng tin nhắn Telegram (ví dụ)

**MUA**

```
🟢
<b>[2025-07-30] Cảnh báo MUA: CTG</b>
• Regime thị trường: <b>bull</b>
• Giá vào lệnh (tham khảo): <b>39.800</b>
• Chốt lời (TP): 41.500  (≈ +4.3%)
• Cắt lỗ (SL): 38.200  (≈ -4.0%)
• Tỷ lệ R/R: <b>1.08</b>
```

**BÁN**

```
🔴
<b>[2025-08-06] Cảnh báo BÁN: CTG</b>
• Lý do: <b>BÁN CHỐT LỜ (MỘT PHẦN)</b>
• Giá thoát (tham khảo): <b>41.600</b>  (≈ +4.5%)
• Giá vào lệnh: 39.800
• Trailing SL hiện tại: 40.000
• Tỷ lệ R/R (ước lượng): <b>1.10</b>
```

> Nội dung HTML đã được escape; Telegram hiển thị đậm/emoji chuẩn.

---

## 6) Tóm tắt chiến lược V12 (EOD screener & exit)

* **Bối cảnh thị trường** (VN-Index): dùng các biến **`market_*`** (MA50/MA200, RSI, ADX, Bollinger width) để xác định **bull/sideway/bear**.

  * **Bear**: **không vào lệnh**.
  * **Bull**: ưu tiên **động lượng + sức mạnh tương đối**.
  * **Sideway**: ưu tiên **breakout nhẹ + volume spike**.

* **Điều kiện chọn lọc tiêu biểu** (rút gọn):

  * **Bull**: `close_adj > SMA200 > ...`, `RSI 50–80`, `volume_spike > 0.3`, `relative_strength > 1.05`, `short_momentum > 0.01`, `close_adj > SMA5`.
  * **Sideway**: `RSI ~ 48–55`, `boll_width < 0.3`, `macd_histogram > 0`, `volume_spike ≥ 1.0`, `ATR/price > 0.02`, `close_adj ≥ 0.95×SMA50/200`, ưu tiên **độ gần dải Bollinger/SMA**.

* **Xếp hạng `score`** theo bối cảnh (tổ hợp các thước đo ở trên) → lấy **top N** làm watchlist.

* **Quản trị lệnh (thoát)**:

  * **TP/SL cố định theo ATR** từ giá vào (entry=close EOD), kiểm tra gap/open và nội phiên (EOD giả lập).
  * **Trailing stop** cập nhật theo **highest**.
  * **Partial take-profit** (bán một phần ở TP lần 1), nâng TP/SL phù hợp.
  * **Ràng buộc T+2** (nắm giữ tối thiểu trước khi bán).

> Logic trên bám đúng phần **backtest/engine** trong `v12.py`. Tham số mặc định thường thấy: `atr_multiplier≈1.5–2.0`, `trailing_stop_pct≈5%`, `partial_profit_pct≈40%`, `min_holding_days≈2–3`.

---

## 7) Cấu hình & tuỳ biến

* **Danh mục mã**: chỉnh trong config (ví dụ `CFG.tickers`) hoặc ở nơi fetch dữ liệu.
* **Nguồn dữ li
