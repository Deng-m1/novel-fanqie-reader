# 小说列表 API 使用示例

## 接口地址
```
GET /api/novels
```

## 功能特性

✅ **标题搜索** - 根据标题关键词模糊搜索  
✅ **标签筛选** - 根据一个或多个标签筛选  
✅ **状态筛选** - 根据小说状态筛选(连载中/已完结等)  
✅ **多字段排序** - 按更新时间、创建时间、章节数、标题排序  
✅ **排序方向** - 支持升序/降序  
✅ **分页** - 完整的分页支持  

---

## 查询参数

| 参数 | 类型 | 说明 | 默认值 | 示例 |
|------|------|------|--------|------|
| `page` | int | 页码 | 1 | `page=2` |
| `per_page` | int | 每页数量 (最大50) | 10 | `per_page=20` |
| `search` | string | 标题关键词搜索 | - | `search=斗破` |
| `tags` | string | 标签筛选(逗号分隔) | - | `tags=玄幻,都市` |
| `status` | string | 状态筛选 | - | `status=连载中` |
| `sort` | string | 排序字段 | last_crawled_at | `sort=total_chapters` |
| `order` | string | 排序方向 (asc/desc) | desc | `order=asc` |

### 排序字段选项
- `last_crawled_at` - 最后更新时间 (默认)
- `created_at` - 创建时间
- `total_chapters` - 章节总数
- `title` - 标题

---

## 使用示例

### 1. 基础查询 - 获取所有小说
```bash
GET /api/novels
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/novels" | ConvertTo-Json -Depth 5
```

### 2. 标题搜索 - 搜索包含"斗破"的小说
```bash
GET /api/novels?search=斗破
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/novels?search=斗破" | ConvertTo-Json -Depth 5
```

### 3. 标签筛选 - 筛选"动漫衍生"标签
```bash
GET /api/novels?tags=动漫衍生
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/novels?tags=动漫衍生" | ConvertTo-Json -Depth 5
```

### 4. 多标签筛选 - 筛选"玄幻"或"都市"
```bash
GET /api/novels?tags=玄幻,都市
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/novels?tags=玄幻,都市" | ConvertTo-Json -Depth 5
```

### 5. 状态筛选 - 只显示连载中的小说
```bash
GET /api/novels?status=连载中
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/novels?status=连载中" | ConvertTo-Json -Depth 5
```

### 6. 按章节数排序 - 降序
```bash
GET /api/novels?sort=total_chapters&order=desc
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/novels?sort=total_chapters&order=desc" | ConvertTo-Json -Depth 5
```

### 7. 按标题排序 - 升序
```bash
GET /api/novels?sort=title&order=asc
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/novels?sort=title&order=asc" | ConvertTo-Json -Depth 5
```

### 8. 按创建时间排序 - 最新的在前
```bash
GET /api/novels?sort=created_at&order=desc
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/novels?sort=created_at&order=desc" | ConvertTo-Json -Depth 5
```

### 9. 组合查询 - 搜索+标签+排序
```bash
GET /api/novels?search=斗破&tags=动漫衍生&sort=total_chapters&order=desc
```

**PowerShell:**
```powershell
$uri = "http://localhost:5000/api/novels?search=斗破&tags=动漫衍生&sort=total_chapters&order=desc"
Invoke-RestMethod -Uri $uri | ConvertTo-Json -Depth 5
```

### 10. 完整查询 - 所有参数
```bash
GET /api/novels?page=1&per_page=20&search=修仙&tags=玄幻&status=连载中&sort=last_crawled_at&order=desc
```

**PowerShell:**
```powershell
$params = @{
    page = 1
    per_page = 20
    search = "修仙"
    tags = "玄幻"
    status = "连载中"
    sort = "last_crawled_at"
    order = "desc"
}
$queryString = ($params.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "&"
$uri = "http://localhost:5000/api/novels?$queryString"
Invoke-RestMethod -Uri $uri | ConvertTo-Json -Depth 5
```

---

## 响应格式

```json
{
  "novels": [
    {
      "id": "7189971807603002425",
      "title": "开局斗破当配角",
      "author": "心晨",
      "status": "连载中",
      "tags": "动漫衍生",
      "total_chapters": 100,
      "last_crawled_at": "2025-10-04T12:13:23.123456",
      "created_at": "2025-10-03T10:00:00.000000",
      "cover_image_url": "https://p6-tt.bytecdn.cn/novel-pic/...",
      "description": "穿越到了斗破的世界，给我绑定了最强配角系统..."
    }
  ],
  "total": 50,
  "page": 1,
  "pages": 5,
  "per_page": 10,
  "filters": {
    "search": "斗破",
    "tags": "动漫衍生",
    "status": "",
    "sort": "last_crawled_at",
    "order": "desc"
  }
}
```

### 响应字段说明

| 字段 | 说明 |
|------|------|
| `novels` | 小说列表数组 |
| `total` | 符合条件的小说总数 |
| `page` | 当前页码 |
| `pages` | 总页数 |
| `per_page` | 每页数量 |
| `filters` | 当前应用的筛选条件 |

### 小说对象字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 小说 ID |
| `title` | string | 小说标题 |
| `author` | string | 作者 |
| `status` | string | 状态 (连载中/已完结等) |
| `tags` | string | 标签 |
| `total_chapters` | int | 总章节数 |
| `last_crawled_at` | string | 最后更新时间 (ISO 8601) |
| `created_at` | string | 创建时间 (ISO 8601) |
| `cover_image_url` | string | 封面图片 URL |
| `description` | string | 小说简介 |

---

## 注意事项

1. **标签匹配**: 使用逗号分隔多个标签时,匹配的是**包含任意一个**标签的小说(OR 逻辑)
2. **搜索不区分大小写**: 标题搜索使用 `ILIKE` 进行模糊匹配
3. **NULL 值处理**: 在按日期排序时,NULL 值会被排在最后
4. **分页限制**: 每页最多返回 50 条记录
5. **默认排序**: 如果不指定排序,默认按最后更新时间降序排列

---

## 前端集成示例

### JavaScript/Fetch API
```javascript
// 基础查询
fetch('/api/novels?page=1&per_page=20')
  .then(res => res.json())
  .then(data => console.log(data.novels));

// 带筛选的查询
const params = new URLSearchParams({
  search: '斗破',
  tags: '动漫衍生',
  sort: 'total_chapters',
  order: 'desc'
});

fetch(`/api/novels?${params}`)
  .then(res => res.json())
  .then(data => {
    console.log('总数:', data.total);
    console.log('小说列表:', data.novels);
  });
```

### Vue.js 示例
```javascript
export default {
  data() {
    return {
      novels: [],
      filters: {
        search: '',
        tags: '',
        status: '',
        sort: 'last_crawled_at',
        order: 'desc'
      },
      pagination: {
        page: 1,
        per_page: 20,
        total: 0,
        pages: 0
      }
    }
  },
  methods: {
    async fetchNovels() {
      const params = new URLSearchParams({
        page: this.pagination.page,
        per_page: this.pagination.per_page,
        ...this.filters
      });
      
      const response = await fetch(`/api/novels?${params}`);
      const data = await response.json();
      
      this.novels = data.novels;
      this.pagination.total = data.total;
      this.pagination.pages = data.pages;
    }
  }
}
```

---

## 测试命令

### 快速测试所有功能
```powershell
# 1. 基础列表
Write-Host "=== 1. 基础列表 ===" -ForegroundColor Green
Invoke-RestMethod "http://localhost:5000/api/novels" | Select-Object -ExpandProperty novels | Format-Table id, title, author

# 2. 标题搜索
Write-Host "`n=== 2. 搜索'斗破' ===" -ForegroundColor Green
Invoke-RestMethod "http://localhost:5000/api/novels?search=斗破" | Select-Object -ExpandProperty novels | Format-Table id, title

# 3. 标签筛选
Write-Host "`n=== 3. 筛选'动漫衍生' ===" -ForegroundColor Green
Invoke-RestMethod "http://localhost:5000/api/novels?tags=动漫衍生" | Select-Object -ExpandProperty novels | Format-Table id, title, tags

# 4. 章节数排序
Write-Host "`n=== 4. 按章节数排序 ===" -ForegroundColor Green
Invoke-RestMethod "http://localhost:5000/api/novels?sort=total_chapters&order=desc" | Select-Object -ExpandProperty novels | Format-Table title, total_chapters

# 5. 组合查询
Write-Host "`n=== 5. 组合查询 ===" -ForegroundColor Green
Invoke-RestMethod "http://localhost:5000/api/novels?search=斗破&sort=total_chapters&order=desc" | ConvertTo-Json -Depth 3
```
