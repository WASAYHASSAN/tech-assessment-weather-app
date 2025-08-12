# 🌤️ Weather App - powered with AI Travel Advisory

An intelligent, interactive weather application built with **Python, Streamlit, GPT, HuggingFace, LangChain, and multiple APIs**, designed to provide **accurate weather updates**, **AI-generated travel advisory**.

---

## 🚀 Features

### **1. AI Travel Advisory**
- Enter a **location** and select the **number of days** for the forecast.
- Get **AI-generated** advice including:
  - ✈️ **Travel advice**
  - 🌦️ **Weather-specific guidance**
  - 🩺 **Health precautions**
- Powered by **LangChain + HuggingFace LLM** with live weather data.

---

### **2. Get Weather Update**
- Search by:
  - Location name (e.g., `Paris`)
  - Landmark (e.g., `Eiffel Tower`)
  - Latitude & Longitude (e.g., `48.8584, 2.2945`)
- Displays:
  - **Current weather** (temperature, wind speed, precipitation)
  - **5-day forecast**
- Maintains **search history** in SQLite:
  - Load previous weather results
  - Delete individual history entries

---

### **3. Explore More About the Location**
- Enter a location to:
  - 🌍 View **interactive Google Map** 
  - ▶️ See **related YouTube videos**
  - 🖼️ Displays **related Unsplash images**

---

### **4. Search History Exporter**
- Export **entire weather search history** as a downloadable **CSV** file.

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Frontend** | Streamlit |
| **Backend** | Python |
| **AI Processing** | GPT (via HuggingFace + LangChain) |
| **Weather Data** | Weather API |
| **Media Content** | YouTube API, Unsplash API |
| **Location Services** | Geopy |
| **Database** | SQLite3 |
| **Deployment** | Streamlit Cloud |

---

- This repository does not contain private API keys.
- This Application is hosted on Streamlit Community Cloud accessable via the provided link in the PM Google Form.
- Current location fetching is disabled because of IP security issues, the user can get their location's forecast by using the "Weather Update" section.
- If intended for local use, provide personal API keys for the variables defined under st.secrets("YOUR_API_KEY_HERE").
