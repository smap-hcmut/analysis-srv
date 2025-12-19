# Hướng dẫn Implement HTTPOnly Cookie Middleware cho Python Service

> **Guide cho việc implement HTTPOnly cookie authentication từ Go services sang Python**

Tài liệu này cung cấp hướng dẫn chi tiết để implement middleware HTTPOnly cookie authentication cho Python service, đảm bảo tương thích với các Go services hiện có trong hệ thống SMAP.

---

## Mục lục

1. [Tổng quan Architecture](#tổng-quan-architecture)
2. [Prerequisites](#prerequisites)
3. [Step-by-Step Implementation](#step-by-step-implementation)
4. [FastAPI Implementation](#fastapi-implementation)
5. [Flask Implementation](#flask-implementation)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## Tổng quan Architecture

### Current Architecture (Go Services)

```
┌─────────────┐                    ┌──────────────────┐
│   Browser   │  Cookie:           │   Go Service     │
│             │  smap_auth_token   │  (Identity/      │
│             │ ─────────────────► │   Project/etc)   │
└─────────────┘                    └──────────────────┘
```

### Target Architecture (Python Service)

```
┌─────────────┐                    ┌──────────────────┐
│   Browser   │  Cookie:           │  Python Service  │
│             │  smap_auth_token   │  (FastAPI/Flask) │
│             │ ─────────────────► │                  │
└─────────────┘                    └──────────────────┘
```

### Nguyên tắc quan trọng

| Config        | Value                 | Mô tả                          |
| ------------- | --------------------- | ------------------------------ |
| JWT Secret    | `JWT_SECRET` env var  | **PHẢI** giống với Go services |
| Cookie Name   | `smap_auth_token`     | **PHẢI** giống với Go services |
| Cookie Domain | `.smap.com`           | **PHẢI** giống với Go services |
| JWT Algorithm | `HS256` (HMAC-SHA256) | **PHẢI** giống với Go services |

---

## Prerequisites

### Dependencies

```bash
# Core
pip install pyjwt python-dotenv

# FastAPI
pip install fastapi uvicorn

# Hoặc Flask
pip install flask flask-cors
```

### JWT Payload Structure (từ Go services)

```go
// Go Payload structure (project/pkg/scope/new.go)
type Payload struct {
    jwt.StandardClaims
    UserID   string `json:"sub"`      // Subject (user ID)
    Username string `json:"username"` // Username
    Role     string `json:"role"`     // User role (USER, ADMIN)
    Type     string `json:"type"`     // Token type (access, refresh)
    Refresh  bool   `json:"refresh"`  // Whether this is a refresh token
}
```

---

## Step-by-Step Implementation

### Step 1: Tạo Project Structure

```
python-service/
├── config.py
├── main.py
├── .env
├── requirements.txt
├── models/
│   └── payload.py
├── services/
│   └── jwt_manager.py
└── middleware/
    └── auth.py
```

---

### Step 2: Tạo Config (`config.py`)

```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class CookieConfig:
    """Cookie configuration - PHẢI match với Go services"""
    domain: str = os.getenv("COOKIE_DOMAIN", ".smap.com")
    secure: bool = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    same_site: str = os.getenv("COOKIE_SAMESITE", "Lax")
    max_age: int = int(os.getenv("COOKIE_MAX_AGE", "7200"))
    max_age_remember: int = int(os.getenv("COOKIE_MAX_AGE_REMEMBER", "2592000"))
    name: str = os.getenv("COOKIE_NAME", "smap_auth_token")

@dataclass
class JWTConfig:
    """JWT configuration - PHẢI match với Go services"""
    secret_key: str = os.getenv("JWT_SECRET", "")

@dataclass
class Config:
    cookie: CookieConfig = None
    jwt: JWTConfig = None

    def __post_init__(self):
        self.cookie = CookieConfig()
        self.jwt = JWTConfig()

config = Config()
```

---

### Step 3: Tạo JWT Payload Model (`models/payload.py`)

```python
from dataclasses import dataclass

@dataclass
class JWTPayload:
    """
    JWT Payload structure - PHẢI match với Go services
    Reference: project/pkg/scope/new.go
    """
    sub: str           # UserID (subject)
    username: str      # Username
    role: str          # User role (USER, ADMIN)
    type: str          # Token type (access, refresh)
    refresh: bool      # Whether this is a refresh token
    exp: int           # Expiration timestamp
    iat: int           # Issued at timestamp
    nbf: int           # Not before timestamp
    jti: str           # JWT ID
```

---

### Step 4: Tạo JWT Manager (`services/jwt_manager.py`)

```python
import jwt
from models.payload import JWTPayload
from config import config

class JWTError(Exception):
    """Custom JWT error"""
    pass

class JWTManager:
    """
    JWT Manager - Verify JWT tokens
    Reference: project/pkg/scope/new.go - func (m implManager) Verify()
    """

    def __init__(self, secret_key: str):
        if not secret_key:
            raise ValueError("JWT secret key cannot be empty")
        self.secret_key = secret_key

    def verify(self, token: str) -> JWTPayload:
        """
        Verify JWT token và return payload.

        Algorithm: HS256 (HMAC-SHA256) - match với Go services
        """
        if not token:
            raise JWTError("Token is empty")

        try:
            # Decode với HS256 algorithm (match Go services)
            decoded = jwt.decode(
                token,
                self.secret_key,
                algorithms=["HS256"],
                options={
                    "verify_exp": True,
                    "verify_nbf": True,
                    "require": ["exp", "sub"]
                }
            )

            return JWTPayload(
                sub=decoded.get("sub", ""),
                username=decoded.get("username", ""),
                role=decoded.get("role", ""),
                type=decoded.get("type", ""),
                refresh=decoded.get("refresh", False),
                exp=decoded.get("exp", 0),
                iat=decoded.get("iat", 0),
                nbf=decoded.get("nbf", 0),
                jti=decoded.get("jti", "")
            )

        except jwt.ExpiredSignatureError:
            raise JWTError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise JWTError(f"Invalid token: {str(e)}")

# Singleton instance
jwt_manager = JWTManager(config.jwt.secret_key)
```

---

### Step 5: Environment Variables (`.env`)

```env
# ===========================================
# JWT Configuration
# QUAN TRỌNG: PHẢI GIỐNG VỚI GO SERVICES
# ===========================================
JWT_SECRET=your-shared-jwt-secret-key

# ===========================================
# Cookie Configuration
# QUAN TRỌNG: PHẢI GIỐNG VỚI GO SERVICES
# ===========================================
COOKIE_DOMAIN=.smap.com
COOKIE_SECURE=true
COOKIE_SAMESITE=Lax
COOKIE_MAX_AGE=7200
COOKIE_MAX_AGE_REMEMBER=2592000
COOKIE_NAME=smap_auth_token

# ===========================================
# Server Configuration
# ===========================================
HOST=0.0.0.0
PORT=8000
ENV=development
```

---

## FastAPI Implementation

### Auth Middleware (`middleware/auth.py`)

```python
from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyCookie
from typing import Optional
from services.jwt_manager import jwt_manager, JWTError
from models.payload import JWTPayload
from config import config

# Cookie security scheme cho Swagger docs
cookie_scheme = APIKeyCookie(name=config.cookie.name, auto_error=False)

async def get_current_user(
    request: Request,
    cookie_token: Optional[str] = Depends(cookie_scheme)
) -> JWTPayload:
    """
    Auth middleware - Extract và verify JWT từ HTTPOnly cookie.

    Reference: project/internal/middleware/middleware.go - func (m Middleware) Auth()
    """
    # Lấy token từ cookie
    token = request.cookies.get(config.cookie.name)

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication cookie"
        )

    try:
        payload = jwt_manager.verify(token)
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )

def auth_required(payload: JWTPayload = Depends(get_current_user)) -> JWTPayload:
    """Dependency để inject vào routes"""
    return payload
```

### Main Application (`main.py`)

```python
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from middleware.auth import auth_required
from models.payload import JWTPayload

app = FastAPI(
    title="Python Service API",
    description="Python service với HTTPOnly cookie authentication",
    version="1.0.0"
)

# ===========================================
# CORS Configuration
# QUAN TRỌNG: credentials=True cho cookies
# ===========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://smap.tantai.dev",
        "https://smap-api.tantai.dev",
    ],
    allow_credentials=True,  # BẮT BUỘC cho cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===========================================
# Protected Routes (yêu cầu authentication)
# ===========================================
@app.get("/api/protected")
async def protected_route(user: JWTPayload = Depends(auth_required)):
    """Route yêu cầu authentication"""
    return {
        "message": "Authenticated!",
        "user_id": user.sub,
        "username": user.username,
        "role": user.role
    }

@app.get("/api/me")
async def get_me(user: JWTPayload = Depends(auth_required)):
    """Lấy thông tin user hiện tại"""
    return {
        "user_id": user.sub,
        "username": user.username,
        "role": user.role
    }

# ===========================================
# Public Routes (không cần authentication)
# ===========================================
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/api/public")
async def public_route():
    """Public endpoint"""
    return {"message": "Public endpoint"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Flask Implementation

### Auth Middleware (`middleware/auth.py`)

```python
from functools import wraps
from flask import request, jsonify, g
from services.jwt_manager import jwt_manager, JWTError
from config import config

def auth_required(f):
    """
    Auth decorator - Extract và verify JWT từ HTTPOnly cookie.

    Reference: project/internal/middleware/middleware.go - func (m Middleware) Auth()
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Lấy token từ cookie
        token = request.cookies.get(config.cookie.name)

        if not token:
            return jsonify({"error": "Missing authentication cookie"}), 401

        try:
            payload = jwt_manager.verify(token)
            # Store payload trong Flask g object
            g.current_user = payload
            return f(*args, **kwargs)
        except JWTError as e:
            return jsonify({"error": str(e)}), 401

    return decorated_function

def get_current_user():
    """Helper để lấy current user từ g object"""
    return getattr(g, 'current_user', None)
```

### Main Application (`main.py`)

```python
from flask import Flask, jsonify
from flask_cors import CORS
from middleware.auth import auth_required, get_current_user

app = Flask(__name__)

# ===========================================
# CORS Configuration
# QUAN TRỌNG: supports_credentials=True cho cookies
# ===========================================
CORS(
    app,
    origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://smap.tantai.dev",
        "https://smap-api.tantai.dev",
    ],
    supports_credentials=True  # BẮT BUỘC cho cookies
)

# ===========================================
# Protected Routes (yêu cầu authentication)
# ===========================================
@app.route("/api/protected")
@auth_required
def protected_route():
    """Route yêu cầu authentication"""
    user = get_current_user()
    return jsonify({
        "message": "Authenticated!",
        "user_id": user.sub,
        "username": user.username,
        "role": user.role
    })

@app.route("/api/me")
@auth_required
def get_me():
    """Lấy thông tin user hiện tại"""
    user = get_current_user()
    return jsonify({
        "user_id": user.sub,
        "username": user.username,
        "role": user.role
    })

# ===========================================
# Public Routes (không cần authentication)
# ===========================================
@app.route("/api/health")
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})

@app.route("/api/public")
def public_route():
    """Public endpoint"""
    return jsonify({"message": "Public endpoint"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
```

---

## Testing

### 1. Login qua Identity Service

```bash
# Login để lấy cookie
curl -i -X POST https://smap-api.tantai.dev/identity/authentication/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}' \
  -c cookies.txt

# Kiểm tra Set-Cookie header
# Expected: Set-Cookie: smap_auth_token=eyJhbGc...; HttpOnly; Secure; SameSite=Lax
```

### 2. Test Python Service với Cookie

```bash
# Test protected endpoint
curl -X GET http://localhost:8000/api/protected \
  -b cookies.txt

# Expected response:
# {"message": "Authenticated!", "user_id": "...", "username": "...", "role": "..."}
```

### 3. Test CORS với Credentials (Browser)

```javascript
// Trong browser console tại https://smap.tantai.dev
fetch("http://localhost:8000/api/protected", {
  credentials: "include",
})
  .then((r) => r.json())
  .then(console.log);

// Expected: {"message": "Authenticated!", ...}
```

### 4. Test Unauthorized Access

```bash
# Test không có cookie
curl -X GET http://localhost:8000/api/protected

# Expected: {"detail": "Missing authentication cookie"} với status 401
```

---

## Troubleshooting

### Issue: "401 Unauthorized" sau khi login

**Nguyên nhân có thể:**

1. JWT Secret không match với Go services
2. Cookie name không đúng
3. Frontend không gửi credentials

**Giải pháp:**

```python
# Kiểm tra JWT_SECRET
print(f"JWT Secret: {config.jwt.secret_key[:10]}...")  # In 10 ký tự đầu

# Kiểm tra cookie name
print(f"Cookie name: {config.cookie.name}")  # Phải là "smap_auth_token"
```

### Issue: CORS Error

**Nguyên nhân:** `allow_credentials` không được set

**Giải pháp:**

```python
# FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,  # PHẢI có
    # ...
)

# Flask
CORS(app, supports_credentials=True)  # PHẢI có
```

### Issue: "Invalid token" error

**Nguyên nhân:** JWT algorithm không match

**Giải pháp:**

```python
# Đảm bảo dùng HS256
decoded = jwt.decode(
    token,
    self.secret_key,
    algorithms=["HS256"],  # PHẢI là HS256
    # ...
)
```

### Issue: Cookie không được gửi từ browser

**Nguyên nhân:** Frontend không set `withCredentials`

**Giải pháp:**

```javascript
// Axios
const api = axios.create({
  baseURL: "http://python-service:8000",
  withCredentials: true, // BẮT BUỘC
});

// Fetch
fetch(url, { credentials: "include" });
```

---

## Checklist

### Pre-Implementation

- [ ] Lấy `JWT_SECRET` từ Go services
- [ ] Xác nhận cookie configuration từ Go services
- [ ] Setup Python environment

### Implementation

- [ ] Tạo `config.py` với CookieConfig và JWTConfig
- [ ] Tạo `models/payload.py` với JWTPayload
- [ ] Tạo `services/jwt_manager.py` với verify function
- [ ] Tạo `middleware/auth.py` với auth middleware
- [ ] Setup CORS với `credentials=True`
- [ ] Tạo `.env` file

### Testing

- [ ] Test login qua Identity service
- [ ] Test protected endpoint với cookie
- [ ] Test CORS từ browser
- [ ] Test unauthorized access

### Deployment

- [ ] Set environment variables
- [ ] Verify JWT_SECRET match với production
- [ ] Test cross-service authentication

---

## References

- Go Middleware: `project/internal/middleware/middleware.go`
- Go JWT Manager: `project/pkg/scope/new.go`
- Go Config: `project/config/config.go`
- Migration Guide: `project/document/httponly_microservice_migration.md`
