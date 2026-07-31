@echo off
echo ============================================
echo   City Brain - Model Setup
echo ============================================
echo.

echo [1/3] Pulling base model (phi3.5)...
echo       This will download ~2.4GB
ollama pull phi3.5

echo.
echo [2/3] Creating citybrain model...
ollama create citybrain -f Modelfile

echo.
echo [3/3] Testing...
echo.
ollama run citybrain "Classify this complaint: pothole on 80 feet road near Koramangala and no water supply for 3 days"

echo.
echo ============================================
echo   DONE! Model 'citybrain' is ready.
echo   Now copy llm_pipeline.py to:
echo   backend\app\services\llm_pipeline.py
echo ============================================
pause
