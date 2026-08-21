# bf -- run book-forge from the book repo you are standing in.
$forge = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$forge;$env:PYTHONPATH" } else { $forge }
$py = if ($env:BOOK_FORGE_PYTHON) { $env:BOOK_FORGE_PYTHON } else { "python" }
& $py -m bookforge @args
exit $LASTEXITCODE
