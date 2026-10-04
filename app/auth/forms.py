"""Form AUTH — Các biểu mẫu Đăng ký, Đăng nhập và Hồ sơ người dùng với Flask-WTF và CSRF protection.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo


class LoginForm(FlaskForm):
    """Biểu mẫu Đăng nhập."""
    username = StringField(
        "Tên đăng nhập hoặc Email",
        validators=[DataRequired(message="Vui lòng nhập tên đăng nhập hoặc email")]
    )
    password = PasswordField(
        "Mật khẩu",
        validators=[DataRequired(message="Vui lòng nhập mật khẩu")]
    )
    remember_me = BooleanField("Ghi nhớ đăng nhập")
    submit = SubmitField("Đăng nhập")


class RegisterForm(FlaskForm):
    """Biểu mẫu Đăng ký thành viên mới."""
    username = StringField(
        "Tên người dùng",
        validators=[
            DataRequired(message="Vui lòng nhập tên người dùng"),
            Length(min=3, max=64, message="Tên người dùng từ 3 đến 64 ký tự")
        ]
    )
    email = StringField(
        "Địa chỉ Email",
        validators=[
            DataRequired(message="Vui lòng nhập email"),
            Email(message="Địa chỉ email không đúng định dạng")
        ]
    )
    password = PasswordField(
        "Mật khẩu",
        validators=[
            DataRequired(message="Vui lòng nhập mật khẩu"),
            Length(min=6, message="Mật khẩu phải có ít nhất 6 ký tự")
        ]
    )
    confirm_password = PasswordField(
        "Xác nhận mật khẩu",
        validators=[
            DataRequired(message="Vui lòng xác nhận lại mật khẩu"),
            EqualTo("password", message="Mật khẩu xác nhận không khớp")
        ]
    )
    role = SelectField(
        "Vai trò tham gia",
        choices=[
            ("traveler", "Traveler • Người đam mê xê dịch"),
            ("local", "Local Guide • Dân bản địa am hiểu"),
            ("creator", "Creator • Tác giả nội dung du lịch"),
            ("owner", "Owner • Chủ địa điểm / Quán xá"),
            ("user", "User • Thành viên cộng đồng")
        ],
        default="traveler"
    )
    agree_terms = BooleanField(
        "Tôi đồng ý với Điều khoản dịch vụ và Chính sách cộng đồng của GEs",
        validators=[DataRequired(message="Vui lòng đồng ý với điều khoản để tiếp tục")]
    )
    submit = SubmitField("Tạo tài khoản GETAPPS")


class EditProfileForm(FlaskForm):
    """Biểu mẫu Cập nhật hồ sơ cá nhân."""
    bio = TextAreaField(
        "Giới thiệu bản thân (Bio)",
        validators=[Length(max=255, message="Tiểu sử tối đa 255 ký tự")]
    )
    phone_number = StringField(
        "Số điện thoại liên hệ",
        validators=[Length(max=20, message="Số điện thoại tối đa 20 ký tự")]
    )
    role = SelectField(
        "Vai trò hiển thị",
        choices=[
            ("traveler", "Traveler"),
            ("local", "Local Guide"),
            ("creator", "Creator"),
            ("owner", "Owner"),
            ("user", "User")
        ]
    )
    submit = SubmitField("Lưu thay đổi")
