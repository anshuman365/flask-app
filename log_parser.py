# log_parser.py

import re
import time
import smtplib
from email.mime.text import MIMEText
from threading import Thread, Lock
from datetime import datetime

LOG_FILE = "access.log"  # path to your Flask log file
EMAIL_INTERVAL = 7200  # 2 hours in seconds

# Email config
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_FROM = "nexoraindustries@gmail.com"
EMAIL_PASSWORD = "qvwi hqax ehqx hsgw"  # Use an app-specific password
EMAIL_TO = "sarvarsingh496@example.com"

log_pattern = re.compile(
    r'(?P<ip>[\d.]+) - - (?P<timestamp>[^]+) "(?P<method>\w+) (?P<path>[^ ]+) [^"]+" (?P<status>\d+) (?P<size>\d+) "(?P<referrer>[^"]*)" "(?P<agent>[^"]+)"'
)

log_storage = []
log_lock = Lock()

def parse_log():
    f=open(LOG_FILE, "a") 
    f.close()
    with open(LOG_FILE, "r") as file:
        lines = file.readlines()
    new_entries = []
    for line in lines:
        match = log_pattern.match(line)
        if match:
            timestamp_str = match.group("timestamp").split()[0]
            timestamp = datetime.strptime(timestamp_str, "%d/%b/%Y:%H:%M:%S")
            new_entries.append({
                "time": timestamp,
                "method": match.group("method"),
                "path": match.group("path"),
                "status": match.group("status"),
                "agent": match.group("agent"),
                "referrer": match.group("referrer"),
                "ip": match.group("ip")
            })
    return new_entries

def send_email(logs):
    if not logs:
        return
    body = "\n".join(
        f"{entry['time']} - {entry['ip']} - {entry['method']} {entry['path']} - {entry['status']} - {entry['agent']}"
        for entry in logs
    )
    msg = MIMEText(body)
    msg['Subject'] = f"Flask Access Logs - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)
            print(f"[EMAIL SENT] {len(logs)} entries sent.")
    except Exception as e:
        print("[EMAIL ERROR]", e)

def monitor_logs():
    last_sent_time = time.time()
    last_log_count = 0
    while True:
        time.sleep(10)
        with log_lock:
            logs = parse_log()
            new_logs = logs[last_log_count:]
            log_storage.extend(new_logs)
            last_log_count = len(logs)
        if time.time() - last_sent_time >= EMAIL_INTERVAL:
            with log_lock:
                logs_to_send = list(log_storage)
                log_storage.clear()
            send_email(logs_to_send)
            last_sent_time = time.time()