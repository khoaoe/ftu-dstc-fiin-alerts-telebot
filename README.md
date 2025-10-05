# 🤖 FinLab - Telegram EOD Alert Bot

> 🌟 Biến chiến lược V12 thành **hệ thống cảnh báo MUA/BÁN** tự động qua **Telegram**, chạy theo **EOD (End-of-Day)**.

---

## 1️⃣ 🚀 Tính năng chính

* 🟢 **Cảnh báo MUA (EOD):** lọc cổ phiếu theo **screener V12** đúng ngày giao dịch.
* 🔴 **Cảnh báo BÁN (EOD):** áp logic thoát lệnh **đồng nhất với backtest V12**: TP/SL, trailing stop, partial take-profit, tối thiểu **T+2**.
* 💬 **Gửi Telegram:** thông điệp HTML đẹp, rõ, có **R/R**, **TP/SL**, **market regime**.
* ⏳ **Replay:** chỉ định `DATE` để chạy lại cảnh báo MUA/BÁN đúng như phiên đó.
* 📊 **Backtest sẵn:** dùng `v12.py` để kiểm chứng hiệu năng chiến lược.

---

## 2️⃣ 🧩 Kiến trúc (rút gọn)

```
repo/
├─ app/
│  ├─ jobs/
│  │  ├─ eod_scan.py           # Quét EOD, gửi cảnh báo MUA
│  │  └─ alerts_on_date.py     # Replay cảnh báo theo DATE (MUA/BÁN)
│  ├─ formatters/vi_alerts.py  # Định dạng tin nhắn HTML
│  ├─ notifier.py              # Gửi Telegram
│  ├─ state.py                 # Quản lý file state.json (vị thế mở)
│  └─ fiin_client.py           # Kết nối FiinQuantX / đọc dữ liệu file
├─ data/                       # (tuỳ chọn) File .csv/.parquet EOD
├─ v12.py                      # Chiến lược V12 + backtest engine
└─ README.md
```

---

## 3️⃣ ⚙️ Cài đặt nhanh

### 🧰 Yêu cầu

* Python **3.10+**
* Pip/venv đầy đủ

### 📦 Cài thư viện

```bash
pip install -r requirements.txt
```

### ⚙️ Biến môi trường `.env`

```dotenv
# 🔑 FiinQuantX (nếu dùng API)
FIIN_USER=your_email
FIIN_PASS=your_password

# 💬 Telegram
BOT_TOKEN=1234567890:xxxx
CHAT_ID=-100xxxxxxxxx
THREAD_ID=0  # tuỳ chọn

# 💾 Dữ liệu EOD từ file (nếu KHÔNG dùng API)
DATA_FILE_PATH=/path/to/eod.parquet
```

> 🔔 Chỉ cần **một nguồn dữ liệu**: API **hoặc** file data chuẩn bị trước.

---

## 4️⃣ 🧠 Cách sử dụng

* **Backtest chiến lược:**

  ```bash
  python v12.py
  ```
* **Quét & gửi cảnh báo EOD hôm nay:**

  ```bash
  python app/jobs/eod_scan.py
  ```
* **Replay cảnh báo theo ngày:**

  ```bash
  python app/jobs/alerts_on_date.py --date 2025-07-30
  ```

---

## 5️⃣ ✉️ Mẫu tin nhắn Telegram

**MUA**

```
🟢
<b>[2025-07-30] Cảnh báo MUA: CTG</b>
• Regime: <b>bull</b>
• Entry: <b>39.800</b>
• TP: 41.500  (≈ +4.3%)
• SL: 38.200  (≈ -4.0%)
• R/R: <b>1.08</b>
```

**BÁN**

```
🔴
<b>[2025-08-06] Cảnh báo BÁN: CTG</b>
• Lý do: <b>TP partial / SL / trailing</b>
• Giá thoát: <b>41.600</b> (≈ +4.5%)
• Entry: 39.800 | Trailing SL: 40.000
```

---

## 6️⃣ 📊 Tóm tắt chiến lược V12

* 📈 **Regime thị trường** (VNINDEX): xác định bull / sideway / bear qua `market_*` (MA50/200, RSI, ADX, BollWidth).
* 🎯 **Screener:** ưu tiên động lượng, volume spike, sức mạnh tương đối và vị trí kỹ thuật.
* 🧮 **Quản trị lệnh:** entry = close EOD; TP/SL theo ATR, trailing stop từ highest, partial take-profit lần 1, giữ tối thiểu T+2.

---

## 7️⃣ ⚙️ Cấu hình & Tuỳ biến

* 🧾 **Danh mục mã giao dịch**: chỉnh trong `config.py` (ví dụ `CFG.tickers`) hoặc trong nơi fetch dữ liệu.
* 🌐 **Nguồn dữ liệu**:

  * ☁️ **FiinQuantX API** — khuyến nghị dùng trong môi trường vận hành thực tế.
  * 💾 **File EOD (.parquet / .csv)** — dùng cho kiểm thử hoặc replay offline.
* ⚙️ **Tham số chiến lược (Strategy Params)**:

  * `atr_multiplier`: hệ số ATR để tính TP/SL (mặc định ~1.5–2.0)
  * `trailing_stop_pct`: % trailing stop (mặc định 5%)
  * `partial_profit_pct`: tỉ lệ chốt lời một phần (mặc định 40%)
  * `min_holding_days`: số ngày nắm giữ tối thiểu (T+2/T+3)
* 💬 **Telegram Config**:

  * `BOT_TOKEN`, `CHAT_ID`, `THREAD_ID` đặt trong `.env`
  * Có thể gửi tới nhóm, channel hoặc topic riêng.
* 📂 **Lưu trạng thái (state)**:

  * File `state.json` chứa các vị thế đang mở (mã, ngày mua, giá, TP/SL…)
  * Được cập nhật tự động sau mỗi phiên `alerts_on_date.py`

💡 *Tip:* Có thể duy trì nhiều `state_*.json` để tách danh mục theo chiến lược hoặc tài khoản.

---

## 8️⃣ 🧩 Lỗi & Khắc phục

| ⚠️ Tình huống                            | 💡 Nguyên nhân                                | 🔧 Cách xử lý                                                |
| ---------------------------------------- | --------------------------------------------- | ------------------------------------------------------------ |
| 🧱 Thiếu cột `market_MA200`, `rsi_14`, … | Feature chưa tính đủ                          | Rà lại bước `compute_features_v12` hoặc cập nhật adapter     |
| ⏰ `Input data missing 'date' column`     | Dữ liệu không có trường thời gian             | Đổi tên cột `time` → `date` hoặc chuẩn hóa kiểu `datetime64` |
| 📉 Không có tín hiệu MUA                 | Thị trường `bear` hoặc điều kiện lọc quá chặt | Kiểm tra chế độ thị trường và tiêu chí lọc trong screener    |
| 🚫 Bot không gửi tin                     | Lỗi token hoặc chat ID                        | Kiểm tra `BOT_TOKEN`, `CHAT_ID`, và quyền của bot trong nhóm |
| 🧩 Sai định dạng HTML                    | Escape ký tự đặc biệt chưa đúng               | Dùng hàm `escape()` sẵn trong `vi_alerts.py`                 |

---

## 9️⃣ 🚀 Hướng phát triển

* 🔁 Bổ sung **intraday 15’** (FiinQuant realtime + callback streaming).
* 📊 Dashboard **Streamlit** hiển thị danh mục, watchlist, R/R.
* 💼 Quản trị rủi ro nâng cao: position sizing, vault profit, calendar filter.
* 🧾 Báo cáo ngày tự động: tổng hợp tín hiệu, hiệu suất, sổ lệnh.

---

## 🔟 © Bản quyền & Ghi công

* 🧠 Mã nguồn chiến lược/backtest trong `v12.py` và các job Telegram thuộc nhóm tác giả repo này.
* 📦 Dữ liệu và SDK từ **FiinQuantX** thuộc bản quyền của **FiinGroup**; người dùng cần tuân thủ điều khoản dịch vụ tương ứng.

---

## 1️⃣1️⃣ 🧭 Lệnh nhanh tham khảo

```bash
# ⚙️ Tạo môi trường & cài thư viện
python -m venv .venv
source .venv/bin/activate   # hoặc .venv\Scripts\activate (Windows)
pip install -r requirements.txt

# 🧮 Backtest chiến lược
python v12.py

# 🔔 Quét & gửi cảnh báo EOD hôm nay
python app/jobs/eod_scan.py

# ⏱️ Replay tín hiệu theo ngày cụ thể
python app/jobs/alerts_on_date.py --date 2025-07-30
```

---

> 🧭 *FiinQuant V12 Bot – chính xác, gọn
