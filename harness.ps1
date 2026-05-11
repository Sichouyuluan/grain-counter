# Grain Counter - Harness 核心循环
# 被 run.ps1 调用，实现 Planner → Generator → Evaluator 循环

param(
    [string]$mode = "auto",
    [int]$iterations = 10
)

$ErrorActionPreference = "Stop"

Write-Host "╔══════════════════════════════════════════╗"
Write-Host "║   🌾 Grain Counter - Long Run Harness   ║"
Write-Host "╚══════════════════════════════════════════╝"
Write-Host ""

# 确保 memory 文件存在
$handoffPath = Join-Path $PSScriptRoot "memory/handoff.md"
$progressPath = Join-Path $PSScriptRoot "memory/progress.md"

if (-not (Test-Path $handoffPath)) {
    @"
# Handoff

## 当前状态
初始状态，尚未开始。

## 最后完成
无

## 下一步
运行 Planner 阶段，将 mission.md 中的需求分解为 tasks.json
"@ | Set-Content $handoffPath -Encoding UTF8
}

if (-not (Test-Path $progressPath)) {
    @"
# 进度日志

## 2026-05-11
- 项目初始化，框架结构搭建完成
"@ | Set-Content $progressPath -Encoding UTF8
}

# 读取 handoff
Write-Host "=== 当前 Handoff ==="
Get-Content $handoffPath -Encoding UTF8
Write-Host ""

switch ($mode) {
    "auto" {
        for ($i = 0; $i -lt $iterations; $i++) {
            Write-Host "=== 迭代 $($i+1)/$iterations ==="

            # 1. 读 handoff
            $handoff = Get-Content $handoffPath -Encoding UTF8 -Raw

            # 2. 根据 handoff 决定阶段
            if ($handoff -match "Planner") {
                & claude "--prompt" (Get-Content "prompts/planner.md" -Encoding UTF8 -Raw)
            } elseif ($handoff -match "Generator") {
                & claude "--prompt" (Get-Content "prompts/generator.md" -Encoding UTF8 -Raw)
            } elseif ($handoff -match "Evaluator") {
                & claude "--prompt" (Get-Content "prompts/evaluator.md" -Encoding UTF8 -Raw)
            } else {
                Write-Host "未知阶段，默认启动 Generator"
                & claude "--prompt" (Get-Content "prompts/generator.md" -Encoding UTF8 -Raw)
            }

            # 检查是否还有待办任务
            $tasks = Get-Content "tasks/tasks.json" -Encoding UTF8 -Raw | ConvertFrom-Json
            $pending = $tasks | Where-Object { $_.status -eq "pending" }
            if (-not $pending) {
                Write-Host "所有任务已完成！"
                break
            }
        }
    }
    "planner" {
        & claude "--prompt" (Get-Content "prompts/planner.md" -Encoding UTF8 -Raw)
    }
    "generator" {
        & claude "--prompt" (Get-Content "prompts/generator.md" -Encoding UTF8 -Raw)
    }
    "evaluator" {
        & claude "--prompt" (Get-Content "prompts/evaluator.md" -Encoding UTF8 -Raw)
    }
}
