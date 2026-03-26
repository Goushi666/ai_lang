cd d:\Yang\project\ai_lang\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

cd d:\Yang\project\ai_lang\web-frontend
npm run dev