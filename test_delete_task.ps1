# Test script to check if delete task API works

# 1. First, login to get token
$loginBody = @{
    username = "test_user"
    password = "test_password"
} | ConvertTo-Json

Write-Host "Step 1: Logging in..." -ForegroundColor Cyan
$loginResponse = Invoke-WebRequest -Uri "http://localhost:5000/api/auth/login" -Method POST -Body $loginBody -ContentType "application/json" -UseBasicParsing

if ($loginResponse.StatusCode -eq 200) {
    $loginData = $loginResponse.Content | ConvertFrom-Json
    $token = $loginData.access_token
    Write-Host "✓ Login successful. Token: $($token.Substring(0, 20))..." -ForegroundColor Green
} else {
    Write-Host "✗ Login failed" -ForegroundColor Red
    exit 1
}

# 2. Get task list
Write-Host "`nStep 2: Fetching task list..." -ForegroundColor Cyan
$headers = @{
    "Authorization" = "Bearer $token"
}

$tasksResponse = Invoke-WebRequest -Uri "http://localhost:5000/api/tasks/list" -Method GET -Headers $headers -UseBasicParsing
$tasks = ($tasksResponse.Content | ConvertFrom-Json).tasks

Write-Host "✓ Found $($tasks.Count) tasks" -ForegroundColor Green

if ($tasks.Count -gt 0) {
    Write-Host "`nTasks:" -ForegroundColor Yellow
    foreach ($task in $tasks) {
        Write-Host "  - ID: $($task.id), Novel: $($task.novel.title), Status: $($task.status)" -ForegroundColor White
    }
    
    # 3. Try to delete the first task
    $taskToDelete = $tasks[0].id
    Write-Host "`nStep 3: Attempting to delete task ID: $taskToDelete" -ForegroundColor Cyan
    
    try {
        $deleteResponse = Invoke-WebRequest -Uri "http://localhost:5000/api/tasks/$taskToDelete" -Method DELETE -Headers $headers -UseBasicParsing
        
        if ($deleteResponse.StatusCode -eq 200) {
            Write-Host "✓ Delete successful!" -ForegroundColor Green
            Write-Host "Response: $($deleteResponse.Content)" -ForegroundColor Gray
        } else {
            Write-Host "✗ Delete failed with status: $($deleteResponse.StatusCode)" -ForegroundColor Red
        }
    } catch {
        Write-Host "✗ Delete request failed:" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $responseBody = $reader.ReadToEnd()
            Write-Host "Response body: $responseBody" -ForegroundColor Gray
        }
    }
    
    # 4. Verify deletion
    Write-Host "`nStep 4: Verifying deletion..." -ForegroundColor Cyan
    $tasksResponse2 = Invoke-WebRequest -Uri "http://localhost:5000/api/tasks/list" -Method GET -Headers $headers -UseBasicParsing
    $tasks2 = ($tasksResponse2.Content | ConvertFrom-Json).tasks
    Write-Host "✓ Now have $($tasks2.Count) tasks (was $($tasks.Count))" -ForegroundColor Green
    
    $deletedTask = $tasks2 | Where-Object { $_.id -eq $taskToDelete }
    if ($null -eq $deletedTask) {
        Write-Host "✓ Task $taskToDelete was successfully deleted!" -ForegroundColor Green
    } else {
        Write-Host "✗ Task $taskToDelete still exists!" -ForegroundColor Red
    }
} else {
    Write-Host "No tasks to delete" -ForegroundColor Yellow
}
