@echo off
REM Tarefa agendada: verificacao periodica das fontes oficiais do Painel ODS.
REM Ver scripts/09_monitor_fontes.py e data/monitoramento.log
cd /d "C:\Users\thiag\OneDrive\01. Projetos\_OpenCode_\Painel ODS"
"C:\Users\thiag\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\09_monitor_fontes.py >> data\monitor_agendado.log 2>&1
