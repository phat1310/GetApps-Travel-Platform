# 📋 BÁO CÁO TIẾN ĐỘ & THÔNG TIN KIỂM SOÁT NHÁNH (BRANCH PROGRESS LOG)

* **Dự án:** GetApps — *"Get Up & Explore"* (PWD301 - Fall 2026)
* **Nhánh làm việc:** `feature/phat-frontend-plan`
* **Người thực hiện:** **Phát (SE173285)** — Vai trò: *Frontend UI/UX & Phân hệ Plan*
* **Người nhận / Reviewer:** **Khánh (Leader)**
* **Thời gian cập nhật:** 16/09/2026
* **Mục đích:** Báo cáo chi tiết các thay đổi đã thực hiện trên nhánh `feature/phat-frontend-plan` trước khi Review & Compare/Merge vào nhánh `main`.

---

## 📌 1. THÔNG TIN PHIÊN BẢN VÀ COMMIT

| Thuộc tính | Chi tiết |
| :--- | :--- |
| **Tên nhánh** | `feature/phat-frontend-plan` |
| **Nhánh gốc (Base)** | `main` (commit gốc: `17838cc Initial commit`) |
| **Commit ID gần nhất** | `99d14dc` |
| **Commit Message** | `feat(ui): upgrade base.html with GEs branding, responsive navbar, user dropdown and add custom stylesheet` |
| **Trạng thái Remote** | Đã đẩy lên GitHub (`origin/feature/phat-frontend-plan`) |
| **Link Pull Request** | [Compare & Pull Request trên GitHub](https://github.com/quockhanhtkh2com-cell/GetApps/pull/new/feature/phat-frontend-plan) |

---

## 🎯 2. MỤC TIÊU CÔNG VIỆC VỪA THỰC HIỆN (BƯỚC 1)

Theo đúng phân công trong tài liệu [`GetApps-Tai-Lieu-Du-An.docx`](file:///d:/ATTT/ATTT_FPT/KY_5_FALL_2026/PWD301/05_Du_An_Nhom_PWD301/GetApps-Tai-Lieu-Du-An.docx) và [`Dự_án_GetApps_Phân tích.md`](file:///d:/ATTT/ATTT_FPT/KY_5_FALL_2026/PWD301/05_Du_An_Nhom_PWD301/D%E1%BB%B1_%C3%A1n_GetApps_Ph%C3%A2n%20t%C3%ADch.md), Phát chịu trách nhiệm xây dựng nền tảng giao diện chuẩn mực để cả nhóm tái sử dụng:

1. **Chuẩn hóa môi trường chạy cục bộ:** Khởi tạo môi trường ảo `venv`, cài đặt đồng bộ thư viện và cập nhật database migration.
2. **Nâng cấp Master Layout (`base.html`):** Thay thế khung HTML đơn sơ ban đầu bằng bộ khung giao diện chuẩn responsive, tích hợp nhận diện thương hiệu `GEs`.
3. **Xây dựng Stylesheet tùy biến (`style.css`):** Thiết lập hệ màu HEX, các class nút bấm, card, avatar và badge vai trò theo concept thiết kế của Vy.

---

## 📂 3. DANH SÁCH FILE THAY ĐỔI & THÊM MỚI (DETAILED CHANGELOG)

### 🟢 3.1. File thêm mới (Created)
* **`app/static/css/style.css`**:
  * Định nghĩa bảng màu biến CSS (`:root`): Màu chủ đạo xanh da trời (`--ges-primary: #0284c7`, hover: `#0369a1`), nền sáng tối giản (`#f8fafc`), chữ đậm tương phản (`#0f172a`).
  * Khối phong cách thương hiệu: `.brand-badge` (Logo GEs góc bo mềm, gradient), `.brand-title`, `.brand-tagline`.
  * Các class nút bấm chuẩn: `.btn-ges-primary` (nút xanh nổi bật), `.btn-ges-outline`.
  * Khối Avatar: `.avatar`, `.avatar-sm` (32px), `.avatar-md` (44px), `.avatar-lg` (80px), `.avatar-placeholder` (cho user chưa có ảnh đại diện).
  * Bộ Badge phân loại người dùng (Role Badges):
    * `.badge-role-traveler` (xanh nhạt)
    * `.badge-role-local` (xanh lá)
    * `.badge-role-creator` (tím)
    * `.badge-role-owner` (vàng hổ phách)
    * `.badge-role-user` (xám slate)
  * Thẻ Card & hiệu ứng hover: `.ges-card`, `.ges-card-hover`.
  * Footer styling: `.footer-ges`.

### 🟡 3.2. File cập nhật (Modified)
* **`app/templates/base.html`**:
  * **Header / Navbar:** 
    * Cấu trúc Bootstrap 5 Navbar chuẩn Responsive với nút Toggler cho thiết bị di động.
    * Tích hợp Bootstrap Icons 1.11.3 và Google Font *Plus Jakarta Sans*.
    * Điều hướng chính: Bảng tin (`locations.feed`), Khám phá (`/explore`), Lịch trình (`/plans`).
    * **Kiểm tra phiên đăng nhập (`current_user.is_authenticated`):**
      * *Khách vãng lai:* Hiện nút `Đăng nhập` và `Đăng ký`.
      * *Đã đăng nhập:* Nút hành động nhanh `+ Đăng ảnh`, `+ Tạo lịch trình`; Dropdown Avatar hiển thị Username, Role badge, link đến *Trang cá nhân*, *Lịch trình của tôi* và Form Đăng xuất bảo mật (`auth.logout`).
  * **Flash Messages Container:** Bắt tự động các thông báo `flash(..., 'category')` của Flask và hiển thị dưới dạng Bootstrap Alert Dismissible.
  * **Khối kế thừa Jinja2 mở rộng:** Cung cấp đầy đủ các block:
    * `{% block title %}`
    * `{% block extra_css %}`
    * `{% block content %}`
    * `{% block extra_js %}`
  * **Footer:** Căn chỉnh 2 cột hiển thị bản quyền đồ án PWD301, slogan *"Get Up & Explore"*, danh sách menu nhanh và credit thành viên nhóm.

* **`requirements.txt`**:
  * Chuyển đổi định dạng mã hóa từ **UTF-16LE có BOM** sang **UTF-8 tiêu chuẩn** để đảm bảo Git so sánh (diff) sạch sẽ, tránh xung đột encoding khi nhóm clone/pull trên các hệ điều hành khác nhau (Mac/Linux/Windows). Không thay đổi danh sách package.

---

## 🛡️ 4. KIỂM THỬ & ĐẢM BẢO TÍNH ĐỘC LẬP (VERIFICATION & DOD)

| Tiêu chí kiểm soát | Kết quả kiểm tra | Ghi chú kỹ thuật |
| :--- | :---: | :--- |
| **Không đụng chạm code thành viên khác** | ✅ ĐẠT | Tuyệt đối **không** chỉnh sửa các file thuộc phạm vi quản lý của Leader (`app/__init__.py`, `config.py`, `extensions.py`) hoặc Blueprint của Tuấn/Trúc. |
| **Không có circular import** | ✅ ĐẠT | App khởi tạo trơn tru qua `create_app()`. |
| **Cú pháp Jinja2 & Template Rendering** | ✅ ĐẠT | Đã kiểm thử qua Flask context script: `render_template('base.html')` trả về kết quả 5,812 bytes, 100% assertions passed. |
| **Database & Migrations** | ✅ ĐẠT | Môi trường ảo cục bộ đã chạy `flask db upgrade` thành công đến migration mới nhất (`339f6ee20932_add_like_model`). |
| **Bảo mật Secret Key** | ✅ ĐẠT | File `.env` chứa secret key phát triển đã được cấu hình và nằm đúng trong `.gitignore`, không bao giờ bị lộ lên Git. |

---

## 🚀 5. CÁC BƯỚC TIẾP THEO CỦA PHÁT (UPCOMING SPRINT)

1. **Bước 2: Xây dựng các Template con kế thừa `base.html`:**
   * Giao diện Đăng ký / Đăng nhập: `templates/auth/login.html`, `templates/auth/register.html` (kết hợp với logic Form Flask-WTF của Tuấn).
   * Giao diện Bảng tin & Tải ảnh: `templates/locations/feed.html`, `templates/locations/upload.html`.
2. **Bước 3: Thiết kế Phân hệ Plan (Tuần 5 - 6):**
   * Định nghĩa model `Plan`, `PlanItem`, `SavedPlan`.
   * Xây dựng giao diện xem lịch trình dạng Timeline và tạo lịch trình tương tác.
   * Phối hợp cùng Trúc để sử dụng module `Like` & `Comment` dùng chung.

---

## 🌟 6. CẬP NHẬT MỚI: SỬA ĐĂNG NHẬP EMAIL & BỔ SUNG GIAO DIỆN CÀI ĐẶT PROFILE (GEs DESIGN SYSTEM)

### 🚀 6.1. Chi tiết các hạng mục đã hoàn thành:
1. **Khắc phục triệt để lỗi đăng nhập bằng Email:**
   - So sánh email và username không phân biệt chữ hoa/thường (`func.lower(User.email) == raw_val.lower()`, `func.lower(User.username) == raw_val.lower()`).
   - Tự động cắt bỏ khoảng trắng thừa (`strip()`) do bàn phím ảo di động tự động thêm vào.
   - Hỗ trợ đăng nhập đa kênh linh hoạt: `Username`, `Email` hoặc `Số điện thoại` (`User.phone_number`).
   - Tự động gọi `logout_user()` dọn sạch session cũ trước khi gán phiên đăng nhập mới, ngăn ngừa conflict session.
2. **Giao diện Cài đặt người dùng (Profile Settings) theo chuẩn ảnh Proposal & Stitch:**
   - Tạo trang `app/templates/auth/settings.html` và route `/settings`, `/profile/settings`.
   - Card Thông tin: Avatar tròn kèm nút Camera Cyan (`#0EA5E9`), Biệt danh, Badge "Tài khoản cá nhân", Dòng "Chỉnh sửa trang cá nhân".
   - Danh sách cài đặt dạng Card bo góc mềm:
     - **Biệt danh (Nickname)**: `Minh Đi Đâu` `>`
     - **Nhãn (Tags)**: Chip `#nguoidulich` `>`
     - **Email**: Hiển thị email `>`
     - **Số điện thoại**: Hiển thị SĐT `>`
     - **Ghi chú / Tiểu sử**: Khối văn bản bio bên dưới `>`
   - Nhóm **BẢO MẬT**: Mục **Chỉnh sửa mật khẩu** (mô tả "Đổi mật khẩu tài khoản đăng nhập") `>` dẫn sang `/change-password`.
   - Nút **Đăng xuất** màu đỏ nhạt bo góc mềm (`#FEE2E2` / `#DC2626`).
   - **Modal Chọn Nhãn Hồ Sơ (Figma / Stitch UI):** Hỗ trợ chọn danh xưng (`Người du lịch`, `Dân địa phương`, `Đi phượt`, `Hướng dẫn viên`, `Người nổi tiếng`) với nút "Xác nhận", "Hủy" và nhãn đã thêm có dấu `x` gỡ bỏ.
3. **Đồng bộ toàn bộ Icon theo Design System (`media_1791099064196.png`):**
   - Chuẩn hóa các icon trên Header, Navbar, Feed, Profile, Settings:
     - Home (`bi-house-door-fill`), Explore (`bi-compass`), Plan (`bi-map`), Post (`bi-pencil-square`), Profile (`bi-person`), Setting (`bi-gear`), Password (`bi-shield-lock`), Logout (`bi-box-arrow-right`), Like (`bi-heart-fill`), Comment (`bi-chat`), Save (`bi-bookmark-fill`), Share (`bi-send`), More (`bi-three-dots`).
4. **Kiểm thử tự động:**
   - Đạt **56/56 tests PASSED 100%** trên pytest.

---

> **Lưu ý dành cho Nhóm trưởng (Khánh):**
> * Nhánh `feature/phat-frontend-plan` hoàn toàn an toàn và sẵn sàng để so sánh (compare) trên GitHub.
> * Các file thay đổi hoàn toàn là Presentation Layer (HTML/CSS), không gây ra Merge Conflict với nhánh `main`.

