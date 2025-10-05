# API 功能增强总结

## 更新日期
2025-10-04

## 概述
本次更新为番茄小说下载服务 API 添加了强大的筛选、搜索和排序功能,大幅提升了API的易用性和灵活性。

---

## 1. 搜索接口增强 (`/api/search`)

### 新增返回字段
搜索接口现在返回更完整的小说信息:

| 字段 | 说明 | 示例 |
|------|------|------|
| `cover` | 封面图片URL | `https://p6-tt.bytecdn.cn/novel-pic/...` |
| `description` | 小说简介 | "穿越斗罗大陆..." |
| `category` | 分类标签 | "动漫衍生" |
| `score` | 评分 | "8.5" |

### 使用示例
```bash
GET /api/search?query=斗破

# 响应
{
  "results": [
    {
      "id": "7366526981938088984",
      "title": "斗破降临前,我成斗帝了",
      "author": "我真不是陈刀仔",
      "cover": "https://p6-tt.bytecdn.cn/novel-pic/...",
      "description": "【游戏氪金+升级不难产+爱国+初期斗破体系+推姨狂魔？】...",
      "category": "动漫衍生",
      "score": "8.5"
    }
  ]
}
```

---

## 2. 小说列表接口增强 (`/api/novels`)

### 新增功能

#### ✅ 标题搜索
- 支持模糊匹配,不区分大小写
- 参数: `search=关键词`

```bash
GET /api/novels?search=斗破
```

#### ✅ 标签筛选
- 支持多标签筛选,用逗号分隔
- 匹配包含任意一个标签的小说(OR逻辑)
- 参数: `tags=标签1,标签2`

```bash
GET /api/novels?tags=动漫衍生,玄幻
```

#### ✅ 状态筛选
- 按小说状态筛选
- 参数: `status=状态值`
- 常见状态: `连载中`, `已完结`

```bash
GET /api/novels?status=连载中
```

#### ✅ 多字段排序
支持按以下字段排序:
- `last_crawled_at` - 最后更新时间(默认)
- `created_at` - 创建时间
- `total_chapters` - 章节总数
- `title` - 标题

参数: `sort=字段名&order=排序方向`
- 排序方向: `asc`(升序) 或 `desc`(降序,默认)

```bash
# 按章节数降序
GET /api/novels?sort=total_chapters&order=desc

# 按标题升序
GET /api/novels?sort=title&order=asc
```

### 组合查询示例

```bash
# 搜索包含"斗"的小说,筛选"动漫衍生"标签,按章节数降序,每页20条
GET /api/novels?search=斗&tags=动漫衍生&sort=total_chapters&order=desc&per_page=20
```

### 响应格式更新

响应中新增 `filters` 字段,显示当前应用的筛选条件:

```json
{
  "novels": [...],
  "total": 50,
  "page": 1,
  "pages": 5,
  "per_page": 10,
  "filters": {
    "search": "斗破",
    "tags": "动漫衍生",
    "status": "连载中",
    "sort": "total_chapters",
    "order": "desc"
  }
}
```

小说对象新增 `description` 字段:

```json
{
  "id": "7189971807603002425",
  "title": "开局斗破当配角",
  "author": "心晨",
  "status": "连载中",
  "tags": "动漫衍生",
  "total_chapters": 927,
  "cover_image_url": "/api/novels/7189971807603002425/cover",
  "description": "穿越到了斗破的世界...",
  "last_crawled_at": "2025-10-04T12:13:23",
  "created_at": "2025-10-03T10:00:00"
}
```

---

## 3. 完整参数说明

### 小说列表接口参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `page` | int | 否 | 1 | 页码 |
| `per_page` | int | 否 | 10 | 每页数量(最大50) |
| `search` | string | 否 | - | 标题关键词搜索 |
| `tags` | string | 否 | - | 标签筛选(逗号分隔) |
| `status` | string | 否 | - | 状态筛选 |
| `sort` | string | 否 | last_crawled_at | 排序字段 |
| `order` | string | 否 | desc | 排序方向(asc/desc) |

---

## 4. 使用场景示例

### 场景 1: 查找最近更新的连载小说
```bash
GET /api/novels?status=连载中&sort=last_crawled_at&order=desc&per_page=20
```

### 场景 2: 查找章节数最多的玄幻小说
```bash
GET /api/novels?tags=玄幻&sort=total_chapters&order=desc
```

### 场景 3: 搜索特定关键词并按相关度排序
```bash
GET /api/novels?search=修仙&sort=total_chapters&order=desc
```

### 场景 4: 查看最新添加的小说
```bash
GET /api/novels?sort=created_at&order=desc
```

### 场景 5: 按字母顺序浏览
```bash
GET /api/novels?sort=title&order=asc
```

---

## 5. 技术实现细节

### 数据库查询优化
- 使用SQLAlchemy的动态查询构建
- ILIKE操作符实现不区分大小写的模糊搜索
- OR逻辑实现多标签筛选
- NULL值处理确保日期排序的正确性

### 性能优化
- 分页限制最大50条记录
- 索引优化(已有的novel表索引)
- 惰性加载关联数据

### 兼容性
- 向后兼容:所有新参数都是可选的
- 默认行为不变:不传参数时保持原有排序逻辑

---

## 6. 前端集成建议

### JavaScript/React 示例
```javascript
const fetchNovels = async (filters) => {
  const params = new URLSearchParams({
    page: filters.page || 1,
    per_page: filters.perPage || 20,
    ...(filters.search && { search: filters.search }),
    ...(filters.tags && { tags: filters.tags.join(',') }),
    ...(filters.status && { status: filters.status }),
    sort: filters.sort || 'last_crawled_at',
    order: filters.order || 'desc'
  });
  
  const response = await fetch(`/api/novels?${params}`);
  return await response.json();
};

// 使用示例
const data = await fetchNovels({
  search: '斗破',
  tags: ['动漫衍生', '玄幻'],
  sort: 'total_chapters',
  order: 'desc',
  page: 1,
  perPage: 20
});
```

### Vue 3 Composition API 示例
```javascript
import { ref, watch } from 'vue';

const filters = ref({
  search: '',
  tags: [],
  status: '',
  sort: 'last_crawled_at',
  order: 'desc',
  page: 1,
  perPage: 20
});

const novels = ref([]);
const pagination = ref({});

watch(filters, async (newFilters) => {
  const params = new URLSearchParams();
  
  Object.entries(newFilters).forEach(([key, value]) => {
    if (value) {
      if (key === 'tags' && Array.isArray(value)) {
        params.append(key, value.join(','));
      } else {
        params.append(key, value);
      }
    }
  });
  
  const response = await fetch(`/api/novels?${params}`);
  const data = await response.json();
  
  novels.value = data.novels;
  pagination.value = {
    total: data.total,
    page: data.page,
    pages: data.pages,
    perPage: data.per_page
  };
}, { deep: true });
```

---

## 7. 测试验证

### 快速测试命令

```powershell
# 1. 搜索接口测试
Invoke-RestMethod "http://localhost:5000/api/search?query=斗破" | ConvertTo-Json -Depth 3

# 2. 标题搜索测试
Invoke-RestMethod "http://localhost:5000/api/novels?search=斗罗" | ConvertTo-Json -Depth 3

# 3. 标签筛选测试
Invoke-RestMethod "http://localhost:5000/api/novels?tags=动漫衍生" | ConvertTo-Json -Depth 3

# 4. 状态筛选测试
Invoke-RestMethod "http://localhost:5000/api/novels?status=连载中" | ConvertTo-Json -Depth 3

# 5. 排序测试
Invoke-RestMethod "http://localhost:5000/api/novels?sort=total_chapters&order=desc" | ConvertTo-Json -Depth 3

# 6. 组合查询测试
Invoke-RestMethod "http://localhost:5000/api/novels?search=斗&tags=动漫衍生&sort=total_chapters&order=desc" | ConvertTo-Json -Depth 3
```

---

## 8. 相关文档

- **完整API文档**: `API_DOCUMENTATION.md`
- **详细使用示例**: `API_NOVELS_LIST_EXAMPLES.md`
- **内部API快速入门**: `INTERNAL_API_QUICK_START.md`

---

## 9. 更新日志

### 2025-10-04
- ✅ 搜索接口增加封面、简介、分类、评分字段
- ✅ 小说列表接口增加标题搜索功能
- ✅ 小说列表接口增加标签筛选功能(支持多标签OR逻辑)
- ✅ 小说列表接口增加状态筛选功能
- ✅ 小说列表接口增加多字段排序功能(4个排序字段)
- ✅ 小说列表接口增加排序方向控制(升序/降序)
- ✅ 小说列表响应增加 `description` 字段
- ✅ 小说列表响应增加 `filters` 字段显示当前筛选条件
- ✅ 更新API文档
- ✅ 创建详细使用示例文档

---

## 10. 后续优化建议

### 短期优化
- [ ] 添加全文搜索支持(搜索简介内容)
- [ ] 添加作者筛选功能
- [ ] 添加评分范围筛选
- [ ] 添加章节数范围筛选

### 中期优化
- [ ] 添加搜索结果高亮
- [ ] 添加搜索历史记录
- [ ] 添加热门搜索推荐
- [ ] 实现搜索自动补全

### 长期优化
- [ ] 使用Elasticsearch实现全文搜索
- [ ] 添加个性化推荐算法
- [ ] 实现搜索结果缓存
- [ ] 添加搜索分析和统计

---

## 联系方式

如有问题或建议,请查看项目文档或提交Issue。
