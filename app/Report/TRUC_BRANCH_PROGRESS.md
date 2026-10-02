# 📋 BÁO CÁO TIẾN ĐỘ & THÔNG TIN KIỂM SOÁT NHÁNH (BRANCH PROGRESS LOG)

* **Dự án:** GetApps — *"Get Up & Explore"*
* **Môn học:** PWD301 — Phát triển Web bằng Python
* **Semester:** Fall 2026
* **Nhánh làm việc:** `refactor/post-photo-like`
* **Nhánh mục tiêu:** `main`
* **Người thực hiện:** **Trúc (SE201580)**
* **Vai trò:** *Comment, Share, SavedPost & QA/Testing*
* **Người nhận / Reviewer:** **Khánh (Leader)**
* **Ngày cập nhật:** 21/09/2026
* **Trạng thái:** Backend interaction APIs + automated testing đã hoàn thành và kiểm thử thành công.

---

# 1. 📌 THÔNG TIN PHIÊN BẢN

| Thuộc tính | Chi tiết |
|---|---|
| **Project** | GetApps — Get Up & Explore |
| **Working Branch** | `refactor/post-photo-like` |
| **Target Branch** | `main` |
| **Owner** | Trúc — SE201580 |
| **Role** | Comment, Share, SavedPost, QA/Testing |
| **Backend Framework** | Flask |
| **ORM / Database Layer** | SQLAlchemy |
| **Authentication** | Flask-Login |
| **Testing Framework** | pytest 9.1.1 |
| **Python Version** | Python 3.14.7 |
| **Test Environment** | Windows / PowerShell / `.venv` |
| **Automated Tests** | 10 tests |
| **Automated Test Result** | **10/10 PASS — 100%** |
| **Total Test Time** | **4.67 seconds** |
| **Warnings** | 67 warnings — không có test failure |

---

# 2. 🎯 MỤC TIÊU CÔNG VIỆC

Sau khi project được refactor theo hướng:

````text
Post
 └── Photo
````

Trong đó:

* `Post` là đối tượng đại diện cho bài đăng.
* `Photo` là media thuộc một Post.
* Các chức năng tương tác bài viết phải tham chiếu đến `post_id`.
* `Like` đã được Leader Khánh triển khai trước đó.

Trúc phụ trách hoàn thiện các chức năng backend tương tác bài viết còn thiếu:

### 2.1. Comment

Xây dựng hệ thống bình luận:

* Tạo Comment.
* Lấy danh sách Comment.
* Xóa Comment.
* Kiểm tra quyền sở hữu Comment.
* Không cho phép Comment rỗng.
* User ID được lấy từ session/login hiện tại.
* Comment tham chiếu đến `post_id`.

### 2.2. Share

Xây dựng chức năng chia sẻ bài viết:

* Share một Post.
* Mỗi lần Share tạo một record mới.
* Cho phép cùng một User Share cùng một Post nhiều lần.
* Lưu User thực hiện Share.
* Lưu Post được Share.
* Lưu thời gian Share.

### 2.3. SavedPost

Xây dựng chức năng lưu bài viết:

* Save Post.
* Unsave Post.
* Toggle bằng cùng một API.
* Nếu chưa lưu → tạo record.
* Nếu đã lưu → xóa record.
* Trạng thái trả về thông qua trường `saved`.

### 2.4. QA / Automated Testing

Thực hiện:

* Manual API testing.
* Ownership testing.
* Database verification.
* Toggle testing.
* Repeat-action testing.
* Automated testing bằng pytest.
* Kiểm tra toàn bộ test suite sau khi hoàn thành.

---

# 3. 🏗️ KIẾN TRÚC DỮ LIỆU SAU KHI REFACTOR

Cấu trúc chính được sử dụng:

````text
User
 │
 ├── Post
 │    │
 │    ├── Photo
 │    │
 │    ├── Like
 │    │
 │    ├── Comment
 │    │
 │    ├── Share
 │    │
 │    └── SavedPost
 │
 └── các interaction records
````

Các model do Trúc bổ sung đều sử dụng:

````text
user_id → users.id
post_id → posts.id
````

### Không sử dụng:

````text
photo_id
````

cho Comment, Share hoặc SavedPost.

Điều này phù hợp với cấu trúc mới của project, trong đó `Post` là đối tượng chính của bài đăng.

---

# 4. 📂 FILE ĐƯỢC TẠO VÀ THAY ĐỔI

## 4.1. Model mới

### `app/models/comment.py`

Tạo model `Comment`.

Các trường:

| Field        | Kiểu       | Mục đích          |
| ------------ | ---------- | ----------------- |
| `id`         | Integer    | Primary key       |
| `user_id`    | Integer FK | User viết Comment |
| `post_id`    | Integer FK | Post được Comment |
| `content`    | Text       | Nội dung Comment  |
| `created_at` | DateTime   | Thời gian tạo     |

---

### `app/models/share.py`

Tạo model `Share`.

Các trường:

| Field        | Kiểu       | Mục đích             |
| ------------ | ---------- | -------------------- |
| `id`         | Integer    | Primary key          |
| `user_id`    | Integer FK | User thực hiện Share |
| `post_id`    | Integer FK | Post được Share      |
| `created_at` | DateTime   | Thời gian Share      |

### Thiết kế Share

Share được xem là một **action/event**.

Do đó:

````text
User 1 → Share Post 1
User 1 → Share Post 1
````

có thể tạo:

````text
Share #1
Share #2
````

Không áp dụng unique constraint giữa:

````text
user_id + post_id
````

---

### `app/models/saved_post.py`

Tạo model `SavedPost`.

Các trường:

| Field        | Kiểu       | Mục đích      |
| ------------ | ---------- | ------------- |
| `id`         | Integer    | Primary key   |
| `user_id`    | Integer FK | User lưu bài  |
| `post_id`    | Integer FK | Post được lưu |
| `created_at` | DateTime   | Thời gian lưu |

Model này phục vụ cơ chế:

````text
Save → Unsave → Save → ...
````

---

## 4.2. Model registration

### `app/models/__init__.py`

Bổ sung import:

````python
Comment
Share
SavedPost
````

để các model có thể được sử dụng trong routes và được SQLAlchemy nhận diện.

---

## 4.3. Routes

### `app/locations/routes.py`

Bổ sung 5 API endpoint:

````text
POST   /locations/posts/<post_id>/comments
GET    /locations/posts/<post_id>/comments
DELETE /locations/comments/<comment_id>

POST   /locations/posts/<post_id>/share

POST   /locations/posts/<post_id>/save
````

Like route hiện có được giữ nguyên:

````text
POST /locations/posts/<post_id>/like
````

Không tạo lại Like model hoặc Like route.

---

# 5. 🗄️ DATABASE MIGRATIONS

Đã tạo 3 migration:

````text
692bd9da455f_add_comment_model.py
1de8d1710892_add_share_model.py
53d5dbdf367b_add_savedpost_model.py
````

Migration đã được chạy thành công theo thứ tự:

````text
... 
    ↓
692bd9da455f
    ↓
1de8d1710892
    ↓
53d5dbdf367b
````

Database hiện đã có các bảng tương ứng:

````text
comments
shares
saved_posts
````

### Migration verification

Kết quả:

````text
Database migration: PASS
Latest migration:
53d5dbdf367b
````

---

# 6. 🔌 API IMPLEMENTATION

## 6.1. Comment API

### Create Comment

````text
POST /locations/posts/<post_id>/comments
````

Request:

````json
{
    "content": "Test comment"
}
````

Response thành công:

````text
HTTP 201 Created
````

Chức năng:

* Kiểm tra Post tồn tại.
* Lấy `user_id` từ `current_user.id`.
* Trim nội dung bằng `.strip()`.
* Không cho phép nội dung rỗng.
* Tạo Comment mới.
* Lưu vào database.

---

### Get Comments

````text
GET /locations/posts/<post_id>/comments
````

Response:

````text
HTTP 200 OK
````

Trả về:

````text
post_id
comments[]
````

Danh sách được sắp xếp theo:

````text
created_at ASC
````

---

### Delete Comment

````text
DELETE /locations/comments/<comment_id>
````

Các trường hợp:

````text
Comment không tồn tại → 404
User không sở hữu Comment → 403
User sở hữu Comment → cho phép xóa
````

---

# 7. 🔗 SHARE API

Endpoint:

````text
POST /locations/posts/<post_id>/share
````

Flow:

````text
User login
   ↓
POST /share
   ↓
Kiểm tra Post
   ↓
Tạo Share record
   ↓
Commit DB
   ↓
HTTP 201
````

### Share nhiều lần

Thiết kế cho phép:

````text
User 1
  ↓
Share Post 1
  ↓
Share #1

User 1
  ↓
Share Post 1
  ↓
Share #2
````

Hai record có ID khác nhau.

Đây là behavior đã được automated test xác nhận.

---

# 8. 🔖 SAVED POST API

Endpoint:

````text
POST /locations/posts/<post_id>/save
````

## Save

Nếu chưa có SavedPost:

````text
POST
 ↓
Create SavedPost
 ↓
saved = true
 ↓
HTTP 201
````

## Unsave

Nếu đã có SavedPost:

````text
POST
 ↓
Delete SavedPost
 ↓
saved = false
 ↓
HTTP 200
````

Flow:

````text
          POST /save
              │
       ┌──────┴──────┐
       │             │
   Chưa lưu       Đã lưu
       │             │
    INSERT         DELETE
       │             │
 saved=True      saved=False
   HTTP 201        HTTP 200
````

---

# 9. ❤️ LIKE

Like/Unlike đã được Leader Khánh triển khai trước đó.

Trúc không tạo lại Like model.

Endpoint sử dụng:

````text
POST /locations/posts/<post_id>/like
````

Behavior:

````text
Chưa Like
    ↓
Like
    ↓
liked = true

Đã Like
    ↓
Unlike
    ↓
liked = false
````

Trúc bổ sung automated test để kiểm tra Like/Unlike cùng với các chức năng thuộc scope của mình.

---

# 10. 🧪 AUTOMATED TESTING

## 10.1. Test environment

````text
Python: 3.14.7
pytest: 9.1.1
Platform: Windows
Environment: .venv
Database: SQLite test database
````

Pytest sử dụng database riêng cho từng test run thông qua fixture.

File:

````text
tests/conftest.py
````

Test database được tạo trong temporary directory.

Điều này giúp:

* Không ảnh hưởng database thật.
* Test độc lập.
* Có thể chạy lại nhiều lần.
* Dữ liệu test được tạo mới.

---

# 11. 📊 TEST COVERAGE THEO CHỨC NĂNG

## ❤️ Like

File:

````text
tests/test_like.py
````

Số test:

````text
2
````

### Test 1 — Like Post

Kiểm tra:

* Login User.
* Gửi request Like.
* HTTP `200`.
* `liked == True`.
* Like record tồn tại trong database.

Kết quả:

````text
PASS
````

### Test 2 — Unlike Post

Kiểm tra:

* Like lần đầu.
* Like lần hai.
* Trạng thái chuyển thành `liked == False`.
* Like record bị xóa khỏi database.

Kết quả:

````text
PASS
````

### Like result

````text
2/2 PASS
100%
````

---

# 12. 💬 COMMENT

File:

````text
tests/test_comment.py
````

Số test:

````text
4
````

### Test 1 — Create Comment

Kiểm tra:

* Login.
* Tạo Comment.
* HTTP `201`.
* Comment tồn tại trong DB.
* `content` được lưu đúng.

````text
PASS
````

### Test 2 — Get Comments

Kiểm tra:

* Tạo Comment.
* GET danh sách Comment.
* HTTP `200`.
* Có đúng Comment được tạo.
* Nội dung trả về chính xác.

````text
PASS
````

### Test 3 — Empty Comment

Request:

````json
{
    "content": "   "
}
````

Expected:

````text
HTTP 400
````

Kết quả:

````text
PASS
````

### Test 4 — Ownership

Flow:

````text
User 1 tạo Comment
       ↓
User 2 cố gắng xóa
       ↓
HTTP 403
       ↓
Comment vẫn tồn tại
````

Kết quả:

````text
PASS
````

### Comment result

````text
4/4 PASS
100%
````

---

# 13. 🔗 SHARE

File:

````text
tests/test_share.py
````

Số test:

````text
2
````

### Test 1 — Share Post

Kiểm tra:

* User login.
* Share Post.
* HTTP `201`.
* `user_id` đúng.
* `post_id` đúng.
* Share record tồn tại trong DB.

````text
PASS
````

### Test 2 — Multiple Share

Kiểm tra:

````text
Share lần 1 → HTTP 201
Share lần 2 → HTTP 201
````

Sau đó:

````text
Share #1 ID != Share #2 ID
````

Database:

````text
Total shares = 2
````

Kết quả:

````text
PASS
````

### Share result

````text
2/2 PASS
100%
````

---

# 14. 🔖 SAVED POST

File:

````text
tests/test_saved_post.py
````

Số test:

````text
2
````

### Test 1 — Save Post

Kiểm tra:

````text
POST /save
````

Expected:

````text
HTTP 201
saved = true
````

Đồng thời kiểm tra SavedPost tồn tại trong database.

Kết quả:

````text
PASS
````

### Test 2 — Unsave Post

Flow:

````text
Save
 ↓
saved = true
 ↓
Unsave
 ↓
saved = false
````

Kiểm tra sau Unsave:

````text
SavedPost record không còn trong DB
````

Kết quả:

````text
PASS
````

### SavedPost result

````text
2/2 PASS
100%
````

---

# 15. 📈 TỔNG KẾT AUTOMATED TEST

| Module       | Test cases | Passed | Failed | Pass rate |
| ------------ | ---------: | -----: | -----: | --------: |
| ❤️ Like      |          2 |      2 |      0 |      100% |
| 💬 Comment   |          4 |      4 |      0 |      100% |
| 🔗 Share     |          2 |      2 |      0 |      100% |
| 🔖 SavedPost |          2 |      2 |      0 |      100% |
| **TOTAL**    |     **10** | **10** |  **0** |  **100%** |

Full test suite:

````text
10 passed, 67 warnings in 4.67s
````

### Kết luận kiểm thử

````text
Total test cases: 10
Passed: 10
Failed: 0
Pass rate: 100%
Execution time: 4.67 seconds
````

---

# 16. ⚠️ TEST WARNINGS

Full test suite có:

````text
67 warnings
````

Các warning không làm test fail.

Hai nhóm warning chính:

### 16.1. `datetime.utcnow()` deprecated

SQLAlchemy/Python cảnh báo việc sử dụng:

````python
datetime.utcnow()
````

nên chuyển dần sang timezone-aware datetime.

### 16.2. `Query.get()` legacy

Một số code hiện tại sử dụng:

````python
Model.query.get(id)
````

SQLAlchemy cảnh báo nên sử dụng:

````python
db.session.get(Model, id)
````

Các warning này hiện chưa được sửa trong scope của Trúc vì có thể liên quan đến code hiện tại của project và các thành viên khác.

**Không có test failure.**

---

# 17. 🛡️ SECURITY / VALIDATION CHECK

Các API mới đều sử dụng:

````python
@login_required
````

Do đó chỉ User đã đăng nhập mới có thể sử dụng.

### User ID

Không lấy `user_id` trực tiếp từ Client.

Thay vào đó:

````python
current_user.id
````

được sử dụng để xác định User thực hiện action.

Điều này tránh việc Client tự gửi User ID của người khác để thực hiện action.

---

## Comment validation

````text
Post không tồn tại → 404
Content rỗng → 400
User không sở hữu Comment → 403
````

---

## Share validation

````text
Post không tồn tại → 404
Chưa login → yêu cầu authentication
````

---

## SavedPost validation

````text
Post không tồn tại → 404
Chưa login → yêu cầu authentication
````

---

# 18. 🔐 OWNERSHIP TESTING

Ownership được kiểm tra cho Comment.

Scenario:

````text
User 1
  ↓
Create Comment #1

User 2
  ↓
DELETE Comment #1

        ↓

HTTP 403 Forbidden
````

Database verification:

````text
Comment #1 vẫn tồn tại
````

Kết quả:

````text
PASS
````

---

# 19. 🔄 DATABASE BEHAVIOR VERIFICATION

Đã kiểm tra trực tiếp trạng thái database trong pytest.

### Comment

````text
Create → Record exists
````

### Like

````text
Like → Record exists
Unlike → Record removed
````

### Share

````text
Share #1 → Record exists
Share #2 → Another record exists
````

### SavedPost

````text
Save → Record exists
Unsave → Record removed
````

---

# 20. 📋 API STATUS SUMMARY

| Chức năng        | Method | Endpoint                              | Status   |
| ---------------- | ------ | ------------------------------------- | -------- |
| Create Comment   | POST   | `/locations/posts/<post_id>/comments` | ✅        |
| Get Comments     | GET    | `/locations/posts/<post_id>/comments` | ✅        |
| Delete Comment   | DELETE | `/locations/comments/<comment_id>`    | ✅        |
| Share Post       | POST   | `/locations/posts/<post_id>/share`    | ✅        |
| Save/Unsave Post | POST   | `/locations/posts/<post_id>/save`     | ✅        |
| Like/Unlike Post | POST   | `/locations/posts/<post_id>/like`     | ✅ Leader |

---

# 21. 🧪 DEFINITION OF DONE

| Tiêu chí                   | Trạng thái | Kết quả                  |
| -------------------------- | :--------: | ------------------------ |
| Comment Create             |      ✅     | PASS                     |
| Comment Get                |      ✅     | PASS                     |
| Comment Delete / Ownership |      ✅     | Ownership test PASS      |
| Comment Empty Validation   |      ✅     | HTTP 400                 |
| Share Create               |      ✅     | PASS                     |
| Share Multiple Times       |      ✅     | PASS                     |
| SavedPost Save             |      ✅     | PASS                     |
| SavedPost Unsave           |      ✅     | PASS                     |
| Like / Unlike integration  |      ✅     | 2/2 PASS                 |
| `post_id` architecture     |      ✅     | Không sử dụng `photo_id` |
| Authentication             |      ✅     | `@login_required`        |
| Database Migration         |      ✅     | Upgrade thành công       |
| Manual API Testing         |      ✅     | Đã thực hiện             |
| Automated Testing          |      ✅     | 10/10 PASS               |
| AJAX Frontend              |      ⏳     | Chưa tích hợp            |
| CSRF integration           |      ⏳     | Chưa hoàn thiện          |
| Full Frontend UI           |      ⏳     | Chờ Frontend integration |

---

# 22. 🚧 CÁC PHẦN CHƯA HOÀN THÀNH

Các API backend và automated testing trong scope hiện tại đã hoàn thành.

Các phần còn lại:

### 22.1. Frontend AJAX

Chưa tích hợp hoàn chỉnh:

````text
Comment
Share
Save
Like
````

với giao diện bằng `fetch()`.

Mục tiêu:

````text
User action
    ↓
fetch()
    ↓
Flask API
    ↓
JSON response
    ↓
Update UI
````

Không reload toàn bộ trang.

---

### 22.2. CSRF

Cần phối hợp với Frontend và kiến trúc authentication hiện tại để hoàn thiện CSRF protection cho các request state-changing.

---

### 22.3. Frontend Error Handling

Cần hiển thị phù hợp các lỗi:

````text
400 → dữ liệu không hợp lệ
403 → không có quyền
404 → Post/Comment không tồn tại
500 → lỗi server
````

---

# 23. 📊 TỔNG QUAN TIẾN ĐỘ

## Backend

````text
Comment       ████████████████████ 100%
Share         ████████████████████ 100%
SavedPost     ████████████████████ 100%
Like          ████████████████████ 100%*
````

`*` Like do Leader Khánh triển khai; Trúc đã bổ sung automated testing cho chức năng này.

## Testing

````text
Manual Testing       ████████████████████ 100%
Automated Testing    ████████████████████ 100%
````

Kết quả:

````text
10/10 PASS
100% pass rate
````

## Frontend integration

````text
AJAX               ⏳ Chưa hoàn thành
CSRF integration   ⏳ Chưa hoàn thành
UI integration     ⏳ Chưa hoàn thành
````

---

# 24. 🎯 KẾ HOẠCH TIẾP THEO

### Bước 1 — Review

Leader Khánh review:

````text
Models
Routes
Migrations
Tests
````

### Bước 2 — Frontend integration

Phối hợp với thành viên Frontend để tích hợp:

````text
Comment
Like
Share
Save
````

bằng AJAX / `fetch()`.

### Bước 3 — Integration testing

Sau khi Frontend được tích hợp:

````text
Backend API
     +
Frontend UI
     ↓
End-to-end testing
````

### Bước 4 — Final regression test

Chạy lại:

````powershell
pytest -v
````

sau khi merge các thay đổi từ các thành viên khác.

---

# 25. 📝 KẾT LUẬN

Phần backend interaction trong scope của Trúc đã hoàn thành các chức năng:

````text
💬 Comment
🔗 Share
🔖 SavedPost
❤️ Like testing
````

Các chức năng Comment, Share và SavedPost đã được xây dựng theo kiến trúc mới sử dụng:

````text
post_id
````

thay vì `photo_id`.

Database migration đã chạy thành công.

Các API đã được kiểm thử thủ công và automated testing.

Kết quả automated testing cuối cùng:

````text
10 test cases
10 passed
0 failed
100% pass rate
4.67 seconds
````

Các warning hiện tại là deprecation/legacy warnings từ SQLAlchemy và không làm test thất bại.

Backend interaction trong scope của Trúc đã hoàn thành; Frontend AJAX, CSRF và integration vẫn đang chờ phối hợp với thành viên phụ trách Frontend.

---

> **📌 Ghi chú dành cho Leader Khánh**
>
> * Trúc không tạo lại Like model/route.
> * Comment, Share và SavedPost đều sử dụng `post_id` theo cấu trúc Post refactor.
> * Share được thiết kế như action/event nên cho phép một User Share cùng một Post nhiều lần.
> * SavedPost sử dụng cơ chế toggle Save/Unsave.
> * Comment có ownership check: User khác không thể xóa Comment của người khác.
> * Automated test suite hiện có **10 test cases và 10/10 PASS**.
> * AJAX, CSRF và Frontend integration vẫn là các phần cần phối hợp với thành viên phụ trách Frontend.