# Hướng dẫn Binance Crypto Pipeline

## Bắt đầu

Mở riêng thư mục `binance_crypto_pipeline` trong VS Code. Bộ tải về đã có raw JSON thật và đầu ra đã xử lý, không cần tải raw lần đầu để xem dữ liệu.

- Mở `data/bronze/20261101T090959Z_8cf668e6/BTCUSDT_0001.json`: đây là toàn bộ nội dung trang đầu Binance trả về, không phải dữ liệu tự sinh.
- Mở `data/current.json` để biết Silver và Gold hiện đang ở thư mục nào.
- Mở file `mart_daily.csv` trong đường dẫn Gold để xem kết quả theo ngày.
- Mở `evidence/overview.png` để xem biểu đồ thực tế.

## Bronze

Lưu JSON đúng nội dung API trả về. Mỗi trang có 12 trường theo thứ tự Binance công bố: thời gian mở, open/high/low/close, volume, thời gian đóng, quote volume, số giao dịch, taker buy base/quote và trường bỏ qua. Không đổi JSON raw thành CSV rồi gọi nó là raw gốc.

## Silver

Chuẩn hóa UTC, số giao dịch và số thập phân; kiểm tra high/low, volume, khoảng thời gian và khóa trùng. Khóa là `(symbol, open_time)`. Ghi lỗi vào quarantine và chặn xuất bản nếu thiếu phút hoặc có dòng không đạt.

## Gold

Gom 60 nến phút thành nến giờ và 1.440 nến phút thành nến ngày. Tính OHLC, volume, số giao dịch, VWAP và tỷ lệ taker mua. Đối chiếu tổng volume và số giao dịch giữa Silver và Gold. Đơn vị quote là USDT.

## Chạy lại

Tạo venv Python 3.11, cài requirements rồi chạy `python run.py build --run-id 20261101T090959Z_8cf668e6`. Đây là replay offline từ raw đã tải. Chạy `python run.py run` để gọi Binance lại. Chạy `python verify_integration.py` để kiểm tra lỗi trước khi publish, chạy lại không trùng và raw không bị thay đổi.

Dữ liệu đi kèm: 3 cặp, từ 01/01/2025 đến hết 07/01/2025 UTC. Đây là batch lịch sử, chưa phải streaming giây/phút liên tục. Trình bày trên CV theo đúng phạm vi này.
