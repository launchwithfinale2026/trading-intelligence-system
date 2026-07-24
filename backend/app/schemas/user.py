from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.profile import ProfileCreate, ProfileRead


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    profile: ProfileCreate


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    profile: ProfileRead | None = None
