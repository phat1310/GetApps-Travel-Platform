# Module Bảo mật — GetApps (PWD301)

Tài liệu này mô tả module bảo mật được thêm vào đồ án, theo phân công của giảng viên
(trọng số 60% demo trực tiếp / 40% báo cáo docx): admin panel, bảo vệ database, quy
trình pentest có patch workflow, và phòng chống DDoS/XSS/SQL Injection với 2-3 kịch
bản tấn công mẫu được demo.

## Phân công trong team

| Phần | Người phụ trách |
|---|---|
| Admin panel (quản lý User/Post, tách UI admin ≠ user) + kịch bản **Broken Access Control** | Khánh |
| Bảo vệ database + kịch bản **SQL Injection** | Tuấn |
| Kịch bản **XSS** | Trúc |
| Phòng chống **DDoS** (rate limiting) + trang **Nhật ký An ninh** | Phát |

Bảng `security_logs` (`app/models/security_log.py`) dùng chung cho cả 4 phần — mỗi
người tự ghi log sự kiện của mình vào đây qua `app/security_logging.py`, hiển thị tập
trung tại `/admin/security-logs`.

---

## 1. Broken Access Control (OWASP A01:2021) — phần của Khánh

### Lỗ hổng là gì
Nhiều web chỉ **ẩn** nút/menu admin ở giao diện (CSS, JS, hoặc `{% if %}` trong
template) mà không kiểm tra quyền thật ở phía server. Kẻ tấn công không cần thấy nút
— chỉ cần biết hoặc đoán đúng URL (`/admin/users`, `/admin/posts`...) và gõ thẳng vào
thanh địa chỉ là vào được, dù giao diện của họ không hề có nút dẫn tới đó.

### Cách phòng chống đã triển khai
Mọi route trong `app/admin/routes.py` đều bọc bởi 2 lớp decorator:

```python
@admin_bp.route("/users")
@login_required      # Flask-Login: phải đăng nhập
@admin_required       # app/admin/decorators.py: phải is_admin = True
def users():
    ...
```

`admin_required` (`app/admin/decorators.py`) chạy **trước khi route xử lý bất kỳ logic
nào**, trả về `403 Forbidden` nếu:
- Chưa đăng nhập, hoặc
- `current_user.is_admin` không phải `True`, hoặc
- Tài khoản đang bị khóa (`is_banned = True`)

Hành động thay đổi dữ liệu (cấp quyền admin, khóa tài khoản, xóa user/post) chỉ nhận
`POST` (không nhận `GET`) kèm CSRF token (Flask-WTF CSRFProtect bật global) — chặn
luôn kiểu tấn công CSRF-qua-link/ảnh hay gặp với các action nhạy cảm để ở GET.

### Cờ demo `DEMO_BAC_VULNERABLE`
Để quay demo/chụp minh họa đúng lỗi "Missing Function Level Access Control" cho báo
cáo, `admin_required` có thể giả vờ "quên" check quyền:

```python
# app/config.py
DEMO_BAC_VULNERABLE = os.environ.get("DEMO_BAC_VULNERABLE", "0") == "1"
```

Bật bằng cách thêm vào `.env`:
```
DEMO_BAC_VULNERABLE=1
```

**⚠️ BẮT BUỘC để `DEMO_BAC_VULNERABLE=0` (hoặc không set, mặc định đã là tắt) khi nộp
bài / deploy thật.** Cờ này chỉ dùng tạm thời lúc quay video minh họa "trước khi vá" —
bật xong nhớ tắt lại và kiểm tra lại bằng kịch bản test bên dưới trước khi deploy.

### Kịch bản test (đã verify — xem log demo ngày 22/10/2026)

1. Đăng nhập 1 tài khoản **không phải admin** (`is_admin = False`).
2. Gõ thẳng URL `/admin/users` (hoặc bất kỳ route `/admin/*` nào) vào thanh địa chỉ.
3. **Kết quả đúng:** nhận `403 Forbidden` — không vào được, dù không có nút dẫn tới
   trang này ở giao diện user thường.
4. Đăng nhập lại bằng tài khoản admin → vào `/admin/security-logs`.
5. **Kết quả đúng:** thấy 1 dòng log mới, `event_type = ACCESS_DENIED_403`, kèm đúng
   IP nguồn, thời gian, endpoint (`GET /admin/users`), mã `403`, hành động `BLOCKED`.

Việc ghi log tự động này do `_log_denied()` trong `app/admin/decorators.py` gọi mỗi
lần `admin_required` chặn 1 request — không cần code gì thêm ở từng route.

### Tạo tài khoản admin để test
Không có form tự đăng ký admin (đúng thiết kế — tránh user tự cấp quyền cho mình).
Đăng ký tài khoản bình thường qua `/register`, sau đó chạy:
```powershell
python scripts/create_admin.py <username_hoac_email> --grant
```
(xem chi tiết trong `scripts/create_admin.py`)

---

## 2. Lưu ý khi pull code về máy (quan trọng — tránh lỗi khi chạy local)

- Cột `is_admin` trên bảng `users` là `NOT NULL`. Nếu DB SQLite cục bộ của bạn được
  tạo **từ trước** khi module admin này được thêm vào, bạn cần chạy migration để có
  cột này (cơ chế tự vá DB trong `app/__init__.py` chủ động bỏ qua cột NOT NULL, chỉ
  tự thêm được cột cho phép NULL):
  ```powershell
  flask --app run db upgrade
  ```
  Nếu vẫn lỗi `no such column: users.is_admin` sau khi upgrade, migration tương ứng
  có thể chưa tồn tại — báo Khánh hoặc tự sinh: `flask --app run db migrate -m "add is_admin to users"` rồi `db upgrade` lại.
- Đồng bộ lại thư viện mỗi khi `app/Report/requirements.txt` thay đổi:
  ```powershell
  pip install -r app/Report/requirements.txt
  ```
- Trước khi coi 1 lỗi "Internal Server Error" là bug logic, luôn kiểm tra 2 điều cơ
  bản trước: (1) terminal chạy `python run.py` có đang chạy **code mới nhất** không
  (routes.py/`.py` không tự reload như template — phải Ctrl+C rồi chạy lại sau khi
  sửa code Python), và (2) `netstat -ano | findstr :5000` có nhiều hơn 1 process cùng
  LISTEN port 5000 không (process cũ "ma" còn sống sẽ nhận request thay vì process
  mới bạn đang theo dõi).

---

## 3. Các module bảo mật khác (tham khảo/điền tiếp)

> Phần này do Tuấn (SQL Injection + bảo vệ DB), Trúc (XSS), Phát (DDoS/rate-limit +
> trang Nhật ký An ninh) tự bổ sung chi tiết kỹ thuật phần mình, theo đúng format ở
> mục 1 (lỗ hổng là gì → cách chống → kịch bản test) để gộp chung 1 file nộp báo cáo.

### SQL Injection — Tuấn
_(điền: ORM/parameterized query dùng ở đâu, kịch bản test, log `SQLI_DETECTED`)_

### XSS — Trúc
_(điền: sanitize input ở đâu — có thể dùng `bleach` đã có trong requirements.txt —
kịch bản test, log `XSS_DETECTED`)_

### DDoS / Rate Limiting — Phát
_(điền: cấu hình Flask-Limiter trong `app/config.py` — `RATELIMIT_DEFAULT`,
`RATELIMIT_STORAGE_URI` — kịch bản test, log `DDOS_RATE_LIMIT`)_
