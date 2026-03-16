@echo off
chcp 65001 >nul
echo.
echo CHAT
echo.

:start
set ip=
set name=
set udp_port=
set tcp_port=

set /p ip="Enter IP address : "
set /p name="Enter your name: "
set /p udp_port="Enter UDP port: "
if "%udp_port%"=="" set udp_port=8888
set /p tcp_port="Enter TCP port: "

echo.
echo Available commands:
echo   /history - show message history
echo   /nodes   - show connected nodes
echo   /exit    - exit the program
echo.

echo Starting with: IP=%ip%, NAME=%name%, UDP=%udp_port%, TCP=%tcp_port%
echo.

if "%tcp_port%"=="" (
    C:\Users\Veronika\anaconda3\python.exe chat.py --ip %ip% --name "%name%" --port %udp_port%
) else (
    C:\Users\Veronika\anaconda3\python.exe chat.py --ip %ip% --name "%name%" --port %udp_port% --tcp-port %tcp_port%
)


if errorlevel 1 (
    echo.
    echo Invalid input detected! Please try again.
    echo.
    goto start
)

pause