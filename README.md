GetApps — "Get Up & Explore"

Mạng xã hội chia sẻ trải nghiệm du lịch — đồ án môn Phát triển Web bằng Python (PWD301). Flask, SQLAlchemy, Flask-Login, Flask-WTF, JWT, Bootstrap 5, AJAX, Docker.

Cài đặt & chạy
Clone repo, tạo virtual environment:
   python -m venv venv
   venv\Scripts\Activate.ps1        # Windows
   source venv/bin/activate         # Mac/Linux
Cài thư viện:
   pip install -r requirements.txt
Copy .env.example thành .env, tự điền giá trị bất kỳ (SECRET_KEY, JWT_SECRET_KEY):
   copy .env.example .env
Chạy migration để tạo database:
   flask --app run db upgrade
Chạy server:
   python run.py

Truy cập: http://127.0.0.1:5000

Trạng thái hiện tại (sườn đã có sẵn — KHÔNG code lại)

Sườn (walking skeleton) đã được dựng và test end-to-end, gồm:

User + Follow model, route /register, /login, /logout, /follow, /unfollow
Photo model + route upload ảnh thật (secure_filename/UUID)
Feed (query ảnh theo danh sách follow)
Like model + route like/unlike (AJAX-ready, JSON response)
1 endpoint API mẫu có JWT: /api/login, /api/users/<id>
base.html (Bootstrap CDN, navbar cơ bản)

Mọi model/route mới đều làm theo đúng pattern các file trên, không tạo cấu trúc khác.

Cấu trúc thư mục & khu vực phụ trách
GetApps/
├── app/
│   ├── __init__.py, extensions.py, config.py   (khung — Khánh)
│   ├── auth/          (Auth & Follow — Tuấn)
│   ├── locations/     (Location/Photo — Tuấn; Feed/Like — Trúc)
│   ├── api/           (REST API + JWT — Khánh)
│   ├── models/        (định nghĩa bảng dữ liệu, dùng chung)
│   ├── templates/      (giao diện HTML — Phát)
│   └── static/uploads/ (ảnh người dùng upload)
├── migrations/
├── instance/app.db
├── run.py
└── requirements.txt

Phân công đầy đủ (nhiệm vụ, timeline, checklist chi tiết, tiêu chí hoàn thành): xem file GetApps-Tai-Lieu-Du-An.docx và sơ đồ ERD đính kèm trong nhóm chat — README này chỉ tập trung phần kỹ thuật để chạy được code.

Quy ước code
Thêm model mới: viết file trong app/models/, theo đúng cấu trúc của photo.py, nhớ import vào app/models/__init__.py
Thêm model xong: chạy flask --app run db migrate -m "mô tả" rồi flask --app run db upgrade
Mọi file mới đều có docstring mô tả đầu file
Không hardcode secret key — luôn đọc qua .env
Không sửa app/__init__.py, app/extensions.py, hoặc file thuộc phạm vi Blueprint của người khác khi chưa trao đổi trước
Trước khi tạo Pull Request: tự chạy thử chức năng của mình với dữ liệu thật, không chỉ dữ liệu mẫu