@echo off
cd /d "D:\GR\src\RAG_v2"

echo.
echo ========== STEP 1: Python Compile Check ==========
python -m py_compile auth/refresh_tokens.py auth/jwt_handler.py routers/auth.py schemas/user.py models/database.py
echo Python compile check exit code: %ERRORLEVEL%
echo.

echo ========== STEP 2: pytest (not integration) ==========
python -m pytest tests/test_auth_refresh.py tests/test_rbac.py tests/test_mobile_api_contracts.py -v -m "not integration"
echo pytest exit code: %ERRORLEVEL%
echo.

echo ========== STEP 3: npm typecheck for @rag/shared ==========
call npm run typecheck --workspace=@rag/shared
echo npm typecheck @rag/shared exit code: %ERRORLEVEL%
echo.

echo ========== STEP 4: npm typecheck for mobile ==========
call npm run typecheck --workspace=mobile
echo npm typecheck mobile exit code: %ERRORLEVEL%
echo.

pause
