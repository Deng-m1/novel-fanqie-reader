# 移除用户过滤 - 查看所有用户任务

如果你希望内部API可以管理**所有用户**的任务和资源，需要修改以下代码：

---

## 方案1: 完全移除用户过滤（推荐）

### 修改文件：`backend/app.py`

#### 1. 修改任务列表接口

```python
# 原代码 (backend/app.py 第570-589行)
@app.route("/api/tasks/list", methods=["GET"])
def list_user_tasks():
    logger = current_app.logger
    user_id = 1  # Fixed user ID for internal API
    logger.info(f"Fetching task list for user ID: {user_id}")
    try:
        tasks = (
            DownloadTask.query.filter_by(user_id=user_id)  # ← 移除这行过滤
            .options(_db.joinedload(DownloadTask.novel))
            .order_by(DownloadTask.created_at.desc())
            .all()
        )
        return jsonify(tasks=[task.to_dict() for task in tasks])
    except Exception as e:
        logger.error(f"Error fetching task list for user {user_id}: {e}", exc_info=True)
        return jsonify(error="Database error fetching task list"), 500

# 修改为（查看所有用户的任务）
@app.route("/api/tasks/list", methods=["GET"])
def list_user_tasks():
    logger = current_app.logger
    logger.info(f"Fetching all tasks (internal API)")
    try:
        tasks = (
            DownloadTask.query  # ← 移除了 filter_by(user_id=user_id)
            .options(_db.joinedload(DownloadTask.novel))
            .order_by(DownloadTask.created_at.desc())
            .all()
        )
        return jsonify(tasks=[task.to_dict() for task in tasks])
    except Exception as e:
        logger.error(f"Error fetching all tasks: {e}", exc_info=True)
        return jsonify(error="Database error fetching task list"), 500
```

---

#### 2. 修改终止任务接口

```python
# 原代码 (backend/app.py 第588-640行)
@app.route("/api/tasks/<int:db_task_id>/terminate", methods=["POST"])
def terminate_task(db_task_id):
    logger = current_app.logger
    user_id = 1  # Fixed user ID for internal API
    logger.info(f"User {user_id} requesting termination for DB Task ID: {db_task_id}")
    try:
        task = DownloadTask.query.filter_by(id=db_task_id, user_id=user_id).first()  # ← 移除 user_id 过滤
        if not task:
            return jsonify(error="Task not found or access denied"), 404
        # ... 其余代码

# 修改为（可以终止任何用户的任务）
@app.route("/api/tasks/<int:db_task_id>/terminate", methods=["POST"])
def terminate_task(db_task_id):
    logger = current_app.logger
    logger.info(f"Internal API requesting termination for DB Task ID: {db_task_id}")
    try:
        task = DownloadTask.query.filter_by(id=db_task_id).first()  # ← 移除了 user_id 过滤
        if not task:
            return jsonify(error="Task not found"), 404
        
        user_id = task.user_id  # 获取任务的真实用户ID用于通知
        # ... 其余代码保持不变
```

---

#### 3. 修改删除任务接口

```python
# 原代码 (backend/app.py 第635-672行)
@app.route("/api/tasks/<int:db_task_id>", methods=["DELETE"])
def delete_task(db_task_id):
    logger = current_app.logger
    user_id = 1  # Fixed user ID for internal API
    logger.info(f"User {user_id} requesting deletion for DB Task ID: {db_task_id}")
    try:
        task = DownloadTask.query.filter_by(id=db_task_id, user_id=user_id).first()  # ← 移除 user_id 过滤
        if not task:
            return jsonify(error="Task not found or access denied"), 404
        # ... 其余代码

# 修改为（可以删除任何用户的任务）
@app.route("/api/tasks/<int:db_task_id>", methods=["DELETE"])
def delete_task(db_task_id):
    logger = current_app.logger
    logger.info(f"Internal API requesting deletion for DB Task ID: {db_task_id}")
    try:
        task = DownloadTask.query.filter_by(id=db_task_id).first()  # ← 移除了 user_id 过滤
        if not task:
            return jsonify(error="Task not found"), 404
        
        user_id = task.user_id  # 获取任务的真实用户ID用于通知
        # ... 其余代码保持不变
```

---

#### 4. 修改重新下载接口

```python
# 原代码 (backend/app.py 第666-741行)
@app.route("/api/tasks/<int:db_task_id>/redownload", methods=["POST"])
def redownload_task(db_task_id):
    logger = current_app.logger
    user_id = 1  # Fixed user ID for internal API
    logger.info(f"User {user_id} requesting re-download for DB Task ID: {db_task_id}")
    try:
        task = DownloadTask.query.filter_by(id=db_task_id, user_id=user_id).first()  # ← 移除 user_id 过滤
        if not task:
            return jsonify(error="Task not found or access denied"), 404
        # ... 其余代码

# 修改为（可以重新下载任何用户的任务）
@app.route("/api/tasks/<int:db_task_id>/redownload", methods=["POST"])
def redownload_task(db_task_id):
    logger = current_app.logger
    logger.info(f"Internal API requesting re-download for DB Task ID: {db_task_id}")
    try:
        task = DownloadTask.query.filter_by(id=db_task_id).first()  # ← 移除了 user_id 过滤
        if not task:
            return jsonify(error="Task not found"), 404
        
        user_id = task.user_id  # 获取任务的真实用户ID
        novel_id_to_redownload = task.novel_id
        # ... 其余代码保持不变
```

---

## 方案2: 添加查询参数支持（灵活）

保留原有逻辑，但添加可选的查询参数来控制是否过滤用户。

```python
@app.route("/api/tasks/list", methods=["GET"])
def list_user_tasks():
    logger = current_app.logger
    # 如果提供 all=true 参数，则查看所有用户的任务
    show_all = request.args.get("all", "false").lower() == "true"
    
    if show_all:
        logger.info("Fetching all tasks (internal API)")
        tasks = (
            DownloadTask.query
            .options(_db.joinedload(DownloadTask.novel))
            .order_by(DownloadTask.created_at.desc())
            .all()
        )
    else:
        user_id = 1
        logger.info(f"Fetching tasks for user ID: {user_id}")
        tasks = (
            DownloadTask.query.filter_by(user_id=user_id)
            .options(_db.joinedload(DownloadTask.novel))
            .order_by(DownloadTask.created_at.desc())
            .all()
        )
    
    return jsonify(tasks=[task.to_dict() for task in tasks])

# 使用示例
# 只看 user_id=1 的任务
curl http://localhost:5000/api/tasks/list

# 看所有用户的任务
curl "http://localhost:5000/api/tasks/list?all=true"
```

---

## 实施步骤

### 推荐：方案1（完全移除用户过滤）

1. **编辑 `backend/app.py`**，按照上述示例修改4个接口
2. **重启服务**
   ```bash
   docker-compose restart backend celery_worker
   ```
3. **测试**
   ```bash
   # 现在应该能看到所有用户的任务
   curl http://localhost:5000/api/tasks/list
   ```

---

## 完整代码示例

完整修改后的代码片段保存在：`PATCH_REMOVE_USER_FILTER.txt`

---

## ⚠️ 注意事项

1. **WebSocket通知**：如果使用了WebSocket，需要确保任务更新通知发送给正确的用户
2. **日志记录**：建议在日志中记录被操作任务的真实用户ID
3. **安全性**：确保服务在内网环境运行，避免未授权访问

---

想让我直接帮你实施方案1吗？我可以立即修改代码。
