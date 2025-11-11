# weekly_report_and_email.py
import os
import glob
import smtplib
import json
from datetime import datetime, timedelta
from email.message import EmailMessage

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ---------- CONFIG ----------
EXPORT_DIR = "strava_exports"
PDF_PREFIX = "weekly_report_"
LONG_RIDE_DAY = os.getenv("LONG_RIDE_DAY", "Sunday")  # "Sunday" or "Saturday"
SENDER = os.getenv("SENDER_EMAIL")
TO = os.getenv("EMAIL_TO")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
ATHLETE_FTP = os.getenv("ATHLETE_FTP")  # optional

# ---------- HELPERS ----------
def latest_export_csv():
    files = sorted(glob.glob(os.path.join(EXPORT_DIR, "strava_export_*.csv")), reverse=True)
    return files[0] if files else None

def read_activities(csv_path):
    try:
        df = pd.read_csv(csv_path)
        return df
    except Exception as e:
        print("Erro a ler CSV:", e)
        return pd.DataFrame()

def summarize(df):
    summary = {"n_activities": 0, "total_hours": 0.0, "total_distance_km": None, "total_tss": None,
               "best_20min": None, "np_mean": None, "if_mean": None}
    if df.empty:
        return summary

    summary["n_activities"] = len(df)

    # Moving time: Strava usually uses 'moving_time' in seconds
    if "moving_time" in df.columns:
        total_seconds = df["moving_time"].sum()
    elif "elapsed_time" in df.columns:
        total_seconds = df["elapsed_time"].sum()
    else:
        total_seconds = df.get("duration", pd.Series()).sum()

    summary["total_hours"] = round((total_seconds or 0) / 3600.0, 2)

    if "distance" in df.columns:
        summary["total_distance_km"] = round(df["distance"].sum() / 1000.0, 1)

    # TSS can be absent; check common names
    if "tss" in df.columns:
        summary["total_tss"] = round(df["tss"].sum(), 1)
    elif "workout_tss" in df.columns:
        summary["total_tss"] = round(df["workout_tss"].sum(), 1)

    # NP / weighted_average_watts / average_watts
    if "weighted_average_watts" in df.columns:
        summary["np_mean"] = round(df["weighted_average_watts"].mean(), 1)
    elif "average_watts" in df.columns:
        summary["np_mean"] = round(df["average_watts"].mean(), 1)

    # IF not always present; if np_mean and FTP known, compute IF mean
    try:
        if summary["np_mean"] and ATHLETE_FTP:
            summary["if_mean"] = round(summary["np_mean"] / float(ATHLETE_FTP), 2)
    except Exception:
        summary["if_mean"] = None

    # best 20' approximation: if 'max_power' windows don't exist, fallback to weighted_average_watts
    if "weighted_average_watts" in df.columns:
        summary["best_20min"] = round(df["weighted_average_watts"].max(), 1)

    return summary

def prescribe_week(summary):
    plan = []
    notes = []
    fatigue_flag = False
    if summary.get("total_tss") is not None and summary["total_tss"] > 700:
        fatigue_flag = True

    plan.append(("Segunda", "Descanso / recuperação ativa (opcional 30–45' suave)"))

    if fatigue_flag:
        tuesday = "2h — resistência aeróbica zona 2, intensidade -10% (sessão mais leve)"
    else:
        tuesday = "2h — treino intervalado: 4x12' zona 3–4 com 8' recuperação (séries foco resistência/threshold)"

    plan.append(("Terça", tuesday))
    plan.append(("Quarta", "Rolo 60–90' — técnica, cadência e mobilidade; incluir 3x6' força sentado a baixa cadência"))
    if fatigue_flag:
        thursday = "2h — rotação suave/tempo zona 2 com 2 blocos curtos em zona 3"
    else:
        thursday = "2h — 6x5' em zona 4 com 5' recuperação"
    plan.append(("Quinta", thursday))
    plan.append(("Sexta", "Rolo 60' — recuperação ativa + mobilidade"))

    # Sábado opcional / Domingo long
    if LONG_RIDE_DAY.lower().startswith("s"):
        # saturday long, sunday easy
        plan.append(("Sábado", "4h — treino longo (3 blocos de 30' em zona 3, restante zona 2)"))
        plan.append(("Domingo", "Descanso / passeio suave 1.5–2h"))
    else:
        plan.append(("Sábado", "Opcional: passeio suave 1.5–2h ou descanso"))
        plan.append(("Domingo", "4h — treino longo (3 blocos de 30' em zona 3, restante zona 2)"))

    if fatigue_flag:
        notes.append("Semana anterior com carga elevada → reduzir intensidades indicadas em ~10–20% e priorizar sono/nutrição.")
    else:
        notes.append("Plano baseado na carga da última semana. Ajusta se sentires fadiga acumulada.")

    if summary.get("best_20min"):
        notes.append(f"Último melhor 20': {summary['best_20min']} W — usar como referência para zonas de threshold.")

    return plan, notes

def generate_pdf(summary, plan, notes, outpath):
    c = canvas.Canvas(outpath, pagesize=A4)
    w, h = A4
    margin = 40
    y = h - margin

    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, f"Relatório semanal — {datetime.now().strftime('%Y-%m-%d')}")
    y -= 26
    c.setFont("Helvetica", 11)
    c.drawString(margin, y, f"Atividades na última semana: {summary.get('n_activities')}, Horas totais: {summary.get('total_hours')}h")
    y -= 16
    if summary.get("total_distance_km") is not None:
        c.drawString(margin, y, f"Distância total: {summary.get('total_distance_km')} km")
        y -= 16
    if summary.get("total_tss") is not None:
        c.drawString(margin, y, f"TSS total: {summary.get('total_tss')}")
        y -= 16
    if summary.get("np_mean") is not None:
        c.drawString(margin, y, f"NP médio (aprox): {summary.get('np_mean')} W")
        y -= 16
    if summary.get("if_mean") is not None:
        c.drawString(margin, y, f"IF médio (aprox): {summary.get('if_mean')}")
        y -= 16

    y -= 8
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Prescrição da semana seguinte")
    y -= 18
    c.setFont("Helvetica", 10)
    for day, text in plan:
        c.drawString(margin, y, f"{day}: {text}")
        y -= 14
        if y < 80:
            c.showPage()
            y = h - margin

    y -= 8
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Notas")
    y -= 14
    c.setFont("Helvetica", 9)
    for n in notes:
        c.drawString(margin, y, f"- {n}")
        y -= 12
        if y < 60:
            c.showPage()
            y = h - margin
    c.save()

def send_email(subject, body, pdf_path):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not SENDER or not TO:
        print("SMTP ou emails não configurados. Cancelando envio.")
        return False

    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = TO
    msg["Subject"] = subject
    msg.set_content(body)

    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            data = f.read()
        msg.add_attachment(data, maintype="application", subtype="pdf", filename=os.path.basename(pdf_path))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        print("✅ Email enviado para", TO)
        return True
    except Exception as e:
        print("Erro ao enviar e-mail:", e)
        return False

# ---------- MAIN ----------
def main():
    csv = latest_export_csv()
    if not csv:
        print("Nenhum export Strava encontrado em", EXPORT_DIR, ". Cancelling.")
        return

    print("Usando CSV:", csv)
    df = read_activities(csv)
    summary = summarize(df)
    plan, notes = prescribe_week(summary)

    pdf_out = f"{PDF_PREFIX}{datetime.now().strftime('%Y%m%d')}.pdf"
    generate_pdf(summary, plan, notes, pdf_out)
    print("PDF gerado:", pdf_out)

    subject = f"Relatório semanal — {datetime.now().strftime('%Y-%m-%d')}"
    body_lines = [
        f"Olá {os.getenv('GONCALO_NAME','Gonçalo')},",
        "",
        f"Aqui vai o resumo da última semana:",
        f"- Número de sessões: {summary.get('n_activities')}",
        f"- Horas totais: {summary.get('total_hours')} h",
    ]
    if summary.get("total_distance_km") is not None:
        body_lines.append(f"- Distância total: {summary.get('total_distance_km')} km")
    if summary.get("total_tss") is not None:
        body_lines.append(f"- TSS total: {summary.get('total_tss')}")
    body_lines.append("")
    body_lines.append("Plano da semana seguinte:")
    for day, text in plan:
        body_lines.append(f"- {day}: {text}")
    body_lines.append("")
    for n in notes:
        body_lines.append(n)
    body = "\n".join(body_lines)

    sent = send_email(subject, body, pdf_out)
    if not sent:
        print("Falhou o envio do e-mail. O PDF foi gerado localmente:", pdf_out)

if __name__ == "__main__":
    main()
