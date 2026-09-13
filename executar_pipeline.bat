@echo off
rem Executa o pipeline completo com o Python que acompanha o QGIS 3.44 LTR.
rem Uso: executar_pipeline.bat 2026-09-11T19
rem      (hora UTC do scan GOES-19; precisa estar dentro da janela de 48 h da CETESB
rem       ou da serie ja acumulada em dados\processados\cetesb_serie_horaria.csv)

setlocal
if "%~1"=="" (
    echo Informe a hora UTC do scan, por exemplo: executar_pipeline.bat 2026-09-11T19
    exit /b 1
)

set "QGIS_PY=C:\Program Files\QGIS 3.44.14\bin\python-qgis-ltr.bat"
if not exist "%QGIS_PY%" (
    echo Python do QGIS nao encontrado em "%QGIS_PY%". Ajuste a variavel QGIS_PY.
    exit /b 1
)

cd /d "%~dp0"
call "%QGIS_PY%" coleta_cetesb.py   || exit /b 1
call "%QGIS_PY%" limites_ibge.py    || exit /b 1
call "%QGIS_PY%" goes_aod.py %1     || exit /b 1
call "%QGIS_PY%" colocalizacao.py   || exit /b 1
call "%QGIS_PY%" qgis_mapa.py       || exit /b 1
echo.
echo Pipeline concluido. Veja a pasta figuras\ e o projeto qgis\rmsp_aod_mp25.qgz
