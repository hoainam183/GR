# Workspace Instructions

## Python Environment

This workspace uses a virtual environment located at `D:\GR\.venv`.

**Always use `.venv` when running Python commands:**

```powershell
# Activate before running scripts
D:\GR\.venv\Scripts\Activate.ps1

# Or invoke directly
D:\GR\.venv\Scripts\python.exe <script>
D:\GR\.venv\Scripts\pip.exe install <package>
```

- Never use the global Python (`AppData\Local\Programs\Python\...`) for this workspace.
- When installing packages, always use `D:\GR\.venv\Scripts\pip.exe` or activate `.venv` first.
- When checking if a package is installed, use `D:\GR\.venv\Scripts\pip.exe show <package>`.
- All terminal commands that invoke `python` or `pip` must target the `.venv` executable.
