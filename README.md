# FinLab Signal Bot

Bot Telegram gửi cảnh báo tín hiệu từ chiến lược V12 trên dữ liệu FiinQuantX – gồm EOD (snapshot) và 15’ realtime (callback).\
Yêu cầu Python 3.11+.

## Cài đặt

Khuyến nghị tạo môi trường ảo riêng để tách biệt phụ thuộc:

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Windows CMD
.venv\Scripts\activate.bat
# macOS/Linux
source .venv/bin/activate
```

Sau khi kích hoạt môi trường ảo, cài đặt thư viện FiinQuantX và các phụ thuộc còn lại:

```bash
pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
# to update FiinQuantX
pip install --upgrade --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
pip install -r requirements.txt
cp .env.example .env  # điền thông tin
```

## Chạy

```bash
bash scripts/run_local.sh
```

## Tích hợp V12

* Thả `v12.py` (bản chuẩn) vào root repo hoặc thêm vào PYTHONPATH.
* Adapter gọi các hàm: `precompute_technical_indicators_vectorized(df)` và `apply_enhanced_screener_v12(feat)`.

## Lịch chạy

* EOD: 15:01 (T2–T6)
* Intraday 15’: mở 09:00, đóng 15:00

## Ghi chú

* EOD là confirm; 15’ là early signal. Tôn trọng hạn mức Telegram nếu cần gom batch.
