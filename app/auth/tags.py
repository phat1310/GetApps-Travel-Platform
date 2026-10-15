"""Nhãn hồ sơ (profile tags): 5 nhãn có sẵn + nhãn do người dùng tự đặt.

Nhãn tự đặt được chuẩn hóa Ở SERVER thành "slug" rồi mới lưu, ví dụ:
    "Người đi bộ"  ->  nguoidibo  ->  hiển thị #nguoidibo
Vì sao không tin hashtag do trình duyệt gửi lên? Vì request có thể được dựng tay (curl/Burp):
chuỗi 10.000 ký tự sẽ tràn cột users.tags (255), chuỗi "<script>" là mầm XSS, tên "admin" dùng để mạo danh.
Nên server luôn: giới hạn độ dài, chỉ cho chữ/số/khoảng trắng, chuyển về [a-z0-9], chặn từ dễ mạo danh, chặn trùng.
"""
import re
import unicodedata

MAX_TAGS = 3
MAX_NAME_LEN = 30
MIN_SLUG_LEN = 2

# mã lưu trong DB -> hashtag hiển thị
FIXED_TAG_HASHTAGS = {
    "nguoi_du_lich": "#nguoidulich",
    "dia_phuong": "#dandiaphuong",
    "phuot": "#daphuot",
    "huong_dan_vien": "#huongdanvien",
    "nguoi_noi_tieng": "#nguoidanoitieng",
}

# Từ khóa dễ bị dùng để mạo danh quản trị / tài khoản chính thức (so khớp trên slug không dấu)
RESERVED_PARTS = (
    "admin", "quantri", "xacminh", "chinhthuc", "official",
    "verified", "moderator", "support", "hotro",
)


def slugify(name):
    """'Người Đi Bộ' -> 'nguoidibo' (bỏ dấu, đ->d, chữ thường, bỏ mọi ký tự ngoài a-z0-9)."""
    s = unicodedata.normalize("NFD", name.replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def normalize_tag(item):
    """Trả về (mã_lưu_DB, None) hoặc (None, thông_báo_lỗi). Nhận mã có sẵn, tên tự do ('Người đi bộ'), hoặc slug đã lưu."""
    if not isinstance(item, str):
        return None, "Nhãn không hợp lệ."
    raw = item.strip()
    if raw in FIXED_TAG_HASHTAGS:
        return raw, None

    raw = unicodedata.normalize("NFC", raw).lstrip("#").strip()
    raw = re.sub(r"\s+", " ", raw)
    if not raw:
        return None, "Tên nhãn không được để trống."
    if len(raw) > MAX_NAME_LEN:
        return None, f"Tên nhãn tối đa {MAX_NAME_LEN} ký tự."
    if any(not (c.isalnum() or c == " ") for c in raw):
        return None, "Tên nhãn chỉ gồm chữ, số và khoảng trắng."

    slug = slugify(raw)
    if len(slug) < MIN_SLUG_LEN:
        return None, "Tên nhãn cần có ít nhất 2 chữ cái Latin hoặc số để tạo hashtag."
    if any(w in slug for w in RESERVED_PARTS):
        return None, "Tên nhãn chứa từ dễ gây hiểu nhầm là tài khoản chính thức, hãy chọn tên khác."
    for code, tag in FIXED_TAG_HASHTAGS.items():     # trùng hashtag của nhãn có sẵn -> dùng nhãn có sẵn
        if "#" + slug == tag:
            return code, None
    return slug, None


def normalize_tags(items):
    """Trả về (list_mã, None) hoặc (None, lỗi). Tối đa 3 nhãn, không trùng hashtag."""
    if not isinstance(items, list):
        return None, "tags phải là một danh sách"
    if len(items) > MAX_TAGS:
        return None, f"Chỉ được chọn tối đa {MAX_TAGS} nhãn"
    codes = []
    for it in items:
        code, err = normalize_tag(it)
        if err:
            return None, err
        if code in codes:
            return None, f"Nhãn {hashtag_for(code)} bị trùng."
        codes.append(code)
    return codes, None


def hashtag_for(code):
    return FIXED_TAG_HASHTAGS.get(code, "#" + code)
