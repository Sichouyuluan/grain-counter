# Grain Counter - Claude Code 长时间运行入口
# 用法: .\run.ps1 [mission]
# 详细用法: .\run.ps1 help

param(
    [string]$mission = "help"
)

if ($mission -eq "help") {
    Write-Host @"
Grain Counter - Claude Code 长时间运行框架
用法: .\run.ps1 <command>

命令:
  plan       - Planner: 分析需求，生成任务列表
  generate   - Generator: 实现下一个待办任务
  evaluate   - Evaluator: 验收已完成任务
  mission    - 显示当前任务定义
  tasks      - 显示当前任务列表
  help       - 显示本帮助

示例:
  .\run.ps1 plan       # 开始规划阶段
  .\run.ps1 generate   # 开始实现阶段
"@
    exit 0
}

Write-Host "=== Grain Counter Long-Run Framework ==="
Write-Host "Mission: $mission"
Write-Host ""

switch ($mission.ToLower()) {
    "plan" {
        Write-Host "[Phase] Planner - 分析需求，分解任务"
        & claude "请读取 tasks/mission.md，将需求分解为可执行任务列表，写入 tasks/tasks.json"
    }
    "generate" {
        Write-Host "[Phase] Generator - 实现下一个任务"
        & claude "请读取 tasks/tasks.json，找一个 pending 且依赖已满足的任务，实现它"
    }
    "evaluate" {
        Write-Host "[Phase] Evaluator - 验收任务"
        & claude "请读取 tasks/tasks.json，验证所有 completed 任务是否满足 acceptance criteria"
    }
    "mission" {
        Get-Content "tasks/mission.md" -ErrorAction SilentlyContinue
    }
    "tasks" {
        Get-Content "tasks/tasks.json" -ErrorAction SilentlyContinue | ConvertFrom-Json | ConvertTo-Json
    }
    default {
        Write-Host "未知命令: $mission"
        Write-Host "用法: .\run.ps1 help"
    }
}
