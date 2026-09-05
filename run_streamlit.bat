@echo off
cd /d "%~dp0"
echo Starting Streamlit app on http://localhost:8501 ...
.venv\Scripts\python.exe -m streamlit run app.py
pause
