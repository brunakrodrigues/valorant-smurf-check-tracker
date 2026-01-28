# Valorant Smurf Checker (Study Project)

⚠️ **Important Notice**  
This project is **for study, learning, and technical experimentation purposes only**.  

---

## 📘 About the Project

This is a **Python + Streamlit** application that analyzes VALORANT player data using the  
**Tracker Network API** to **study ranking patterns** and **identify potential smurf behavior** based on:

- Highest rank achieved in the last 3 acts
- Estimated current rank
- Rank gap between historical peak and current placement

👉 **Results are heuristic-based and not definitive.**  
They should not be used to judge, report, or penalize players.

---

## 🎯 Project Goals

- API integration study (third-party APIs)
- Semi-structured JSON data parsing
- Simple heuristic-based behavior analysis
- Spreadsheet upload and batch processing
- Data visualization with Streamlit

---

## 🧪 Limitations

- “Smurf” detection is **heuristic**, not official
- Depends on the availability and structure of Tracker API responses
- Act/season detection is inferred and may be imperfect
- Does not replace official Riot Games data or decisions

---

## 🔑 Requirements

- Python 3.10+
- **Tracker Network API Key (TRN-Api-Key)**

> The API key must be entered manually in the app UI  
> **Never hardcode your API key in the source code**

---

## ▶️ Running the Project Locally

```bash
pip install -r requirements.txt
streamlit run app.py
