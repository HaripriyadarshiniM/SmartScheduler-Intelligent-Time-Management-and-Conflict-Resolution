@echo off
echo ======================================
echo ChronoSync - Setup ^& Start
echo ======================================
echo.

REM Create database directory if it doesn't exist
if not exist "database\" mkdir database

REM Initialize database
echo Initializing database...
python -c "from app import init_db; init_db()"

if %errorlevel% equ 0 (
    echo [SUCCESS] Database initialized successfully
    echo.
    echo ======================================
    echo Starting ChronoSync Application...
    echo ======================================
    echo.
    echo Access the application at:
    echo   -^> http://localhost:5000
    echo.
    echo Press Ctrl+C to stop the server
    echo.
    
    REM Run the application
    python app.py
) else (
    echo [ERROR] Database initialization failed
    pause
    exit /b 1
)
