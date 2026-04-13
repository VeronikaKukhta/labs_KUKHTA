@echo off
title File Storage Server



echo    File Storage
echo.

set PYTHON_PATH=C:\Users\Veronika\anaconda3\python.exe


echo Server address: http://localhost:5000
echo Storage folder: %CD%\storage
echo.

echo Starting server
echo.

echo Press Ctrl+C to stop the server
echo.

%PYTHON_PATH% storage_server.py

echo.
echo Server stopped
pause