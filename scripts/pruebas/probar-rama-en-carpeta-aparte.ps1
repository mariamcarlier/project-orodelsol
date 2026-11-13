<#
.SYNOPSIS
    Ejecuta las pruebas de una rama en una carpeta aparte, sin tocar tu copia.

.DESCRIPTION
    Descarga la última versión de la rama indicada en una carpeta nueva
    (una "copia de trabajo" de git) y corre ahí las pruebas. Sirve para
    comprobar una rama sin moverte de la que estás usando ni arriesgar los
    archivos que tengas a medio hacer.

    Al terminar, la carpeta queda ahí: puedes mirarla, abrirla en el editor o
    borrarla. No borra nada de tu proyecto.

.EXAMPLE
    .\scripts\pruebas\probar-rama-en-carpeta-aparte.ps1

.EXAMPLE
    .\scripts\pruebas\probar-rama-en-carpeta-aparte.ps1 -Rama otra/rama -Carpeta C:\temp\prueba
#>
param(
    [string]$Rama = "arena/456ac8d6-project-orodelsol",
    [string]$Carpeta = "",
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

# 1. De dónde sale la carpeta y el intérprete de Python.
$raiz = (git rev-parse --show-toplevel)
if (-not $Carpeta) {
    $nombre = ($Rama -replace "[^A-Za-z0-9_.-]", "-")
    $Carpeta = Join-Path (Split-Path $raiz -Parent) "prueba-$nombre"
}
if (-not $Python) {
    $Python = Join-Path $raiz ".venv\Scripts\python.exe"
}
if (-not (Test-Path $Python)) {
    throw "No encuentro Python en $Python. Abre la terminal con el entorno (.venv) activado o pásame -Python <ruta>."
}

Write-Host "Rama que se va a probar: $Rama" -ForegroundColor Cyan
Write-Host "Carpeta:                  $Carpeta" -ForegroundColor Cyan

# 2. Traer la última versión de la rama desde GitHub.
git fetch origin $Rama
if ($LASTEXITCODE -ne 0) { throw "No pude descargar la rama $Rama desde GitHub." }

# 3. Crear la carpeta aparte con esa rama. No toca tu copia de trabajo.
if (Test-Path $Carpeta) {
    throw "La carpeta $Carpeta ya existe. Bórrala o pásame otra con -Carpeta."
}
git worktree add --detach $Carpeta "origin/$Rama"
if ($LASTEXITCODE -ne 0) { throw "No pude crear la carpeta de prueba." }

# 4. Copiar el .env (tiene la configuración y no está en el repositorio).
$envOrigen = Join-Path $raiz ".env"
if (Test-Path $envOrigen) {
    Copy-Item $envOrigen (Join-Path $Carpeta ".env")
} else {
    Write-Host "Aviso: no hay .env en $raiz; las pruebas pueden quejarse de configuración." -ForegroundColor Yellow
}

# 5. Ejecutar las pruebas dentro de la carpeta aparte.
Push-Location $Carpeta
try {
    Write-Host "`nEjecutando las pruebas...`n" -ForegroundColor Cyan
    & $Python manage.py test
    $resultado = $LASTEXITCODE
} finally {
    Pop-Location
}

# 6. Resumen y cómo limpiar.
Write-Host ""
if ($resultado -eq 0) {
    Write-Host "Todo correcto: las pruebas de la rama $Rama pasan." -ForegroundColor Green
} else {
    Write-Host "Hubo fallos en la rama $Rama. Copia la salida de arriba." -ForegroundColor Red
}
Write-Host ""
Write-Host "La carpeta de prueba sigue en: $Carpeta" -ForegroundColor Cyan
Write-Host "Para borrarla cuando ya no la necesites:" -ForegroundColor Cyan
Write-Host "  git worktree remove `"$Carpeta`"" -ForegroundColor Gray

exit $resultado
