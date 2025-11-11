import os
import glob
import smtplib
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
import pandas as pd
import numpy as np

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

def prepare_daily_tss(df):
    if "start_date_local" not in df.columns:
        return pd.Series(dtype=float)
    if "tss" not in df.columns:
        df["tss"] = 0
    df["date"] = pd.to_datetime(df["start_date_local"], errors="coerce").dt.date
    df = df.dropna(subset=["date"])
    daily = df.groupby("date")["tss"].sum().asfreq("D", fill_value=0)
    return daily

def compute_performance_metrics(daily):
    # CTL (42d), ATL (7d) — média móvel exponencial
    ctl = daily.ewm(span=42, adjust=False).mean()
    atl = daily.ewm(span=7, adjust=False).mean()
    form = ctl - atl
    return round(ctl.iloc[-1],1), round(atl.iloc[-1],1), round(form.iloc[-1],1)

def build_load_chart(daily):
    if daily.empty:
        return "(sem dados de TSS)"
    daily = daily.tail(14)
    max_tss = max(daily.max(), 1)
    chart = "Gráfico de carga (TSS/dia):\n\n"
    for d, t in daily.items():
        bars = "█" * int((t / max_tss) * 30)
        chart += f"{d.strftime('%a %d/%m')} | {bars} {int(t)}\n"
    return chart

def format_email(summary, chart, ctl, atl, form):
    trend = "🟢 em forma" if form > -10 else "🟡 equilíbrio" if -25 < form <= -10 else "🔴 fadiga acumulada"
    html = f"""
    <html><body style="font-family:Arial,sans-serif;">
    <h2>📊 Relatório semanal — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}</h2>
    <p><b>Resumo da última semana</b></p>
    <ul>
      <li>Atividades: {summary.get('n_activities')}</li>
      <li>Horas totais: {summary.get('total_hours')} h</li>
      <li>Distância total: {summary.get('total_distance_km')} km</li>
      <li>TSS total: {summary.get('total_tss')}</li>
    </ul>
    <p><b>Performance atual (PMC)</b></p>
    <ul>
      <li>CTL (fitness, 42 d): <b>{ctl}</b></li>
      <li>ATL (fatigue, 7 d): <b>{atl}</b></li>
      <li>Form (freshness): <b>{form}</b> → {trend}</li>
    </ul>
    <pre style="font-family:monospace;background:#f4f4f4;padding:10px;border-radius:6px;">{chart}</pre>
    <p>Abraço,<br><i>Road-to-Power</i></p>
    </body></html>
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
        print("Nenhum ficheiro Strava encontrado.")
        return
    print("A usar:", csv)
    df = pd.read_csv(csv)
    summary = summarize(df)
    daily = prepare_daily_tss(df)
    chart = build_load_chart(daily)
    ctl, atl, form = compute_performance_metrics(daily)
    html_body = format_email(summary, chart, ctl, atl, form)
    subject = f"📊 Relatório semanal — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    send_email(subject, html_body)

if __name__ == "__main__":
    main()
