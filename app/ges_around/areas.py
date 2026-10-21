"""Danh sách khu vực / địa danh làm điểm xuất phát (whitelist) — HCM mới = HCM cũ + Bình Dương + BR-VT.

Người dùng chỉ chọn ID trong danh sách này (hoặc dùng GPS); server không nhận toạ độ tuỳ ý cho 'area'.
Toạ độ là điểm đại diện (xấp xỉ), đủ cho ước tính thời gian di chuyển.
"""

# (id, tên, nhóm, lat, lon)
_RAW = [
    # --- Trung tâm TP.HCM ---
    ("ben-thanh", "Chợ Bến Thành", "Trung tâm TP.HCM", 10.7725, 106.6980),
    ("dinh-doc-lap", "Dinh Độc Lập", "Trung tâm TP.HCM", 10.7769, 106.6954),
    ("nha-tho-duc-ba", "Nhà thờ Đức Bà", "Trung tâm TP.HCM", 10.7798, 106.6990),
    ("nguyen-hue", "Phố đi bộ Nguyễn Huệ", "Trung tâm TP.HCM", 10.7744, 106.7036),
    ("bui-vien", "Phố Tây Bùi Viện", "Trung tâm TP.HCM", 10.7677, 106.6934),
    ("thao-cam-vien", "Thảo Cầm Viên Sài Gòn", "Trung tâm TP.HCM", 10.7875, 106.7052),
    ("q1", "Quận 1", "Trung tâm TP.HCM", 10.7769, 106.7009),
    ("q3", "Quận 3", "Trung tâm TP.HCM", 10.7840, 106.6844),
    ("q4", "Quận 4", "Trung tâm TP.HCM", 10.7578, 106.7013),
    ("q5-cho-lon", "Quận 5 – Chợ Lớn", "Trung tâm TP.HCM", 10.7540, 106.6634),
    ("q10", "Quận 10", "Trung tâm TP.HCM", 10.7727, 106.6672),
    ("q11-dam-sen", "Công viên Đầm Sen (Q.11)", "Trung tâm TP.HCM", 10.7633, 106.6350),
    ("phu-nhuan", "Phú Nhuận", "Trung tâm TP.HCM", 10.7990, 106.6800),
    # --- Khu vực khác trong TP.HCM ---
    ("q2-thao-dien", "Thảo Điền (TP. Thủ Đức)", "Khu vực khác TP.HCM", 10.8031, 106.7335),
    ("landmark81", "Landmark 81 (Bình Thạnh)", "Khu vực khác TP.HCM", 10.7951, 106.7218),
    ("binh-thanh", "Quận Bình Thạnh", "Khu vực khác TP.HCM", 10.8106, 106.7091),
    ("thu-thiem", "Thủ Thiêm (TP. Thủ Đức)", "Khu vực khác TP.HCM", 10.7880, 106.7220),
    ("suoi-tien", "Khu du lịch Suối Tiên", "Khu vực khác TP.HCM", 10.8645, 106.8006),
    ("dhqg-thu-duc", "ĐH Quốc gia TP.HCM (Thủ Đức)", "Khu vực khác TP.HCM", 10.8700, 106.8030),
    ("tan-binh-san-bay", "Sân bay Tân Sơn Nhất", "Khu vực khác TP.HCM", 10.8185, 106.6588),
    ("go-vap", "Quận Gò Vấp", "Khu vực khác TP.HCM", 10.8386, 106.6652),
    ("q7-phu-my-hung", "Phú Mỹ Hưng (Q.7)", "Khu vực khác TP.HCM", 10.7290, 106.7194),
    ("q6-q8", "Quận 6 / Quận 8", "Khu vực khác TP.HCM", 10.7450, 106.6400),
    ("binh-tan", "Quận Bình Tân", "Khu vực khác TP.HCM", 10.7653, 106.6039),
    ("tan-phu", "Quận Tân Phú", "Khu vực khác TP.HCM", 10.7900, 106.6280),
    ("q12", "Quận 12", "Khu vực khác TP.HCM", 10.8670, 106.6540),
    ("hoc-mon", "Huyện Hóc Môn", "Khu vực khác TP.HCM", 10.8870, 106.5922),
    ("cu-chi", "Huyện Củ Chi", "Khu vực khác TP.HCM", 10.9725, 106.4933),
    ("binh-chanh", "Huyện Bình Chánh", "Khu vực khác TP.HCM", 10.6869, 106.5679),
    ("nha-be", "Huyện Nhà Bè", "Khu vực khác TP.HCM", 10.6962, 106.7377),
    ("can-gio", "Huyện Cần Giờ", "Khu vực khác TP.HCM", 10.4114, 106.9544),
    # --- Bình Dương (cũ) ---
    ("thu-dau-mot", "Thủ Dầu Một", "Bình Dương", 10.9804, 106.6519),
    ("di-an", "Dĩ An", "Bình Dương", 10.9034, 106.7693),
    ("thuan-an", "Thuận An", "Bình Dương", 10.9370, 106.7134),
    ("tan-uyen", "Tân Uyên", "Bình Dương", 11.0670, 106.8000),
    ("ben-cat", "Bến Cát", "Bình Dương", 11.1480, 106.6012),
    # --- Bà Rịa – Vũng Tàu (cũ) ---
    ("vung-tau", "Trung tâm Vũng Tàu", "Bà Rịa – Vũng Tàu", 10.3460, 107.0843),
    ("bai-sau", "Bãi Sau (Vũng Tàu)", "Bà Rịa – Vũng Tàu", 10.3375, 107.0926),
    ("bai-truoc", "Bãi Trước (Vũng Tàu)", "Bà Rịa – Vũng Tàu", 10.3479, 107.0733),
    ("tuong-chua-kito", "Tượng Chúa Kitô Vua", "Bà Rịa – Vũng Tàu", 10.3266, 107.0870),
    ("ba-ria", "Thành phố Bà Rịa", "Bà Rịa – Vũng Tàu", 10.4967, 107.1685),
    ("long-hai", "Long Hải", "Bà Rịa – Vũng Tàu", 10.3948, 107.2339),
    ("phu-my", "Phú Mỹ", "Bà Rịa – Vũng Tàu", 10.5760, 107.0565),
    ("con-dao", "Côn Đảo", "Bà Rịa – Vũng Tàu", 8.6930, 106.6090),
]

AREAS = [{"id": i, "name": n, "group": g, "lat": la, "lng": lo} for i, n, g, la, lo in _RAW]
AREA_BY_ID = {a["id"]: a for a in AREAS}
