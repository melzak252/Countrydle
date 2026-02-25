import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

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
GUEST_COOKIE_NAME = "guest_id"
GUEST_EMAIL_DOMAIN = "guest.local"
GUEST_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365

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
    response: Response,
    access_token: str = Cookie(None),
    session: AsyncSession = Depends(get_db),
) -> User:
    email = verify_access_token(access_token)

    user = await UserRepository(session).get_by_email(email)

    if not user:
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
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return user


def is_guest_user(user: User | None) -> bool:
    if not user:
        return False

    return user.email.endswith(f"@{GUEST_EMAIL_DOMAIN}")


async def _get_or_create_guest_user(session: AsyncSession, guest_id: str) -> User:
    guest_email = f"guest_{guest_id}@{GUEST_EMAIL_DOMAIN}"
    user_repository = UserRepository(session)
    guest_user = await user_repository.get_by_email(guest_email)
    if guest_user:
        return guest_user

    guest_user = User(
        username=f"guest_{guest_id[:12]}",
        email=guest_email,
        verified=True,
    )
    session.add(guest_user)
    await session.commit()
    await session.refresh(guest_user)
    return guest_user


async def get_current_or_guest_user(
    response: Response,
    access_token: str = Cookie(None),
    guest_id: str = Cookie(None, alias=GUEST_COOKIE_NAME),
    session: AsyncSession = Depends(get_db),
) -> User:
    if access_token:
        try:
            return await get_current_user(
                response=response,
                access_token=access_token,
                session=session,
            )
        except HTTPException:
            pass

    if not guest_id:
        guest_id = uuid4().hex
        response.set_cookie(
            key=GUEST_COOKIE_NAME,
            value=guest_id,
            httponly=True,
            secure=False,
            samesite="lax",
            path="/",
            max_age=GUEST_COOKIE_MAX_AGE_SECONDS,
        )

    return await _get_or_create_guest_user(session, guest_id)


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
