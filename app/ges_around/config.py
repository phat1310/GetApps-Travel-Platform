"""Hằng số của GEs Around — chỉnh ở ĐÂY, không rải trong code.

MÔ HÌNH THỜI GIAN DI CHUYỂN (phần AI/ML của tính năng)
------------------------------------------------------
Với mỗi phương tiện v:   phút_di_chuyển = a_v * d + b_v     (d = khoảng cách đường chim bay, km)
Hệ số (a, b) được HỒI QUY TUYẾN TÍNH (bình phương tối thiểu) trên 25 cặp điểm do nhóm tự đo tay trên
Google Maps (xlsx "ges_do_tay_google_maps"): xe máy n=10, xe đạp n=5, ô tô n=5, đi bộ n=5.
  Xe máy  : R²=0.886  MAE 5.9 ph   LOO-CV MAE 7.6 ph
  Xe đạp  : R²=0.985  MAE 1.0 ph   LOO-CV MAE 1.7 ph
  Ô tô    : R²=0.918  MAE 7.1 ph   LOO-CV MAE 11.2 ph
  Đi bộ   : R²=0.985  MAE 1.8 ph   LOO-CV MAE 3.5 ph  (refit qua gốc toạ độ vì b âm vô lý)
  Xe buýt : KHÔNG có dữ liệu đo — ước lượng = ô tô × 1.4 + 12 phút (chờ xe). Metro: không hỗ trợ.
LƯU Ý TRUNG THỰC: số đo trên Google Maps nhiều khả năng đã gồm tình trạng giao thông lúc đo (chiều tối),
nên mô hình thiên về "giờ thường/đông" chứ không phải đường vắng. Mẫu nhỏ → sai số vài phút đến ~10 phút;
vì vậy nhân thêm hệ số an toàn SAFETY để lỡ sai thì sai theo hướng AN TOÀN (đi dư giờ, không thiếu giờ).
"""

# CẢNH BÁO DỮ LIỆU: hệ số xe đạp khớp từ 5 mẫu (a=2.18) NHANH HƠN xe máy (a=2.47) — vô lý ngoài đời, do 5 mẫu
# xe đạp đo ở quãng ngắn. Để tránh gợi ý sai (đạp xe mà "đến nhanh hơn" xe máy) ta ép xe đạp chậm hơn xe máy tối thiểu 25%.
# Muốn dùng số đo thật: đo thêm ≥5 cặp xe đạp ở quãng 6–15 km rồi thay BIKE_A bằng hệ số hồi quy mới.
BIKE_A_FITTED = 2.18
BIKE_A = max(BIKE_A_FITTED, 2.47 * 1.25)

# vehicle_id: (nhãn, a [phút/km], b [phút], travelmode của Google Maps)
VEHICLES = {
    "walk":      ("Đi bộ",   19.5,  0.0,  "walking"),
    "bike":      ("Xe đạp",   BIKE_A, 6.06, "bicycling"),
    "motorbike": ("Xe máy",   2.47, 5.46, "two-wheeler"),
    "car":       ("Ô tô",     2.637, 6.56, "driving"),
    "bus":       ("Xe buýt",  2.637 * 1.4, 6.56 * 1.4 + 12.0, "transit"),
}
VEHICLE_ORDER = ["motorbike", "car", "bus", "bike", "walk"]
SAFETY = 1.10                      # nhân vào thời gian di chuyển ước tính

# Thời gian lưu lại tại điểm đến (phút) theo nhu cầu — dùng cho quy tắc "đi + chơi + về ≤ thời gian rảnh"
DWELL_MIN = {"an_uong": 45, "giai_tri": 90, "tham_quan": 60}
GROUPS = ["an_uong", "giai_tri", "tham_quan"]
GROUP_LABEL = {"an_uong": "Ăn uống", "giai_tri": "Giải trí", "tham_quan": "Tham quan"}

FREE_MIN_CHOICES = (30, 45, 60, 90, 120, 180, 240, 360, 480)   # phút; server chỉ nhận khoảng 20..720
FREE_MIN_RANGE = (20, 720)
BUDGET_MAX = 20_000_000
MAX_PER_GROUP_TOTAL = 30           # tối đa kết quả / phương tiện (chia đều cho các nhu cầu đã chọn)

# Khung toạ độ HCM mới (HCM cũ + Bình Dương + Bà Rịa–Vũng Tàu, gồm Côn Đảo) — chỉ để chặn GPS ngoài vùng
REGION_BBOX = (8.40, 105.95, 11.70, 107.60)   # lat_min, lon_min, lat_max, lon_max

# Giới hạn tần suất: tối đa N lần tìm / cửa sổ giây / người dùng (trong bộ nhớ của từng worker)
RATE_LIMIT = (20, 60)

# Giá ƯỚC TÍNH (VND/người, thấp–cao) theo loại hình khi chưa có giá thật. Hiển thị là "ước tính".
COST_BY_KIND = {
    "cafe": (25_000, 80_000), "coffee_shop": (25_000, 80_000), "coffee": (25_000, 80_000), "tea": (20_000, 60_000),
    "restaurant": (40_000, 200_000), "fast_food": (30_000, 90_000), "fast_food_restaurant": (30_000, 90_000),
    "food_court": (30_000, 100_000), "bakery": (15_000, 60_000), "pastry": (20_000, 70_000),
    "ice_cream": (10_000, 50_000), "beverages": (15_000, 50_000), "bar": (80_000, 300_000), "pub": (80_000, 300_000),
    "nightclub": (150_000, 500_000), "marketplace": (0, 100_000),
    "cinema": (60_000, 150_000), "karaoke_box": (80_000, 250_000), "theatre": (100_000, 400_000),
    "amusement_arcade": (50_000, 200_000), "sports_centre": (30_000, 150_000), "casino": (0, 0),
    "mall": (0, 0), "stadium": (0, 150_000), "golf_course": (500_000, 3_000_000), "resort": (100_000, 1_000_000),
    "museum": (20_000, 60_000), "zoo": (40_000, 120_000), "aquarium": (100_000, 250_000),
    "amusement_park": (100_000, 500_000),
    "park": (0, 0), "garden": (0, 20_000), "beach": (0, 0), "viewpoint": (0, 0), "attraction": (0, 60_000),
    "place_of_worship": (0, 0), "monument": (0, 0), "memorial": (0, 0), "ruins": (0, 0), "peak": (0, 0),
    "cave_entrance": (0, 50_000), "public_plaza": (0, 0),
    "casual_eatery": (25_000, 100_000), "non_alcoholic_beverage_venue": (20_000, 60_000), "smoothie_juice_bar": (20_000, 60_000),
    "food_truck_stand": (20_000, 70_000), "alcoholic_beverage_venue": (80_000, 300_000), "lounge": (100_000, 300_000),
    "brewery": (80_000, 250_000), "winery": (100_000, 400_000), "food_and_drink": (30_000, 150_000),
    "movie_theater": (60_000, 150_000), "art_gallery": (0, 50_000), "music_venue": (80_000, 250_000),
    "dance_club": (150_000, 500_000), "arcade": (50_000, 200_000), "stadium_arena": (0, 150_000),
    "theatre_venue": (100_000, 400_000), "gaming_venue": (30_000, 150_000), "performing_arts_venue": (100_000, 400_000),
    "comedy_club": (100_000, 300_000), "event_venue": (0, 300_000), "fairgrounds": (0, 100_000),
    "animal_attraction": (30_000, 120_000), "amusement_attraction": (50_000, 300_000), "planetarium": (30_000, 100_000),
    "science_attraction": (30_000, 100_000), "cultural_center": (0, 50_000), "historic_site": (0, 30_000),
    "buddhist_place_of_worship": (0, 0), "christian_place_of_worship": (0, 0), "hindu_place_of_worship": (0, 0),
    "muslim_place_of_worship": (0, 0), "religious_organization": (0, 0), "sculpture_statue": (0, 0),
    "castle": (0, 40_000), "fort": (0, 40_000), "lighthouse": (0, 30_000), "national_park": (0, 60_000),
}
COST_BY_GROUP = {"an_uong": (30_000, 150_000), "giai_tri": (0, 150_000), "tham_quan": (0, 50_000)}

# Nhãn tiếng Việt cho loại hình (khoá = phần sau dấu '=' của OSM hoặc category của Overture)
KIND_LABEL = {
    "cafe": "Quán cà phê", "coffee_shop": "Quán cà phê", "coffee": "Quán cà phê", "tea": "Trà / trà sữa",
    "restaurant": "Nhà hàng / quán ăn", "fast_food": "Đồ ăn nhanh", "fast_food_restaurant": "Đồ ăn nhanh",
    "food_court": "Khu ẩm thực", "bakery": "Tiệm bánh", "pastry": "Tiệm bánh", "ice_cream": "Kem",
    "beverages": "Đồ uống", "bar": "Quán bar", "pub": "Pub / quán nhậu", "nightclub": "Club", "marketplace": "Chợ",
    "cinema": "Rạp chiếu phim", "karaoke_box": "Karaoke", "theatre": "Nhà hát", "amusement_arcade": "Khu game",
    "sports_centre": "Trung tâm thể thao", "casino": "Casino", "mall": "Trung tâm thương mại",
    "stadium": "Sân vận động", "golf_course": "Sân golf", "resort": "Khu nghỉ dưỡng", "museum": "Bảo tàng",
    "zoo": "Sở thú", "aquarium": "Thủy cung", "amusement_park": "Công viên giải trí", "park": "Công viên",
    "garden": "Vườn / thảo cầm viên", "beach": "Bãi biển", "viewpoint": "Điểm ngắm cảnh", "attraction": "Điểm tham quan",
    "place_of_worship": "Chùa / nhà thờ / đền", "monument": "Tượng đài", "memorial": "Đài tưởng niệm",
    "ruins": "Di tích", "peak": "Núi / đồi", "cave_entrance": "Hang động", "public_plaza": "Quảng trường",
    "events_venue": "Địa điểm sự kiện", "yes": "Di tích lịch sử", "aircraft": "Di tích (máy bay)",
    "fishing": "Câu cá",
    "casual_eatery": "Quán ăn", "non_alcoholic_beverage_venue": "Quán nước", "smoothie_juice_bar": "Nước ép / sinh tố",
    "food_truck_stand": "Xe / quầy đồ ăn", "alcoholic_beverage_venue": "Quán rượu / bia", "lounge": "Lounge",
    "brewery": "Nhà máy bia", "winery": "Rượu vang", "food_and_drink": "Ăn uống", "movie_theater": "Rạp chiếu phim",
    "art_gallery": "Phòng tranh", "music_venue": "Karaoke / nhạc sống", "dance_club": "Club", "arcade": "Khu game",
    "stadium_arena": "Sân vận động", "theatre_venue": "Nhà hát", "gaming_venue": "Khu game",
    "performing_arts_venue": "Nghệ thuật biểu diễn", "comedy_club": "Hài kịch", "event_venue": "Địa điểm sự kiện",
    "fairgrounds": "Hội chợ", "animal_attraction": "Khu động vật", "amusement_attraction": "Trò chơi giải trí",
    "planetarium": "Cung thiên văn", "science_attraction": "Khoa học", "cultural_center": "Trung tâm văn hóa",
    "historic_site": "Di tích lịch sử", "buddhist_place_of_worship": "Chùa", "christian_place_of_worship": "Nhà thờ",
    "hindu_place_of_worship": "Đền Hindu", "muslim_place_of_worship": "Thánh đường", "religious_organization": "Cơ sở tôn giáo",
    "sculpture_statue": "Tượng", "castle": "Thành / lâu đài", "fort": "Pháo đài", "lighthouse": "Hải đăng",
    "national_park": "Vườn quốc gia",
}

ATTRIBUTION = "Dữ liệu địa điểm: © OpenStreetMap contributors (ODbL) và Overture Maps Foundation."
