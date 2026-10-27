from pydantic import BaseModel

class UpdateProfileRequest(BaseModel):
    username: str

class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class UserSettingsUpdate(BaseModel):
    theme: str | None = None
    notifications_enabled: int | None = None
    email_notifications: int | None = None
    public_profile: int | None = None
    allow_document_sharing: int | None = None
    auto_delete_old_chats: int | None = None
    delete_after_days: int | None = None
