"""密码强度校验（注册、改密、管理员重置共用）"""

MIN_PASSWORD_LENGTH = 6


def validate_password(password: str) -> str | None:
    """校验通过返回 None，否则返回错误信息。"""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"密码至少 {MIN_PASSWORD_LENGTH} 位"
    return None
