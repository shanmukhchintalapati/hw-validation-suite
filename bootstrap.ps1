# bootstrap.ps1
# -------------
# Sets up the hw-validation-suite on Windows (PowerShell).
# Covers: PowerShell scripting for automation and infrastructure management.

param(
    [string]$PythonPath = "python",
    [switch]$RunTests,
    [switch]$RunSuite
)

function Write-Step([string]$msg) {
    Write-Host "`n[STEP] $msg" -ForegroundColor Cyan
}

function Write-Ok([string]$msg) {
    Write-Host "[OK]   $msg" -ForegroundColor Green
}

function Write-Err([string]$msg) {
    Write-Host "[FAIL] $msg" -ForegroundColor Red
}

# ── 1. Python version check ───────────────────────────────────────────────────
Write-Step "Checking Python version"
try {
    $ver = & $PythonPath --version 2>&1
    Write-Ok $ver
} catch {
    Write-Err "Python not found at '$PythonPath'. Install Python 3.11+ and retry."
    exit 1
}

# ── 2. Create virtual environment ────────────────────────────────────────────
Write-Step "Creating virtual environment (.venv)"
if (-not (Test-Path ".venv")) {
    & $PythonPath -m venv .venv
    Write-Ok "Virtual environment created"
} else {
    Write-Ok "Virtual environment already exists — skipping"
}

# ── 3. Activate + install deps ───────────────────────────────────────────────
Write-Step "Installing dependencies from requirements.txt"
$pip = ".\.venv\Scripts\pip.exe"
& $pip install --upgrade pip -q
& $pip install -r requirements.txt -q
Write-Ok "Dependencies installed"

# ── 4. Create output directories ─────────────────────────────────────────────
Write-Step "Ensuring output directories exist"
foreach ($dir in @("logs", "reports")) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
        Write-Ok "Created $dir/"
    } else {
        Write-Ok "$dir/ already exists"
    }
}

# ── 5. Optionally run tests ───────────────────────────────────────────────────
if ($RunTests) {
    Write-Step "Running pytest"
    $pytest = ".\.venv\Scripts\pytest.exe"
    & $pytest tests/ -v
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "All tests passed"
    } else {
        Write-Err "Some tests failed — check output above"
        exit $LASTEXITCODE
    }
}

# ── 6. Optionally run the full suite ─────────────────────────────────────────
if ($RunSuite) {
    Write-Step "Running full validation suite"
    $python = ".\.venv\Scripts\python.exe"
    & $python -m src.framework_runner
}

Write-Host "`n=============================" -ForegroundColor White
Write-Host " Setup complete!" -ForegroundColor Green
Write-Host " Activate venv : .\.venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host " Run suite     : python -m src.framework_runner" -ForegroundColor Gray
Write-Host " Run tests     : pytest tests/ -v" -ForegroundColor Gray
Write-Host "=============================" -ForegroundColor White
