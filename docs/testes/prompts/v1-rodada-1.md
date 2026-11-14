Você é um engenheiro de testes experiente em Python. Preciso de uma suíte de testes automatizados para a API back-end de um sistema de acompanhamento de patentes e programas de computador no INPI.

## Stack e framework de teste
- Python 3.13, FastAPI 0.143, SQLAlchemy 2.1, Pydantic 2, python-jose (JWT), passlib/bcrypt.
- Testes com **pytest** e o `TestClient` do FastAPI. Já existe um `tests/conftest.py` (abaixo) com fixtures de banco SQLite em memória, cliente HTTP, usuários e ativos de exemplo, e o helper `auth_header`. Use essas fixtures; não crie banco real nem dependa de rede.
- Os arquivos de teste serão colocados em uma subpasta de `backend/tests/`, e o pytest roda a partir de `backend/` (`pythonpath = ["."]`).

## User stories e critérios de aceitação

**US01** — Como membro da equipe do NIT, quero fazer login no sistema, para acessar a gestão da carteira de ativos.

- CA01-1: Dado um usuário NIT com e-mail e senha corretos, quando faz login, então recebe um token JWT (tipo bearer) e os dados do usuário com perfil NIT.
- CA01-2: Dado um e-mail cadastrado e uma senha incorreta, quando faz login, então recebe 401 com a mensagem "E-mail ou senha incorretos.".
- CA01-3: Dado um e-mail não cadastrado, quando faz login, então recebe 401 com a mesma mensagem do CA01-2 (não revela quais e-mails existem).
- CA01-4: Dado um e-mail cadastrado digitado com maiúsculas, quando faz login com a senha correta, então o login funciona.
- CA01-5: Dado um e-mail com formato inválido ou uma senha vazia, quando faz login, então recebe 422 (requisição malformada).
- CA01-6: Dado o formulário OAuth2 (botão Authorize do Swagger), quando envia e-mail no campo username e a senha, então o comportamento é o mesmo do login JSON.

**US02** — Como autor/inventor, quero fazer login com acesso restrito, para acompanhar apenas os meus próprios processos.

- CA02-1: Dado um autor com e-mail e senha corretos, quando faz login, então recebe token e perfil AUTOR.
- CA02-2: Dado um autor logado, quando lista os ativos, então recebe somente os ativos vinculados a ele.
- CA02-3: Dado um autor sem nenhum ativo vinculado, quando lista os ativos, então recebe uma lista vazia.

**US03** — Como membro do NIT, quero que o sistema diferencie os dois perfis de acesso, para que o autor não veja dados de outros processos.

- CA03-1: Dado um usuário AUTOR, quando tenta cadastrar um ativo, então recebe 403 "Seu perfil não tem permissão para esta ação.".
- CA03-2: Dada uma requisição sem token, quando acessa uma rota protegida (listar, cadastrar, /me), então recebe 401.
- CA03-3: Dado um token malformado, assinado com outra chave ou expirado, quando acessa uma rota protegida, então recebe 401 "Sessão inválida ou expirada. Faça login novamente.".
- CA03-4: Dado um token bem assinado cujo usuário não existe mais (ou cujo sub não é um id), quando acessa uma rota protegida, então recebe 401.
- CA03-5: Dado um usuário logado, quando consulta /auth/me, então recebe os próprios dados (id, e-mail, perfil).

**US04** — Como membro do NIT, quero cadastrar um novo ativo (patente ou programa de computador) com título, natureza, inventores/autores, código do processo, data de depósito e situação atual, para começar a monitorá-lo.

- CA04-1: Dado um NIT logado e dados válidos, quando cadastra um ativo, então recebe 201 com o ativo criado e ele passa a constar na listagem.
- CA04-2: A natureza do ativo deve ser "Patente" ou "Programa de Computador"; qualquer outro valor é recusado com 422.
- CA04-3: O título deve ter de 3 a 500 caracteres efetivos; espaços repetidos e nas bordas são normalizados e não contam. Fora disso, 422.
- CA04-4: O número do processo deve ter de 5 a 50 caracteres efetivos e é gravado normalizado (maiúsculas e espaços simples). Fora disso, 422.
- CA04-5: Dado um número de processo já cadastrado (inclusive se diferir só por maiúsculas/espaços), quando cadastra, então recebe 409 com o número na mensagem.
- CA04-6: A data de depósito não pode estar no futuro (hoje é aceito); data futura ou inexistente é recusada com 422.
- CA04-7: A situação atual deve ter de 2 a 100 caracteres efetivos. Fora disso, 422.
- CA04-8: Os inventores/autores devem ter de 2 a 1000 caracteres efetivos. Fora disso, 422.
- CA04-9: Título, natureza, processo, data, situação e autores são obrigatórios; a ausência de qualquer um gera 422.

**US06** — Como membro do NIT, quero ver uma lista consolidada de todos os ativos com status atual, para ter visão geral da carteira.

- CA06-1: Dado um NIT logado, quando lista os ativos, então recebe todos os ativos da carteira (com ou sem autor vinculado).
- CA06-2: A lista vem ordenada da data de depósito mais recente para a mais antiga; em empate, o cadastrado por último vem primeiro.
- CA06-3: Cada item traz título, natureza, processo, data, situação atual, autores e o e-mail do autor vinculado (ou nulo).
- CA06-4: Dada uma carteira vazia, quando o NIT lista os ativos, então recebe 200 com lista vazia.

**US07** — Como membro do NIT, quero associar um autor/inventor a um ativo, para que ele tenha acesso de acompanhamento ao processo correspondente.

- CA07-1: Dado o e-mail de um usuário AUTOR cadastrado, quando o NIT cadastra o ativo com ele, então o ativo fica vinculado e o autor passa a vê-lo (e só ele, entre os autores).
- CA07-2: Dado um e-mail não cadastrado, quando o NIT tenta vincular, então recebe 422 e o ativo não é gravado.
- CA07-3: Dado o e-mail de um usuário NIT, quando o NIT tenta vinculá-lo como autor, então recebe 422.
- CA07-4: Dado o campo de autor ausente, vazio ou só com espaços, quando o NIT cadastra, então o ativo é criado sem vínculo.
- CA07-5: Dado o e-mail de um AUTOR digitado com maiúsculas, quando o NIT vincula, então o autor correto é encontrado.
- CA07-6: Dado um e-mail de autor com formato inválido, quando o NIT cadastra, então recebe 422.

## O que eu quero
1. Gere a suíte de testes cobrindo **todos** os critérios de aceitação acima.
2. Aplique explicitamente **partições de equivalência** (classes válidas e inválidas de cada entrada), **análise de valores-limite** (os dois lados de cada fronteira) e **cobertura dos critérios de aceitação**.
3. Em cada teste, coloque um comentário indicando **qual técnica** ele aplica (partição, valor-limite ou critério de aceitação) e **qual requisito/critério** (ex.: `# US04 / CA04-3 — valor-limite: título com 500 caracteres`).
4. O resultado esperado de cada teste deve vir do critério de aceitação.
5. Entregue código completo, pronto para rodar com `pytest`, organizado em arquivos por assunto (autenticação, perfis/sessão, ativos).

## Código do sistema

### `app/core/config.py`
```python
"""Configurações da aplicação, lidas de variáveis de ambiente ou do arquivo .env."""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Radar INPI — Acompanhamento de PI no INPI"
    api_prefix: str = "/api"

    # SQLite no MVP. Para PostgreSQL, basta trocar a URL:
    # postgresql+psycopg://usuario:senha@host:5432/pi_inpi
    database_url: str = "sqlite:///./pi_inpi.db"

    # JWT — em produção, defina JWT_SECRET_KEY no .env com um valor longo e aleatório.
    jwt_secret_key: str = "dev-secret-troque-em-producao"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    # Origens (frontends) autorizadas a chamar a API pelo navegador.
    # No .env: CORS_ORIGINS=http://localhost:5173,https://radar.instituicao.edu.br
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        # Aceita lista separada por vírgulas; remove espaços e barra final ("http://x/" == "http://x").
        if isinstance(value, str):
            value = value.split(",")
        if isinstance(value, list):
            return [str(origin).strip().rstrip("/") for origin in value if str(origin).strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

### `app/core/security.py`
```python
"""Hash de senhas e emissão/validação de tokens JWT."""

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str | int, extra_claims: dict[str, Any] | None = None) -> str:
    """Gera um JWT assinado. `subject` identifica o usuário (claim `sub`)."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        **(extra_claims or {}),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Retorna o payload se o token for válido e não expirado; caso contrário, None."""
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
```

### `app/database/session.py`
```python
"""Engine, fábrica de sessões e classe base declarativa do SQLAlchemy."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

# check_same_thread só existe no SQLite; o FastAPI atende requisições em threads diferentes.
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(settings.database_url, connect_args=_connect_args)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        # O SQLite ignora FOREIGN KEY (e o ON DELETE SET NULL) sem este PRAGMA.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Classe base de todos os models ORM."""


def get_db() -> Generator[Session, None, None]:
    """Dependência do FastAPI: abre uma sessão por requisição e garante o fechamento."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### `app/models/enums.py`
```python
"""Enumerações de domínio compartilhadas entre models e schemas."""

from enum import Enum


class UserRole(str, Enum):
    """Perfis de acesso do sistema (US01, US02, US03)."""

    NIT = "NIT"  # Equipe do Núcleo de Inovação Tecnológica: gestão completa da carteira
    AUTOR = "AUTOR"  # Autor/inventor: acompanha apenas os próprios processos


class AssetType(str, Enum):
    """Natureza do ativo de propriedade intelectual (escopo do MVP)."""

    PATENTE = "Patente"
    PROGRAMA_DE_COMPUTADOR = "Programa de Computador"
```

### `app/models/user.py`
```python
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.asset import Asset


class User(Base):
    """Usuário do sistema: membro da equipe do NIT ou autor/inventor."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        # native_enum=False grava o valor como texto + CHECK constraint,
        # funcionando igual no SQLite e no PostgreSQL.
        SAEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [member.value for member in enum],
            length=20,
        ),
        default=UserRole.AUTOR,
    )

    # Ativos em que este usuário está vinculado como autor com acesso de acompanhamento (US07).
    assets: Mapped[list[Asset]] = relationship(back_populates="author_user")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"
```

### `app/models/asset.py`
```python
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AssetType

if TYPE_CHECKING:
    from app.models.user import User


class Asset(Base):
    """Ativo de propriedade intelectual acompanhado junto ao INPI (US04)."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    asset_type: Mapped[AssetType] = mapped_column(
        SAEnum(
            AssetType,
            name="asset_type",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [member.value for member in enum],
            length=40,
        )
    )
    # Número do processo no INPI (ex.: "BR 10 2023 001234-5"). É a chave usada
    # no cruzamento com os despachos da RPI (Step 3), por isso é único e indexado.
    process_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    deposit_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(100))
    # Nomes dos inventores/autores conforme o depósito, separados por vírgula.
    authors: Mapped[str] = mapped_column(String(1000))

    # Autor com acesso de acompanhamento ao processo (opcional — US07).
    # SET NULL: se o usuário for removido, o ativo continua cadastrado.
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, default=None
    )
    author_user: Mapped[User | None] = relationship(back_populates="assets")

    @property
    def author_email(self) -> str | None:
        """E-mail do autor vinculado, exposto diretamente na resposta da API."""
        return self.author_user.email if self.author_user else None

    def __repr__(self) -> str:
        return f"<Asset id={self.id} process={self.process_number!r} type={self.asset_type.value}>"
```

### `app/schemas/auth.py`
```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: UserRole


class TokenResponse(BaseModel):
    """Resposta do login: token JWT + dados do usuário para o frontend montar a sessão."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead
```

### `app/schemas/asset.py`
```python
import re
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import AssetType


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class AssetBase(BaseModel):
    title: str = Field(min_length=3, max_length=500, examples=["Sistema de irrigação automatizada por sensores"])
    asset_type: AssetType = Field(examples=[AssetType.PATENTE])
    process_number: str = Field(min_length=5, max_length=50, examples=["BR 10 2023 001234-5"])
    deposit_date: date = Field(examples=["2023-03-12"])
    status: str = Field(min_length=2, max_length=100, examples=["Em exame"])
    authors: str = Field(
        min_length=2,
        max_length=1000,
        description="Inventores/autores separados por vírgula.",
        examples=["Fernanda Lima Costa, Rodrigo A. Nascimento"],
    )

    @field_validator("title", "status", "authors")
    @classmethod
    def _strip(cls, value: str) -> str:
        return _collapse_spaces(value)

    @field_validator("process_number")
    @classmethod
    def _normalize_process_number(cls, value: str) -> str:
        # Padroniza para casar com o número publicado na RPI: maiúsculas e espaços simples.
        return _collapse_spaces(value).upper()


class AssetCreate(AssetBase):
    author_email: EmailStr | None = Field(
        default=None,
        description="E-mail de um usuário AUTOR já cadastrado, para dar a ele acesso de acompanhamento (US07).",
        examples=["fernanda.costa@instituicao.edu.br"],
    )

    @field_validator("deposit_date")
    @classmethod
    def _not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("A data de depósito não pode estar no futuro.")
        return value

    @field_validator("author_email", mode="before")
    @classmethod
    def _empty_email_as_none(cls, value: object) -> object:
        # O formulário do frontend envia "" quando o campo opcional fica em branco.
        if isinstance(value, str) and not value.strip():
            return None
        return value


class AssetRead(AssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_user_id: int | None
    author_email: EmailStr | None
```

### `app/services/auth_service.py`
```python
"""Regras de autenticação, independentes da camada HTTP."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models import User

# Hash usado quando o e-mail não existe, para o tempo de resposta não revelar
# quais e-mails estão cadastrados.
_DUMMY_HASH = hash_password("senha-inexistente")


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def issue_token(user: User) -> str:
    return create_access_token(user.id, {"role": user.role.value, "email": user.email})
```

### `app/services/asset_service.py`
```python
"""Regras de negócio da carteira de ativos, independentes da camada HTTP."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, User, UserRole
from app.schemas.asset import AssetCreate
from app.services.auth_service import get_user_by_email


class AssetServiceError(Exception):
    """Erro de regra de negócio, com mensagem pronta para o usuário."""


class DuplicateProcessError(AssetServiceError):
    pass


class AuthorNotFoundError(AssetServiceError):
    pass


def list_assets_for(db: Session, user: User) -> Sequence[Asset]:
    """NIT vê a carteira inteira; AUTOR vê apenas os ativos vinculados a ele (US03, US06)."""
    query = select(Asset).options(selectinload(Asset.author_user)).order_by(Asset.deposit_date.desc(), Asset.id.desc())
    if user.role != UserRole.NIT:
        query = query.where(Asset.author_user_id == user.id)
    return db.scalars(query).all()


def create_asset(db: Session, data: AssetCreate) -> Asset:
    """Cadastra um novo ativo (US04), opcionalmente vinculando um autor (US07)."""
    if db.scalar(select(Asset.id).where(Asset.process_number == data.process_number)) is not None:
        raise DuplicateProcessError(f"Já existe um ativo cadastrado com o processo {data.process_number}.")

    author_user = None
    if data.author_email:
        author_user = get_user_by_email(db, data.author_email)
        if author_user is None or author_user.role != UserRole.AUTOR:
            raise AuthorNotFoundError(f"Nenhum usuário com perfil AUTOR encontrado com o e-mail {data.author_email}.")

    asset = Asset(**data.model_dump(exclude={"author_email"}), author_user=author_user)
    db.add(asset)
    try:
        db.commit()
    except IntegrityError as exc:
        # Cobre a corrida entre a checagem acima e o INSERT (duas requisições simultâneas).
        db.rollback()
        raise DuplicateProcessError(f"Já existe um ativo cadastrado com o processo {data.process_number}.") from exc
    db.refresh(asset)
    return asset
```

### `app/routes/deps.py`
```python
"""Dependências compartilhadas pelas rotas: sessão do banco, usuário logado e controle de perfil."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.database import get_db
from app.models import User, UserRole

# tokenUrl aponta para a rota de formulário, usada pelo botão "Authorize" do Swagger.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/token")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessão inválida ou expirada. Faça login novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None or not str(payload.get("sub", "")).isdigit():
        raise credentials_error

    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Cria uma dependência que só deixa passar usuários com um dos perfis informados (US03)."""

    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seu perfil não tem permissão para esta ação.",
            )
        return user

    return checker


NitUser = Annotated[User, Depends(require_roles(UserRole.NIT))]
```

### `app/routes/auth.py`
```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.models import User
from app.routes.deps import CurrentUser, DbSession
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Autenticação"])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="E-mail ou senha incorretos.",
    headers={"WWW-Authenticate": "Bearer"},
)


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(access_token=auth_service.issue_token(user), user=UserRead.model_validate(user))


@router.post("/login", response_model=TokenResponse, summary="Login com e-mail e senha (US01, US02)")
def login(credentials: LoginRequest, db: DbSession) -> TokenResponse:
    """Recebe JSON com e-mail e senha e devolve o token JWT com o perfil do usuário."""
    user = auth_service.authenticate(db, credentials.email, credentials.password)
    if user is None:
        raise _INVALID_CREDENTIALS
    return _token_response(user)


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Login via formulário OAuth2 (usado pelo botão Authorize do Swagger)",
)
def login_form(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession) -> TokenResponse:
    # No formulário OAuth2 o campo se chama "username"; aqui ele recebe o e-mail.
    user = auth_service.authenticate(db, form.username, form.password)
    if user is None:
        raise _INVALID_CREDENTIALS
    return _token_response(user)


@router.get("/me", response_model=UserRead, summary="Dados do usuário logado")
def read_current_user(user: CurrentUser) -> User:
    return user
```

### `app/routes/assets.py`
```python
from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, status

from app.models import Asset
from app.routes.deps import CurrentUser, DbSession, NitUser
from app.schemas.asset import AssetCreate, AssetRead
from app.services import asset_service

router = APIRouter(prefix="/assets", tags=["Ativos"])


@router.get("/", response_model=list[AssetRead], summary="Lista os ativos visíveis ao usuário (US06, US03)")
def list_assets(db: DbSession, user: CurrentUser) -> Sequence[Asset]:
    """Perfil NIT recebe a carteira completa; perfil AUTOR recebe só os ativos vinculados a ele."""
    return asset_service.list_assets_for(db, user)


@router.post(
    "/",
    response_model=AssetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra um novo ativo (US04) — apenas perfil NIT",
    responses={
        403: {"description": "Usuário sem perfil NIT"},
        409: {"description": "Número de processo já cadastrado"},
        422: {"description": "Dados inválidos ou autor não encontrado"},
    },
)
def create_asset(data: AssetCreate, db: DbSession, _user: NitUser) -> Asset:
    try:
        return asset_service.create_asset(db, data)
    except asset_service.DuplicateProcessError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except asset_service.AuthorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
```

### `app/main.py`
```python
"""Ponto de entrada da API. Execute com: uvicorn app.main:app --reload"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database.init_db import init_db
from app.routes import assets, auth, health


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Garante que as tabelas existam antes de atender a primeira requisição.
    init_db()
    yield


def create_app(cors_origins: list[str] | None = None) -> FastAPI:
    """Monta a aplicação. `cors_origins` substitui a configuração (usado nos testes)."""
    app = FastAPI(
        title=settings.app_name,
        description="API para gestão e acompanhamento de patentes e programas de computador junto ao INPI.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # O frontend roda em outra origem (Vite em :5173) e se autentica com o cabeçalho
    # Authorization (JWT), sem cookies — por isso allow_credentials fica desligado.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins is not None else settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        max_age=600,
    )

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(assets.router, prefix=settings.api_prefix)
    return app


app = create_app()
```

### `tests/conftest.py`
```python
"""Fixtures dos testes: banco SQLite em memória isolado por teste e cliente HTTP."""

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registra as tabelas no metadata)
from app.core.security import hash_password
from app.database import Base, get_db
from app.main import create_app
from app.models import Asset, AssetType, User, UserRole

PASSWORD = "senha-teste-123"


@pytest.fixture
def db_session() -> Iterator[Session]:
    # StaticPool mantém uma única conexão, para o banco em memória sobreviver entre sessões.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda conn, _rec: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestingSession() as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    application = create_app()
    application.dependency_overrides[get_db] = lambda: db_session
    # Sem o "with", o lifespan (que criaria o banco real) não é executado.
    yield TestClient(application)


@pytest.fixture
def users(db_session: Session) -> dict[str, User]:
    created = {
        "nit": User(email="nit@teste.edu.br", hashed_password=hash_password(PASSWORD), role=UserRole.NIT),
        "autora": User(email="autora@teste.edu.br", hashed_password=hash_password(PASSWORD), role=UserRole.AUTOR),
        "outro_autor": User(email="outro@teste.edu.br", hashed_password=hash_password(PASSWORD), role=UserRole.AUTOR),
    }
    db_session.add_all(created.values())
    db_session.commit()
    return created


@pytest.fixture
def assets(db_session: Session, users: dict[str, User]) -> list[Asset]:
    created = [
        Asset(
            title="Patente da autora",
            asset_type=AssetType.PATENTE,
            process_number="BR 10 2023 000001-1",
            deposit_date=date(2023, 1, 10),
            status="Em exame",
            authors="Autora Teste",
            author_user=users["autora"],
        ),
        Asset(
            title="Software de outro autor",
            asset_type=AssetType.PROGRAMA_DE_COMPUTADOR,
            process_number="BR 51 2024 000002-2",
            deposit_date=date(2024, 5, 20),
            status="Registrado",
            authors="Outro Autor",
            author_user=users["outro_autor"],
        ),
        Asset(
            title="Patente sem autor vinculado",
            asset_type=AssetType.PATENTE,
            process_number="BR 10 2022 000003-3",
            deposit_date=date(2022, 8, 1),
            status="Deferida",
            authors="Equipe",
        ),
    ]
    db_session.add_all(created)
    db_session.commit()
    return created


def auth_header(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
```

### `pyproject.toml`
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

### `requirements-dev.txt`
```text
# Dependências de desenvolvimento e testes (inclui as de produção).
-r requirements.txt

pytest==9.1.1
httpx2==2.13.1  # cliente HTTP usado pelo TestClient do FastAPI
```
