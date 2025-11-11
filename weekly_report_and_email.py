import os
import glob
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
import pandas as pd

# ---------- CONFIG ----------
EXPORT_DIR = "strava_exports"
SENDER = os.getenv("SENDER_EMAIL")
TO = os.getenv("EMAIL_TO")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

# ---------- FUNÇÕES ----------
def latest_export_csv():
    files = sorted(glob.glob(os.path.join(EXPORT_DIR, "strava_export_*.csv")), reverse=True)
    return files[0] if files else None

def summarize(df):
    summary = {"n_activities": len(df)}
    total_seconds = df.get("moving_time", pd.Series()).sum()
    summary["total_hours"] = round((total_seconds or 0)/3600, 2)
    summary["total_distance_km"] = round(df.get("distance", pd.Series()).sum()/1000.0, 1) if "distance" in df.columns else None
    summary["total_tss"] = round(df.get("tss", pd.Series()).sum(), 1) if "tss" in df.columns else None
    return summary

def build_load_chart(df):
    if "start_date_local" not in df.columns:
        return "(sem dados de data)"
    if "tss" not in df.columns:
        df["tss"] = 0

    df["date"] = pd.to_datetime(df["start_date_local"], errors="coerce").dt.date
    df = df.dropna(subset=["date"])
    daily = df.groupby("date")["tss"].sum().tail(14)  # últimas 2 semanas
    if daily.empty:
        return "(sem dados de TSS)"
    max_tss = max(daily.max(), 1)
    chart = "Gráfico de carga (TSS/dia):\n\n"
    for d, t in daily.items():
        bars = "█" * int((t / max_tss) * 30)
        chart += f"{d.strftime('%a %d/%m')} | {bars} {int(t)}\n"
    return chart

def format_email(summary, chart):
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
    <h2>📊 Relatório semanal — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}</h2>
    <p><b>Resumo da última semana</b></p>
    <ul>
      <li>Atividades: {summary.get('n_activities')}</li>
      <li>Horas totais: {summary.get('total_hours')} h</li>
      <li>Distância total: {summary.get('total_distance_km')} km</li>
      <li>TSS total: {summary.get('total_tss')}</li>
    </ul>
    <pre style="font-family: monospace; background:#f4f4f4; padding:10px; border-radius:6px;">{chart}</pre>
    <p>Abraço,<br><i>Road-to-Power</i></p>
    </body>
    </html>
    """
    return html

def send_email(subject, html_body):
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = TO
    msg["Subject"] = subject
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        print("✅ E-mail enviado com sucesso para", TO)
    except Exception as e:
        print("❌ Erro ao enviar e-mail:", e)

def main():
    csv = latest_export_csv()
    if not csv:
        print("Nenhum ficheiro Strava encontrado em", EXPORT_DIR)
        return

    print("A usar:", csv)
    df = pd.read_csv(csv)
    summary = summarize(df)
    chart = build_load_chart(df)
    html_body = format_email(summary, chart)
    subject = f"📊 Relatório semanal — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    send_email(subject, html_body)

if __name__ == "__main__":
    main()
