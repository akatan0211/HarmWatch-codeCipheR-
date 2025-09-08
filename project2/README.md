# HarmWatch - Example Project Scaffold

This zip provides a starter scaffold for the HarmWatch research pipeline:
- Streamlit dashboard (app.py)
- Utils and feedback manager (utils.py, feedback_manager.py)
- FastAPI backend for extension feedback (backend/main.py)
- Chrome extension (extension/)
- Training script (train_tfidf_lr.py)
- requirements.txt

This is a starting point — you'll need to train models and adjust paths before production.

Run backend:
```
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Run Streamlit dashboard:
```
pip install -r ../requirements.txt
streamlit run app.py
```

Load extension: open Chrome → Extensions → Load unpacked → choose the `extension/` folder.
