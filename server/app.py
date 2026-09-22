from dotenv import load_dotenv

load_dotenv()

import logging
import time
import traceback

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_mail import MessageSchema
from utils.google import verify_google_token

import datetime
from utils.app import lifespan
from countrydle import router as countrydle_router
from powiatdle import router as powiatdle_router
from us_statedle import router as us_statedle_router
from wojewodztwodle import router as wojewodztwodle_router
from continental import router as continental_router
from blog import router as blog_router
from admin import router as admin_router
from answer_reports import router as answer_reports_router, admin_router as admin_answer_reports_router
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
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from users import router as users_router
from users.utils import (
    create_access_token,
    send_verification_email,
    verify_email_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

from utils.email import fm_noreply
from version import SERVER_VERSION

app = FastAPI(lifespan=lifespan)

logger = logging.getLogger("countrydle")
logging.basicConfig(level=logging.INFO)

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
    allow_origin_regex="https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_question_requests_and_errors(request: Request, call_next):
    """Log enough detail to debug local /question failures in Docker logs."""
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.error(
            "Unhandled error on %s %s after %.1fms: %s",
            request.method,
            request.url.path,
            elapsed_ms,
            repr(exc),
        )
        logger.error("%s", traceback.format_exc())

        # For question-asking endpoints, NEVER crash the game with a 500!
        if request.url.path.endswith("/question"):
            return JSONResponse(
                status_code=200,
                content={
                    "id": 0,
                    "original_question": "",
                    "question": "Question could not be verified.",
                    "valid": False,
                    "answer": None,
                    "explanation": "Unable to verify this question right now. Your turn was not deducted.",
                    "context": "error:handled",
                    "user": None,
                },
            )

        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred. Please try again."},
        )

    if request.url.path.endswith("/question") or response.status_code >= 500:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "Request: %s %s -> %s in %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Global exception caught on %s %s: %s", request.method, request.url.path, repr(exc))
    logger.error("%s", traceback.format_exc())
    if request.url.path.endswith("/question"):
        return JSONResponse(
            status_code=200,
            content={
                "id": 0,
                "original_question": "",
                "question": "Question could not be verified.",
                "valid": False,
                "answer": None,
                "explanation": "Unable to verify this question right now. Your turn was not deducted.",
                "context": "error:handled",
                "user": None,
            },
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="templates"), name="static")

app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(countrydle_router, tags=["countrydle"])
app.include_router(powiatdle_router, tags=["powiatdle"])
app.include_router(us_statedle_router, tags=["us_statedle"])
app.include_router(wojewodztwodle_router, tags=["wojewodztwodle"])
app.include_router(continental_router, tags=["continental"])
app.include_router(blog_router)
app.include_router(admin_router)
app.include_router(answer_reports_router)
app.include_router(admin_answer_reports_router)



@app.get("/")
async def root():
    return {"message": "Welcome to the Game API!"}


@app.get("/version")
async def get_version():
    return {"version": SERVER_VERSION}


@app.get("/sitemap.xml", response_class=Response)
async def dynamic_sitemap(session: AsyncSession = Depends(get_db)):
    """Dynamically generated XML sitemap for search engine crawlers and AdSense reviewers."""
    from db.models.blog import DailyBlogPost
    from sqlalchemy import desc, select
    posts = []
    try:
        res = await session.execute(
            select(DailyBlogPost.slug, DailyBlogPost.date).order_by(desc(DailyBlogPost.date))
        )
        posts = res.all()
    except Exception as exc:
        logger.warning("Could not fetch blog posts for sitemap: %s", exc)

    urls_xml = [
        "<url><loc>https://countrydle.online/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>",
        "<url><loc>https://countrydle.online/game</loc><changefreq>daily</changefreq><priority>0.9</priority></url>",
        "<url><loc>https://countrydle.online/us-states</loc><changefreq>daily</changefreq><priority>0.9</priority></url>",
        "<url><loc>https://countrydle.online/powiaty</loc><changefreq>daily</changefreq><priority>0.9</priority></url>",
        "<url><loc>https://countrydle.online/wojewodztwa</loc><changefreq>daily</changefreq><priority>0.9</priority></url>",
        "<url><loc>https://countrydle.online/blog</loc><changefreq>daily</changefreq><priority>0.9</priority></url>",
        "<url><loc>https://countrydle.online/leaderboard</loc><changefreq>daily</changefreq><priority>0.8</priority></url>",
        "<url><loc>https://countrydle.online/archive</loc><changefreq>daily</changefreq><priority>0.8</priority></url>",
        "<url><loc>https://countrydle.online/faq</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>",
        "<url><loc>https://countrydle.online/about</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>",
        "<url><loc>https://countrydle.online/contact</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>",
        "<url><loc>https://countrydle.online/privacy-policy</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>",
        "<url><loc>https://countrydle.online/terms</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>",
        "<url><loc>https://countrydle.online/cookie-policy</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>",
    ]

    for p in posts:
        urls_xml.append(
            f"<url><loc>https://countrydle.online/blog/{p.slug}</loc><lastmod>{p.date}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>"
        )

    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  ' + "\n  ".join(urls_xml) + "\n</urlset>"
    return Response(content=xml_content, media_type="application/xml")

@app.get("/cache-stats")
async def get_cache_stats():
    """Returns runtime statistics for the in-memory question plan cache."""
    from utils.plan_cache import plan_cache
    return plan_cache.stats()



@app.get("/time")
async def get_server_time():
    """Returns the current server time and the time until the next midnight (UTC)"""
    now = datetime.datetime.now(datetime.timezone.utc)
    tomorrow = now + datetime.timedelta(days=1)
    next_midnight = datetime.datetime(
        year=tomorrow.year,
        month=tomorrow.month,
        day=tomorrow.day,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=datetime.timezone.utc
    )
    
    # If the server uses local time for date.today(), we should probably use local time here too.
    # However, standard practice is usually UTC. 
    # Let's check if date.today() is timezone aware. It usually returns local date.
    # If the server is running in UTC (which it likely is in Docker), then UTC is correct.
    
    return {
        "server_time": now.isoformat(),
        "next_game_at": next_midnight.isoformat()
    }


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

    expiration = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to False for local development (HTTP)
        samesite="lax",
        path="/",
        expires=expiration.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
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

    expiration = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to False for local development (HTTP)
        samesite="lax",
        path="/",
        expires=expiration.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
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
