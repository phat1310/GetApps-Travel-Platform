"""Form PLANS — Biểu mẫu tạo và quản lý Lịch trình chuyến đi (Flask-WTF + CSRF).
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, DateField, FloatField, SelectField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Length, Optional


class PlanCreateForm(FlaskForm):
    """Biểu mẫu Tạo mới hoặc Chỉnh sửa Lịch trình du lịch."""
    title = StringField(
        "Tên chuyến đi / Tiêu đề lịch trình",
        validators=[
            DataRequired(message="Vui lòng nhập tên chuyến đi"),
            Length(max=150, message="Tiêu đề tối đa 150 ký tự")
        ]
    )
    destination = StringField(
        "Điểm đến chính",
        validators=[
            DataRequired(message="Vui lòng nhập điểm đến chính"),
            Length(max=150, message="Tên điểm đến tối đa 150 ký tự")
        ]
    )
    start_date = DateField(
        "Ngày bắt đầu",
        validators=[Optional()],
        format='%Y-%m-%d'
    )
    end_date = DateField(
        "Ngày kết thúc",
        validators=[Optional()],
        format='%Y-%m-%d'
    )
    trip_type = StringField(
        "Dạng chuyến đi",
        validators=[Optional(), Length(max=50)]
    )
    participants_count = IntegerField(
        "Số người tham gia",
        validators=[Optional()]
    )
    estimated_budget = FloatField(
        "Dự toán ngân sách (VNĐ)",
        validators=[Optional()]
    )
    visibility = SelectField(
        "Chế độ hiển thị",
        choices=[
            ("public", "Công khai — Chia sẻ cùng cộng đồng"),
            ("private", "Riêng tư — Chỉ mình tôi xem được")
        ],
        default="public"
    )
    cover_image = FileField(
        "Ảnh bìa lịch trình",
        validators=[
            Optional(),
            FileAllowed(['jpg', 'jpeg', 'png', 'webp'], message="Chỉ chấp nhận file ảnh JPG, PNG, WEBP")
        ]
    )
    attachment_file = FileField(
        "Tài liệu đính kèm (PDF, Word, Excel, PowerPoint)",
        validators=[
            Optional(),
            FileAllowed(['pdf', 'docx', 'xlsx', 'pptx'], message="Chỉ chấp nhận file PDF, DOCX, XLSX, PPTX")
        ]
    )
    description = TextAreaField(
        "Mô tả & Lưu ý chung cho chuyến đi",
        validators=[Optional()]
    )
    submit = SubmitField("Lưu lịch trình")


class PlanDayForm(FlaskForm):
    """Biểu mẫu thêm Ngày trong hành trình."""
    title = StringField(
        "Chủ đề ngày",
        validators=[Optional(), Length(max=150)]
    )
    note = TextAreaField(
        "Ghi chú",
        validators=[Optional()]
    )
    submit = SubmitField("Thêm ngày")


class PlanStopForm(FlaskForm):
    """Biểu mẫu thêm Điểm dừng / Hoạt động trong ngày."""
    location_name = StringField(
        "Địa điểm / Điểm tham quan / Quán xá",
        validators=[
            DataRequired(message="Vui lòng nhập tên địa điểm"),
            Length(max=150)
        ]
    )
    address = StringField(
        "Địa chỉ",
        validators=[Optional(), Length(max=255)]
    )
    arrival_time = StringField(
        "Giờ ghé thăm (vd: 08:30)",
        validators=[Optional(), Length(max=20)]
    )
    transportation = SelectField(
        "Phương tiện di chuyển",
        choices=[
            ("Xe máy", "Xe máy"),
            ("Ô tô / Taxi", "Ô tô / Taxi"),
            ("Đi bộ", "Đi bộ"),
            ("Xe bus", "Xe bus"),
            ("Tàu hỏa", "Tàu hỏa"),
            ("Máy bay", "Máy bay")
        ],
        default="Xe máy"
    )
    estimated_cost = FloatField(
        "Chi phí dự kiến (VNĐ)",
        validators=[Optional()],
        default=0.0
    )
    notes = TextAreaField(
        "Lưu ý (món ăn ngon, giá vé...)",
        validators=[Optional()]
    )
    submit = SubmitField("Thêm điểm dừng")
