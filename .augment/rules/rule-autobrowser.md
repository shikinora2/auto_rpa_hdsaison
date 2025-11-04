---
type: "always_apply"
description: "Example description"
---

Luôn luôn trả lời bằng TIẾNG VIỆT
Không tạo thêm file Test
1. Rules Tự động (Applied Automatically)
Đây là các nguyên tắc cốt lõi mà Agent phải luôn tuân thủ trong mọi cuộc hội thoại liên quan đến tự động hóa trình duyệt.

Rule 1: Ưu tiên Thư viện Hiện đại (Modern First)

Khi được yêu cầu tạo code, luôn ưu tiên các thư viện hiện đại và mạnh mẽ như Playwright hoặc Selenium 4+.

Nếu sử dụng Selenium, phải đi kèm với WebDriverWait và By (ví dụ: By.CSS_SELECTOR).

Nếu sử dụng Playwright, phải tận dụng cơ chế auto-waiting (chờ tự động) của nó.

Rule 2: Chống Sử dụng time.sleep() (No Static Waits)

Tuyệt đối không sử dụng time.sleep() (hoặc các hàm chờ cố định) để chờ element xuất hiện.

Luôn thay thế bằng các cơ chế chờ đợi tường minh (explicit waits) hoặc chờ đợi động (dynamic waits) (ví dụ: page.wait_for_selector() trong Playwright, WebDriverWait trong Selenium). Phải giải thích lý do tại sao điều này quan trọng (để tránh "race conditions" và làm script ổn định hơn).

Rule 3: Ưu tiên Bộ chọn Lọc (Selectors) Ổn định

Luôn ưu tiên các bộ chọn lọc (selector) mạnh mẽ và ít thay đổi:

Ưu tiên cao: data-testid, id, name, ARIA roles (vai trò trợ năng).

Ưu tiên trung bình: CSS Selector (class) ổn định, placeholder, text (nội dung văn bản).

Tránh sử dụng: Full XPath tuyệt đối (ví dụ: /html/body/div[3]/...), các class được tạo tự động (ví dụ: css-1qbjwzi), hoặc nth-child.

Rule 4: Xử lý Lỗi Chủ động (Proactive Error Handling)

Mọi đoạn code được tạo ra phải nằm trong khối try...except (Python) hoặc try...catch (JavaScript) để xử lý các lỗi phổ biến như TimeoutError (không tìm thấy element) hoặc NoSuchElementException.

Luôn đề xuất việc ghi log (logging) các lỗi thay vì chỉ print().

Rule 5: Giả lập Người dùng (User Emulation)

Khi khởi tạo trình duyệt, luôn đề xuất việc thiết lập một User-Agent thực tế.

chạy ở chế độ headful (có giao diện) để gỡ lỗi (debug).

Rule 6: Nguyên tắc Đạo đức (Ethical Boundaries)

Agent sẽ từ chối các yêu cầu vi phạm rõ ràng Điều khoản Dịch vụ (ToS) của một trang web (ví dụ: tự động hóa việc mua hàng số lượng lớn, spam, tấn công).

Agent sẽ không cung cấp code để vượt qua CAPTCHA một cách tự động. Agent có thể đề xuất các giải pháp xử lý CAPTCHA thủ công hoặc thông qua các dịch vụ API (nhưng phải nêu rõ rủi ro).

2. Rules @mention (Referenced in Conversations)
Đây là các "snippet" (đoạn code mẫu) hoặc hướng dẫn chuyên sâu có thể được gọi ra bằng @mention để giải quyết các vấn đề cụ thể một cách nhanh chóng.

@login

Mục đích: Cung cấp mẫu code hoàn chỉnh để tự động điền và gửi (submit) biểu mẫu đăng nhập.

Hành động: Tạo một hàm (function) nhận page (hoặc driver), username, password. Hàm này sẽ:

Tìm ô username (sử dụng selector [name="username"] hoặc [type="email"]).

Tìm ô password (sử dụng selector [name="password"] hoặc [type="password"]).

Tìm nút submit (sử dụng [type="submit"] hoặc text="Đăng nhập").

Thực hiện fill và click.

Quan trọng: Chờ một element cụ thể sau khi đăng nhập (ví dụ: ảnh đại diện người dùng) để xác nhận đăng nhập thành công.

@cookies

Mục đích: Hướng dẫn lưu và tải lại cookie để duy trì phiên đăng nhập.

Hành động: Cung cấp hai hàm: save_cookies(page, file_path) và load_cookies(page, file_path).

save_cookies: Lấy cookie từ context trình duyệt và lưu vào file JSON.

load_cookies: Đọc file JSON và thêm cookie vào context trước khi truy cập trang.

@user_data

Mục đích: Hướng dẫn cách sử dụng "User Data Directory" (thư mục dữ liệu người dùng) để duy trì trạng thái trình duyệt (cookie, local storage, v.v.) một cách tự động.

Hành động: Cung cấp tùy chọn khởi chạy (launch option) cho Playwright (launch_persistent_context) hoặc Selenium (user-data-dir) để chỉ định một thư mục profile. Giải thích đây là cách thay thế cho @cookies khi cần lưu trữ nhiều hơn.

@debug

Mục đích: Cung cấp các kỹ thuật gỡ lỗi script tự động hóa.

Hành động:

Giới thiệu await page.pause() (Playwright) để mở trình gỡ lỗi Playwright Inspector.

Giới thiệu input("Nhấn Enter để tiếp tục...") (Python/Selenium) để tạm dừng script và kiểm tra trình duyệt.

Hướng dẫn cách sử dụng console.log() bên trong page.evaluate() để in ra console của trình duyệt.

@extract_data

Mục đích: Cung cấp mẫu code để trích xuất dữ liệu từ một danh sách các element (ví dụ: danh sách sản phẩm, bài viết).

Hành động:

Sử dụng page.locator() (Playwright) hoặc driver.find_elements() (Selenium) để lấy tất cả các "card" (thẻ) chứa item.

Tạo một vòng lặp for qua từng element.

Bên trong vòng lặp, trích xuất các thông tin con (như tiêu đề, giá, link) bằng cách tìm kiếm bên trong element cha đó.

Lưu kết quả vào một danh sách (list) các dictionary.

@iframe

Mục đích: Giải thích cách tương tác với các element nằm bên trong <iframe>.

Hành động: Cung cấp code để "chuyển ngữ cảnh" (switch context) vào bên trong iframe (sử dụng page.frame_locator() hoặc driver.switch_to.frame()) trước khi tìm element, và sau đó chuyển về ngữ cảnh chính.