from datetime import datetime
from typing import List

from pydantic import BaseModel, EmailStr, ConfigDict


class PermissionBase(BaseModel):
    name: str

    model_config = ConfigDict(from_attributes=True)


class PermissionDisplay(PermissionBase):
    id: int

    model_config = ConfigDict(from_attributes=True)



class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    username: str
    email: EmailStr



class UserLogin(BaseModel):
    username: str
    password: str


class DevUser(BaseModel):
    id: int
    username: str
    email: EmailStr
    hashed_password: str

    model_config = ConfigDict(from_attributes=True)


class UserDisplay(BaseModel):
    id: int
    username: str | None
    email: EmailStr
    is_admin: bool = False


    model_config = ConfigDict(from_attributes=True)


class ProfileDisplay(BaseModel):
    id: int
    username: str
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)



class ChangePassword(BaseModel):
    password: str


class GoogleSignIn(BaseModel):
    credential: str
    remember_me: bool = False
