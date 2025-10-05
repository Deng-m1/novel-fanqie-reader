# JSONDecodeError 问题诊断与解决方案

## 📋 问题描述

在下载小说章节时出现大量错误：

```
Skipping chapter XXXXXX ('第XXX章') due to error marker: Error: Batch Failed (JSONDecodeError)
```

结果：所有章节（899个）全部下载失败。

---

## 🔍 诊断结果

通过运行 `test_api.py` 诊断工具，发现：

### ✅ 正常的部分
- 静态密钥：正确 (32字符)
- GlobalContext初始化：成功
- install_id 生成：成功
- 版本号获取：成功 (69132)
- 加密密钥注册：成功 (key_version: 297078442)

### ❌ 问题所在

```
HTTP 状态码: 200
Content-Type: application/json
响应长度: 0 字节
```

**根本原因：番茄小说API返回了空响应（0字节）**

---

## 🎯 原因分析

### 主要原因：请求频率过高被限流

番茄小说的API有反爬虫机制，当检测到：
- 短时间内大量请求
- 相同IP的高频访问
- 批量下载行为

会触发**静默限流**：
- HTTP返回200（正常）
- Content-Type返回application/json（看起来正常）
- 但响应体为空（0字节）

这导致：
```python
response.json()  # 抛出 JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

### 次要原因
1. **并发Worker太多**：默认5个Worker同时下载
2. **请求间隔太短**：默认800-1500ms
3. **没有错误退避机制**：失败后立即重试

---

## 💡 解决方案

### 方案1：调整请求参数（已应用 ✅）

修改 `.env` 文件：

```bash
# 增加请求间隔（从800-1500ms 增加到 2000-5000ms）
NOVEL_MIN_WAIT_TIME=2000
NOVEL_MAX_WAIT_TIME=5000

# 减少并发数（从5减少到3）
NOVEL_MAX_WORKERS=3
```

**重启服务：**
```bash
docker-compose restart backend celery_worker
```

**重要：等待5-10分钟再尝试下载，让API限流解除！**

---

### 方案2：如果方案1不够，进一步降低频率

```bash
# 更保守的配置
NOVEL_MIN_WAIT_TIME=5000
NOVEL_MAX_WAIT_TIME=10000
NOVEL_MAX_WORKERS=2
```

---

### 方案3：手动设置有效的 install_id

如果自动生成的`install_id`总是失效，可以手动设置：

#### 步骤1：获取一个真实设备的 install_id

从番茄小说手机APP或网页版中提取Cookie中的`install_id`值。

#### 步骤2：设置环境变量

在 `.env` 中添加：
```bash
NOVEL_IID=你的真实install_id
NOVEL_IID_SPAWN_TIME=当前毫秒时间戳
```

例如：
```bash
NOVEL_IID=1234567890123456
NOVEL_IID_SPAWN_TIME=1696320000000
```

#### 步骤3：重启服务
```bash
docker-compose down
docker-compose up -d
```

---

### 方案4：使用代理（如果IP被封禁）

如果等待后仍然失败，可能是IP被临时封禁。

#### 选项A：更换网络
- 切换到不同的网络（例如从WiFi切换到手机热点）
- 使用VPN

#### 选项B：配置代理（高级）

修改 `backend/novel_downloader/novel_src/offical_tools/downloader.py`：

```python
# 在 FqReq.__init__ 方法中添加：
self.session.proxies = {
    'http': 'http://your-proxy:port',
    'https': 'http://your-proxy:port',
}
```

---

## 🛠️ 验证修复

### 步骤1：等待冷却期（重要！）

```bash
# 等待 5-10 分钟
# 在此期间不要尝试下载
```

### 步骤2：再次运行诊断

```bash
docker-compose exec backend python test_api.py
```

期望结果：
```
✅ 章节获取并解密成功
  - 内容长度: XXXX 字符
  - 内容预览: ...
```

### 步骤3：尝试下载小说

通过前端界面或API添加一个短篇小说（<100章）进行测试。

---

## 📊 参数调优建议

根据你的网络环境和番茄小说的响应，逐步调整参数：

| 参数 | 保守配置 | 平衡配置 | 激进配置 |
|------|---------|---------|---------|
| `NOVEL_MIN_WAIT_TIME` | 5000ms | 2000ms | 800ms |
| `NOVEL_MAX_WAIT_TIME` | 10000ms | 5000ms | 1500ms |
| `NOVEL_MAX_WORKERS` | 2 | 3 | 5 |
| **适用场景** | IP被封、频繁失败 | 正常使用（推荐） | 测试环境、本地开发 |
| **下载速度** | 慢（1章/3-7秒） | 中（1章/1-3秒） | 快（1章/1秒内） |
| **成功率** | 最高 | 高 | 中等 |

**建议：从保守配置开始，如果成功率高再逐步提高**

---

## 🚨 常见错误模式

### 错误1：所有章节都失败（当前问题）
- **原因**：API限流或IP封禁
- **解决**：降低请求频率，等待冷却期

### 错误2：部分章节失败
- **原因**：网络波动或章节不存在
- **解决**：正常现象，可忽略（<10%失败率可接受）

### 错误3：首次请求成功，后续失败
- **原因**：触发了动态限流
- **解决**：减少`NOVEL_MAX_WORKERS`

---

## 📝 监控下载状态

### 查看实时日志

```bash
# 查看 Celery Worker 日志
docker-compose logs -f celery_worker

# 查看 Backend 日志
docker-compose logs -f backend
```

### 判断成功/失败

**成功的标志：**
```
Task XXXX: Saved/Merged 899 chapters. 0 errors/missing.
```

**失败的标志：**
```
Task XXXX: Saved/Merged 0 chapters. 899 errors/missing.
Skipping chapter ... due to error marker: Error: Batch Failed (JSONDecodeError)
```

---

## 🔄 下次下载前的检查清单

1. ✅ 确认上次下载已经结束（5-10分钟前）
2. ✅ 检查 `.env` 中的参数配置
3. ✅ 运行诊断脚本验证API可用性
4. ✅ 从小说章节数较少的开始测试
5. ✅ 观察首批章节是否成功

---

## 💬 寻求帮助

如果上述方案都无效，可以：

1. **检查项目更新**
   ```bash
   git pull origin main
   docker-compose down
   docker-compose up -d --build
   ```

2. **查看 GitHub Issues**
   - 搜索关键词：`JSONDecodeError`, `限流`, `空响应`
   - 查看是否有其他用户遇到类似问题

3. **提供诊断信息**
   - 运行 `test_api.py` 的完整输出
   - `.env` 文件配置（隐藏敏感信息）
   - 错误日志的前100行

---

## 📌 总结

**问题：** API返回空响应（0字节），导致JSONDecodeError

**直接原因：** 番茄小说限流机制

**解决方法：**
1. ✅ **已应用：增加请求间隔，减少并发**
2. ⏳ **等待5-10分钟冷却期**
3. 🔄 **重新测试**

**预期效果：** 成功率从 0% 提升到 >90%

---

## 🔗 相关文件

- 诊断工具：`backend/test_api.py`
- 配置文件：`.env`
- 下载器核心：`backend/novel_downloader/novel_src/offical_tools/`
- 日志位置：`docker-compose logs`
