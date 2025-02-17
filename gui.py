import os
import subprocess

# Check if running on Render (no display environment)
if os.getenv("RENDER"):
    print("Running on Render - Starting Flask Server Automatically")
    subprocess.run(["gunicorn", "-k", "eventlet", "-w", "1", "--timeout", "50", "app:app"])
else:
    import tkinter as tk
    from tkinter import scrolledtext
    import threading

    class FlaskGUI:
        def __init__(self, root):
            self.root = root
            self.root.title("Flask Backend Monitor")
            self.root.geometry("600x400")
            self.root.configure(bg="gray")

            self.label = tk.Label(root, text="Flask Backend Status", font=("Arial", 12, "bold"), bg="gray", fg="black")
            self.label.pack(pady=5)

            self.start_button = tk.Button(root, text="Start Flask Server", command=self.start_flask_backend, bg="green", fg="white")
            self.start_button.pack(pady=5)

            self.stop_button = tk.Button(root, text="Stop Flask Server", command=self.stop_flask_backend, bg="red", fg="white")
            self.stop_button.pack(pady=5)

            self.log_text = scrolledtext.ScrolledText(root, height=20, width=70, bg="black", fg="green", font=("Courier", 10))
            self.log_text.pack(pady=5)

            self.process = None

        def start_flask_backend(self):
            if self.process is None:
                self.log_text.insert(tk.END, "Starting Flask Server...\n")
                self.process = subprocess.Popen(
                    ["python", "app.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                threading.Thread(target=self.read_output, daemon=True).start()

        def stop_flask_backend(self):
            if self.process:
                self.process.terminate()
                self.process = None
                self.log_text.insert(tk.END, "Flask Server Stopped.\n")
                self.log_text.see(tk.END)

        def read_output(self):
            while True:
                line = self.process.stdout.readline()
                if not line:
                    break
                self.log_text.insert(tk.END, line)
                self.log_text.see(tk.END)

    if __name__ == "__main__":
        root = tk.Tk()
        app = FlaskGUI(root)
        root.mainloop()