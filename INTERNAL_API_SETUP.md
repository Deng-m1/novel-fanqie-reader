# 内部 API 访问配置指南

如果你想把这个服务作为内部服务使用，不需要 JWT 鉴权，有以下几种方案：

---

## 方案 1: 移除所有接口的 JWT 鉴权（最简单）⭐

### 修改步骤：

#### 1. 编辑 `backend/app.py`，批量移除 `@jwt_required()` 装饰器

找到以下接口，删除它们的 `@jwt_required()` 装饰器：

```python
# 搜索接口
@app.route("/api/search", methods=["GET"])
# @jwt_required()  # <-- 注释掉或删除这行
def search_novels_api():
    # ...

# 添加小说接口
@app.route("/api/novels", methods=["POST"])
# @jwt_required()  # <-- 注释掉或删除这行
def add_novel_and_crawl():
    logger = current_app.logger
    # user_id = int(get_jwt_identity())  # <-- 注释掉这行
    user_id = 1  # <-- 使用固定用户ID
    # ...

# 其他所有需要鉴权的接口都做相同修改
```

#### 2. 修改后端代码中所有依赖 `get_jwt_identity()` 的地方

在 `backend/app.py` 中搜索 `get_jwt_identity()`，将其替换为固定用户ID：

```python
# 原代码
user_id = int(get_jwt_identity())

# 修改为
user_id = 1  # 使用默认内部用户ID
```

#### 3. 重启服务

```bash
docker-compose restart fanqie fanqie_celery_worker
```

### 修改后的 API 调用示例：

```bash
# 不再需要 token，直接调用
curl -X POST http://localhost:5000/api/novels \
  -H "Content-Type: application/json" \
  -d '{"novel_id":"7518662933425966105","max_chapters":10}'

# 查询任务列表
curl http://localhost:5000/api/tasks/list

# 下载小说
curl http://localhost:5000/api/novels/7518662933425966105/download \
  -o novel.epub
```

---

## 方案 2: 添加 API Key 认证（推荐用于内部服务）⭐⭐

创建一个简单的 API Key 中间件，只允许持有密钥的客户端访问。

### 实现步骤：

#### 1. 在 `.env` 中添加 API Key 配置

```bash
# Internal API Access
INTERNAL_API_KEY=your-secret-api-key-here
ENABLE_INTERNAL_API=true
```

#### 2. 创建 API Key 装饰器 `backend/internal_auth.py`

```python
# backend/internal_auth.py
from functools import wraps
from flask import request, jsonify, current_app
import os

def internal_api_required(f):
    """装饰器：验证内部API密钥"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 如果启用了内部API模式
        if os.getenv("ENABLE_INTERNAL_API", "false").lower() == "true":
            api_key = request.headers.get("X-Internal-API-Key")
            expected_key = os.getenv("INTERNAL_API_KEY")
            
            if not api_key or api_key != expected_key:
                return jsonify(error="Invalid or missing internal API key"), 401
        
        # 如果未启用内部API模式，则继续使用JWT认证（保持原逻辑）
        return f(*args, **kwargs)
    
    return decorated_function
```

#### 3. 修改需要的接口，使用新的装饰器

```python
from internal_auth import internal_api_required

@app.route("/api/novels", methods=["POST"])
@internal_api_required  # <-- 使用内部API认证
def add_novel_and_crawl():
    logger = current_app.logger
    user_id = 1  # 内部API使用固定用户ID
    # ... 其余代码保持不变
```

#### 4. 调用示例

```bash
# 使用 API Key 调用
curl -X POST http://localhost:5000/api/novels \
  -H "Content-Type: application/json" \
  -H "X-Internal-API-Key: your-secret-api-key-here" \
  -d '{"novel_id":"7518662933425966105"}'
```

---

## 方案 3: 使用 IP 白名单（适用于固定内网环境）⭐⭐⭐

只允许特定IP地址访问，无需任何认证。

### 实现步骤：

#### 1. 创建 IP 白名单中间件 `backend/ip_whitelist.py`

```python
# backend/ip_whitelist.py
from functools import wraps
from flask import request, jsonify
import os

ALLOWED_IPS = os.getenv("ALLOWED_IPS", "127.0.0.1,localhost").split(",")

def ip_whitelist_required(f):
    """装饰器：验证请求来源IP"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        
        # Docker 容器内部访问会显示为内网IP
        if client_ip not in ALLOWED_IPS and client_ip not in ["172.17.0.1", "172.18.0.1"]:
            return jsonify(error=f"Access denied for IP: {client_ip}"), 403
        
        return f(*args, **kwargs)
    
    return decorated_function
```

#### 2. 在 `.env` 中配置白名单

```bash
# IP Whitelist (comma-separated)
ALLOWED_IPS=127.0.0.1,localhost,172.17.0.0/16,172.18.0.0/16
```

#### 3. 应用到接口

```python
from ip_whitelist import ip_whitelist_required

@app.route("/api/novels", methods=["POST"])
@ip_whitelist_required
def add_novel_and_crawl():
    user_id = 1  # 固定用户ID
    # ... 其余代码
```

---

## 方案 4: 混合模式（JWT + 内部 API Key）⭐⭐⭐

支持两种认证方式：外部用户使用JWT，内部服务使用API Key。

### 实现步骤：

#### 1. 创建混合认证装饰器 `backend/hybrid_auth.py`

```python
# backend/hybrid_auth.py
from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask_jwt_extended.exceptions import JWTDecodeError, NoAuthorizationError
import os

def hybrid_auth_required(f):
    """装饰器：支持JWT或内部API Key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. 检查是否有内部API Key
        api_key = request.headers.get("X-Internal-API-Key")
        expected_key = os.getenv("INTERNAL_API_KEY")
        
        if api_key and api_key == expected_key:
            # 使用内部API Key认证成功，使用固定用户ID
            request.internal_user_id = 1
            return f(*args, **kwargs)
        
        # 2. 尝试JWT认证
        try:
            verify_jwt_in_request()
            # JWT认证成功，获取真实用户ID
            request.internal_user_id = int(get_jwt_identity())
            return f(*args, **kwargs)
        except (JWTDecodeError, NoAuthorizationError):
            return jsonify(error="Authentication required (JWT or API Key)"), 401
    
    return decorated_function

def get_user_id():
    """获取当前用户ID（来自JWT或内部API）"""
    return getattr(request, 'internal_user_id', None)
```

#### 2. 修改接口使用混合认证

```python
from hybrid_auth import hybrid_auth_required, get_user_id

@app.route("/api/novels", methods=["POST"])
@hybrid_auth_required
def add_novel_and_crawl():
    logger = current_app.logger
    user_id = get_user_id()  # 自动获取用户ID
    # ... 其余代码保持不变
```

#### 3. 调用示例

```bash
# 方式1: 使用内部API Key
curl -X POST http://localhost:5000/api/novels \
  -H "Content-Type: application/json" \
  -H "X-Internal-API-Key: your-secret-api-key-here" \
  -d '{"novel_id":"7518662933425966105"}'

# 方式2: 使用JWT Token（前端用户）
curl -X POST http://localhost:5000/api/novels \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"novel_id":"7518662933425966105"}'
```

---

## 推荐方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| 方案1: 完全移除鉴权 | 最简单，无需任何认证 | 无安全性，任何人都可访问 | 完全隔离的内网环境 |
| 方案2: API Key | 简单且有基本安全性 | 需要在请求中携带密钥 | 内部服务间调用 |
| 方案3: IP白名单 | 透明，无需携带凭证 | 不适合动态IP环境 | 固定内网环境 |
| 方案4: 混合模式 | 灵活，同时支持内外部 | 实现稍复杂 | 既有前端用户又有内部服务 |

---

## 快速实施指南（推荐：方案2 API Key）

### 完整代码修改：

#### 1. 创建 `backend/internal_auth.py`

```python
# backend/internal_auth.py
from functools import wraps
from flask import request, jsonify
import os

def internal_api_key_required(f):
    """验证内部API密钥，通过则使用固定用户ID"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get("X-Internal-API-Key")
        expected_key = os.getenv("INTERNAL_API_KEY")
        
        if not expected_key:
            return jsonify(error="Internal API not configured"), 500
        
        if not api_key or api_key != expected_key:
            return jsonify(error="Invalid or missing internal API key"), 401
        
        # 设置固定用户ID供后续使用
        request.internal_user_id = int(os.getenv("INTERNAL_USER_ID", "1"))
        
        return f(*args, **kwargs)
    
    return decorated_function

def get_internal_user_id():
    """获取内部API用户ID"""
    return getattr(request, 'internal_user_id', 1)
```

#### 2. 修改 `backend/app.py` 中的接口（示例）

```python
from internal_auth import internal_api_key_required, get_internal_user_id

# 原接口
@app.route("/api/novels", methods=["POST"])
@jwt_required()
def add_novel_and_crawl():
    logger = current_app.logger
    user_id = int(get_jwt_identity())
    # ...

# 修改为内部API接口
@app.route("/api/novels", methods=["POST"])
@internal_api_key_required
def add_novel_and_crawl():
    logger = current_app.logger
    user_id = get_internal_user_id()
    # ... 其余代码保持不变
```

#### 3. 在 `.env` 中添加配置

```bash
# Internal API Configuration
INTERNAL_API_KEY=your-secret-key-here-change-me
INTERNAL_USER_ID=1
```

#### 4. 重启服务

```bash
docker-compose restart fanqie fanqie_celery_worker
```

#### 5. 使用示例

```bash
# 设置API Key
API_KEY="your-secret-key-here-change-me"

# 提交下载任务
curl -X POST http://localhost:5000/api/novels \
  -H "Content-Type: application/json" \
  -H "X-Internal-API-Key: $API_KEY" \
  -d '{"novel_id":"7518662933425966105","max_chapters":10}'

# 查询任务列表
curl http://localhost:5000/api/tasks/list \
  -H "X-Internal-API-Key: $API_KEY"

# 下载小说
curl http://localhost:5000/api/novels/7518662933425966105/download \
  -H "X-Internal-API-Key: $API_KEY" \
  -o novel.epub
```

---

## 需要修改的接口列表

如果使用方案2（API Key），需要将以下接口的 `@jwt_required()` 替换为 `@internal_api_key_required`：

1. `POST /api/novels` - 添加小说
2. `GET /api/novels` - 小说列表
3. `GET /api/novels/<id>` - 小说详情
4. `GET /api/novels/<id>/chapters` - 章节列表
5. `GET /api/novels/<id>/chapters/<chapter_id>` - 章节内容
6. `GET /api/novels/<id>/download` - 下载小说
7. `GET /api/search` - 搜索小说
8. `GET /api/tasks/list` - 任务列表
9. `GET /api/tasks/status/<task_id>` - 任务状态
10. `POST /api/tasks/<id>/terminate` - 终止任务
11. `DELETE /api/tasks/<id>` - 删除任务
12. `POST /api/tasks/<id>/redownload` - 重新下载
13. `GET /api/stats/*` - 统计接口

并将获取用户ID的代码：
```python
user_id = int(get_jwt_identity())
```

修改为：
```python
user_id = get_internal_user_id()
```

---

## 注意事项

1. **生产环境安全**：如果服务暴露在公网，务必使用强密钥（方案2）或IP白名单（方案3）
2. **用户隔离**：内部API使用固定用户ID，所有内部服务的请求都会关联到同一用户
3. **日志记录**：建议记录所有内部API调用，方便审计
4. **密钥轮换**：定期更换内部API Key

---

想要我帮你直接实现哪个方案？我可以为你生成完整的代码修改。
