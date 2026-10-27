from pydantic import BaseModel, Field

class VisibilityUpdate(BaseModel):
    visibility: str

class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)

class ShareDocumentRequest(BaseModel):
    email: str
    permission: str = "view"

class SharePermissionUpdate(BaseModel):
    permission: str = "view"
