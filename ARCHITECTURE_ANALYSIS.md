# Fanqie Reader 架构分析与数据库替代方案

## 当前架构组件依赖分析

### 1. MySQL 的使用场景

#### 作用：持久化存储
**必要性：✅ 必需（但可替换）**

MySQL 在项目中存储以下数据：

| 表名 | 用途 | 记录数量级 | 查询特点 |
|------|------|----------|---------|
| **User** | 用户账户信息 | 少量 | 简单查询（用户名/ID） |
| **Novel** | 小说元数据 | 中等 | 列表查询、分页 |
| **Chapter** | 章节内容 | 大量 | 按novel_id范围查询 |
| **DownloadTask** | 下载任务状态 | 中等 | 按user_id和status查询 |
| **WordStat** | 词频统计 | 大量 | 按novel_id聚合查询 |

#### MongoDB 替代方案

**✅ 完全可行！MongoDB 更适合这个场景**

**优势：**
- 📄 **文档结构天然匹配**：小说+章节的层级关系非常适合文档嵌套
- 🚀 **灵活的Schema**：小说元数据可能经常变化（标签、分类等）
- 📊 **文本搜索**：内置全文搜索支持小说内容检索
- 💾 **大文本存储**：章节内容存储更高效

**数据模型对比：**

```javascript
// MySQL关系模型（5张表，多次JOIN）
User -> DownloadTask -> Novel -> Chapter
                              -> WordStat

// MongoDB文档模型（2个集合，减少JOIN）
{
  // users 集合
  _id: ObjectId,
  username: String,
  password: String,
  download_tasks: [
    {task_id, novel_id, status, progress, ...}
  ]
}

{
  // novels 集合
  _id: ObjectId("novel_id"),
  title, author, description, tags,
  chapters: [
    {index, title, content, fetched_at}
  ],
  word_stats: [
    {word, freq}
  ],
  metadata: {...}
}
```

**迁移工作量：中等**
- 需要修改 `models.py` 使用 MongoEngine 或 PyMongo
- 需要重写查询逻辑（SQLAlchemy → MongoDB查询）
- 保留业务逻辑不变

---

### 2. Redis 的使用场景

#### 作用1：Celery 消息队列（Broker）
**必要性：⚠️ 可选（但需替代品）**

**当前用途：**
- 接收来自Flask的任务请求
- 分发任务给Celery Worker
- 存储任务队列（PENDING状态的任务）

**替代方案：**

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **RabbitMQ** | 专业消息队列，功能完善 | 需要额外服务 | ⭐⭐⭐⭐⭐ |
| **MongoDB** | 你已经有了，无需额外服务 | 不是专门做消息队列的 | ⭐⭐⭐ |
| **PostgreSQL** | 你已经有了（如果用） | 性能不如专业MQ | ⭐⭐ |
| **SQLAlchemy** | 数据库作为broker | 性能较差 | ⭐⭐ |

**最佳方案：使用 MongoDB 作为 Celery Broker**

```python
# config.py
CELERY_BROKER_URL = "mongodb://localhost:27017/fanqie_celery"
CELERY_RESULT_BACKEND = "mongodb://localhost:27017/fanqie_celery"
```

**需要安装：**
```bash
pip install celery[mongodb]
```

#### 作用2：Flask-SocketIO 消息广播
**必要性：⚠️ 可选（仅在多进程部署时需要）**

**当前用途：**
- 在多个 Flask 进程间同步 WebSocket 消息
- 确保任务进度更新能推送到正确的客户端

**场景分析：**

| 部署方式 | 是否需要Redis | 说明 |
|---------|--------------|------|
| **单进程** | ❌ 不需要 | SocketIO 内存模式即可 |
| **多进程/多服务器** | ✅ 需要 | 需要消息队列同步 |

**替代方案：**

```python
# 方案1：单进程部署（不需要Redis）
socketio = SocketIO(
    app,
    async_mode="eventlet",
    cors_allowed_origins="*"
    # 不设置 message_queue，使用内存模式
)

# 方案2：使用 MongoDB 作为消息队列
socketio = SocketIO(
    app,
    message_queue="mongodb://localhost:27017/fanqie_socketio",
    async_mode="eventlet",
    cors_allowed_origins="*"
)
```

**注意：** Flask-SocketIO 官方支持 Redis、RabbitMQ、Kafka，**但不直接支持 MongoDB**。

**最佳实践：**
- 小型项目/单机部署：不使用 message_queue（内存模式）
- 中大型项目：使用 RabbitMQ（更专业）

---

## 针对你的需求的推荐架构

### 场景：你有 MongoDB，没有 Redis

#### 推荐方案 A：MongoDB + RabbitMQ（最佳）

```yaml
services:
  backend:
    # Flask API 服务器
  
  celery_worker:
    # 后台任务处理
  
  mongodb:
    image: mongo:7
    # 存储所有业务数据
  
  rabbitmq:
    image: rabbitmq:3-management
    # Celery 消息队列
    # SocketIO 消息广播（可选）
```

**优点：**
- ✅ 使用现有的 MongoDB
- ✅ RabbitMQ 是专业消息队列，性能好
- ✅ RabbitMQ 资源占用小（比 Redis 小）
- ✅ 架构清晰，职责分明

**工作量：**
- 修改数据模型：中等（3-5天）
- 修改 Celery 配置：小（1小时）
- 修改 SocketIO 配置：小（30分钟）

---

#### 推荐方案 B：仅使用 MongoDB（极简）

```yaml
services:
  backend:
    # Flask API 服务器（单进程）
  
  celery_worker:
    # 后台任务处理
  
  mongodb:
    image: mongo:7
    # 存储业务数据 + Celery队列
```

**优点：**
- ✅ 只需要一个数据库服务
- ✅ 部署最简单
- ✅ 运维成本最低

**限制：**
- ⚠️ Flask 必须单进程运行（无法水平扩展）
- ⚠️ Celery 用 MongoDB 做 broker 性能略低（但对小型项目够用）

**工作量：**
- 修改数据模型：中等（3-5天）
- 修改 Celery 配置：小（1小时）
- 修改 SocketIO 配置：极小（去掉 message_queue 参数）

---

## 关键代码修改示例

### 1. 使用 MongoDB 替代 MySQL

#### 安装依赖
```bash
pip install mongoengine pymongo
```

#### 修改 models.py
```python
from mongoengine import Document, EmbeddedDocument, fields
from datetime import datetime

class User(Document):
    username = fields.StringField(required=True, unique=True, max_length=32)
    password = fields.StringField(required=True, max_length=256)
    created_at = fields.DateTimeField(default=datetime.utcnow)
    last_login_at = fields.DateTimeField()
    
    meta = {'collection': 'users'}

class Chapter(EmbeddedDocument):
    chapter_id = fields.StringField(required=True)
    index = fields.IntField(required=True)
    title = fields.StringField(required=True, max_length=255)
    content = fields.StringField(required=True)
    fetched_at = fields.DateTimeField(default=datetime.utcnow)

class WordStat(EmbeddedDocument):
    word = fields.StringField(required=True, max_length=64)
    freq = fields.IntField(required=True)

class Novel(Document):
    novel_id = fields.StringField(required=True, unique=True)
    title = fields.StringField(required=True, max_length=255)
    author = fields.StringField(max_length=128)
    description = fields.StringField()
    tags = fields.ListField(fields.StringField())
    status = fields.StringField(max_length=32)
    total_chapters = fields.IntField()
    cover_image_url = fields.StringField(max_length=512)
    
    # 嵌入章节（适合章节不太多的情况，< 1000章）
    chapters = fields.EmbeddedDocumentListField(Chapter)
    
    # 嵌入词频统计
    word_stats = fields.EmbeddedDocumentListField(WordStat)
    
    last_crawled_at = fields.DateTimeField()
    created_at = fields.DateTimeField(default=datetime.utcnow)
    
    meta = {
        'collection': 'novels',
        'indexes': [
            'novel_id',
            'title',
            'author'
        ]
    }

class DownloadTask(EmbeddedDocument):
    task_id = fields.IntField()
    novel_id = fields.StringField(required=True)
    celery_task_id = fields.StringField()
    status = fields.StringField(default="PENDING")
    progress = fields.IntField(default=0)
    message = fields.StringField(max_length=255)
    created_at = fields.DateTimeField(default=datetime.utcnow)
    updated_at = fields.DateTimeField(default=datetime.utcnow)

class UserTask(Document):
    user_id = fields.ReferenceField(User, required=True)
    tasks = fields.EmbeddedDocumentListField(DownloadTask)
    
    meta = {'collection': 'user_tasks'}
```

#### 修改 config.py
```python
class Settings:
    # --- MongoDB Settings ---
    MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
    MONGODB_PORT = int(os.getenv('MONGODB_PORT', 27017))
    MONGODB_DB = os.getenv('MONGODB_DB', 'fanqie_reader')
    MONGODB_USERNAME = os.getenv('MONGODB_USERNAME', '')
    MONGODB_PASSWORD = os.getenv('MONGODB_PASSWORD', '')
    
    # --- Celery Settings ---
    CELERY_BROKER_URL = os.getenv(
        'CELERY_BROKER_URL', 
        f'mongodb://{MONGODB_HOST}:{MONGODB_PORT}/celery_broker'
    )
    CELERY_RESULT_BACKEND = os.getenv(
        'CELERY_RESULT_BACKEND',
        f'mongodb://{MONGODB_HOST}:{MONGODB_PORT}/celery_results'
    )
```

#### 修改 app.py
```python
from mongoengine import connect

# MongoDB连接
connect(
    db=settings.MONGODB_DB,
    host=settings.MONGODB_HOST,
    port=settings.MONGODB_PORT,
    username=settings.MONGODB_USERNAME or None,
    password=settings.MONGODB_PASSWORD or None
)

# SocketIO 单进程模式（不需要 message_queue）
socketio = SocketIO(
    app,
    async_mode="eventlet",
    cors_allowed_origins="http://localhost:5173"
    # 移除 message_queue 参数
)
```

---

### 2. 使用 RabbitMQ 作为 Celery Broker（推荐）

#### docker-compose.yml
```yaml
services:
  backend:
    # ... 保持不变
    environment:
      - CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
      - CELERY_RESULT_BACKEND=mongodb://mongodb:27017/celery_results
  
  celery_worker:
    # ... 保持不变
    depends_on:
      - mongodb
      - rabbitmq
  
  mongodb:
    image: mongo:7
    container_name: fanqie_mongodb
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
  
  rabbitmq:
    image: rabbitmq:3-management
    container_name: fanqie_rabbitmq
    ports:
      - "5672:5672"    # AMQP端口
      - "15672:15672"  # 管理界面
    environment:
      - RABBITMQ_DEFAULT_USER=guest
      - RABBITMQ_DEFAULT_PASS=guest
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq

volumes:
  mongodb_data:
  rabbitmq_data:
```

#### 安装依赖
```bash
pip install celery[amqp]  # RabbitMQ支持
```

---

## 性能对比

| 组件 | MySQL+Redis | MongoDB+RabbitMQ | 仅MongoDB |
|------|------------|-----------------|----------|
| **查询速度** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **写入速度** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **消息队列性能** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **水平扩展** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **运维复杂度** | 高（2个服务） | 中（2个服务） | 低（1个服务） |
| **资源占用** | 高 | 中 | 低 |

---

## 总结与建议

### 你的情况：有 MongoDB，没有 Redis

#### 🎯 最佳方案：**MongoDB + RabbitMQ**

**理由：**
1. ✅ MongoDB 非常适合存储小说这种文档结构数据
2. ✅ RabbitMQ 是轻量级消息队列（比Redis轻）
3. ✅ 可以水平扩展
4. ✅ 架构清晰，各司其职

#### 📦 预算有限/小型项目：**仅使用 MongoDB**

**理由：**
1. ✅ 最简单，只需一个数据库
2. ✅ 运维成本最低
3. ⚠️ 限制：Flask单进程（对小项目影响不大）

#### ❌ 不推荐：**使用原项目的 MySQL + Redis**

**理由：**
- 你已经有 MongoDB，再加 MySQL 是重复投资
- Redis 必须保留（Celery必须用消息队列）
- 这样变成3个数据服务，运维复杂

---

## 下一步行动

如果你决定迁移，我建议按以下顺序：

1. ✅ **第一步**：先把 Redis 换成 RabbitMQ（Celery broker）
   - 影响最小
   - 测试 Celery 任务是否正常

2. ✅ **第二步**：修改 SocketIO 为单进程模式
   - 去掉 message_queue 参数
   - 测试实时推送是否正常

3. ✅ **第三步**：逐步迁移 MySQL 到 MongoDB
   - 先迁移 User 表（最简单）
   - 再迁移 Novel + Chapter（重点）
   - 最后迁移 DownloadTask

需要我提供更详细的迁移代码吗？
