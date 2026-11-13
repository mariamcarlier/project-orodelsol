@echo off
REM Pasa todos los commits de la rama de la galeria a la rama actual (respaldo),
REM aunque haya cambios sin confirmar. Lo que este sin confirmar se guarda antes
REM en un apartado ("guardado provisional") y se devuelve al final.
REM
REM Uso, desde la carpeta del proyecto:
REM     scripts\git\pasar-rama-galeria.bat
REM
REM No sube nada a GitHub: eso es el comando aparte que te doy al final.

setlocal
set RAMA=arena/456ac8d6-project-orodelsol

echo ============================================
echo  1. En que rama estoy
echo ============================================
git branch --show-current
echo.

echo ============================================
echo  2. Guardo aparte lo que no este confirmado
echo     (si no hay nada, no pasa nada)
echo ============================================
git stash push --include-untracked --message "antes de traer la galeria"

echo.
echo ============================================
echo  3. Traigo la ultima version de la rama
echo ============================================
git fetch origin %RAMA%
if errorlevel 1 goto :error

echo.
echo ============================================
echo  4. Mezclo. Si algo choca, se queda MI version
echo     (los archivos a medias de la rama de
echo     respaldo eran versiones viejas de la mia)
echo ============================================
git merge -X theirs --no-edit origin/%RAMA%
if errorlevel 1 goto :error

echo.
echo ============================================
echo  5. Devuelvo lo que habia guardado aparte
echo ============================================
git stash list
echo (si arriba aparece "antes de traer la galeria", se recupera ahora)
git stash pop
echo.
echo Si avisa de conflictos al recuperar, NO pasa nada grave: tus archivos
echo sin confirmar siguen en el guardado provisional. Dime que dice y lo vemos.

echo.
echo ============================================
echo  6. Resultado
echo ============================================
git log --oneline -3
echo.
echo Archivos sin confirmar ahora:
git status --short

echo.
echo ============================================
echo  Listo. Para comprobar que todo funciona:
echo      python manage.py test
echo  Debe decir:  Ran 828 tests ... OK
echo ============================================
goto :eof

:error
echo.
echo Algo fallo. NO toques nada mas y copiame lo que salga arriba.
exit /b 1
