@echo off
REM common.cmd — 邮件skill公共函数库 (Windows CMD版)
REM 提供统一的HTTP请求发送、JSON解析、响应处理和标准化输出
REM Token 由本地代理服务自动注入，无需手动传入

setlocal enabledelayedexpansion

REM 远程 API 基础地址（通过 Remote-URL header 传递给本地代理）
set "REMOTE_BASE_URL=https://jprx.m.qq.com"

REM --------------------------------------------------------
REM 解析本地代理端口（从环境变量获取）
REM --------------------------------------------------------

REM 从环境变量 AUTH_GATEWAY_PORT 获取本地代理端口
REM 该变量由 Electron 主进程在启动 Auth Gateway 时自动设置，子进程自动继承
REM 若环境变量未设置，则回退到默认端口 19000

if defined AUTH_GATEWAY_PORT (
    set "PROXY_PORT=%AUTH_GATEWAY_PORT%"
) else (
    set "PROXY_PORT=19000"
    echo [QClaw] AUTH_GATEWAY_PORT not set, falling back to default port: 19000 >&2
)

echo [QClaw] AUTH_GATEWAY_PORT: %PROXY_PORT%

set "PROXY_BASE_URL=http://localhost:%PROXY_PORT%"

REM 返回到调用者
exit /b 0
