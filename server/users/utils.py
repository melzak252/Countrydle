import os
from datetime import UTC, datetime, timedelta

from fastapi_mail import MessageSchema

from db import get_db
from db.models import User
from db.repositories.user import UserRepository
from fastapi import BackgroundTasks, Cookie, Depends, HTTPException, status, Response

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from sqlalchemy.ext.asyncio import AsyncSession
from utils.email import fm, fm_noreply

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username


def create_verification_token(email: str):
    expiration = datetime.now() + timedelta(hours=24)  # Token valid for 24 hours
    to_encode = {"email": email, "exp": expiration}
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token


def verify_email_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["email"]
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Token expired"
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token"
        )


async def get_current_user(
    response: Response, access_token: str = Cookie(None), session: AsyncSession = Depends(get_db)
) -> User:
    print(f"DEBUG: get_current_user called. Token: {access_token}")
    if access_token is None:
        print("DEBUG: Token is None")

    try:
        email = verify_access_token(access_token)
        print(f"DEBUG: Token verified. Email: {email}")
    except Exception as e:
        print(f"DEBUG: verify_access_token failed: {e}")
        raise

    user = await UserRepository(session).get_by_email(email)

    if not user:
        print("DEBUG: User not found in DB")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Refresh the token and cookie
    new_access_token = create_access_token(data={"sub": user.email})
    
    # Calculate expiration time for the cookie
    expiration = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=False,  # Set to False for local development (HTTP)
        samesite="lax",
        path="/",
        expires=expiration.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

    return user



async def send_verification_email(
    user: User, background_tasks: BackgroundTasks
) -> None:
    token = create_verification_token(user.email)

    verification_url = f"https://jmelzacki.com/api/verify-email?token={token}"
    message = MessageSchema(
        subject="Verify Your Email",
        recipients=[user.email],  # List of recipients
        subtype="html",
        template_body={"username": user.username, "verification_url": verification_url},
    )

    background_tasks.add_task(
        fm_noreply.send_message, message, template_name="verification_email.html"
    )
