from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int
    created_at: datetime
    last_active: Optional[datetime] = None

    class Config:
        orm_mode = True

class UserLanguageBase(BaseModel):
    user_id: int
    target_language_id: int
    level: str

class UserLanguage(UserLanguageBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class WordBase(BaseModel):
    text: str
    difficulty: int
    language_id: int

class Word(WordBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class WordOptionBase(BaseModel):
    id: int
    text: str

class WordWithOptions(BaseModel):
    wordId: int
    text: str
    correctTranslation: str
    options: List[str]

class WordSession(BaseModel):
    sessionId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    words: List[WordWithOptions]
    totalWords: int

class UserAnswer(BaseModel):
    wordId: int
    userAnswer: str
    sessionId: str
    correctTranslation: str

class AnswerResult(BaseModel):
    isCorrect: bool
    correctTranslation: str

class SessionComplete(BaseModel):
    sessionId: str
    
class SessionResult(BaseModel):
    status: str
    increasePatch: Optional[bool] = None
    newLevel: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class UserProgress(BaseModel):
    id: int
    user_language_id: int
    word_id: int
    repeats: int
    successes: int
    success_rate: float
    first_seen: datetime
    last_seen: datetime
    last_answer_wrong: bool
    session_id: Optional[str] = None

    class Config:
        orm_mode = True 