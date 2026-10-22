"""
Script tiện ích: cấp/gỡ quyền ADMIN cho 1 tài khoản đã tồn tại.

Vì web KHÔNG có form tự đăng ký admin (đúng thiết kế bảo mật — is_admin chỉ
được gán qua DB/script, xem app/models/user.py), mỗi thành viên team cần
chạy script này trên máy mình để tạo tài khoản admin test riêng, thay vì
sửa tay vào DB bằng tool khác.

Cách dùng (đứng ở thư mục gốc GetApps/, đã activate venv):
    python scripts/create_admin.py <username_hoac_email> --grant
    python scripts/create_admin.py <username_hoac_email> --revoke

Ví dụ cấp quyền admin cho tài khoản 'admin_test' (phải đăng ký tài khoản
này qua form /register bình thường TRƯỚC, script chỉ nâng quyền, không
tạo user mới):
    python scripts/create_admin.py admin_test --grant
"""
import argparse
import sys

from app import create_app
from app.extensions import db
from app.models.user import User


def main():
    parser = argparse.ArgumentParser(description="Cấp/gỡ quyền admin cho 1 user đã có sẵn.")
    parser.add_argument("identifier", help="username hoặc email của tài khoản")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--grant", action="store_true", help="cấp quyền admin (is_admin = True)")
    group.add_argument("--revoke", action="store_true", help="gỡ quyền admin (is_admin = False)")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        user = User.query.filter(
            db.or_(User.username == args.identifier, User.email == args.identifier)
        ).first()

        if user is None:
            print(f"❌ Không tìm thấy user '{args.identifier}'. "
                  f"Đăng ký tài khoản này qua /register trước, rồi chạy lại script.")
            sys.exit(1)

        user.is_admin = bool(args.grant)
        db.session.commit()

        action = "CẤP" if args.grant else "GỠ"
        print(f"✅ Đã {action} quyền admin cho '{user.username}' (email: {user.email}). "
              f"is_admin = {user.is_admin}")


if __name__ == "__main__":
    main()
