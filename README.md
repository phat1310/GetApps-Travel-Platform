GetApps — "Get Up & Explore"

Mạng xã hội chia sẻ trải nghiệm du lịch — đồ án môn Phát triển Web bằng Python (PWD301). Flask, SQLAlchemy, Flask-Login, Flask-WTF, JWT, Bootstrap 5, AJAX, Docker.

Cài đặt & chạy
Clone repo, tạo virtual environment:
   python -m venv venv
   venv\Scripts\Activate.ps1        # Windows
   source venv/bin/activate         # Mac/Linux
Cài thư viện:
   pip install -r app/Report/requirements.txt
Copy .env.example thành .env, tự điền giá trị bất kỳ (SECRET_KEY, JWT_SECRET_KEY):
   copy .env.example .env
Chạy migration để tạo database:
   flask --app run db upgrade
Chạy server:
   python run.py

Truy cập: http://127.0.0.1:5000

Trạng thái hiện tại (cập nhật 23/09/2026)

ĐÃ XONG — không code lại, chỉ mở rộng nếu cần:
User + Follow model, route /register, /login, /logout, /follow, /unfollow (Tuấn)
Password policy khi đăng ký — tối thiểu 8 ký tự, có chữ + số (Khánh)
Post model (bài viết) + Photo model (ảnh/video con, 1 Post - N Photo, tối đa 10 file/post,
  hỗ trợ media_type "image"/"video") + route đăng bài nhiều file /locations/upload (Tuấn)
Location model + gán location_id/extra_locations cho Post — ĐÃ MERGE xong vào sườn chính (Tuấn)
Feed (query bài viết theo danh sách follow, trả kèm mảng media) — hiện vẫn giới hạn chỉ bài người đang follow, CHƯA đổi sang Discovery
Like / Comment / Share / Save — đầy đủ CRUD + toggle 2 chiều, chống trùng bằng UniqueConstraint (Trúc + Khánh)
Xóa comment của chính mình (Trúc)
Chặn quyền xem/tương tác bài Private — hàm user_can_access_post() (Khánh)
Đồng bộ SQLAlchemy syntax mới — db.session.get()/db.get_or_404() thay Model.query.get() (Khánh)
Unit test (pytest) cho like/comment/share/saved_post — thư mục tests/ (Trúc)
1 endpoint API mẫu có JWT: /api/login, /api/users/<id> (Khánh)
base.html (Bootstrap CDN, navbar cơ bản)

CHƯA LÀM — xem chi tiết ở file phân công (bảng "Chưa làm" + "Mở rộng"):
Hashtag, Onboarding sau đăng ký, Feed Discovery, Profile routes, CSRF/Flask-WTF, Docker,
14 màn hình frontend, và 3 module mới: Lịch trình (Plan), Thông báo (Notification), Tìm kiếm (Search).

Lưu ý: Photo trước đây gắn trực tiếp vào user + có field "caption" riêng.
Từ bản refactor này, "caption" thuộc về Post (không phải Photo), và mọi FK
tham chiếu tới 1 bài viết phải dùng post_id (không dùng photo_id nữa).

Mọi model/route mới đều làm theo đúng pattern các file trên, không tạo cấu trúc khác.

Cấu trúc thư mục & khu vực phụ trách
GetApps/
├── app/
│   ├── __init__.py, extensions.py, config.py   (khung — Khánh)
│   ├── auth/          (Auth & Follow — Tuấn)
│   ├── locations/     (Post/Photo/Feed/Location/Like/Comment/Share/Save — Tuấn + Trúc + Khánh)
│   ├── api/           (REST API + JWT — Khánh)
│   ├── models/        (định nghĩa bảng dữ liệu, dùng chung)
│   ├── templates/      (giao diện HTML — Phát)
│   ├── static/uploads/ (ảnh người dùng upload)
│   └── Report/         (requirements.txt + file progress cá nhân — KHÔNG phải code)
├── migrations/
├── tests/               (pytest — Trúc)
├── instance/app.db
└── run.py

Phân công đầy đủ (nhiệm vụ, timeline, checklist chi tiết, tiêu chí hoàn thành): xem file bảng phân công Word mới nhất trong nhóm chat — README này chỉ tập trung phần kỹ thuật để chạy được code.

Quy ước code
Thêm model mới: viết file trong app/models/, theo đúng cấu trúc của photo.py, nhớ import vào app/models/__init__.py
Thêm model xong: chạy flask --app run db migrate -m "mô tả" rồi flask --app run db upgrade
Mọi file mới đều có docstring mô tả đầu file
Không hardcode secret key — luôn đọc qua .env
Không commit file cookie/session test (cookies*.txt) — đã thêm vào .gitignore, xóa nếu thấy lại
Không sửa app/__init__.py, app/extensions.py, hoặc file thuộc phạm vi Blueprint của người khác khi chưa trao đổi trước
Trước khi tạo Pull Request: tự chạy thử chức năng của mình với dữ liệu thật, không chỉ dữ liệu mẫu