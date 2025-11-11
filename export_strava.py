import requests
import os
import json
from datetime import datetime, timedelta, timezone
import pandas as pd

# ======== CONFIGURAÇÃO ========
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
AUTH_CODE = os.getenv("STRAVA_AUTH_CODE")

# Obter o access token
token_url = "https://www.strava.com/oauth/token"
payload = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "code": AUTH_CODE,
    "grant_type": "authorization_code"
}

print("🔑 A obter token de acesso do Strava...")
r = requests.post(token_url, data=payload)
if r.status_code != 200:
    print("❌ Erro ao obter token:", r.text)
    exit(1)
token_data = r.json()
ACCESS_TOKEN = token_data["access_token"]

# Buscar as atividades
headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
activities_url = f"https://www.strava.com/api/v3/athlete/activities"

params = {"after": int(one_week_ago.timestamp()), "per_page": 100}

print("📡 A descarregar atividades da última semana...")
res = requests.get(activities_url, headers=headers, params=params)

if res.status_code == 200:
    data = res.json()
    os.makedirs("strava_exports", exist_ok=True)
    file_path = f"strava_exports/strava_export_{datetime.now().strftime('%Y%m%d')}.csv"
    pd.DataFrame(data).to_csv(file_path, index=False)
    print(f"✅ Export concluído: {file_path}")
else:
    print("❌ Erro ao buscar atividades:", res.status_code, res.text)
