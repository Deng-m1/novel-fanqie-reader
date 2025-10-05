# 变更日志 - 内部API模式配置

## 日期：2025-10-03

---

## 🎯 变更概述

将番茄小说下载服务从**需要JWT认证的多用户系统**改造为**内部API模式**：
- ✅ 完全移除JWT认证要求
- ✅ 任务管理支持查看和操作所有用户的任务
- ✅ 前端移除登录功能
- ✅ 配置使用代理API模式下载

---

## 📝 详细变更列表

### 1. 后端变更

#### 1.1 移除JWT认证 (`backend/app.py`)

修改的接口（共13个）：

**搜索和小说管理**：
- `GET /api/search` - 移除 `@jwt_required()`
- `POST /api/novels` - 移除 `@jwt_required()`，使用固定 `user_id = 1`
- `GET /api/novels` - 移除 `@jwt_required()`
- `GET /api/novels/<id>` - 移除 `@jwt_required()`
- `GET /api/novels/<id>/chapters` - 移除 `@jwt_required()`
- `GET /api/novels/<id>/chapters/<chapter_id>` - 移除 `@jwt_required()`
- `GET /api/novels/<id>/download` - 移除 `@jwt_required()`

**任务管理**：
- `GET /api/tasks/list` - 移除 `@jwt_required()` + **移除用户过滤**
- `GET /api/tasks/status/<task_id>` - 移除 `@jwt_required()`
- `POST /api/tasks/<id>/terminate` - 移除 `@jwt_required()` + **移除用户过滤**
- `DELETE /api/tasks/<id>` - 移除 `@jwt_required()` + **移除用户过滤**
- `POST /api/tasks/<id>/redownload` - 移除 `@jwt_required()` + **移除用户过滤**

**统计分析**：
- `GET /api/stats/upload` - 移除 `@jwt_required()`
- `GET /api/stats/genre` - 移除 `@jwt_required()`
- `GET /api/stats/wordcloud/<id>` - 移除 `@jwt_required()`

#### 1.2 移除用户过滤 (`backend/app.py`)

**任务列表接口** (`list_user_tasks`):
```python
# 原代码
tasks = DownloadTask.query.filter_by(user_id=user_id).options(...).all()

# 修改为
tasks = DownloadTask.query.options(...).all()  # 返回所有用户的任务
```

**任务操作接口** (`terminate_task`, `delete_task`, `redownload_task`):
```python
# 原代码
task = DownloadTask.query.filter_by(id=db_task_id, user_id=user_id).first()

# 修改为
task = DownloadTask.query.filter_by(id=db_task_id).first()
user_id = task.user_id  # 从任务中获取真实user_id用于通知
```

#### 1.3 配置代理API模式

**环境变量配置** (`.env`):
```bash
# 禁用官方API（已失效）
NOVEL_USE_OFFICIAL_API=false

# 启用代理API（推荐）
NOVEL_USE_PROXY_API=true
```

**Docker配置** (`docker-compose.yml`):
- 添加 `NOVEL_USE_PROXY_API` 环境变量到 backend 和 celery_worker 服务

**代码配置** (`backend/novel_downloader/novel_src/base_system/context.py`):
- 添加 `use_proxy_api` 字段到 `Config` 类

**下载器修改** (`backend/novel_downloader/novel_src/network_parser/downloader.py`):
- 修改 `APIManager` 初始化逻辑，代理模式下不初始化
- 优先使用代理API进行下载

---

### 2. 前端变更

#### 2.1 移除路由认证 (`frontend/src/router/index.ts`)

```typescript
// 原代码 - 需要认证的路由
{
  path: '/tasks',
  meta: { requiresAuth: true },
}

// 修改为 - 移除认证要求
{
  path: '/tasks',
  // meta: { requiresAuth: true },  // 已移除
}

// 原代码 - 路由守卫
router.beforeEach((to, from, next) => {
  if (to.matched.some(record => record.meta.requiresAuth)) {
    if (!authStore.isAuthenticated) {
      next({ path: '/auth' })
    }
  }
})

// 修改为 - 注释掉路由守卫
// router.beforeEach(...) 已完全注释
```

#### 2.2 移除JWT Token (`frontend/src/api.ts`)

```typescript
// 原代码 - 请求拦截器添加token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 修改为 - 跳过token注入
apiClient.interceptors.request.use((config) => {
  // Internal API mode - no token required
  return config
})
```

#### 2.3 更新主页面 (`frontend/src/views/HomeView.vue`)

```vue
<!-- 原代码 - 登录/退出按钮 -->
<template v-if="authStore.isAuthenticated">
  <el-dropdown>
    <span>{{ authStore.user?.username }}</span>
  </el-dropdown>
</template>
<template v-else>
  <el-button @click="router.push('/auth')">登录/注册</el-button>
</template>

<!-- 修改为 - 内部API模式标识 -->
<span class="internal-mode-badge">内部API模式</span>
```

```typescript
// 移除认证检查和WebSocket认证逻辑
// 原代码
onMounted(() => {
  authStore.checkAuth()
  if (authStore.isAuthenticated) {
    setupWebSocketConnection()
  }
})

// 修改为
onMounted(() => {
  console.log('Running in internal API mode - no authentication')
})
```

---

### 3. 文档变更

#### 3.1 更新的文档

1. **API_DOCUMENTATION.md** - 完整的API接口文档（保留，作为参考）
2. **INTERNAL_API_SETUP.md** - 4种去除鉴权的方案详解
3. **INTERNAL_API_QUICK_START.md** - 快速上手指南（✅ 已更新）
4. **REMOVE_USER_FILTER_GUIDE.md** - 移除用户过滤的指南
5. **CHANGELOG_INTERNAL_MODE.md** - 本变更日志（新增）

#### 3.2 关键更新点

- 明确说明"任务列表返回所有用户的任务"
- 强调"可以操作任何用户的任务"
- 添加 `user_id` 字段到示例查询中
- 更新注意事项章节

---

## 🔄 数据库影响

### 用户表 (user)
- **无变更** - 用户数据保持完整
- 现有用户：
  - `user_id = 1` (admin)
  - `user_id = 2` (test_user)

### 任务表 (download_task)
- **无变更** - 任务记录保持完整
- 任务归属关系不变：
  - user_id=1 的任务：19个
  - user_id=2 的任务：2个
- **行为变化**：
  - 任务列表API现在返回全部21个任务
  - 可以跨用户操作任务

### 小说表 (novel) 和章节表 (chapter)
- **无变更** - 数据完整保留

---

## 📊 测试验证

### 后端测试

```bash
# 1. 验证无需认证即可访问
curl http://localhost:5000/api/novels?page=1&per_page=1
# ✅ 返回 200 OK

# 2. 验证返回所有用户的任务
curl http://localhost:5000/api/tasks/list | jq '.tasks | length'
# ✅ 返回 21（之前只返回19个）

# 3. 验证可以操作其他用户的任务
# 假设 task_id=10 属于 user_id=2
curl -X POST http://localhost:5000/api/tasks/10/terminate
# ✅ 成功终止（不再返回404）
```

### 前端测试

1. ✅ 访问 `http://localhost:5173` - 无需登录即可进入
2. ✅ 顶部显示"内部API模式"标识
3. ✅ 任务页面显示所有用户的任务
4. ✅ 可以操作任何任务

---

## 🔐 安全注意事项

### ⚠️ 重要警告

1. **此配置仅适用于内网环境**
   - 所有API接口完全开放，无需认证
   - 任何人都可以查看、修改、删除任务
   - **切勿**在公网环境使用此配置

2. **建议的安全措施**
   - 使用防火墙限制访问来源IP
   - 在反向代理（如Nginx）层面添加IP白名单
   - 考虑使用VPN或内网隧道访问

3. **如需恢复认证**
   - 参考 `INTERNAL_API_SETUP.md` 中的"方案4：混合模式"
   - 或者重新添加 `@jwt_required()` 装饰器

---

## 📦 部署步骤回顾

### 执行的命令

```bash
# 1. 修改环境变量
# 编辑 .env 文件

# 2. 重启服务
docker-compose restart backend celery_worker

# 3. 验证
curl http://localhost:5000/api/tasks/list
```

### 配置文件修改

1. `.env` - 环境变量配置
2. `docker-compose.yml` - 添加环境变量传递
3. `backend/app.py` - 移除认证和用户过滤
4. `backend/novel_downloader/novel_src/base_system/context.py` - 添加配置字段
5. `backend/novel_downloader/novel_src/network_parser/downloader.py` - 修复API管理器
6. `frontend/src/router/index.ts` - 移除路由守卫
7. `frontend/src/api.ts` - 移除JWT拦截器
8. `frontend/src/views/HomeView.vue` - 更新UI

---

## 🎉 功能验证清单

- [x] 后端API无需认证即可访问
- [x] 任务列表返回所有用户的任务
- [x] 可以终止任何用户的任务
- [x] 可以删除任何用户的任务
- [x] 可以重新下载任何用户的任务
- [x] 前端无需登录即可访问
- [x] 前端显示"内部API模式"标识
- [x] 代理API模式正常工作
- [x] 章节下载成功
- [x] 文档已更新

---

## 📞 技术支持

如需恢复原有的认证系统或调整配置，请参考：
- `INTERNAL_API_SETUP.md` - 多种认证方案
- `REMOVE_USER_FILTER_GUIDE.md` - 用户过滤相关
- Git历史记录 - 可以回滚到任何版本

---

**变更完成时间**: 2025-10-03 21:05 (UTC+8)
**变更执行人**: AI Assistant
**验证状态**: ✅ 已完成并验证
