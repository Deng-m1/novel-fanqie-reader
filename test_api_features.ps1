# 番茄小说 API 新功能测试脚本
# 测试筛选、搜索和排序功能

$baseUrl = "http://localhost:5000"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "番茄小说 API 新功能测试" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 测试 1: 搜索接口 - 返回封面和简介
Write-Host "【测试 1】搜索接口 - 检查返回字段" -ForegroundColor Green
Write-Host "查询: 斗破" -ForegroundColor Yellow
$searchResult = Invoke-RestMethod -Uri "$baseUrl/api/search?query=斗破"
if ($searchResult.results.Count -gt 0) {
    $first = $searchResult.results[0]
    Write-Host "✓ 找到 $($searchResult.results.Count) 个结果" -ForegroundColor Green
    Write-Host "  标题: $($first.title)" -ForegroundColor White
    Write-Host "  作者: $($first.author)" -ForegroundColor White
    Write-Host "  封面: $($first.cover)" -ForegroundColor White
    Write-Host "  分类: $($first.category)" -ForegroundColor White
    Write-Host "  评分: $($first.score)" -ForegroundColor White
    Write-Host "  简介: $($first.description.Substring(0, [Math]::Min(50, $first.description.Length)))..." -ForegroundColor White
} else {
    Write-Host "✗ 未找到结果" -ForegroundColor Red
}
Write-Host ""

# 测试 2: 小说列表 - 基础查询
Write-Host "【测试 2】小说列表 - 基础查询" -ForegroundColor Green
$novels = Invoke-RestMethod -Uri "$baseUrl/api/novels?per_page=3"
Write-Host "✓ 总数: $($novels.total), 当前页: $($novels.page)/$($novels.pages)" -ForegroundColor Green
$novels.novels | ForEach-Object {
    Write-Host "  - $($_.title) ($($_.total_chapters) 章)" -ForegroundColor White
}
Write-Host ""

# 测试 3: 标题搜索
Write-Host "【测试 3】标题搜索功能" -ForegroundColor Green
Write-Host "查询: 斗罗" -ForegroundColor Yellow
$searchNovels = Invoke-RestMethod -Uri "$baseUrl/api/novels?search=斗罗&per_page=5"
Write-Host "✓ 找到 $($searchNovels.total) 部小说" -ForegroundColor Green
$searchNovels.novels | ForEach-Object {
    Write-Host "  - $($_.title)" -ForegroundColor White
}
Write-Host ""

# 测试 4: 标签筛选
Write-Host "【测试 4】标签筛选功能" -ForegroundColor Green
Write-Host "筛选: 动漫衍生" -ForegroundColor Yellow
$tagNovels = Invoke-RestMethod -Uri "$baseUrl/api/novels?tags=动漫衍生&per_page=5"
Write-Host "✓ 找到 $($tagNovels.total) 部小说" -ForegroundColor Green
$tagNovels.novels | ForEach-Object {
    Write-Host "  - $($_.title) [标签: $($_.tags)]" -ForegroundColor White
}
Write-Host ""

# 测试 5: 状态筛选
Write-Host "【测试 5】状态筛选功能" -ForegroundColor Green
Write-Host "筛选: 连载中" -ForegroundColor Yellow
$statusNovels = Invoke-RestMethod -Uri "$baseUrl/api/novels?status=连载中&per_page=3"
Write-Host "✓ 找到 $($statusNovels.total) 部连载中的小说" -ForegroundColor Green
$statusNovels.novels | ForEach-Object {
    Write-Host "  - $($_.title) [状态: $($_.status)]" -ForegroundColor White
}
Write-Host ""

# 测试 6: 按章节数排序（降序）
Write-Host "【测试 6】按章节数排序（降序）" -ForegroundColor Green
$sortedNovels = Invoke-RestMethod -Uri "$baseUrl/api/novels?sort=total_chapters&order=desc&per_page=5"
Write-Host "✓ 章节数最多的 5 部小说:" -ForegroundColor Green
$sortedNovels.novels | ForEach-Object {
    Write-Host "  - $($_.title): $($_.total_chapters) 章" -ForegroundColor White
}
Write-Host ""

# 测试 7: 按章节数排序（升序）
Write-Host "【测试 7】按章节数排序（升序）" -ForegroundColor Green
$sortedNovelsAsc = Invoke-RestMethod -Uri "$baseUrl/api/novels?sort=total_chapters&order=asc&per_page=5"
Write-Host "✓ 章节数最少的 5 部小说:" -ForegroundColor Green
$sortedNovelsAsc.novels | ForEach-Object {
    Write-Host "  - $($_.title): $($_.total_chapters) 章" -ForegroundColor White
}
Write-Host ""

# 测试 8: 按标题排序
Write-Host "【测试 8】按标题排序（升序）" -ForegroundColor Green
$titleSorted = Invoke-RestMethod -Uri "$baseUrl/api/novels?sort=title&order=asc&per_page=5"
Write-Host "✓ 标题排序:" -ForegroundColor Green
$titleSorted.novels | ForEach-Object {
    Write-Host "  - $($_.title)" -ForegroundColor White
}
Write-Host ""

# 测试 9: 按更新时间排序
Write-Host "【测试 9】按最后更新时间排序（降序）" -ForegroundColor Green
$timeSorted = Invoke-RestMethod -Uri "$baseUrl/api/novels?sort=last_crawled_at&order=desc&per_page=5"
Write-Host "✓ 最近更新的小说:" -ForegroundColor Green
$timeSorted.novels | ForEach-Object {
    $updateTime = if ($_.last_crawled_at) { $_.last_crawled_at.Substring(0, 19) } else { "未更新" }
    Write-Host "  - $($_.title) [$updateTime]" -ForegroundColor White
}
Write-Host ""

# 测试 10: 组合查询
Write-Host "【测试 10】组合查询" -ForegroundColor Green
Write-Host "条件: 搜索'斗', 标签'动漫衍生', 按章节数降序" -ForegroundColor Yellow
$combined = Invoke-RestMethod -Uri "$baseUrl/api/novels?search=斗&tags=动漫衍生&sort=total_chapters&order=desc&per_page=5"
Write-Host "✓ 找到 $($combined.total) 部小说" -ForegroundColor Green
Write-Host "✓ 应用的筛选条件:" -ForegroundColor Cyan
Write-Host "  - 搜索: $($combined.filters.search)" -ForegroundColor White
Write-Host "  - 标签: $($combined.filters.tags)" -ForegroundColor White
Write-Host "  - 排序: $($combined.filters.sort) ($($combined.filters.order))" -ForegroundColor White
Write-Host "✓ 结果:" -ForegroundColor Cyan
$combined.novels | ForEach-Object {
    Write-Host "  - $($_.title) [$($_.total_chapters) 章]" -ForegroundColor White
}
Write-Host ""

# 测试 11: 分页功能
Write-Host "【测试 11】分页功能" -ForegroundColor Green
$page1 = Invoke-RestMethod -Uri "$baseUrl/api/novels?per_page=3&page=1"
$page2 = Invoke-RestMethod -Uri "$baseUrl/api/novels?per_page=3&page=2"
Write-Host "✓ 第 1 页 (共 $($page1.pages) 页):" -ForegroundColor Green
$page1.novels | ForEach-Object {
    Write-Host "  - $($_.title)" -ForegroundColor White
}
Write-Host "✓ 第 2 页 (共 $($page2.pages) 页):" -ForegroundColor Green
$page2.novels | ForEach-Object {
    Write-Host "  - $($_.title)" -ForegroundColor White
}
Write-Host ""

# 测试 12: 响应中包含 description 字段
Write-Host "【测试 12】小说列表包含简介字段" -ForegroundColor Green
$novelsWithDesc = Invoke-RestMethod -Uri "$baseUrl/api/novels?per_page=2"
$novelsWithDesc.novels | ForEach-Object {
    Write-Host "✓ $($_.title)" -ForegroundColor Cyan
    if ($_.description) {
        $desc = $_.description.Substring(0, [Math]::Min(60, $_.description.Length))
        Write-Host "  简介: $desc..." -ForegroundColor White
    } else {
        Write-Host "  简介: [无]" -ForegroundColor Gray
    }
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "测试完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
