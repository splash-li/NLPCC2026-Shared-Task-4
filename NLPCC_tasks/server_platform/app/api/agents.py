from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt

from server_platform.app.core.user_management import authenticate_user, create_user, get_user, user_exists
from server_platform.app.models.agent import AgentRegistration

# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
# FK！
ACCESS_TOKEN_EXPIRE_MINUTES = 6000000

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/agents/token")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(username)
    if user is None:
        raise credentials_exception
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


@router.post("/register")
def register_agent(agent: AgentRegistration):
    # 检查用户是否已存在
    if user_exists(agent.username):
        # 如果用户已存在，尝试验证密码
        authenticated_user = authenticate_user(agent.username, agent.password)
        if authenticated_user:
            # 用户已存在且密码正确，直接返回成功
            return {"username": agent.username, "status": "existing_user_authenticated"}
        else:
            # 用户已存在但密码错误
            raise HTTPException(status_code=400, detail="Username already exists with different password")

    # 用户不存在，创建新用户
    user = create_user(agent.username, agent.password)
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create user")

    # 创建用户后立即尝试验证登录，确保可以成功登录
    authenticated_user = authenticate_user(agent.username, agent.password)
    if not authenticated_user:
        # 如果创建后无法登录，这是一个严重错误
        raise HTTPException(status_code=500, detail="User created but login verification failed")

    return {"username": agent.username, "status": "new_user_created"}


@router.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user["username"]}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}
