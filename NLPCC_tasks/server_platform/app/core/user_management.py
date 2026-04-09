import json
import os
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 用户数据文件路径
USER_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "users.json")

def _load_users():
    """从文件加载用户数据"""
    if not os.path.exists(USER_DATA_FILE):
        # 如果文件不存在，创建空文件
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
        return {}
    
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # 如果文件损坏，创建新的空文件
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
        return {}

def _save_users(users_db):
    """保存用户数据到文件"""
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_db, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_user(username, password):
    """创建用户，如果用户已存在则返回None"""
    users_db = _load_users()
    
    if username in users_db:
        return None
    
    hashed_password = get_password_hash(password)
    users_db[username] = {
        "password": hashed_password,
        "created_at": "2025-01-01"  # 简单的时间戳
    }
    
    if _save_users(users_db):
        return {"username": username}
    else:
        # 保存失败，回滚
        return None

def authenticate_user(username, password):
    """验证用户登录"""
    users_db = _load_users()
    
    if username not in users_db:
        return None
    
    user = users_db[username]
    if not verify_password(password, user["password"]):
        return None
    
    return {"username": username}

def get_user(username: str):
    """获取用户信息"""
    users_db = _load_users()
    
    if username in users_db:
        return users_db[username]
    return None

def user_exists(username: str) -> bool:
    """检查用户是否存在"""
    users_db = _load_users()
    return username in users_db
