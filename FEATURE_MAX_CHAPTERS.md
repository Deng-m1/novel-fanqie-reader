# 章节限制下载功能（预览模式）

## 功能概述

本次更新为 fanqie-reader 项目添加了**章节限制下载功能**，允许用户在添加小说时选择只下载前 N 章（默认前 10 章）用于预览，从而节省下载时间和存储空间。

## 功能特性

- ✅ **预览模式**：用户可选择只下载前 10 章进行预览
- ✅ **灵活配置**：`max_chapters` 参数可以设置为任意正整数
- ✅ **向后兼容**：不传 `max_chapters` 参数时保持原有的完整下载行为
- ✅ **友好提示**：前端界面清晰标识预览模式状态

## 技术实现

### 1. 后端修改

#### 1.1 API 接口 (`backend/app.py`)

**路径**: `/api/novels` (POST)

**新增参数**:
```python
max_chapters: int (可选)
```

**修改内容**:
- 添加 `max_chapters` 参数解析和验证（必须为正整数）
- 将参数传递给 Celery 任务
- 在日志中记录预览模式信息

**代码位置**: `backend/app.py` 第 286-297 行，第 353-366 行

#### 1.2 Celery 任务 (`backend/tasks.py`)

**任务名称**: `tasks.process_novel`

**修改内容**:
- 添加 `max_chapters` 参数到任务签名
- 在获取章节列表后，根据 `max_chapters` 裁剪列表
- 记录限制章节数量的日志信息

**代码位置**: `backend/tasks.py` 第 103-115 行，第 307-316 行

**实现逻辑**:
```python
if max_chapters is not None and max_chapters > 0:
    original_count = total_chapters_src
    chapters_list = chapters_list[:max_chapters]
    total_chapters_src = len(chapters_list)
```

### 2. 前端修改

#### 2.1 类型定义 (`frontend/src/api.ts`)

**修改内容**:
```typescript
export interface AddNovelRequest {
  novel_id: string
  max_chapters?: number  // 新增可选参数
}
```

**代码位置**: `frontend/src/api.ts` 第 60-63 行

#### 2.2 状态管理 (`frontend/src/store/index.ts`)

**修改内容**:
- 更新 `addNovel` 方法签名，添加 `maxChapters` 可选参数
- 构建请求时根据参数动态添加 `max_chapters` 字段

**代码位置**: `frontend/src/store/index.ts` 第 223-243 行

**实现逻辑**:
```typescript
async addNovel(novelId: string, maxChapters?: number): Promise<{ task_id: string } | null> {
  const requestData: { novel_id: string; max_chapters?: number } = { novel_id: novelId }
  if (maxChapters !== undefined) {
    requestData.max_chapters = maxChapters
  }
  // ...
}
```

#### 2.3 用户界面 (`frontend/src/views/SearchView.vue`)

**新增 UI 元素**:
在搜索结果表格的操作列中，为每个小说显示两个独立的按钮：
1. **下载全本按钮** (蓝色主按钮): 下载小说的所有章节
2. **前十章预览按钮** (绿色成功按钮): 仅下载前 10 章

**UI 组件**:
```vue
<div class="action-buttons">
  <el-button
    type="primary"
    size="small"
    @click="addNovel(row.id, false)"
  >
    下载全本
  </el-button>
  <el-button
    type="success"
    size="small"
    @click="addNovel(row.id, true)"
  >
    前十章预览
  </el-button>
</div>
```

**代码位置**: `frontend/src/views/SearchView.vue` 第 59-82 行，第 128-150 行

**样式优化**:
- 使用 Flexbox 布局，按钮水平排列
- 按钮之间 8px 间距
- 每个按钮最小宽度 90px
- 点击后显示 loading 状态，其他按钮禁用

**代码位置**: `frontend/src/views/SearchView.vue` 第 188-197 行

## 使用方式

### 用户操作流程

1. 打开 **搜索小说** 页面
2. 输入小说名称或作者进行搜索
3. 在搜索结果中，每个小说显示两个按钮：
   - **下载全本**: 下载小说的所有章节
   - **前十章预览**: 仅下载前 10 章用于预览
4. 根据需求点击相应的按钮
5. 系统将按照选择的模式开始下载

### API 调用示例

#### 完整下载（默认行为）
```bash
POST /api/novels
Content-Type: application/json
Authorization: Bearer <token>

{
  "novel_id": "123456"
}
```

#### 预览模式（限制章节数）
```bash
POST /api/novels
Content-Type: application/json
Authorization: Bearer <token>

{
  "novel_id": "123456",
  "max_chapters": 10
}
```

#### 自定义章节数
```bash
POST /api/novels
Content-Type: application/json
Authorization: Bearer <token>

{
  "novel_id": "123456",
  "max_chapters": 5
}
```

## 验证测试

### 后端测试

已验证后端代码编译无误：
```bash
✓ python -m py_compile backend/app.py
✓ python -m py_compile backend/tasks.py
```

### 建议测试场景

1. **默认行为测试**: 不传 `max_chapters`，验证完整下载
2. **预览模式测试**: 传 `max_chapters=10`，验证只下载前 10 章
3. **边界测试**: 
   - 传 `max_chapters=0`，验证参数验证逻辑
   - 传 `max_chapters=-1`，验证错误处理
   - 传 `max_chapters="abc"`，验证类型验证
4. **章节数超出测试**: 对只有 5 章的小说设置 `max_chapters=10`，验证不会出错

## 日志示例

### 后端日志

**接收请求时**:
```
User 1 requested add/crawl for novel ID: 123456 (max_chapters: 10)
```

**Celery 任务启动时**:
```
Celery Task abc-123: Starting processing for Novel ID: 123456, User ID: 1, DB Task ID: 5 (max_chapters: 10)
```

**限制章节时**:
```
Task abc-123: Limited to 10 chapters (from 150) for preview mode.
```

### 前端提示

**成功消息**:
- 预览模式: `小说添加成功，开始下载前10章（预览模式）`
- 完整模式: `小说添加成功，开始下载全本`

## 兼容性说明

- ✅ **向后兼容**: 已有的 API 调用无需修改，默认行为不变
- ✅ **数据库兼容**: 不涉及数据库结构修改
- ✅ **前端兼容**: 点击"下载全本"按钮时行为与原版一致

## 未来扩展

可能的功能增强方向：

1. **章节范围选择**: 支持指定起始和结束章节（如第 20-30 章）
2. **增量下载**: 在预览后继续下载剩余章节
3. **快速预览**: 为预览模式提供更高的下载优先级
4. **预设模板**: 提供"前 10 章"、"前 50 章"等快捷选项

## 修改文件清单

### 后端
- `backend/app.py` - API 接口参数处理
- `backend/tasks.py` - Celery 任务章节限制逻辑

### 前端
- `frontend/src/api.ts` - API 类型定义
- `frontend/src/store/index.ts` - 状态管理方法
- `frontend/src/views/SearchView.vue` - 用户界面和交互

## 总结

本次更新成功为 fanqie-reader 添加了章节限制下载功能，用户可以通过简单的复选框操作选择预览模式，只下载小说的前几章进行试读。该功能实现了前后端的完整联动，提供了良好的用户体验，同时保持了对现有功能的完全兼容。
