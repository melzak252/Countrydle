from datetime import datetime
from db import get_db
from db.models import User
from schemas.user import ChangePassword, UserDisplay, UserUpdate
from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories.user import UserRepository
from db.repositories.countrydle import CountrydleRepository
from db.repositories.powiatdle import PowiatdleStateRepository
from db.repositories.us_statedle import USStatedleStateRepository
from db.repositories.wojewodztwodle import WojewodztwodleStateRepository
from schemas.statistics import UserProfileStatistics

from .utils import create_access_token, get_current_user, send_verification_email

load_dotenv()
router = APIRouter()


@router.get("/me", response_model=UserDisplay)
async def read_users_me(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
):
    return user


@router.get("/{username}/stats", response_model=UserProfileStatistics)
async def get_user_stats_by_username(
    username: str,
    session: AsyncSession = Depends(get_db)
):
    user = await UserRepository(session).get_user(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    countrydle_stats = await CountrydleRepository(session).get_game_statistics(user)
    powiatdle_stats = await PowiatdleStateRepository(session).get_user_statistics(user)
    us_statedle_stats = await USStatedleStateRepository(session).get_user_statistics(user)
    wojewodztwodle_stats = await WojewodztwodleStateRepository(session).get_user_statistics(user)
    
    return UserProfileStatistics(
        user=user,
        countrydle=countrydle_stats,
        powiatdle=powiatdle_stats,
        us_statedle=us_statedle_stats,
        wojewodztwodle=wojewodztwodle_stats
    )


@router.post("/update")
async def change_username(
    updated_user: UserUpdate,
    response: Response,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    last_update = await UserRepository(session).get_last_user_update(user.id)

    updated_user.username = updated_user.username.strip()
    updated_user.email = updated_user.email.strip()

    if not updated_user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username cannot be empty!"
        )

    if len(updated_user.username) > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be longer than 30 characters!",
        )

    if not updated_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email cannot be empty!"
        )

    if len(updated_user.email) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email cannot be longer than 100 characters!",
        )


    if last_update is not None:
        raise HTTPException(
            status_code=400, detail="Username can only be changed once every 30 days."
        )

    up_user: User = await UserRepository(session).update_user_email_username(
        user.id, updated_user
    )
    if not up_user.verified:

        await send_verification_email(user, background_tasks)
        response.set_cookie(
            key="access_token",
            value="",
            httponly=True,
            secure=True,  # Set to True in production
            samesite="Lax",
            path="/",
        )
        return {
            "email_sent": True,
            "message": "Account updated successfully! You will be logged out!",
        }

    access_token = create_access_token(data={"sub": user.email})


    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,  # Set to True in production
        samesite="Lax",
        path="/",
    )

    return {"email_sent": False, "message": "Account updated successfully!"}


@router.post("/change/password")
async def change_username(
    password: ChangePassword,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    password.password = password.password.strip()
    if not password.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Password cannot be empty!"
        )

    if len(password.password) > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password cannot be longer than 30 characters!",
        )

    updated_user = await UserRepository(session).change_password(
        user.id, password.password
    )
    return {"message": "Password changed successfully"}
