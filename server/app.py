from dotenv import load_dotenv

load_dotenv()

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_mail import MessageSchema
from utils.google import verify_google_token

import datetime
from utils.app import lifespan
from countrydle import router as countrydle_router
from db import get_db
from db.repositories.user import UserRepository
from schemas.user import GoogleSignIn, UserCreate, UserDisplay
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from users import router as users_router
from users.utils import (
    create_access_token,
    send_verification_email,
    verify_email_token,
)
from utils.email import fm_noreply

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:80",
        "http://localhost",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:80",
        "http://127.0.0.1",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="templates"), name="static")

app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(countrydle_router, tags=["countrydle"])


@app.get("/")
async def root():
    return {"message": "Welcome to the Game API!"}


@app.post("/login", response_model=UserDisplay)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
):
    user = await UserRepository(session).get_user(form_data.username)

    if not user or not UserRepository.verify_password(
        form_data.password, user.hashed_password
    ):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # if not user.verified:
    #     raise HTTPException(
    #         status_code=400,
    #         detail="User's email is not verified! Verify your email before login!",
    #     )

    access_token = create_access_token(data={"sub": user.email})


    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to False for local development (HTTP)
        samesite="lax",
        path="/",
    )

    return user


@app.post("/google-signin", response_model=UserDisplay)
async def google_signin(
    credential: GoogleSignIn,
    response: Response,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    token_info = verify_google_token(credential.credential)
    user = await UserRepository(session).get_by_email(token_info["email"])

    if not user:
        user = await UserRepository(session).register_by_google(token_info)
        message = MessageSchema(
            subject="Verify Your Email",
            recipients=[user.email],  # List of recipients
            subtype="html",
            template_body={"username": user.username},
        )
        background_tasks.add_task(
            fm_noreply.send_message, message, template_name="google_login_alert.html"
        )

    access_token = create_access_token(data={"sub": user.email})


    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to False for local development (HTTP)
        samesite="lax",
        path="/",
    )
    return user


@app.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response):
    response.set_cookie(
        key="access_token",
        value="",
        httponly=True,
        secure=False,  # Set to False for local development (HTTP)
        expires=datetime.datetime.now().isoformat(),
        samesite="lax",
        path="/",
    )
    return {"success": True}


@app.post("/register")
async def register(
    user: UserCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    new_user = await UserRepository(session).register_user(user=user)
    # await send_verification_email(new_user, background_tasks)
    return {"message": "User registered successfully!", "ok": True}


@app.get("/verify-email")
async def verify_email(
    request: Request, token: str, session: AsyncSession = Depends(get_db)
):
    email = verify_email_token(token)
    user = await UserRepository(session).verify_user_email(email)
    return templates.TemplateResponse(
        "verified_email.html",
        {
            "request": request,
            "username": user.username,
        },
    )
