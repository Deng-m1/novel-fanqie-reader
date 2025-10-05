# 内部 API 快速使用指南（无需认证版）

## ✅ 已完成配置

你的服务已经配置为**内部API模式**：
- ✅ **所有接口**都已移除JWT鉴权，可以直接调用
- ✅ **任务管理**接口返回并可操作**所有用户**的任务（不再按用户过滤）
- ✅ **前端页面**已移除登录功能，直接显示"内部API模式"

---

## 🚀 快速开始

### 基础配置

- **Base URL**: `http://localhost:5000` 或 `http://127.0.0.1:5000`
- **容器内部访问**: `http://fanqie:5000`（如果在 Docker 网络内）
- **用户管理**: 
  - 新增任务使用固定 `user_id = 1`
  - 任务列表返回**所有用户**的任务
  - 可以操作（终止/删除/重新下载）**任何用户**的任务

---

## 📝 常用接口示例

### 1. 搜索小说

```bash
# PowerShell
$response = Invoke-WebRequest -Uri "http://localhost:5000/api/search?query=斗罗大陆" -Method GET
$response.Content | ConvertFrom-Json | ConvertTo-Json

# Bash (Linux/Mac)
curl "http://localhost:5000/api/search?query=斗罗大陆"
```

---

### 2. 提交下载任务

```bash
# PowerShell - 完整下载
$body = @{
    novel_id = "7518662933425966105"
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:5000/api/novels" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body | Select-Object -ExpandProperty Content

# PowerShell - 预览模式（只下载前10章）
$body = @{
    novel_id = "7518662933425966105"
    max_chapters = 10
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:5000/api/novels" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body | Select-Object -ExpandProperty Content

# Bash (Linux/Mac)
curl -X POST http://localhost:5000/api/novels \
  -H "Content-Type: application/json" \
  -d '{"novel_id":"7518662933425966105","max_chapters":10}'
```

---

### 3. 查询任务列表（所有用户）

```bash
# PowerShell - 查看所有用户的任务
Invoke-WebRequest -Uri "http://localhost:5000/api/tasks/list" -Method GET | 
  Select-Object -ExpandProperty Content | ConvertFrom-Json | 
  Select-Object -ExpandProperty tasks | Format-Table id, user_id, status, progress, novel_id

# Bash - 查看所有用户的任务
curl http://localhost:5000/api/tasks/list | jq '.tasks[] | {id, user_id, status, progress, novel_id}'

# 注意：返回所有用户的任务，包括 user_id=1, 2, 3... 等所有用户
```

---

### 4. 获取小说列表

```bash
# PowerShell
Invoke-WebRequest -Uri "http://localhost:5000/api/novels?page=1&per_page=10" -Method GET |
  Select-Object -ExpandProperty Content

# Bash
curl "http://localhost:5000/api/novels?page=1&per_page=10"
```

---

### 5. 获取小说详情

```bash
# PowerShell
Invoke-WebRequest -Uri "http://localhost:5000/api/novels/7518662933425966105" -Method GET |
  Select-Object -ExpandProperty Content

# Bash
curl http://localhost:5000/api/novels/7518662933425966105
```

---

### 6. 下载 EPUB 文件

```bash
# PowerShell
Invoke-WebRequest -Uri "http://localhost:5000/api/novels/7518662933425966105/download" `
  -Method GET -OutFile "novel.epub"

# Bash
curl http://localhost:5000/api/novels/7518662933425966105/download -o novel.epub
```

---

### 7. 终止下载任务（任意用户）

```bash
# PowerShell - 可以终止任何用户的任务
Invoke-WebRequest -Uri "http://localhost:5000/api/tasks/24/terminate" -Method POST |
  Select-Object -ExpandProperty Content

# Bash - 可以终止任何用户的任务
curl -X POST http://localhost:5000/api/tasks/24/terminate

# 注意：不再需要任务属于特定用户，可以终止任意任务
```

---

### 8. 删除任务记录（任意用户）

```bash
# PowerShell - 可以删除任何用户的任务
Invoke-WebRequest -Uri "http://localhost:5000/api/tasks/24" -Method DELETE |
  Select-Object -ExpandProperty Content

# Bash - 可以删除任何用户的任务
curl -X DELETE http://localhost:5000/api/tasks/24

# 注意：不再需要任务属于特定用户，可以删除任意任务
```

---

## 🔄 完整工作流示例（PowerShell）

```powershell
# 1. 搜索小说
$searchQuery = "斗罗大陆"
$searchResult = Invoke-RestMethod -Uri "http://localhost:5000/api/search?query=$searchQuery" -Method GET
$novelId = $searchResult.results[0].id
Write-Host "找到小说ID: $novelId"

# 2. 提交下载任务（预览10章）
$body = @{
    novel_id = $novelId
    max_chapters = 10
} | ConvertTo-Json

$task = Invoke-RestMethod -Uri "http://localhost:5000/api/novels" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body

$taskId = $task.id
Write-Host "任务ID: $taskId, Celery Task ID: $($task.celery_task_id)"

# 3. 轮询任务状态
Write-Host "等待任务完成..."
do {
    Start-Sleep -Seconds 3
    $tasks = Invoke-RestMethod -Uri "http://localhost:5000/api/tasks/list" -Method GET
    $currentTask = $tasks.tasks | Where-Object { $_.id -eq $taskId }
    Write-Host "当前状态: $($currentTask.status), 进度: $($currentTask.progress)%"
} while ($currentTask.status -notin @("COMPLETED", "FAILED", "TERMINATED"))

# 4. 如果成功，下载EPUB文件
if ($currentTask.status -eq "COMPLETED") {
    Write-Host "下载完成！正在保存EPUB文件..."
    Invoke-WebRequest -Uri "http://localhost:5000/api/novels/$novelId/download" `
      -Method GET -OutFile "novel_$novelId.epub"
    Write-Host "文件已保存为: novel_$novelId.epub"
} else {
    Write-Host "任务失败: $($currentTask.message)"
}
```

---

## 🔄 完整工作流示例（Bash）

```bash
#!/bin/bash

# 1. 搜索小说
SEARCH_QUERY="斗罗大陆"
SEARCH_RESULT=$(curl -s "http://localhost:5000/api/search?query=$SEARCH_QUERY")
NOVEL_ID=$(echo $SEARCH_RESULT | jq -r '.results[0].id')
echo "找到小说ID: $NOVEL_ID"

# 2. 提交下载任务（预览10章）
TASK_RESPONSE=$(curl -s -X POST http://localhost:5000/api/novels \
  -H "Content-Type: application/json" \
  -d "{\"novel_id\":\"$NOVEL_ID\",\"max_chapters\":10}")

TASK_ID=$(echo $TASK_RESPONSE | jq -r '.id')
echo "任务ID: $TASK_ID"

# 3. 轮询任务状态
echo "等待任务完成..."
while true; do
  TASKS=$(curl -s http://localhost:5000/api/tasks/list)
  STATUS=$(echo $TASKS | jq -r ".tasks[] | select(.id == $TASK_ID) | .status")
  PROGRESS=$(echo $TASKS | jq -r ".tasks[] | select(.id == $TASK_ID) | .progress")
  
  echo "当前状态: $STATUS, 进度: $PROGRESS%"
  
  if [ "$STATUS" = "COMPLETED" ]; then
    echo "下载完成！"
    break
  elif [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "TERMINATED" ]; then
    echo "任务失败或被终止"
    exit 1
  fi
  
  sleep 3
done

# 4. 下载EPUB文件
echo "正在下载EPUB文件..."
curl "http://localhost:5000/api/novels/$NOVEL_ID/download" -o "novel_$NOVEL_ID.epub"
echo "文件已保存为: novel_$NOVEL_ID.epub"
```

---

## 📋 所有可用接口

### 小说相关
- `GET /api/search?query=<关键词>` - 搜索小说
- `POST /api/novels` - 添加小说并开始下载
- `GET /api/novels?page=1&per_page=10` - 获取小说列表
- `GET /api/novels/<novel_id>` - 获取小说详情
- `GET /api/novels/<novel_id>/chapters` - 获取章节列表
- `GET /api/novels/<novel_id>/chapters/<chapter_id>` - 获取章节内容
- `GET /api/novels/<novel_id>/cover` - 获取封面图片
- `GET /api/novels/<novel_id>/download` - 下载EPUB文件

### 任务相关
- `GET /api/tasks/list` - 获取任务列表
- `GET /api/tasks/status/<celery_task_id>` - 获取任务状态
- `POST /api/tasks/<task_id>/terminate` - 终止任务
- `DELETE /api/tasks/<task_id>` - 删除任务
- `POST /api/tasks/<task_id>/redownload` - 重新下载

### 统计相关
- `GET /api/stats/upload` - 上传统计（最近30天）
- `GET /api/stats/genre` - 分类统计
- `GET /api/stats/wordcloud/<novel_id>` - 词云图片

---

## 🐳 Docker 网络访问

### 方式1: 从其他 Docker 容器访问

如果你的服务也在 Docker 中运行，加入同一网络：

```bash
# 让你的容器加入 fanqie-reader 网络
docker network connect fanqie-reader_default your-service-container

# 在容器内使用容器名访问
curl http://fanqie:5000/api/novels
```

### 方式2: 使用 docker-compose

在你的 `docker-compose.yml` 中添加网络配置：

```yaml
services:
  your-service:
    # ... 其他配置
    networks:
      - fanqie-reader_default

networks:
  fanqie-reader_default:
    external: true
```

---

## ⚠️ 注意事项

1. **无认证模式**：所有接口都不需要认证，请确保服务在安全的内网环境运行
2. **用户管理变化**：
   - 新增任务使用固定 `user_id = 1`
   - 任务列表返回**所有用户**的任务（user_id=1, 2, 3...）
   - 可以操作（终止/删除/重新下载）**任何用户**的任务
3. **并发控制**：建议控制同时下载的任务数量
4. **代理模式**：当前使用代理API模式，更稳定（`NOVEL_USE_PROXY_API=true`）
5. **错误重试**：失败的任务可以使用 `/api/tasks/<id>/redownload` 接口重试
6. **前端访问**：前端页面已移除登录功能，直接访问即可使用

---

## 🔧 如果需要恢复JWT认证

如果后续需要恢复JWT认证，只需重新添加 `@jwt_required()` 装饰器并重启服务即可。
备份的认证配置文档在 `INTERNAL_API_SETUP.md` 中。

---

## 📞 快速测试

```powershell
# 测试服务是否可用
Invoke-WebRequest -Uri "http://localhost:5000/api/novels?page=1&per_page=1" -Method GET |
  Select-Object StatusCode
# 应该返回: StatusCode: 200
```

---

🎉 现在你可以直接调用 API，无需任何认证！
