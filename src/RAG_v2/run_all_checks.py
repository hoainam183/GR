#!/usr/bin/env python3
"""
Run all the required checks sequentially and report output
"""
import subprocess
import sys
import os

os.chdir("D:\\GR\\src\\RAG_v2")

def run_command(description, command, shell=False):
    """Run a command and print full output"""
    print(f"\n{'='*60}")
    print(f"STEP: {description}")
    print(f"{'='*60}")
    print(f"Command: {command}\n")
    
    try:
        result = subprocess.run(
            command,
            shell=shell,
            capture_output=False,
            text=True,
            cwd="D:\\GR\\src\\RAG_v2"
        )
        print(f"\nExit Code: {result.returncode}")
    except Exception as e:
        print(f"Error running command: {e}")
    
    print()

# Step 1: Python compile check
run_command(
    "1: Python Compile Check",
    "python -m py_compile auth/refresh_tokens.py auth/jwt_handler.py routers/auth.py schemas/user.py models/database.py",
    shell=True
)

# Step 2: pytest
run_command(
    "2: pytest (not integration)",
    'python -m pytest tests/test_auth_refresh.py tests/test_rbac.py tests/test_mobile_api_contracts.py -v -m "not integration"',
    shell=True
)

# Step 3: npm typecheck @rag/shared
run_command(
    "3: npm typecheck for @rag/shared",
    "npm run typecheck --workspace=@rag/shared",
    shell=True
)

# Step 4: npm typecheck for mobile
run_command(
    "4: npm typecheck for mobile",
    "npm run typecheck --workspace=mobile",
    shell=True
)

print("\n" + "="*60)
print("All checks completed")
print("="*60)
