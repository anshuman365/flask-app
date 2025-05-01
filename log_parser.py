# log_parser.py

import re
import time
import smtplib
from email.mime.text import MIMEText
from threading import Thread, Lock
from datetime import datetime

LOG_FILE = "access.log"
EMAIL_INTERVAL = 7200  # 2 hours

# Email config
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_FROM = "nexoraindustries@gmail.com"
EMAIL_PASSWORD = "qvwi hqax ehqx hsgw"
EMAIL_TO = "sarvarsingh496@gmail.com"

# Updated regex to handle all log formats
#log_pattern = re.compile(
#    r'(?P<ip>\S+) - - \[(?P<timestamp>.*?)\] "(?P<method>\w+) (?P<path>\S+).*?" (?P<status>\d+) (?P<size>\d+|-) "(?P<referrer>.*?)" "(?P<agent>.*?)"'
#)
# Update the regex pattern
log_pattern = re.compile(
    r'(?P<ip>\S+) - - \[(?P<timestamp>.+?)\] "(?P<method>\w+) (?P<path>\S+).*?" (?P<status>\d+) (?P<size>\d+|-) "(?P<referrer>.*?)" "(?P<agent>.*?)"'
)


log_storage = []
log_lock = Lock()

def parse_log():
    try:
        with open(LOG_FILE, "r") as file:
            lines = file.readlines()
    except FileNotFoundError:
        return []

    new_entries = []
    for line in lines:
        line = line.strip()
        if not line or " - - [" not in line:
            continue  # Skip empty lines and non-request logs

        match = log_pattern.match(line)
        if match:
            try:
                # Parse timestamp (ignore timezone)
                timestamp_str = match.group("timestamp").split()[0]
                timestamp = datetime.strptime(timestamp_str, "%d/%b/%Y:%H:%M:%S")
                
                new_entries.append({
                    "time": timestamp,
                    "method": match.group("method"),
                    "path": match.group("path"),
                    "status": int(match.group("status")),
                    "agent": match.group("agent"),
                    "ip": match.group("ip")
                })
            except Exception as e:
                print(f"Failed to parse log line: {line}\nError: {e}")
    return new_entries

def get_and_clear_logs():
    global log_storage
    with log_lock:
        logs = list(log_storage)
        log_storage.clear()
        return logs

def send_email(logs):
    if not logs:
        return False
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
            return True
    except Exception as e:
        print("[EMAIL ERROR]", e)
        return False

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