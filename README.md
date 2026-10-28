# Sổ Chi Tiêu AI

Ứng dụng web quản lý thu nhập, chi tiêu, ngân sách và mục tiêu tiết kiệm cá nhân. Trợ lý AI phân tích số liệu của tài khoản đang đăng nhập. Ứng dụng dùng Python standard library và SQLite, không cần cài framework hay thư viện ngoài.

## Chạy trên Windows

1. Cài Python 3.10 trở lên.
2. Giải nén thư mục dự án.
3. Mở PowerShell tại thư mục `expense-ai`.
4. Chạy:

   ```powershell
   python app.py
   ```

5. Mở trình duyệt tại `http://127.0.0.1:8000`.
6. Đăng nhập demo: **binh** / **Demo@12345**. Có thể tạo tài khoản riêng ở mục “Tạo tài khoản”.

Lần chạy đầu tiên, ứng dụng tự tạo `data/expense_ai.db` và nạp vài giao dịch mẫu cho tài khoản demo. Dữ liệu tài khoản mới được lưu riêng theo `user_id`.

## Chạy bằng Docker Desktop

1. Cài Docker Desktop cho Windows, mở ứng dụng và chờ trạng thái báo đang chạy.
2. Mở PowerShell tại thư mục `expense-ai`.
3. Tạo file cấu hình riêng: `Copy-Item .env.example .env`.
4. Mở file bằng Notepad: `notepad .env`. Nếu muốn dùng AI trực tuyến, dán API key sau `AI_API_KEY=`. Lưu rồi đóng Notepad. Không gửi file `.env` cho người khác.
5. Tạo và khởi chạy ứng dụng: `docker compose up --build -d`.
6. Mở `http://localhost:8000` trong trình duyệt. Tài khoản demo: **binh** / **Demo@12345**.

Docker lưu cơ sở dữ liệu trong volume `expense_data`, nên dữ liệu vẫn còn sau khi dừng container. Xem log bằng `docker compose logs -f`; dừng ứng dụng bằng `docker compose down`. Tránh dùng `docker compose down -v` nếu cần giữ dữ liệu, vì lệnh đó xóa volume.

## Chức năng

- Đăng nhập, tạo tài khoản và đăng xuất; mật khẩu được băm bằng PBKDF2-HMAC-SHA256.
- CRUD giao dịch thu/chi: thêm, xem, sửa, xóa; lọc theo tháng, loại và từ khóa.
- CRUD danh mục thu/chi; tự thêm danh mục mới khi ghi giao dịch; ngăn xóa danh mục đang được dùng.
- Dashboard: tổng thu, tổng chi, số dư, biểu đồ dòng tiền, cơ cấu danh mục, giao dịch mới và cảnh báo vượt hạn mức.
- Biểu đồ xu hướng thu chi theo 12 tháng của năm được chọn.
- Ngân sách theo tháng và danh mục; xem phần đã dùng và cảnh báo trực quan khi vượt hạn mức.
- Mục tiêu tiết kiệm: số tiền đích, số đã tích lũy và tiến độ.
- AI phân tích tổng thu/chi, danh mục chi, tình trạng ngân sách; trả lời câu hỏi tự nhiên và đưa gợi ý.
- Giao diện responsive, thông báo lỗi, xác thực dữ liệu ở máy chủ và bảo vệ phiên cập nhật bằng CSRF token.

## Chế độ AI

Mặc định, chức năng AI chạy ở **chế độ demo ngoại tuyến** bằng quy tắc phân tích dữ liệu có sẵn. Chế độ này phù hợp để trình diễn khi phòng thi không có Internet hoặc chưa cấu hình API key.

Để gọi DeepSeek thật khi chạy trực tiếp bằng Python, đặt biến môi trường trong PowerShell trước khi chạy ứng dụng. API key chỉ được đọc ở backend và không gửi về trình duyệt:

```powershell
$env:AI_API_KEY="dán-api-key-của-bạn-vào-đây"
$env:AI_BASE_URL="https://api.deepseek.com/chat/completions"
$env:AI_MODEL="deepseek-flash"
python app.py
```

Không đưa API key vào mã nguồn, GitHub, ảnh chụp màn hình hoặc báo cáo. API trực tuyến cần mạng và tính phí theo mức sử dụng. Nếu gọi API lỗi hoặc quá thời gian, ứng dụng chuyển sang phần phân tích dự phòng. Không nhập thông tin đăng nhập ngân hàng, số thẻ hay dữ liệu nhạy cảm vào ghi chú.

## Dữ liệu và sao lưu

- CSDL SQLite: `data/expense_ai.db`.
- Sao lưu: dừng ứng dụng, copy file CSDL ra vị trí an toàn.
- Khôi phục: dừng ứng dụng rồi chép file sao lưu vào lại thư mục `data`.
- Xóa dữ liệu demo: xóa `data/expense_ai.db`, ứng dụng tạo lại dữ liệu mẫu khi chạy lần kế tiếp.

## Kịch bản kiểm tra thủ công

1. Đăng nhập bằng tài khoản demo; mở dashboard và đối chiếu tổng thu/chi với các giao dịch mẫu.
2. Thêm một khoản chi, lọc theo tháng và từ khóa; sửa số tiền rồi xóa giao dịch.
3. Thêm một khoản thu và kiểm tra số dư trên dashboard.
4. Tạo ngân sách cho một danh mục; thêm khoản chi làm vượt hạn mức và xem tiến độ ngân sách.
5. Tạo mục tiêu tiết kiệm, cập nhật số đã tích lũy và xem phần trăm hoàn thành.
6. Mở Trợ lý AI, tạo phân tích; hỏi “Tháng này tôi chi nhiều nhất vào đâu?” và đối chiếu với danh mục trên dashboard.
7. Tạo tài khoản thứ hai, đăng nhập và xác nhận tài khoản mới không xem được dữ liệu của tài khoản demo.
8. Thử để trống danh mục hoặc nhập số tiền âm; ứng dụng phải báo lỗi và không lưu dữ liệu sai.
9. Đăng xuất rồi truy cập lại chức năng dữ liệu; ứng dụng yêu cầu đăng nhập.

## Chia việc nhóm 2 người

| Thành viên | Phần phụ trách | Bằng chứng có thể trình bày |
|---|---|---|
| **Bùi Ngọc Bình** | Phân tích nghiệp vụ; thiết kế SQLite và API; đăng nhập, phân quyền theo tài khoản; xử lý thu/chi, ngân sách, mục tiêu; tích hợp AI phía máy chủ và bảo vệ API key. | Sơ đồ dữ liệu, các endpoint, phần xử lý trong `app.py`, luồng gọi AI và ví dụ dữ liệu. |
| **Nguyễn Ngọc Lương** | Giao diện web và trải nghiệm người dùng; dashboard, biểu đồ, form giao dịch, ngân sách, mục tiêu, màn AI; kiểm thử thủ công các luồng chính; hướng dẫn chạy và chuẩn bị dữ liệu demo. | Các màn hình trên trình duyệt, luồng thao tác, các trường hợp nhập hợp lệ/sai và tài liệu chạy. |

Cả hai cùng rà soát yêu cầu, chạy ứng dụng, kiểm tra kết quả AI và chuẩn bị demo. Khi làm bài thật, mỗi người cần hiểu được luồng tổng thể để trả lời câu hỏi của giảng viên.

## Phạm vi trình diễn và giới hạn

Ứng dụng hiện chạy cục bộ trên `127.0.0.1:8000`, phù hợp demo trên cùng máy. Muốn người khác truy cập qua mạng cần cấu hình host, tường lửa và triển khai riêng. Phiên bản này là sản phẩm học phần, chưa có HTTPS, khôi phục mật khẩu, phân quyền nhiều cấp hoặc triển khai production.
