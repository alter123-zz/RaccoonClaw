@echo off
REM send_email.cmd — 发送邮件到指定邮箱 (Windows CMD版)
REM
REM 用法:
REM   send_email.cmd --email EMAIL --subject SUBJECT --body BODY [--content_type text]

setlocal enabledelayedexpansion

REM 解析参数
set "EMAIL="
set "SUBJECT="
set "BODY="
set "CONTENT_TYPE=text"

:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--email" (
    set "EMAIL=%~2"
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--subject" (
    set "SUBJECT=%~2"
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--body" (
    set "BODY=%~2"
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--content_type" (
    set "CONTENT_TYPE=%~2"
    shift
    shift
    goto :parse_args
)
shift
goto :parse_args

:args_done
if "%EMAIL%"=="" (
    echo {"success": false, "error_code": 1, "message": "缺少必填参数: email"}
    exit /b 1
)
if "%SUBJECT%"=="" (
    echo {"success": false, "error_code": 1, "message": "缺少必填参数: subject"}
    exit /b 1
)
if "%BODY%"=="" (
    echo {"success": false, "error_code": 1, "message": "缺少必填参数: body"}
    exit /b 1
)

REM 初始化公共变量
call "%~dp0common.cmd"
if errorlevel 1 exit /b 1

REM 使用 node 构造 JSON 请求体（确保特殊字符正确转义）
set "REMOTE_URL=%REMOTE_BASE_URL%/data/4123/forward"
set "TMP_FILE=%TEMP%\email_skill_%RANDOM%.tmp"
set "TMP_STATUS=%TEMP%\email_skill_status_%RANDOM%.tmp"
set "TMP_BODY=%TEMP%\email_skill_body_%RANDOM%.tmp"

node -e "console.log(JSON.stringify({email:process.argv[1],subject:process.argv[2],body:process.argv[3],content_type:process.argv[4]}))" "%EMAIL%" "%SUBJECT%" "%BODY%" "%CONTENT_TYPE%" > "%TMP_BODY%"

curl -s -o "%TMP_FILE%" -w "%%{http_code}" -X POST "%PROXY_BASE_URL%/proxy/api" -H "Remote-URL: %REMOTE_URL%" -H "Content-Type: application/json" -d @"%TMP_BODY%" > "%TMP_STATUS%" 2>nul

set /p HTTP_STATUS=<"%TMP_STATUS%"

if not "%HTTP_STATUS%"=="200" (
    echo {"success": false, "error_code": 999, "message": "HTTP请求失败，状态码: %HTTP_STATUS%"}
    del "%TMP_FILE%" 2>nul
    del "%TMP_STATUS%" 2>nul
    del "%TMP_BODY%" 2>nul
    exit /b 1
)

REM 使用 node 解析网关响应
node -e "const fs=require('fs');const raw=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));const ret=raw.ret!==undefined?raw.ret:-1;if(ret!==0){console.log(JSON.stringify({success:false,error_code:999,message:'网关层错误，ret='+ret}));process.exit(1);}const resp=(raw.data||{}).resp||{};const code=((resp.common||{}).code!==undefined)?(resp.common||{}).code:-1;const msg=(resp.common||{}).message||'';let data=(resp.data!==undefined&&resp.data!==null)?resp.data:{};if(code===0){console.log(JSON.stringify({success:true,data:data,message:msg}));}else{console.log(JSON.stringify({success:false,error_code:code,message:msg}));process.exit(1);}" "%TMP_FILE%"

set "EXIT_CODE=%ERRORLEVEL%"
del "%TMP_FILE%" 2>nul
del "%TMP_STATUS%" 2>nul
del "%TMP_BODY%" 2>nul
exit /b %EXIT_CODE%
