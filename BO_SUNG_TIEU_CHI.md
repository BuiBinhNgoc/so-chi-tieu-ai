# Chuẩn bị theo tiêu chí chấm của cô Nguyễn Thị Tuyển

Tài liệu này là kế hoạch thực hiện và mẫu ghi kết quả; các ô chưa ghi phải được nhóm chạy thực tế và điền, không trình bày là kết quả đã đạt.

## 1. Phân tích và thiết kế
- Bài toán: quản lý thu chi cá nhân, hỗ trợ theo dõi ngân sách và phân tích số liệu bằng AI.
- Tác nhân: người dùng đăng ký, đăng nhập, quản lý dữ liệu của mình. Phân quyền hiện tại là cách ly dữ liệu theo tài khoản, không có vai trò quản trị viên riêng.
- Kiến trúc: trình duyệt → máy chủ Python (xác thực, nghiệp vụ, tổng hợp dữ liệu) → SQLite; máy chủ gọi API AI khi được cấu hình, còn lỗi thì dùng phân tích theo quy tắc.
- AI nằm sau bước tổng hợp dữ liệu, để diễn giải và gợi ý; số liệu cần đối chiếu với giao dịch, không mặc định tin câu trả lời AI.
- Trong báo cáo cần vẽ sơ đồ kiến trúc và sơ đồ CSDL dựa trên mã nguồn thực tế.

## 2. Bảng kiểm thử thực nghiệm
Ghi ngày chạy, người thực hiện, kết quả thực tế và ảnh minh chứng. Không đánh dấu đạt trước khi thử.

| Mã | Thao tác | Kết quả mong đợi | Kết quả thực tế/ảnh |
|---|---|---|---|
| T01 | Đăng nhập đúng tài khoản demo | Vào màn hình tổng quan | Chưa ghi |
| T02 | Nhập sai mật khẩu | Báo lỗi, không đăng nhập | Chưa ghi |
| T03 | Tạo giao dịch số tiền hợp lệ | Giao dịch xuất hiện, tổng thay đổi | Chưa ghi |
| T04 | Nhập số tiền âm hoặc để trống dữ liệu bắt buộc | Báo lỗi, không lưu | Chưa ghi |
| T05 | Thử số tiền bằng 0, ngày đầu/cuối tháng | Ghi nhận thực tế và so sánh quy tắc kiểm tra | Chưa ghi |
| T06 | Tạo ngân sách rồi nhập chi tiêu vượt mức | Hiện thông tin vượt ngân sách | Chưa ghi |
| T07 | Tạo tài khoản thứ hai | Không xem được giao dịch tài khoản thứ nhất | Chưa ghi |
| T08 | Hỏi AI danh mục chi nhiều nhất | Đối chiếu với tổng chi theo danh mục | Chưa ghi |
| T09 | Dùng API key sai hoặc ngắt mạng | Hiển thị chế độ dự phòng và hệ thống tiếp tục chạy | Chưa ghi |
| T10 | Khởi động lại Docker | Kiểm tra dữ liệu còn trong volume | Chưa ghi |

## 3. So sánh hai phiên bản prompt
Thử cùng mô hình, cùng dữ liệu giả lập và cùng câu hỏi. Chép đầu ra thực tế, thời điểm, model, dữ liệu đầu vào, thời gian, số đúng/sai và ảnh minh chứng. Không dùng thông tin tài chính thật hoặc API key trong minh chứng.

- Prompt A: “Hãy phân tích chi tiêu tháng này và gợi ý ngân sách.”
- Prompt B: “Bạn là trợ lý quản lý chi tiêu. Chỉ sử dụng dữ liệu JSON được cung cấp. Nêu tổng thu, tổng chi, danh mục chi lớn nhất và gợi ý ngân sách. Không bịa số; nếu thiếu dữ liệu hãy nói rõ. Trả lời ngắn bằng tiếng Việt.”
- Dữ liệu thử: tháng 2026-10; thu 12.000.000 đồng; chi ăn uống 300.000 đồng, đi lại 160.000 đồng; tổng chi 460.000 đồng. Câu hỏi: “Tháng này tôi chi nhiều nhất vào đâu?”
- Đáp án đối chiếu: ăn uống 300.000 đồng. Cả hai phiên bản cần chạy thực tế; bảng dưới chưa có kết quả.

| Tiêu chí | Prompt A | Prompt B |
|---|---|---|
| Đầu ra thực tế | Chưa thử | Chưa thử |
| Đúng tổng và danh mục? | Chưa đánh giá | Chưa đánh giá |
| Có bịa hoặc thêm dữ liệu không? | Chưa đánh giá | Chưa đánh giá |
| Có nêu thiếu dữ liệu, dễ hiểu? | Chưa đánh giá | Chưa đánh giá |
| Thời gian phản hồi và nhận xét | Chưa ghi | Chưa ghi |

Lưu ý: việc so sánh này là thực nghiệm riêng; giao diện ứng dụng hiện không có nút chọn hai phiên bản prompt. Prompt đang chạy thực tế nằm trong hàm call_ai của app.py.

## 4. Minh chứng AI trong quá trình phát triển
Ghi lại trung thực với từng công việc: giai đoạn (phân tích/thiết kế/lập trình/kiểm thử), yêu cầu đã đưa AI, kết quả AI đề xuất, người kiểm tra và điều chỉnh, bằng chứng. Ghi rõ các phần được AI hỗ trợ và không nhận toàn bộ là tự viết. Không ghi API key.

## 5. Sản phẩm và demo
- Chuẩn bị README, mã nguồn và lịch sử Git thực tế; chưa coi Git đã hoàn thành khi chưa tạo repository và commit.
- Xác nhận trạng thái AI trực tuyến trên giao diện. demo-local hoặc demo-fallback là phân tích dự phòng, không chứng minh API thành công.
- Docker trên máy cá nhân là triển khai cục bộ; không chứng minh website có địa chỉ công khai.
- Chuẩn bị ảnh giao diện, kết quả kiểm thử, luồng kiến trúc, phân công và báo cáo; mỗi thành viên tự luyện vấn đáp phần của mình và luồng chung.
- API key từng xuất hiện trong ảnh phải được thu hồi; tạo key mới và chỉ nhập cục bộ.
