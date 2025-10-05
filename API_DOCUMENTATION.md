# 番茄小说下载服务 - API 接口文档

## 服务信息

- **Base URL（容器内部）**: `http://fanqie:5000`
- **Base URL（主机访问）**: `http://localhost:5000`
- **Base URL（同机器其他服务）**: `http://127.0.0.1:5000` 或 `http://localhost:5000`

## 认证说明

大部分 API 需要 JWT 认证。请先通过登录接口获取 token，然后在后续请求中添加 `Authorization: Bearer <token>` 头。

---

## 1. 认证相关接口

### 1.1 用户注册
```bash
POST /api/auth/register
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**示例 curl 命令**:
```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123"}'
```

**响应示例（成功）**:
```json
{
  "msg": "注册成功"
}
```

**响应示例（失败）**:
```json
{
  "msg": "用户已存在"
}
```

---

### 1.2 用户登录
```bash
POST /api/auth/login
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**示例 curl 命令**:
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123"}'
```

**响应示例（成功）**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**保存 token 供后续使用**:
```bash
# 保存到变量
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123"}' | jq -r '.access_token')

echo $TOKEN
```

---

### 1.3 获取当前用户信息
```bash
GET /api/auth/me
Authorization: Bearer <token>
```

**示例 curl 命令**:
```bash
curl http://localhost:5000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

**响应示例**:
```json
{
  "id": 1,
  "username": "testuser"
}
```

---

## 2. 小说搜索接口

### 2.1 搜索小说
```bash
GET /api/search?query=<搜索关键词>
Authorization: Bearer <token>
```

**示例 curl 命令**:
```bash
curl "http://localhost:5000/api/search?query=斗罗大陆" \
  -H "Authorization: Bearer $TOKEN"
```

**响应示例**:
```json
{
  "results": [
    {
      "id": "7518662933425966105",
      "title": "斗罗：神级选择，开局三武魂镇天",
      "author": "南有嘉木辞",
      "cover": "https://p6-tt.bytecdn.cn/novel-pic/...",
      "description": "穿越斗罗大陆，我开局觉醒三生神级武魂！...",
      "category": "动漫衍生",
      "score": "8.5"
    },
    {
      "id": "7451778865157917758",
      "title": "没钱回家过年？我激活0元购系统",
      "author": "麓南的风",
      "cover": "https://p6-tt.bytecdn.cn/novel-pic/...",
      "description": "系统小说...",
      "category": "都市生活",
      "score": "8.2"
    }
  ]
}
```

**返回字段说明**:
- `id`: 小说ID
- `title`: 小说标题
- `author`: 作者
- `cover`: 封面图片URL（可直接使用）
- `description`: 小说简介
- `category`: 分类
- `score`: 评分

---

## 3. 小说管理接口

### 3.1 添加小说并开始下载
```bash
POST /api/novels
Authorization: Bearer <token>
Content-Type: application/json

{
  "novel_id": "7518662933425966105",
  "max_chapters": 10  // 可选，限制下载章节数（用于预览）
}
```

**示例 curl 命令（完整下载）**:
```bash
curl -X POST http://localhost:5000/api/novels \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"novel_id":"7518662933425966105"}'
```

**示例 curl 命令（预览模式 - 仅下载前10章）**:
```bash
curl -X POST http://localhost:5000/api/novels \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"novel_id":"7518662933425966105","max_chapters":10}'
```

**响应示例（成功）**:
```json
{
  "id": 23,
  "novel_id": "7518662933425966105",
  "user_id": 1,
  "status": "PENDING",
  "progress": 0,
  "message": null,
  "created_at": "2025-10-03T12:30:00",
  "updated_at": "2025-10-03T12:30:00",
  "celery_task_id": "abc123-def456-...",
  "novel": {
    "id": "7518662933425966105",
    "title": "Novel 7518662933425966105",
    "author": null
  }
}
```

**响应状态码**:
- `202 Accepted`: 任务创建成功
- `409 Conflict`: 该小说已有下载任务进行中
- `400 Bad Request`: 参数错误
- `500 Internal Server Error`: 服务器错误

---

### 3.2 获取小说列表（支持筛选、搜索和排序）
```bash
GET /api/novels?page=1&per_page=10&search=<标题搜索>&tags=<标签>&status=<状态>&sort=<排序字段>&order=<排序方向>
Authorization: Bearer <token>
```

**查询参数**:
- `page`: 页码（默认: 1）
- `per_page`: 每页数量（默认: 10，最大: 50）
- `search`: 标题搜索（模糊匹配，不区分大小写）
- `tags`: 标签筛选（逗号分隔，匹配任意一个，如: "玄幻,都市"）
- `status`: 状态筛选（如: "连载中", "已完结"）
- `sort`: 排序字段（可选值: `last_crawled_at`, `created_at`, `total_chapters`, `title`，默认: `last_crawled_at`）
- `order`: 排序方向（可选值: `asc`, `desc`，默认: `desc`）

**示例 1: 基础查询**
```bash
curl "http://localhost:5000/api/novels?page=1&per_page=10" \
  -H "Authorization: Bearer $TOKEN"
```

**示例 2: 标题搜索**
```bash
curl "http://localhost:5000/api/novels?search=斗破" \
  -H "Authorization: Bearer $TOKEN"
```

**示例 3: 标签筛选**
```bash
curl "http://localhost:5000/api/novels?tags=动漫衍生,玄幻" \
  -H "Authorization: Bearer $TOKEN"
```

**示例 4: 状态筛选**
```bash
curl "http://localhost:5000/api/novels?status=连载中" \
  -H "Authorization: Bearer $TOKEN"
```

**示例 5: 按章节数排序**
```bash
curl "http://localhost:5000/api/novels?sort=total_chapters&order=desc" \
  -H "Authorization: Bearer $TOKEN"
```

**示例 6: 组合查询**
```bash
curl "http://localhost:5000/api/novels?search=斗罗&tags=动漫衍生&sort=total_chapters&order=desc&per_page=20" \
  -H "Authorization: Bearer $TOKEN"
```

**响应示例**:
```json
{
  "novels": [
    {
      "id": "7518662933425966105",
      "title": "斗罗：神级选择，开局三武魂镇天",
      "author": "南有嘉木辞",
      "status": "连载中",
      "tags": "动漫衍生|系统|穿越",
      "total_chapters": 412,
      "cover_image_url": "/api/novels/7518662933425966105/cover",
      "description": "穿越斗罗大陆，我开局觉醒三生神级武魂！...",
      "last_crawled_at": "2025-10-03T12:30:00",
      "created_at": "2025-10-03T12:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 10,
  "pages": 1,
  "filters": {
    "search": "斗罗",
    "tags": "动漫衍生",
    "status": "",
    "sort": "total_chapters",
    "order": "desc"
  }
}
```

**排序字段说明**:
- `last_crawled_at`: 最后更新时间（默认）
- `created_at`: 创建时间
- `total_chapters`: 章节总数
- `title`: 标题

**注意事项**:
- 标题搜索使用模糊匹配，不区分大小写
- 标签筛选支持多个标签，用逗号分隔，匹配包含**任意一个**标签的小说（OR 逻辑）
- 日期字段排序时，NULL 值会被排在最后
- 响应中的 `filters` 字段显示当前应用的筛选条件

---

### 3.3 获取小说详情
```bash
GET /api/novels/<novel_id>
Authorization: Bearer <token>
```

**示例 curl 命令**:
```bash
curl http://localhost:5000/api/novels/7518662933425966105 \
  -H "Authorization: Bearer $TOKEN"
```

**响应示例**:
```json
{
  "id": "7518662933425966105",
  "title": "斗罗：神级选择，开局三武魂镇天",
  "author": "南有嘉木辞",
  "description": "穿越斗罗大陆，我开局觉醒三生神级武魂！...",
  "status": "连载中",
  "tags": "动漫衍生|系统|穿越",
  "total_chapters": 412,
  "cover_image_url": "/api/novels/7518662933425966105/cover",
  "last_crawled_at": "2025-10-03T12:30:00",
  "created_at": "2025-10-03T12:00:00"
}
```

---

### 3.4 获取小说封面图片
```bash
GET /api/novels/<novel_id>/cover
```

**示例 curl 命令（保存到文件）**:
```bash
curl http://localhost:5000/api/novels/7518662933425966105/cover \
  -o cover.jpg
```

**注意**: 此接口不需要认证

---

### 3.5 下载小说文件（EPUB）
```bash
GET /api/novels/<novel_id>/download
Authorization: Bearer <token>
```

**示例 curl 命令**:
```bash
curl http://localhost:5000/api/novels/7518662933425966105/download \
  -H "Authorization: Bearer $TOKEN" \
  -o novel.epub
```

---

## 4. 章节管理接口

### 4.1 获取小说章节列表
```bash
GET /api/novels/<novel_id>/chapters?page=1&per_page=50
Authorization: Bearer <token>
```

**参数说明**:
- `page`: 页码（默认 1）
- `per_page`: 每页数量（默认 50，最大 200）

**示例 curl 命令**:
```bash
curl "http://localhost:5000/api/novels/7518662933425966105/chapters?page=1&per_page=20" \
  -H "Authorization: Bearer $TOKEN"
```

**注意**: 章节默认按 `chapter_index` 升序排列

**响应示例**:
```json
{
  "chapters": [
    {
      "id": "12345",
      "novel_id": "7518662933425966105",
      "index": 1,
      "title": "第1章 楔子：亡魂归处"
    },
    {
      "id": "12346",
      "novel_id": "7518662933425966105",
      "index": 2,
      "title": "第2章 泥泞中的审判台"
    }
  ],
  "total": 412,
  "page": 1,
  "per_page": 20,
  "pages": 21,
  "novel_id": "7518662933425966105"
}
```

---

### 4.2 获取章节内容
```bash
GET /api/novels/<novel_id>/chapters/<chapter_id>
Authorization: Bearer <token>
```

**示例 curl 命令**:
```bash
curl http://localhost:5000/api/novels/7518662933425966105/chapters/12345 \
  -H "Authorization: Bearer $TOKEN"
```

**响应示例**:
```json
{
  "id": "12345",
  "novel_id": "7518662933425966105",
  "index": 1,
  "title": "第1章 楔子：亡魂归处",
  "content": "章节内容文本..."
}
```

---

## 5. 下载任务管理接口

### 5.1 获取用户的下载任务列表
```bash
GET /api/tasks/list
Authorization: Bearer <token>
```

**示例 curl 命令**:
```bash
curl http://localhost:5000/api/tasks/list \
  -H "Authorization: Bearer $TOKEN"
```

**响应示例**:
```json
{
  "tasks": [
    {
      "id": 23,
      "novel_id": "7518662933425966105",
      "user_id": 1,
      "status": "COMPLETED",
      "progress": 100,
      "message": "Download completed successfully",
      "created_at": "2025-10-03T12:30:00",
      "updated_at": "2025-10-03T12:35:00",
      "celery_task_id": "abc123-def456-...",
      "novel": {
        "id": "7518662933425966105",
        "title": "斗罗：神级选择，开局三武魂镇天",
        "author": "南有嘉木辞"
      }
    }
  ]
}
```

**任务状态说明**:
- `PENDING`: 等待开始
- `DOWNLOADING`: 下载中
- `PROCESSING`: 处理中（如生成词云）
- `COMPLETED`: 完成
- `FAILED`: 失败
- `TERMINATED`: 已终止

---

### 5.2 获取任务状态（通过 Celery Task ID）
```bash
GET /api/tasks/status/<celery_task_id>
Authorization: Bearer <token>
```

**示例 curl 命令**:
```bash
curl http://localhost:5000/api/tasks/status/abc123-def456-ghi789 \
  -H "Authorization: Bearer $TOKEN"
```

**响应示例**:
```json
{
  "task_id": "abc123-def456-ghi789",
  "status": "SUCCESS",
  "result": "Task completed.",
  "meta": {
    "status": "SUCCESS",
    "message": "Completed. Saved 10/10 chapters.",
    "chapters_processed_db": 10,
    "errors": 0
  }
}
```

---

### 5.3 终止下载任务
```bash
POST /api/tasks/<db_task_id>/terminate
Authorization: Bearer <token>
```

**示例 curl 命令**:
```bash
curl -X POST http://localhost:5000/api/tasks/23/terminate \
  -H "Authorization: Bearer $TOKEN"
```

**响应示例**:
```json
{
  "message": "Task termination signal sent.",
  "task": {
    "id": 23,
    "status": "TERMINATED",
    "progress": 0,
    "message": "Task terminated by user."
  }
}
```

---

### 5.4 删除任务记录
```bash
DELETE /api/tasks/<db_task_id>
Authorization: Bearer <token>
```

**示例 curl 命令**:
```bash
curl -X DELETE http://localhost:5000/api/tasks/23 \
  -H "Authorization: Bearer $TOKEN"
```

**响应示例**:
```json
{
  "message": "Task deleted successfully."
}
```

---

### 5.5 重新下载任务
```bash
POST /api/tasks/<db_task_id>/redownload
Authorization: Bearer <token>
```

**示例 curl 命令**:
```bash
curl -X POST http://localhost:5000/api/tasks/23/redownload \
  -H "Authorization: Bearer $TOKEN"
```

**响应示例**:
```json
{
  "message": "Re-download task queued.",
  "task": {
    "id": 23,
    "status": "PENDING",
    "progress": 0,
    "celery_task_id": "xyz789-abc123-..."
  }
}
```

---

## 6. 统计分析接口

### 6.1 获取上传统计（最近30天）
```bash
GET /api/stats/upload
Authorization: Bearer <token>
```

**示例 curl 命令**:
```bash
curl http://localhost:5000/api/stats/upload \
  -H "Authorization: Bearer $TOKEN"
```

**响应示例**:
```json
[
  {"date": "2025-09-04", "count": 5},
  {"date": "2025-09-05", "count": 3},
  {"date": "2025-10-03", "count": 12}
]
```

---

### 6.2 获取分类统计
```bash
GET /api/stats/genre
Authorization: Bearer <token>
```

**示例 curl 命令**:
```bash
curl http://localhost:5000/api/stats/genre \
  -H "Authorization: Bearer $TOKEN"
```

**响应示例**:
```json
[
  {"name": "动漫衍生", "value": 15},
  {"name": "都市脑洞", "value": 23},
  {"name": "玄幻奇幻", "value": 8}
]
```

---

### 6.3 获取小说词云图片
```bash
GET /api/stats/wordcloud/<novel_id>
Authorization: Bearer <token>
```

**示例 curl 命令**:
```bash
curl http://localhost:5000/api/stats/wordcloud/7518662933425966105 \
  -H "Authorization: Bearer $TOKEN" \
  -o wordcloud.png
```

---

## 7. 完整工作流示例

### 示例1: 搜索并下载一本小说

```bash
# 1. 登录获取 token
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123"}' \
  | jq -r '.access_token')

# 2. 搜索小说
curl "http://localhost:5000/api/search?query=斗罗大陆" \
  -H "Authorization: Bearer $TOKEN" \
  | jq

# 3. 提交下载任务（假设小说ID是 7518662933425966105）
TASK_RESPONSE=$(curl -s -X POST http://localhost:5000/api/novels \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"novel_id":"7518662933425966105","max_chapters":10}')

echo $TASK_RESPONSE | jq

# 获取任务ID
TASK_ID=$(echo $TASK_RESPONSE | jq -r '.id')

# 4. 查询任务状态
curl http://localhost:5000/api/tasks/list \
  -H "Authorization: Bearer $TOKEN" \
  | jq

# 5. 等任务完成后下载EPUB文件
curl http://localhost:5000/api/novels/7518662933425966105/download \
  -H "Authorization: Bearer $TOKEN" \
  -o novel.epub
```

---

### 示例2: 从另一个服务调用（同机器）

```bash
#!/bin/bash
# download_novel.sh

# 配置
API_BASE="http://127.0.0.1:5000"
USERNAME="your_username"
PASSWORD="your_password"
NOVEL_ID="7518662933425966105"

# 登录
echo "登录中..."
TOKEN=$(curl -s -X POST "$API_BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" \
  | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "登录失败！"
  exit 1
fi

echo "登录成功！Token: ${TOKEN:0:20}..."

# 提交下载任务
echo "提交下载任务..."
TASK=$(curl -s -X POST "$API_BASE/api/novels" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"novel_id\":\"$NOVEL_ID\"}")

TASK_ID=$(echo $TASK | jq -r '.id')
echo "任务ID: $TASK_ID"

# 轮询任务状态
echo "等待任务完成..."
while true; do
  STATUS=$(curl -s "$API_BASE/api/tasks/list" \
    -H "Authorization: Bearer $TOKEN" \
    | jq -r ".tasks[] | select(.id == $TASK_ID) | .status")
  
  echo "当前状态: $STATUS"
  
  if [ "$STATUS" == "COMPLETED" ]; then
    echo "下载完成！"
    break
  elif [ "$STATUS" == "FAILED" ] || [ "$STATUS" == "TERMINATED" ]; then
    echo "任务失败或被终止"
    exit 1
  fi
  
  sleep 5
done

# 下载文件
echo "下载EPUB文件..."
curl "$API_BASE/api/novels/$NOVEL_ID/download" \
  -H "Authorization: Bearer $TOKEN" \
  -o "novel_${NOVEL_ID}.epub"

echo "完成！文件已保存为 novel_${NOVEL_ID}.epub"
```

---

## 8. WebSocket 实时更新（可选）

如果你的服务需要实时接收任务更新，可以使用 WebSocket 连接：

```javascript
// 连接 WebSocket (示例使用 socket.io-client)
const socket = io('http://localhost:5000');

socket.on('connect', () => {
  console.log('Connected to WebSocket');
  // 使用 JWT token 进行认证
  socket.emit('authenticate', { token: 'your_jwt_token_here' });
});

socket.on('auth_response', (data) => {
  console.log('Auth response:', data);
});

socket.on('task_update', (taskData) => {
  console.log('Task update:', taskData);
  // 处理任务更新
});
```

---

## 9. 错误处理

### 常见错误响应

```json
// 401 Unauthorized - 未认证或 token 无效
{
  "msg": "需要提供授权令牌",
  "error": "authorization_required"
}

// 404 Not Found - 资源不存在
{
  "error": "Novel not found"
}

// 409 Conflict - 资源冲突（如任务已存在）
{
  "error": "Task is already active with status DOWNLOADING.",
  "task": { ... }
}

// 500 Internal Server Error - 服务器错误
{
  "error": "Database error fetching chapters"
}
```

---

## 10. Docker 网络说明

如果你的其他服务也在 Docker 中运行：

### 方式1: 加入同一网络
```bash
# 查看 fanqie-reader 使用的网络
docker network ls | grep fanqie

# 让你的服务加入该网络
docker network connect fanqie-reader_default your-service-container
```

### 方式2: 使用容器名称
如果在同一 Docker Compose 项目中，直接使用容器名：
```bash
curl http://fanqie:5000/api/novels \
  -H "Authorization: Bearer $TOKEN"
```

### 方式3: 使用主机网络
从容器内访问主机上的服务：
```bash
# Linux/Mac
curl http://host.docker.internal:5000/api/novels

# Windows
curl http://host.docker.internal:5000/api/novels
```

---

## 11. 注意事项

1. **Token 有效期**: JWT token 默认有效期为 60 分钟（可在 `.env` 中配置 `JWT_ACCESS_TOKEN_EXPIRES_MINUTES`）

2. **并发限制**: 建议控制并发下载任务数量，避免对番茄小说服务器造成压力

3. **代理模式**: 当前系统配置为使用代理API模式（`NOVEL_USE_PROXY_API=true`），更稳定可靠

4. **文件路径**: 下载的 EPUB 文件保存在容器的 `/app/data/novel_downloads/` 目录

5. **错误重试**: 下载失败的任务可以使用重新下载接口重试

---

## 12. 技术支持

如有问题，请检查：
1. 容器日志: `docker logs fanqie`
2. Worker 日志: `docker logs fanqie_celery_worker`
3. 数据库连接: 确保 MySQL 容器运行正常
4. Redis 连接: 确保 Redis 容器运行正常
