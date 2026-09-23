"""
Routes API — REST API dùng JWT, dành cho mobile app/client ngoài.
Sườn chỉ có 1 endpoint mẫu để chứng minh JWT hoạt động đúng.
Khánh sẽ mở rộng thêm /api/feed, /api/photos... ở tuần 6.
"""
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from app.api import api_bp
from app.extensions import db
from app.models import User

@api_bp.route("/login", methods=["POST"])
def api_login():
    from flask import request
    data = request.get_json()
    user = User.query.filter_by(username=data.get("username")).first()

    if not user or not user.check_password(data.get("password")):
        return jsonify({"error": "Sai username hoặc password"}), 401

    access_token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": access_token})

@api_bp.route("/users/<int:user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):
    user = db.get_or_404(User, user_id)
    return jsonify({
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "bio": user.bio,
    })