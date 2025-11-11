import requests
import os
import json
import pandas as pd
from datetime import datetime, timedelta, timezone

# ======== CONFIGURAÇÃO ========
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
AUTH_CODE = os.getenv("STRAVA_AUTH_CODE")

TOKEN_FILE = "strava_token.json"

def get_token():
    """Obtém o access token do ficheiro ou via refresh/auth code"""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token_data = json.load(f)
        # Verificar se o token ainda é válido
        expires_at = token_data.get("expires_at", 0)
        if expires_at > datetime.now(timezone.utc).timestamp():
            print("✅ Token válido encontrado.")
            return token_data["access_token"]

        # Caso contrário, fazer refresh
        print("🔁 Token expirado. A refrescar...")
        refresh_payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": token_data["refresh_token"]
        }
        res = requests.post("https://www.strava.com/oauth/token", data=refresh_payload)
        if res.status_code == 200:
            new_token = res.json()
            with open(TOKEN_FILE, "w") as f:
                json.dump(new_token, f)
            print("✅ Token atualizado via refresh token.")
            return new_token["access_token"]
        else:
            print("❌ Erro ao refrescar token:", res.text)
            exit(1)
    else:
        # Primeira execução (sem token guardado)
        print("🆕 A obter token inicial a partir do AUTH_CODE...")
        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": AUTH_CODE,
            "grant_type": "authorization_code"
        }
        res = requests.post("https://www.strava.com/oauth/token", data=payload)
        if res.status_code == 200:
            token_data = res.json()
            with open(TOKEN_FILE, "w") as f:
                json.dump(token_data, f)
            print("✅ Token inicial guardado.")
            return token_data["access_token"]
        else:
            print("❌ Erro ao obter token inicial:", res.text)
            exit(1)

def export_activities(access_token):
    """Exporta as atividades da última semana"""
    headers = {"Authorization": f"Bearer {access_token}"}
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    activities_url = "https://www.strava.com/api/v3/athlete/activities"
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
        exit(1)

if __name__ == "__main__":
    token = get_token()
    export_activities(token)
