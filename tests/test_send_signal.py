# tests/test_send_signal.py
import os, sys
# giả sử tests/ nằm tại same-level với app/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.jobs.eod_scan import run_eod_scan

if __name__ == "__main__":
    print("Run EOD scan test → gửi tín hiệu nếu có mã đáp filter …")
    run_eod_scan()
    print("Done.")