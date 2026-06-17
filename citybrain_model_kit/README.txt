============================================
  CITY BRAIN — Model Setup Instructions
============================================

STEP 1: Install Ollama
   → Download from https://ollama.com
   → Run the installer

STEP 2: Pull the base model
   → Open terminal/cmd and run:
   
   ollama pull phi3.5

   (This downloads ~2.4GB, takes 5-10 min)

STEP 3: Create the City Brain model
   → Navigate to this folder in terminal:
   
   cd Desktop\city_brain\citybrain_model_kit
   
   → Run:
   
   ollama create citybrain -f Modelfile

   → Test it:
   
   ollama run citybrain "Classify this complaint: pothole on 80 feet road near Koramangala"

STEP 4: Replace backend pipeline
   → Copy llm_pipeline.py to:
   
   Desktop\city_brain\backend\app\services\llm_pipeline.py
   
   (Overwrite the existing file)

STEP 5: Run the backend
   
   cd Desktop\city_brain\backend
   venv\Scripts\activate
   uvicorn app.main:app --reload

DONE! Submit a complaint from the frontend and it will
be classified by the City Brain model running locally.
