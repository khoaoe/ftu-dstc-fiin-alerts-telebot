# FinLab Signal Bot

Bot Telegram gửi cảnh báo tín hiệu từ chiến lược V12 trên dữ liệu FiinQuantX – gồm EOD (snapshot) và 15’ realtime (callback).\
Yêu cầu Python 3.11+.

## Cài đặt (local)
```bash
pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
pip install -r requirements.txt
cp .env.example .env  # điền thông tin
```

Trong `.env`, đặt `DATA_FILE_PATH` trỏ tới file dữ liệu (vd .parquet/.csv) mà V12 sử dụng khi bạn chạy backtest trực tiếp trong `v12.py`.

## Chạy

```bash
bash scripts/run_local.sh
```

## Tích hợp V12

* Thả `v12.py` (bản chuẩn) vào root repo hoặc thêm vào PYTHONPATH.
* Adapter gọi các hàm: `precompute_technical_indicators_vectorized(df)` và `apply_enhanced_screener_v12(feat)`.
* Đảm bảo `v12.py` đọc `DATA_FILE_PATH` từ ENV và chỉ chạy backtest khi `__name__ == "__main__"`.

## Lịch chạy

* EOD: 15:01 (T2–T6)
* Lịch có thể cấu hình qua `.env`:
  - `TIMEZONE` (mặc định `Asia/Ho_Chi_Minh`, sử dụng `ZoneInfo`)
  - `EOD_HOUR` (mặc định `15`) và `EOD_MINUTE` (mặc định `5`)
  - `OPEN_HOUR` (mặc định `9`) và `CLOSE_HOUR` (mặc định `15`)
* Intraday 15’: mở 09:00, đóng 15:00

## Chạy bằng Docker

```bash
docker build --build-arg FQ_VERSION="fiinquantx" -t finlab-signal-bot .
docker run --env-file .env --name finlab-bot finlab-signal-bot
```

> `fiinquantx` không có trong requirements, Dockerfile đã cài bằng extra index theo build arg `FQ_VERSION`.

## Ghi chú

* EOD là confirm; 15’ là early signal. Tôn trọng hạn mức Telegram nếu cần gom batch.

