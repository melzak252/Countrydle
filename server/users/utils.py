import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi_mail import MessageSchema

from db import get_db
from db.models import User
from db.repositories.user import UserRepository
from fastapi import BackgroundTasks, Cookie, Depends, HTTPException, Request, status, Response

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from sqlalchemy.ext.asyncio import AsyncSession
from utils.email import fm, fm_noreply

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REMEMBER_ME_EXPIRE_DAYS = int(os.getenv("REMEMBER_ME_EXPIRE_DAYS", "90"))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def set_access_cookie(response: Response, request: Request, email: str, *, remember_me: bool = False):
    lifetime = timedelta(days=REMEMBER_ME_EXPIRE_DAYS) if remember_me else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expiration = datetime.now(UTC) + lifetime
    token = jwt.encode(
        {"sub": email, "exp": expiration, "remember_me": remember_me},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
        expires=expiration,
        max_age=int(lifetime.total_seconds()),
    )


def clear_access_cookie(response: Response, request: Request):
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )


def _decode_access_token(token: str):
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
    return payload


def verify_access_token(token: str):
    return _decode_access_token(token)["sub"]


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
    request: Request,
    response: Response,
    access_token: str = Cookie(None),
    session: AsyncSession = Depends(get_db),
) -> User:
    claims = _decode_access_token(access_token)
    user = await UserRepository(session).get_by_email(claims["sub"])

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # The signed preference must survive renewal; otherwise /users/me shortens
    # a remembered login back to the ordinary idle timeout.
    set_access_cookie(response, request, user.email, remember_me=claims.get("remember_me") is True)

    return user


async def get_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges",
        )
    return user


async def get_current_or_guest_user(
    request: Request,
    response: Response,
    access_token: str = Cookie(None),
    session: AsyncSession = Depends(get_db),
) -> User | None:
    client_thinks_authenticated = request.headers.get("x-client-authenticated", "").lower() == "true"

    if access_token:
        try:
            return await get_current_user(
                request=request,
                response=response,
                access_token=access_token,
                session=session,
            )
        except HTTPException as exc:
            if client_thinks_authenticated:
                raise exc
            pass

    if client_thinks_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or missing. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return None


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
