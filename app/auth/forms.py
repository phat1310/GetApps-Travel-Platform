import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError


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
            Length(min=8, message="Mật khẩu phải có ít nhất 8 ký tự")
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
            ("traveler", "Traveler Enthusiast • Người đam mê du lịch"),
            ("local", "Local Guides • Hướng dẫn viên địa phương"),
            ("creator", "Travel content creator • Người sáng tạo nội dung du lịch"),
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

    def validate_password(self, field):
        """Xác thực độ phức tạp của mật khẩu: ít nhất 8 ký tự, có chữ hoa, chữ thường, ký tự đặc biệt."""
        pwd = field.data or ""
        if len(pwd) < 8:
            raise ValidationError("Mật khẩu phải có ít nhất 8 ký tự.")
        if not re.search(r'[A-Z]', pwd):
            raise ValidationError("Mật khẩu phải chứa ít nhất 1 chữ in hoa (A-Z).")
        if not re.search(r'[a-z]', pwd):
            raise ValidationError("Mật khẩu phải chứa ít nhất 1 chữ thường (a-z).")
        if not re.search(r'[@$!%*?&#^()_+\-=\[\]{};:\'",.<>\/\\|`~]', pwd):
            raise ValidationError("Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt (!@#$%^&*...).")


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
            ("traveler", "Traveler Enthusiast • Người đam mê du lịch"),
            ("local", "Local Guides • Hướng dẫn viên địa phương"),
            ("creator", "Travel content creator • Người sáng tạo nội dung du lịch"),
            ("owner", "Owner • Chủ địa điểm / Quán xá"),
            ("user", "User • Thành viên cộng đồng")
        ]
    )
    submit = SubmitField("Lưu thay đổi")


class SettingsForm(FlaskForm):
    """Biểu mẫu Cài đặt thông tin tài khoản người dùng theo thiết kế GEs Proposal."""
    nickname = StringField(
        "Biệt danh (Nickname)",
        validators=[Length(max=64, message="Biệt danh tối đa 64 ký tự")]
    )
    profile_tag = StringField(
        "Nhãn (Tags)",
        validators=[Length(max=64, message="Nhãn tối đa 64 ký tự")]
    )
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Vui lòng nhập email"),
            Email(message="Địa chỉ email không đúng định dạng")
        ]
    )
    phone_number = StringField(
        "Số điện thoại",
        validators=[Length(max=20, message="Số điện thoại tối đa 20 ký tự")]
    )
    bio = TextAreaField(
        "Ghi chú / Tiểu sử",
        validators=[Length(max=255, message="Tiểu sử tối đa 255 ký tự")]
    )
    avatar_url = StringField(
        "Đường dẫn ảnh đại diện",
        validators=[Length(max=255, message="Đường dẫn ảnh tối đa 255 ký tự")]
    )
    submit = SubmitField("Lưu thay đổi")



class ChangePasswordForm(FlaskForm):
    """Biểu mẫu Đổi mật khẩu tài khoản người dùng."""
    current_password = PasswordField(
        "Mật khẩu hiện tại",
        validators=[DataRequired(message="Vui lòng nhập mật khẩu hiện tại")]
    )
    new_password = PasswordField(
        "Mật khẩu mới",
        validators=[
            DataRequired(message="Vui lòng nhập mật khẩu mới"),
            Length(min=8, message="Mật khẩu mới phải có ít nhất 8 ký tự")
        ]
    )
    confirm_new_password = PasswordField(
        "Xác nhận mật khẩu mới",
        validators=[
            DataRequired(message="Vui lòng xác nhận mật khẩu mới"),
            EqualTo("new_password", message="Mật khẩu xác nhận không khớp")
        ]
    )
    submit = SubmitField("Cập nhật mật khẩu")

    def validate_new_password(self, field):
        """Kiểm tra độ phức tạp của mật khẩu mới theo chuẩn bảo mật."""
        pwd = field.data or ""
        if len(pwd) < 8:
            raise ValidationError("Mật khẩu mới phải có ít nhất 8 ký tự.")
        if not re.search(r'[A-Z]', pwd):
            raise ValidationError("Mật khẩu mới phải chứa ít nhất 1 chữ in hoa (A-Z).")
        if not re.search(r'[a-z]', pwd):
            raise ValidationError("Mật khẩu mới phải chứa ít nhất 1 chữ thường (a-z).")
        if not re.search(r'[@$!%*?&#^()_+\-=\[\]{};:\'",.<>\/\\|`~]', pwd):
            raise ValidationError("Mật khẩu mới phải chứa ít nhất 1 ký tự đặc biệt (!@#$%^&*...).")


class ForgotPasswordForm(FlaskForm):
    """Biểu mẫu Quên mật khẩu — Hỗ trợ phục hồi qua Email hoặc Số điện thoại."""
    method = SelectField(
        "Phương thức nhận mã xác nhận",
        choices=[
            ("email", "Địa chỉ Email"),
            ("phone", "Số điện thoại (SĐT)")
        ],
        default="email"
    )
    target = StringField(
        "Email hoặc Số điện thoại",
        validators=[DataRequired(message="Vui lòng nhập Email hoặc Số điện thoại đã đăng ký")]
    )
    submit = SubmitField("Gửi mã xác thực")


class ResetPasswordForm(FlaskForm):
    """Biểu mẫu Xác thực OTP và Đặt lại mật khẩu mới."""
    otp = StringField(
        "Mã xác thực OTP (6 chữ số)",
        validators=[
            DataRequired(message="Vui lòng nhập mã OTP 6 chữ số"),
            Length(min=6, max=6, message="Mã OTP gồm chính xác 6 chữ số")
        ]
    )
    new_password = PasswordField(
        "Mật khẩu mới",
        validators=[
            DataRequired(message="Vui lòng nhập mật khẩu mới"),
            Length(min=8, message="Mật khẩu mới phải có ít nhất 8 ký tự")
        ]
    )
    confirm_new_password = PasswordField(
        "Xác nhận mật khẩu mới",
        validators=[
            DataRequired(message="Vui lòng xác nhận mật khẩu mới"),
            EqualTo("new_password", message="Mật khẩu xác nhận không khớp")
        ]
    )
    submit = SubmitField("Xác nhận & Đặt lại mật khẩu")

    def validate_new_password(self, field):
        """Kiểm tra độ phức tạp của mật khẩu mới theo chuẩn bảo mật."""
        pwd = field.data or ""
        if len(pwd) < 8:
            raise ValidationError("Mật khẩu mới phải có ít nhất 8 ký tự.")
        if not re.search(r'[A-Z]', pwd):
            raise ValidationError("Mật khẩu mới phải chứa ít nhất 1 chữ in hoa (A-Z).")
        if not re.search(r'[a-z]', pwd):
            raise ValidationError("Mật khẩu mới phải chứa ít nhất 1 chữ thường (a-z).")
        if not re.search(r'[@$!%*?&#^()_+\-=\[\]{};:\'",.<>\/\\|`~]', pwd):
            raise ValidationError("Mật khẩu mới phải chứa ít nhất 1 ký tự đặc biệt (!@#$%^&*...).")


