@echo off
REM email_gateway.cmd — email-skill 统一入口 (Windows CMD版)

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

REM 定位项目根目录（scripts\windows -> scripts -> email-skill）
for %%I in ("%SCRIPT_DIR%\..\.." ) do set "EMAIL_SKILL_DIR=%%~fI"
for %%I in ("%EMAIL_SKILL_DIR%\..\imap-smtp-email") do set "IMAP_SMTP_DIR=%%~fI"

set "IMAP_JS=%IMAP_SMTP_DIR%\scripts\imap.js"
set "SMTP_JS=%IMAP_SMTP_DIR%\scripts\smtp.js"
set "SETUP_SH=%IMAP_SMTP_DIR%\setup.sh"

REM 获取第一个参数作为命令
set "CMD=%~1"
if "%CMD%"=="" (
    call :print_help
    exit /b 0
)
shift

REM 路由命令
if /i "%CMD%"=="help" goto :do_help
if /i "%CMD%"=="-h" goto :do_help
if /i "%CMD%"=="--help" goto :do_help
if /i "%CMD%"=="capabilities" goto :do_capabilities
if /i "%CMD%"=="bind-check" goto :do_bind_check
if /i "%CMD%"=="bind-send-code" goto :do_bind_send_code
if /i "%CMD%"=="bind-verify" goto :do_bind_verify
if /i "%CMD%"=="send" goto :do_send
if /i "%CMD%"=="setup-personal" goto :do_setup_personal
if /i "%CMD%"=="inbox-check" goto :do_inbox_personal
if /i "%CMD%"=="inbox-search" goto :do_inbox_personal
if /i "%CMD%"=="inbox-fetch" goto :do_inbox_personal
if /i "%CMD%"=="inbox-download" goto :do_inbox_personal
if /i "%CMD%"=="inbox-mark-read" goto :do_inbox_personal
if /i "%CMD%"=="inbox-mark-unread" goto :do_inbox_personal
if /i "%CMD%"=="inbox-list-mailboxes" goto :do_inbox_personal

echo {"success": false, "error_code": 1, "message": "未知命令: %CMD%，可用命令见 --help"}
exit /b 1

REM --------------------------------------------------------
REM 命令实现
REM --------------------------------------------------------

:do_help
call :print_help
exit /b 0

:do_capabilities
call :print_capabilities
exit /b 0

:do_bind_check
call "%SCRIPT_DIR%\check_bind.cmd" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:do_bind_send_code
call "%SCRIPT_DIR%\send_code.cmd" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:do_bind_verify
call "%SCRIPT_DIR%\verify_bind.cmd" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:do_send
REM 解析 --provider 参数
set "PROVIDER="
set "REST_ARGS="
call :parse_send_args %1 %2 %3 %4 %5 %6 %7 %8 %9
if "%PROVIDER%"=="platform" (
    call "%SCRIPT_DIR%\send_email.cmd" %REST_ARGS%
    exit /b !ERRORLEVEL!
)
if "%PROVIDER%"=="personal" (
    call :ensure_personal_ready
    if errorlevel 1 exit /b 1
    pushd "%IMAP_SMTP_DIR%"
    node "%SMTP_JS%" send %REST_ARGS%
    set "EC=!ERRORLEVEL!"
    popd
    exit /b !EC!
)
echo {"success": false, "error_code": 1, "message": "send 命令必须指定 --provider platform|personal"}
exit /b 1

:do_setup_personal
if not exist "%IMAP_SMTP_DIR%\setup.sh" (
    echo {"success": false, "error_code": 2, "message": "未找到 setup.sh，无法初始化 personal provider"}
    exit /b 1
)
pushd "%IMAP_SMTP_DIR%"
bash setup.sh
set "EC=%ERRORLEVEL%"
popd
exit /b %EC%

:do_inbox_personal
REM 提取 inbox 子命令类型
set "INBOX_SUB=%CMD:inbox-=%"
REM 检查 --provider personal
set "HAS_PERSONAL=0"
for %%A in (%1 %2 %3 %4 %5 %6 %7 %8 %9) do (
    if /i "%%A"=="personal" set "HAS_PERSONAL=1"
)
if "%HAS_PERSONAL%"=="0" (
    echo {"success": false, "error_code": 1, "message": "%CMD% 仅支持 --provider personal"}
    exit /b 1
)
call :ensure_personal_ready
if errorlevel 1 exit /b 1
REM 移除 --provider personal 后转发
set "FWD_ARGS="
call :strip_provider %1 %2 %3 %4 %5 %6 %7 %8 %9
pushd "%IMAP_SMTP_DIR%"
node "%IMAP_JS%" %INBOX_SUB% %FWD_ARGS%
set "EC=!ERRORLEVEL!"
popd
exit /b !EC!

REM --------------------------------------------------------
REM 辅助函数
REM --------------------------------------------------------

:parse_send_args
set "PROVIDER="
set "REST_ARGS="
:psa_loop
if "%~1"=="" goto :psa_done
if /i "%~1"=="--provider" (
    set "PROVIDER=%~2"
    shift
    shift
    goto :psa_loop
)
if defined REST_ARGS (
    set "REST_ARGS=!REST_ARGS! %~1"
) else (
    set "REST_ARGS=%~1"
)
shift
goto :psa_loop
:psa_done
goto :eof

:strip_provider
set "FWD_ARGS="
set "SKIP_NEXT=0"
:sp_loop
if "%~1"=="" goto :sp_done
if "%SKIP_NEXT%"=="1" (
    set "SKIP_NEXT=0"
    shift
    goto :sp_loop
)
if /i "%~1"=="--provider" (
    set "SKIP_NEXT=1"
    shift
    goto :sp_loop
)
if defined FWD_ARGS (
    set "FWD_ARGS=!FWD_ARGS! %~1"
) else (
    set "FWD_ARGS=%~1"
)
shift
goto :sp_loop
:sp_done
goto :eof

:ensure_personal_ready
if not exist "%IMAP_SMTP_DIR%" (
    echo {"success": false, "error_code": 2, "message": "未找到 imap-smtp-email 目录，无法使用 personal provider"}
    exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
    echo {"success": false, "error_code": 2, "message": "未检测到 node，无法使用 personal provider"}
    exit /b 1
)
if not exist "%SMTP_JS%" (
    echo {"success": false, "error_code": 2, "message": "imap-smtp-email 脚本缺失，请检查 scripts\smtp.js"}
    exit /b 1
)
if not exist "%IMAP_JS%" (
    echo {"success": false, "error_code": 2, "message": "imap-smtp-email 脚本缺失，请检查 scripts\imap.js"}
    exit /b 1
)
exit /b 0

:print_help
echo email_gateway.cmd — 统一邮件入口 (Windows)
echo.
echo 命令：
echo   capabilities
echo       展示所有可用能力、适用场景与配置方式
echo.
echo   send --provider ^<platform^|personal^> [参数]
echo       发送邮件统一命令
echo       - provider=platform: 走平台公邮服务
echo           必填参数：--email --subject --body
echo           可选参数：--content_type text（当前仅支持纯文本）
echo           注意：收件人必须是用户有登录权限的邮箱
echo       - provider=personal: 走个人邮箱SMTP
echo           必填参数：--to --subject
echo           可选参数：--body --cc --bcc --attach --from --html
echo.
echo   bind-check --email ^<email^>
echo   bind-send-code --email ^<email^>
echo   bind-verify --email ^<email^> --code ^<code^>
echo.
echo   setup-personal
echo       启动个人邮箱 IMAP/SMTP 初始化向导
echo.
echo   inbox-check --provider personal [--limit N] [--recent 2h]
echo   inbox-search --provider personal [search options]
echo   inbox-fetch --provider personal ^<uid^>
echo   inbox-download --provider personal ^<uid^> [--dir PATH]
echo   inbox-mark-read --provider personal ^<uid...^>
echo   inbox-mark-unread --provider personal ^<uid...^>
echo   inbox-list-mailboxes --provider personal
goto :eof

:print_capabilities
echo {
echo   "success": true,
echo   "entry": "email-skill/scripts/windows/email_gateway.cmd",
echo   "providers": [
echo     {
echo       "id": "platform",
echo       "name": "平台公邮服务",
echo       "config": "无需SMTP/IMAP配置；首次发送需完成邮箱绑定",
echo       "abilities": [
echo         "检查绑定状态",
echo         "发送验证码并绑定邮箱",
echo         "发送纯文本邮件"
echo       ],
echo       "limitations": [
echo         "收件人必须是用户有登录权限的邮箱（绑定需要验证码校验）",
echo         "不支持发送给任意第三方",
echo         "不支持收件/检索/附件下载",
echo         "不支持抄送(CC)、密送(BCC)",
echo         "不支持附件发送"
echo       ],
echo       "best_for": [
echo         "给自己发送通知/报告",
echo         "自动化提醒推送",
echo         "不想管理邮箱密码/授权码"
echo       ]
echo     },
echo     {
echo       "id": "personal",
echo       "name": "个人邮箱(IMAP/SMTP)",
echo       "config": "在 imap-smtp-email/.env 配置 IMAP/SMTP 凭据",
echo       "abilities": [
echo         "SMTP发送（支持任意收件人、抄送/密送/附件）",
echo         "IMAP收件、检索、读取详情",
echo         "下载附件、标记已读/未读、列出文件夹"
echo       ],
echo       "limitations": [],
echo       "best_for": [
echo         "需要给他人发送邮件",
echo         "需要读取邮箱内容",
echo         "需要使用个人发件身份",
echo         "需要完整IMAP/SMTP能力"
echo       ]
echo     }
echo   ]
echo }
goto :eof
