@echo off
rem Runs Hunter from this folder with the project's own environment (.venv, built by doctrine
rem check from requirements.lock). Usage: hunter discover, hunter boards add <link>.
setlocal
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Hunter's environment isn't built yet: run "doctrine check" once in %~dp0
    exit /b 1
)
set "PYTHONPATH=%~dp0src"
pushd "%~dp0"
"%~dp0.venv\Scripts\python.exe" -m hunter %*
set "status=%errorlevel%"
popd
exit /b %status%
