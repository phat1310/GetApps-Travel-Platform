"""Utils AUTH — validate input cho đăng ký/đăng nhập.
Tách riêng khỏi routes.py để dễ unit test và tái sử dụng.
"""
import re
 
MIN_PASSWORD_LENGTH = 8
 
 
def validate_password(password: str) -> str | None:
    """Kiểm tra password theo policy tối thiểu (OWASP Authentication Cheat Sheet).
    Trả về None nếu hợp lệ, hoặc chuỗi thông báo lỗi nếu không hợp lệ.
    """
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự"
 
    if not re.search(r"[A-Za-z]", password):
        return "Mật khẩu phải chứa ít nhất 1 chữ cái"
 
    if not re.search(r"[0-9]", password):
        return "Mật khẩu phải chứa ít nhất 1 chữ số"
 
    return None