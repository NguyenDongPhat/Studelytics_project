from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'admin')",
            name="users_role_check",
        ),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    role = Column(String(20), nullable=False, server_default=text("'user'"))
    is_active = Column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "file_hash ~ '^[0-9a-fA-F]{64}$'",
            name="documents_file_hash_check",
        ),
        CheckConstraint(
            "total_pages IS NULL OR total_pages >= 0",
            name="documents_total_pages_check",
        ),
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'ready', 'failed')",
            name="documents_status_check",
        ),
        CheckConstraint(
            "visibility IN ('private', 'shared', 'public')",
            name="documents_visibility_check",
        ),
        UniqueConstraint("owner_id", "file_hash", name="uq_documents_owner_file_hash"),
        Index("idx_documents_owner_upload_date", "owner_id", "upload_date"),
        Index("idx_documents_visibility_status", "visibility", "status"),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    owner_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    file_path = Column(Text, nullable=False)
    file_hash = Column(String(64), nullable=False)
    total_pages = Column(Integer)
    status = Column(String(20), nullable=False, server_default=text("'uploaded'"))
    visibility = Column(String(20), nullable=False, server_default=text("'private'"))
    upload_date = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (
        CheckConstraint("chapter_number > 0", name="chapters_chapter_number_check"),
        CheckConstraint(
            "start_page IS NULL OR start_page > 0",
            name="chapters_start_page_check",
        ),
        CheckConstraint(
            "end_page IS NULL OR end_page > 0",
            name="chapters_end_page_check",
        ),
        CheckConstraint(
            "start_page IS NULL OR end_page IS NULL OR end_page >= start_page",
            name="ck_chapters_page_range",
        ),
        UniqueConstraint("document_id", "chapter_number", name="uq_chapters_document_number"),
        UniqueConstraint("document_id", "id", name="uq_chapters_document_id"),
        Index("idx_chapters_document", "document_id", "chapter_number"),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    document_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    start_page = Column(Integer)
    end_page = Column(Integer)
    summary = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint(
            "page_number IS NULL OR page_number > 0",
            name="document_chunks_page_number_check",
        ),
        CheckConstraint("chunk_index >= 0", name="document_chunks_chunk_index_check"),
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_index"),
        UniqueConstraint("chroma_id", name="document_chunks_chroma_id_key"),
        ForeignKeyConstraint(
            ["document_id", "chapter_id"],
            ["chapters.document_id", "chapters.id"],
            name="fk_document_chunks_chapter_same_document",
        ),
        Index("idx_document_chunks_document_page", "document_id", "page_number"),
        Index("idx_document_chunks_chapter", "chapter_id"),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    document_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(BigInteger)
    page_number = Column(Integer)
    chunk_index = Column(Integer, nullable=False)
    chroma_id = Column(String(255))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    content = Column(Text, nullable=False, default="")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "chapter_id"],
            ["chapters.document_id", "chapters.id"],
            name="fk_conversations_chapter_same_document",
        ),
        CheckConstraint(
            "chapter_id IS NULL OR document_id IS NOT NULL",
            name="ck_conversations_chapter_requires_document",
        ),
        Index("idx_conversations_user_created", "user_id", "created_at"),
        Index("idx_conversations_document", "document_id"),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"))
    chapter_id = Column(BigInteger)
    title = Column(String(255), nullable=False, server_default=text("'Cuộc trò chuyện mới'"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class ChatHistory(Base):
    __tablename__ = "chat_history"
    __table_args__ = (
        CheckConstraint(
            "JSONB_TYPEOF(retrieved_chunks) = 'array'",
            name="ck_chat_history_retrieved_chunks_array",
        ),
        CheckConstraint(
            "JSONB_TYPEOF(citations) IN ('array', 'object')",
            name="ck_chat_history_citations_json",
        ),
        Index("idx_chat_history_conversation_created", "conversation_id", "created_at"),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    conversation_id = Column(BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    retrieved_chunks = Column(JSONB, nullable=False, server_default=text("'[]'::JSONB"))
    citations = Column(JSONB, nullable=False, server_default=text("'[]'::JSONB"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class Quiz(Base):
    __tablename__ = "quizzes"
    __table_args__ = (
        CheckConstraint("question_count >= 0", name="quizzes_question_count_check"),
        UniqueConstraint("document_id", "id", name="uq_quizzes_document_id"),
        ForeignKeyConstraint(
            ["document_id", "chapter_id"],
            ["chapters.document_id", "chapters.id"],
            name="fk_quizzes_chapter_same_document",
        ),
        Index("idx_quizzes_document", "document_id"),
        Index("idx_quizzes_chapter", "chapter_id"),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    document_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(BigInteger)
    title = Column(String(255), nullable=False)
    question_count = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(
            "question_type IN ('multiple_choice', 'multiple_select', 'true_false', 'short_answer')",
            name="questions_question_type_check",
        ),
        CheckConstraint(
            "source_page IS NULL OR source_page > 0",
            name="questions_source_page_check",
        ),
        UniqueConstraint("quiz_id", "id", name="uq_questions_quiz_id"),
        Index("idx_questions_quiz", "quiz_id"),
        Index("idx_questions_source_chunk", "source_chunk_id"),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    quiz_id = Column(BigInteger, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(30), nullable=False)
    option_a = Column(Text)
    option_b = Column(Text)
    option_c = Column(Text)
    option_d = Column(Text)
    correct_answer = Column(Text, nullable=False)
    explanation = Column(Text)
    source_page = Column(Integer)
    source_chunk_id = Column(BigInteger, ForeignKey("document_chunks.id", ondelete="SET NULL"))


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        CheckConstraint("score IS NULL OR score BETWEEN 0 AND 100", name="quiz_attempts_score_check"),
        CheckConstraint("correct_count >= 0", name="quiz_attempts_correct_count_check"),
        CheckConstraint("total_questions >= 0", name="quiz_attempts_total_questions_check"),
        CheckConstraint("correct_count <= total_questions", name="ck_quiz_attempt_counts"),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_quiz_attempt_time",
        ),
        UniqueConstraint("id", "quiz_id", name="uq_quiz_attempts_id_quiz"),
        Index("idx_quiz_attempts_user_started", "user_id", "started_at"),
        Index("idx_quiz_attempts_quiz", "quiz_id"),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quiz_id = Column(BigInteger, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    score = Column(Numeric(5, 2))
    correct_count = Column(Integer, nullable=False, server_default=text("0"))
    total_questions = Column(Integer, nullable=False, server_default=text("0"))
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    completed_at = Column(DateTime(timezone=True))


class QuizAttemptAnswer(Base):
    __tablename__ = "quiz_attempt_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question"),
        CheckConstraint(
            "selected_answer IS NULL OR JSONB_TYPEOF(selected_answer) IN ('array', 'object', 'string', 'number', 'boolean')",
            name="ck_selected_answer_json",
        ),
        Index("idx_quiz_attempt_answers_question", "question_id"),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    attempt_id = Column(BigInteger, ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    selected_answer = Column(JSONB)
    is_correct = Column(Boolean)
    answered_at = Column(DateTime(timezone=True))


class Flashcard(Base):
    __tablename__ = "flashcards"
    __table_args__ = (
        CheckConstraint(
            "source_page IS NULL OR source_page > 0",
            name="flashcards_source_page_check",
        ),
        ForeignKeyConstraint(
            ["document_id", "chapter_id"],
            ["chapters.document_id", "chapters.id"],
            name="fk_flashcards_chapter_same_document",
        ),
        Index("idx_flashcards_user_document", "user_id", "document_id"),
        Index("idx_flashcards_chapter", "chapter_id"),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(BigInteger)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    source_page = Column(Integer)
    source_chunk_id = Column(BigInteger, ForeignKey("document_chunks.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = (
        CheckConstraint("duration_minutes >= 0", name="study_sessions_duration_minutes_check"),
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'abandoned')",
            name="study_sessions_status_check",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_study_sessions_time",
        ),
        Index("idx_study_sessions_user_started", "user_id", "started_at"),
        Index("idx_study_sessions_document", "document_id"),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255))
    duration_minutes = Column(Integer, nullable=False, server_default=text("0"))
    status = Column(String(20), nullable=False, server_default=text("'in_progress'"))
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class StudySessionItem(Base):
    __tablename__ = "study_session_items"
    __table_args__ = (
        CheckConstraint(
            "activity_type IN ('reading', 'chat', 'quiz', 'flashcards', 'summary', 'other')",
            name="study_session_items_activity_type_check",
        ),
        CheckConstraint("duration_minutes >= 0", name="study_session_items_duration_check"),
        CheckConstraint("elapsed_minutes >= 0", name="study_session_items_elapsed_check"),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'skipped')",
            name="study_session_items_status_check",
        ),
        Index("idx_study_session_items_session", "session_id"),
        Index("idx_study_session_items_chapter", "chapter_id"),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    session_id = Column(BigInteger, ForeignKey("study_sessions.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(BigInteger, ForeignKey("chapters.id", ondelete="SET NULL"))
    activity_type = Column(String(30), nullable=False)
    duration_minutes = Column(Integer, nullable=False, server_default=text("0"))
    elapsed_minutes = Column(Integer, nullable=False, server_default=text("0"))
    status = Column(String(20), nullable=False, server_default=text("'pending'"))


class UserChapterProgress(Base):
    __tablename__ = "user_chapter_progress"
    __table_args__ = (
        CheckConstraint(
            "progress_percent BETWEEN 0 AND 100",
            name="user_chapter_progress_progress_percent_check",
        ),
        CheckConstraint(
            "time_spent_minutes >= 0",
            name="user_chapter_progress_time_spent_minutes_check",
        ),
        CheckConstraint(
            "status IN ('not_started', 'in_progress', 'completed')",
            name="user_chapter_progress_status_check",
        ),
        UniqueConstraint("user_id", "chapter_id", name="uq_user_chapter_progress"),
        Index("idx_user_chapter_progress_chapter", "chapter_id"),
    )

    id = Column(BigInteger, Identity(always=False), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(BigInteger, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    progress_percent = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    time_spent_minutes = Column(Integer, nullable=False, server_default=text("0"))
    status = Column(String(20), nullable=False, server_default=text("'not_started'"))
    last_studied_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
