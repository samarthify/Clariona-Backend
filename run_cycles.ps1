# PowerShell script to run Clariti cycles continuously
# Usage: .\run_cycles.ps1 -UserId "your-user-id" -IntervalMinutes 30

param(
    [string]$UserId = "6440da7fe6304b2f884ea8721cc9a9c0",
    [int]$IntervalMinutes = 30,
    [string]$BackendUrl = "http://localhost:8000",
    [string]$LogFile = "logs\automatic_scheduling.log"
)

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Smart Sequential Cycle Runner" -ForegroundColor Cyan
Write-Host "User: $UserId" -ForegroundColor Yellow
Write-Host "Interval: $IntervalMinutes min (after completion)" -ForegroundColor Yellow
Write-Host "Backend URL: $BackendUrl" -ForegroundColor Yellow
Write-Host "Log File: $LogFile" -ForegroundColor Yellow
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Ensure log directory exists
$logDir = Split-Path -Path $LogFile -Parent
if ($logDir -and -not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# Function to wait for cycle completion
function Wait-ForCycleCompletion {
    param([DateTime]$CycleStartTime)
    
    $maxWaitHours = 6
    $maxWaitSeconds = $maxWaitHours * 3600
    $iteration = 0
    
    Write-Host "  ⏳ Waiting for cycle to complete (max ${maxWaitHours}h)..." -ForegroundColor Yellow
    
    while ($true) {
        Start-Sleep -Seconds 30
        $iteration++
        $elapsed = (Get-Date) - $CycleStartTime
        
        # Check for timeout
        if ($elapsed.TotalSeconds -gt $maxWaitSeconds) {
            Write-Host "  ⚠️  Cycle exceeded maximum wait time (${maxWaitHours}h), assuming stuck. Moving on..." -ForegroundColor Red
            break
        }
        
        # Check for cycle completion in log file
        if (Test-Path $LogFile) {
            $userIdWithDashes = $UserId -replace '(.{8})(.{4})(.{4})(.{4})(.{12})', '$1-$2-$3-$4-$5'
            $lastLog = Get-Content $LogFile -Tail 100 | 
                Select-String -Pattern "\[CYCLE (END|SUMMARY)\]" | 
                Select-String -Pattern "$UserId|$userIdWithDashes" | 
                Select-Object -Last 1
            
            if ($lastLog) {
                # Extract timestamp from log line
                if ($lastLog -match '(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})') {
                    $logTime = [DateTime]::ParseExact($matches[1], "yyyy-MM-dd HH:mm:ss", $null)
                    if ($logTime -gt $CycleStartTime) {
                        Write-Host "  ✅ Cycle completed at $logTime" -ForegroundColor Green
                        break
                    }
                }
            }
        }
        
        # Log progress every 10 minutes
        if ($iteration % 20 -eq 0) {
            $minutes = [math]::Floor($elapsed.TotalMinutes)
            Write-Host "  ⏳ Still waiting... ($([math]::Floor($elapsed.TotalSeconds))s elapsed, ~$minutes minutes)" -ForegroundColor Yellow
        }
    }
}

# Main loop
while ($true) {
    $cycleStart = Get-Date
    $cycleStartTime = $cycleStart.ToString("yyyy-MM-dd HH:mm:ss")
    
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "[$cycleStartTime] Starting new cycle..." -ForegroundColor Cyan
    
    # Check if backend is accessible
    try {
        $healthCheck = Invoke-WebRequest -Uri "$BackendUrl/health" -Method Get -UseBasicParsing -TimeoutSec 5
        if ($healthCheck.StatusCode -ne 200) {
            throw "Backend not healthy"
        }
    } catch {
        Write-Host "  ❌ Backend not accessible at ${BackendUrl}/health" -ForegroundColor Red
        Write-Host "  ⏸️  Waiting 5 minutes before retry..." -ForegroundColor Yellow
        Start-Sleep -Seconds 300
        continue
    }
    
    # Trigger the cycle
    try {
        $response = Invoke-RestMethod -Uri "$BackendUrl/agent/test-cycle-no-auth?test_user_id=$UserId" `
            -Method Post -ContentType "application/json"
        
        if ($response.status -eq "success") {
            Write-Host "  ✅ Cycle triggered successfully" -ForegroundColor Green
            Write-Host "  📝 Message: $($response.message)" -ForegroundColor Gray
            
            # Wait for it to complete
            Wait-ForCycleCompletion -CycleStartTime $cycleStart
            
            $actualEnd = Get-Date
            $duration = $actualEnd - $cycleStart
            $minutes = [math]::Floor($duration.TotalMinutes)
            $seconds = [math]::Floor($duration.TotalSeconds % 60)
            Write-Host "  📊 Total duration: $minutes minutes $seconds seconds" -ForegroundColor Cyan
            
            # Wait interval before next cycle
            Write-Host "  ⏸️  Waiting $IntervalMinutes minutes before next cycle..." -ForegroundColor Yellow
            Start-Sleep -Seconds ($IntervalMinutes * 60)
        } else {
            Write-Host "  ❌ Failed to trigger cycle: $($response | ConvertTo-Json)" -ForegroundColor Red
            Write-Host "  ⏸️  Waiting 5 minutes before retry..." -ForegroundColor Yellow
            Start-Sleep -Seconds 300
        }
    } catch {
        Write-Host "  ❌ Failed to trigger cycle: $_" -ForegroundColor Red
        Write-Host "  ⏸️  Waiting 5 minutes before retry..." -ForegroundColor Yellow
        Start-Sleep -Seconds 300
    }
}




