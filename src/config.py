from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"

    # LLM — cascade router: mỗi task type một model (bài học cost-management:
    # không đốt model mạnh cho việc classify). Judge PHẢI khác model generator
    # để tránh self-preference bias (bài học team 002 — eval judge riêng).
    openai_api_key: str = ""
    model_name: str = "gpt-4o"  # legacy alias cho model_generate
    model_classify: str = "gpt-4o-mini"  # cheap: classify / route / quyết định tool
    model_generate: str = "gpt-4o"  # strong: sinh câu trả lời cuối
    model_judge: str = "gpt-4o-mini"  # judge: khác model_generate mặc định
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Agent loop — escape hatch chống loop vô hạn (bài học team 011:
    # luôn phải có một đường tới END dù LLM cứ đòi gọi tool mãi)
    agent_max_iterations: int = Field(default=8, ge=1, le=50)

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    # VIN-15 — Hệ thống hỗ trợ thực tập
    # SSO/OIDC (R1.2) — để trống OIDC_ISSUER là tắt, chỉ dùng tài khoản nội bộ
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "https://localhost/api/v1/auth/oidc/callback"
    oidc_scopes: str = "openid email profile"
    # Giới hạn tần suất (in-memory, một process)
    login_max_failures: int = Field(default=5, ge=1)
    login_lock_minutes: int = Field(default=15, ge=1)
    login_ip_per_minute: int = Field(default=30, ge=1)
    assistant_per_minute: int = Field(default=20, ge=1)
    intake_per_minute: int = Field(default=10, ge=1)
    # Endpoint tương thích OpenAI (vd Ollama: http://ollama:11434/v1). Trống = api.openai.com
    openai_base_url: str = ""
    llm_max_tokens: int = Field(default=400, ge=50, le=4096)
    llm_context_hits: int = Field(default=3, ge=1, le=10)  # số đoạn quy định gửi cho model
    llm_context_chars: int = Field(default=600, ge=100)  # cắt mỗi đoạn — prompt ngắn, trả lời nhanh
    # NFR-1: tổng thời gian dành cho model mỗi câu hỏi (mọi lần sinh). Hết → trả trích dẫn nguyên văn
    # đã kiểm chứng (mode=extractive_timeout). 0 = không giới hạn.
    llm_answer_budget_seconds: float = Field(default=8.0, ge=0.0)
    jwt_secret: str = "dev-only-change-me"
    jwt_ttl_minutes: int = Field(default=480, ge=5)
    file_url_ttl_seconds: int = Field(default=300, ge=30)
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = Field(default=10, ge=1, le=100)
    # OCR cục bộ (Tesseract) cho giấy tiếp nhận dạng scan/ảnh — chỉ dùng ở /intake/extract
    ocr_enabled: bool = True
    ocr_lang: str = "vie+eng"
    ocr_max_pages: int = Field(default=3, ge=1, le=10)
    ocr_timeout_seconds: int = Field(default=30, ge=1, le=300)
    cohort_config: str = "config/cohort.yaml"
    policy_seed_dir: str = "seed/policies"
    # Vai trò tùy chọn: tắt thì cấu hình lấy từ YAML/seed, kho quy định do GV điều phối quản lý
    enable_admin_role: bool = True
    seed_demo_data: bool = True
    monitor_enabled: bool = True
    monitor_hour: int = Field(default=7, ge=0, le=23)
    retrieval_min_score: float = Field(default=2.0, ge=0.0)
    retrieval_min_coverage: float = Field(default=0.4, ge=0.0, le=1.0)
    retrieval_top_k: int = Field(default=4, ge=1, le=10)
    # Embedding (R9.2) — chỉ dùng khi có API key; chưa tinh chỉnh với model thật
    embedding_model: str = "text-embedding-3-small"
    # None = dùng ngưỡng đã hiệu chỉnh theo model (policy_index.CALIBRATED_SIMILARITY); đặt số để ghi đè
    embedding_min_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    embedding_weight: float = Field(default=8.0, ge=0.0)


    @field_validator("embedding_min_similarity", mode="before")
    @classmethod
    def _blank_is_none(cls, value):
        # `EMBEDDING_MIN_SIMILARITY=` để trống trong .env → dùng ngưỡng theo model, không lỗi parse
        return None if isinstance(value, str) and not value.strip() else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
