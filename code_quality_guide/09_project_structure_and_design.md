# 09. Project Structure & Architecture

> **Module:** Architectural Design, Boundaries & Structure  
> **Source:** Section 10 of the Revised Code Quality Guide  
> **Related:** [01. Clean Code](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/01_clean_code_fundamentals.md) | [02. Backend Reliability](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/02_backend_reliability_patterns.md) | [05. AI Engineering](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/05_ai_engineering_practices.md)

---

## 1. Layered Architecture: Inward Dependencies

To build a codebase that remains maintainable over years of business change, separate core domain business rules from external frameworks, databases, and third-party SDKs.

> **The Inward Dependency Rule:**  
> Dependencies must always point inward toward high-level business policies. The core domain never imports the web framework (Express, FastAPI), the database driver (SQLAlchemy, Mongoose), or external AI SDKs (Google GenAI, OpenAI).

```
┌────────────────────────────────────────────────────────┐
│  Interface Layer (HTTP Controllers, CLI, Queues)      │
└───────────────────────────┬────────────────────────────┘
                            │ depends on
┌───────────────────────────▼────────────────────────────┐
│  Service Layer (Use Cases & Application Orchestration) │
└───────────────────────────┬────────────────────────────┘
                            │ depends on
┌───────────────────────────▼────────────────────────────┐
│  Domain Layer (Entities, Value Objects, Business Rules) │
└────────────────────────────────────────────────────────┘
                            ▲
                            │ implements protocols defined by Domain/Service
┌───────────────────────────┴────────────────────────────┐
│  Adapters / Infrastructure (PostgreSQL, Redis, Gemini) │
└────────────────────────────────────────────────────────┘
```

### Standard Directory Layout

```
src/app/
  api/              # HTTP routers, controllers, request/response schemas
  services/         # Application use cases: ExtractPaper, AnswerQuestion, TriageTicket
  domain/           # Pure business entities, value objects, rules (Zero I/O imports)
  ports/            # Protocols/Interfaces defined by domain: LLMClient, PaperRepository
  adapters/         # Concrete implementations: PostgresRepo, RedisCache, GeminiAdapter
  ai/
    prompts/        # Version-controlled prompt templates
    pipelines/      # Deterministic extraction & chunking algorithms
    evals/          # Datasets, scorers, and benchmark runners
  config.py         # Strongly-typed environment settings
  main.py           # Composition root (dependency wiring)
tests/              # Mirroring src/ layout (unit/, integration/, e2e/)
docs/               # adr/, runbooks/, architecture/
```

> **Automated Boundary Enforcement:** Use tools such as `import-linter` (Python) or ESLint boundary rules to mechanically prevent the domain layer from accidentally importing database or framework packages.

---

## 2. Dependency Injection & The Composition Root

Do not instantiate database clients, network libraries, or AI SDKs inside the middle of business services or domain classes. Instead, pass collaborators explicitly via class constructors.

### The Composition Root (`main.py`)
Wire all concrete implementations together in **one single place** during application bootstrap. This ensures that:
1. Unit tests can effortlessly inject in-memory fakes without monkeypatching global modules.
2. Swapping infrastructure components (e.g., migrating from Redis to Memcached) requires editing only the composition root.

```python
class AnswerService:
    def __init__(self, retriever: RetrieverPort, llm: LLMClient, cache: CachePort) -> None:
        self._retriever = retriever
        self._llm = llm
        self._cache = cache

# main.py: The only file that instantiates concrete infrastructure adapters
def build_application(settings: Settings) -> App:
    db_pool = create_postgres_pool(settings.database_url)
    
    llm_client = GeminiAdapter(
        api_key=settings.gemini_api_key.get_secret_value(),
        timeout_s=settings.llm_timeout_s,
    )
    retriever = PgVectorRetriever(db_pool)
    cache = RedisCache(settings.redis_url)
    
    answer_service = AnswerService(retriever, llm_client, cache)
    return App(answer_service)
```

---

## 3. Configuration & Secrets Management (12-Factor App)

- **Configuration via Environment Variables:** Store configuration in the environment, never hardcoded in source control.
- **Fail Fast at Boot:** Validate all environment variables at startup. If `DATABASE_URL` or `GEMINI_API_KEY` is missing or malformed, the process must immediately crash with an explanatory message, rather than failing on the first live user request.
- **Hide Secrets with `SecretStr`:** Wrap credentials in secret types that mask the value when printed or serialized into error logs.

```python
from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = Field(..., description="PostgreSQL connection string")
    redis_url: str = Field("redis://localhost:6379/0")
    gemini_api_key: SecretStr = Field(..., description="API key for Gemini models")
    gemini_model: str = Field("gemini-1.5-pro")
    llm_timeout_s: float = Field(30.0, ge=1.0, le=120.0)

    class Config:
        env_file = ".env"
```

---

## 4. Boundaries & Explicit Contracts

1. **Schema Validation at Outer Edges:**  
   Validate all external data (HTTP bodies, query parameters, queue messages, raw file uploads, and LLM text outputs) through strict schemas before passing them to internal services. Once inside the application, code should deal exclusively with strongly-typed objects.
2. **Explicit Public Interfaces:**  
   In Python, mark internal module helpers with a leading underscore (`_helper()`) or export only public symbols via `__all__`. Prevent other modules from reaching deep into private module internals.
3. **Versioned Contracts:**  
   Ensure that message formats, database schemas, and public API endpoints are versioned so updates can be rolled out without breaking active clients.

---

## 5. "Modular Monolith First" Principle

A well-structured **Modular Monolith** is vastly superior to a distributed microservices architecture for most teams and projects:

- **Simpler Local Development & Testing:** You can run the entire system locally in a single command without maintaining 15 Docker containers and complex network meshes.
- **Zero Network Latency & Failure Modes:** In-process function calls do not suffer from network serialization overhead, transient timeouts, circuit breaking, or distributed tracing complexity.
- **Refactoring Ease:** Moving logic between modules in a monolith is a safe compiler-assisted refactor; moving logic between microservices requires multi-team API deprecations and cross-service migrations.

### When to Extract a Microservice
Extract a microservice only when forced by a compelling business or technical reality:
- Fundamentally divergent scaling characteristics (e.g., a CPU-intensive background ML pipeline vs. a lightweight CRUD HTTP gateway).
- Strictly isolated security or compliance boundaries (e.g., PCI-DSS card processing).
- Independent engineering teams that require decoupled deployment pipelines.
