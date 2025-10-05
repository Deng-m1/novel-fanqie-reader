# 测试代理API是否可用

$proxy_base = "https://fanqie.hnxianxin.cn"

# 测试章节ID（从之前的日志中获取）
$item_id = "7549037381060395582"

Write-Host "Testing Proxy API..." -ForegroundColor Cyan
Write-Host "Proxy: $proxy_base" -ForegroundColor Yellow
Write-Host "Item ID: $item_id" -ForegroundColor Yellow

$url = "$proxy_base/content?item_id=$item_id"

try {
    $response = Invoke-WebRequest -Uri $url -TimeoutSec 10 -UseBasicParsing
    
    Write-Host "`n✓ Response Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "✓ Content Length: $($response.Content.Length) bytes" -ForegroundColor Green
    
    $data = $response.Content | ConvertFrom-Json
    
    if ($data.code -eq 0 -and $data.data) {
        $title = $data.data.title
        $content_length = $data.data.content.Length
        
        Write-Host "`n========== SUCCESS! ==========" -ForegroundColor Green
        Write-Host "Chapter Title: $title" -ForegroundColor White
        Write-Host "Content Length: $content_length characters" -ForegroundColor White
        Write-Host "Content Preview:" -ForegroundColor White
        Write-Host $data.data.content.Substring(0, [Math]::Min(200, $content_length)) -ForegroundColor Gray
        Write-Host "...`n" -ForegroundColor Gray
        Write-Host "代理API可用！✓" -ForegroundColor Green
    } else {
        Write-Host "`n✗ API Error: $($data.message)" -ForegroundColor Red
    }
    
} catch {
    Write-Host "`n✗ Request Failed:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}
