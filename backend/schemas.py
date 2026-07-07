"""
schemas.py
----------
Pydantic request / response models for the DocSense API.
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The user's question")


class SourceChunk(BaseModel):
    content: str = Field(..., description="Preview of the retrieved chunk text")
    page: int | None = Field(None, description="Page number from PDF metadata")
    source: str | None = Field(None, description="Source filename")


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk] = Field(default_factory=list)


class UploadResponse(BaseModel):
    message: str
    chunks_created: int


class ErrorResponse(BaseModel):
    detail: str
