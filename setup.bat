@echo off
REM ========================================
REM  SETUP SCRIPT FOR WINDOWS
REM ========================================
REM 
REM This script helps you set up .env file
REM for first-time deployment
REM 
REM Usage: setup.bat
REM 
REM ========================================

echo ========================================
echo  BOOKING BOT - INITIAL SETUP
echo ========================================
echo.

REM Check if .env already exists
if exist ".env" (
    echo ⚠️  .env file already exists!
    echo.
    echo Options:
    echo   1. Keep existing .env (press Ctrl+C to cancel)
    echo   2. Overwrite with .env.example (press Enter)
    echo.
    choice /C YN /M "Do you want to OVERWRITE existing .env"
    if errorlevel 2 goto :EOF
    if errorlevel 1 (
        echo.
        echo Creating backup: .env.backup
        copy .env .env.backup >nul
    )
)

REM Check if .env.example exists
if not exist ".env.example" (
    echo ❌ ERROR: .env.example not found!
    echo.
    echo Please make sure you're in the project root directory.
    echo Expected file: .env.example
    pause
    exit /b 1
)

REM Copy .env.example to .env
echo ✅ Creating .env from .env.example...
copy .env.example .env >nul

if errorlevel 1 (
    echo ❌ ERROR: Failed to create .env file!
    pause
    exit /b 1
)

echo.
echo ========================================
echo  ✅ .env FILE CREATED!
echo ========================================
echo.
echo 📝 Next steps:
echo.
echo 1. EDIT .env file and set your tokens:
echo.
echo    notepad .env
echo.
echo    Or use any text editor:
echo    - Notepad++
    - VS Code
    - Sublime Text
echo.
echo 2. Required values to change:
echo.
echo    BOT_TOKEN_MASTER=your_master_bot_token_here
echo    BOT_TOKEN_SALES=your_sales_bot_token_here
echo    ADMIN_IDS_MASTER=your_telegram_id
echo    ADMIN_IDS_SALES=your_telegram_id
echo    POSTGRES_PASSWORD=secure_password_here
echo.
echo 3. Get Telegram Bot tokens from @BotFather:
echo    - Send: /newbot
    - Follow instructions
    - Copy token
echo.
echo 4. Get your Telegram ID from @userinfobot:
echo    - Send any message
    - Copy your ID
echo.
echo 5. After editing .env, run deployment:
echo.
echo    rebuild.bat
echo.
echo ========================================
echo.
choice /C YN /M "Do you want to open .env in Notepad now"
if errorlevel 2 goto :end
if errorlevel 1 notepad .env

:end
echo.
echo 🚀 Ready to deploy! Run: rebuild.bat
echo.
pause
