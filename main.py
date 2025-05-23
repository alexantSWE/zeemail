import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from tkinter import messagebox
import json
import smtplib
from email.mime.text import MIMEText

CONFIG_FILE = "email_config.json"
current_config = {"email": "", "app_password": ""}

# --- Main Window Setup ---
root = tk.Tk()
root.title("Simple Email Sender")
root.geometry("600x500")

# --- StringVars for Entry Fields ---
status_var = tk.StringVar()
to_entry_var = tk.StringVar()
subject_entry_var = tk.StringVar()

# -------------------------------------------------------------------------
# ALL FUNCTION DEFINITIONS MUST COME BEFORE THEY ARE USED BY WIDGETS
# -------------------------------------------------------------------------

# --- Configuration Functions ---
def load_config():
    """Loads email configuration from CONFIG_FILE."""
    global current_config
    try:
        with open(CONFIG_FILE, "r") as f:
            loaded_data = json.load(f)
            if isinstance(loaded_data, dict) and "email" in loaded_data and "app_password" in loaded_data:
                current_config = loaded_data
                if status_var:
                    status_var.set(f"Configuration loaded for {current_config.get('email', 'N/A')}")
                return True
            else:
                if status_var:
                    status_var.set("Error: Config file has incorrect format. Please re-configure.")
                current_config = {"email": "", "app_password": ""}
                return False
    except FileNotFoundError:
        if status_var:
            status_var.set("Configuration file not found. Please configure your account.")
    except json.JSONDecodeError:
        if status_var:
            status_var.set("Error: Configuration file is corrupted. Please re-configure.")
    except Exception as e:
        if status_var:
            status_var.set(f"Error loading config: {e}")
    current_config = {"email": "", "app_password": ""}
    return False

def save_config(email, app_password):
    """Saves email configuration to CONFIG_FILE."""
    global current_config
    config_data = {"email": email, "app_password": app_password}
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
        current_config = config_data
        if status_var:
            status_var.set(f"Configuration saved for {email}")
        messagebox.showinfo("Configuration Saved", "Email account configuration has been saved.", parent=root) # Good to specify parent
        return True
    except Exception as e:
        if status_var:
            status_var.set(f"Error saving config: {e}")
        messagebox.showerror("Error", f"Could not save configuration: {e}", parent=root) # Good to specify parent
        return False

def open_config_window():
    """Opens a Toplevel window to configure email account."""
    config_window = tk.Toplevel(root)
    config_window.title("Configure Email Account")
    config_window.geometry("450x300") # Slightly taller for instructions
    config_window.transient(root)
    config_window.grab_set()

    instructions = (
        "For Gmail, you need an 'App Password'.\n"
        "1. Go to your Google Account (myaccount.google.com).\n"
        "2. Go to 'Security'.\n"
        "3. Ensure '2-Step Verification' is ON.\n"
        "4. Find 'App passwords' (might need to search for it).\n"
        "5. Generate: App: 'Mail', Device: 'Other (Custom name)'.\n"
        "   Name it (e.g., 'MyPythonMailer') and click Generate.\n"
        "6. Copy the 16-character password (no spaces) below."
    )
    ttk.Label(config_window, text=instructions, justify=tk.LEFT, wraplength=430).pack(pady=(10,5))

    form_frame = ttk.Frame(config_window)
    form_frame.pack(padx=10, pady=5, fill="x", expand=True)

    ttk.Label(form_frame, text="Email Address:").grid(row=0, column=0, sticky="w", pady=2)
    email_var_config = tk.StringVar(value=current_config.get("email", ""))
    email_entry_config = ttk.Entry(form_frame, textvariable=email_var_config, width=40)
    email_entry_config.grid(row=0, column=1, sticky="ew", pady=2)

    ttk.Label(form_frame, text="App Password:").grid(row=1, column=0, sticky="w", pady=2)
    password_var_config = tk.StringVar(value=current_config.get("app_password", ""))
    password_entry_config = ttk.Entry(form_frame, textvariable=password_var_config, show="*", width=40)
    password_entry_config.grid(row=1, column=1, sticky="ew", pady=2)

    form_frame.columnconfigure(1, weight=1)

    def on_save_config(): # Renamed to avoid conflict if a global 'on_save' existed
        email = email_var_config.get()
        app_pwd = password_var_config.get()
        if not email or "@" not in email or not app_pwd:
            messagebox.showerror("Input Error", "Please enter both email and App Password.", parent=config_window)
            return
        if save_config(email, app_pwd):
            config_window.destroy()

    button_frame = ttk.Frame(config_window)
    button_frame.pack(pady=10)
    ttk.Button(button_frame, text="Save", command=on_save_config).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=config_window.destroy).pack(side=tk.LEFT, padx=5)

    email_entry_config.focus_set()
    config_window.wait_window()


# --- Email Sending Function ---
def send_email_action():
    if not current_config or not current_config.get("email") or not current_config.get("app_password"):
        status_var.set("Error: Email account not configured. Please configure first.")
        messagebox.showerror("Configuration Error", "Email account is not configured. Please use 'Configure Account'.", parent=root)
        return

    sender_email = current_config["email"]
    app_password = current_config["app_password"]

    to_email = to_entry_var.get()
    subject = subject_entry_var.get()
    message_body = message_text.get("1.0", f"{tk.END}-1c")
    # OR this also works:
    # message_body = message_text.get("1.0", "end-1c")

    if not to_email or "@" not in to_email:
        status_var.set("Error: Please enter a valid 'To' email address.")
        messagebox.showwarning("Input Error", "Please enter a valid 'To' email address.", parent=root)
        return
    if not subject:
        status_var.set("Error: Please enter a subject.")
        messagebox.showwarning("Input Error", "Please enter a subject for the email.", parent=root)
        return
    if not message_body:
        status_var.set("Error: Please enter a message.")
        messagebox.showwarning("Input Error", "Please enter a message body.", parent=root)
        return

    status_var.set(f"Sending to: {to_email}...")
    root.update_idletasks()

    try:
        msg = MIMEText(message_body)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = to_email

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        
        status_var.set(f"Email sent successfully to {to_email}!")
        messagebox.showinfo("Success", f"Email sent to {to_email}", parent=root)

    except smtplib.SMTPAuthenticationError:
        status_var.set("Error: SMTP Authentication failed. Check email/App Password.")
        messagebox.showerror("Authentication Error", "Failed to authenticate with Gmail. Please check your email and App Password in configuration. Ensure 2-Step Verification is ON and the App Password is correct.", parent=root)
    except smtplib.SMTPConnectError:
        status_var.set("Error: Could not connect to Gmail SMTP server.")
        messagebox.showerror("Connection Error", "Could not connect to Gmail's SMTP server. Check your internet connection.", parent=root)
    except Exception as e:
        status_var.set(f"Error sending email: {e}")
        messagebox.showerror("Sending Error", f"An unexpected error occurred: {e}", parent=root)

# -------------------------------------------------------------------------
# END OF FUNCTION DEFINITIONS
# -------------------------------------------------------------------------

# --- SET THE WINDOW ICON / LOGO ---
try:
    app_icon = tk.PhotoImage(file='logo.gif')
    root.iconphoto(False, app_icon)
except Exception as e:
    print(f"Could not load logo.gif: {e}")

# --- Load initial configuration ---
load_config() # Now all functions, including status_var, are defined

# --- Configure Grid Layout ---
root.columnconfigure(1, weight=1)
root.rowconfigure(3, weight=1)

# --- Set initial status_var text AFTER load_config ---
if not current_config.get("email"):
    if not status_var.get():
        status_var.set("Ready. Please configure your email account.")
elif not status_var.get():
    status_var.set(f"Ready. Configured as {current_config.get('email')}.")


# --- Widgets ---
# (This block is now AFTER all function definitions)

# Row 0: Configure Account Button
configure_button = ttk.Button(root, text="Configure Account", command=open_config_window) # Now open_config_window is defined
configure_button.grid(row=0, column=1, padx=10, pady=10, sticky="e")

# Row 1: "To" field
to_label = ttk.Label(root, text="To:")
to_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
to_entry = ttk.Entry(root, textvariable=to_entry_var, width=50)
to_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

# Row 2: "Subject" field
subject_label = ttk.Label(root, text="Subject:")
subject_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
subject_entry = ttk.Entry(root, textvariable=subject_entry_var, width=50)
subject_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

# Row 3: "Message" Label and Text Area
message_label = ttk.Label(root, text="Message:")
message_label.grid(row=3, column=0, padx=10, pady=5, sticky="nw")
message_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=60, height=15)
message_text.grid(row=3, column=1, padx=10, pady=5, sticky="nsew")

# Row 4: "Send" Button
send_button = ttk.Button(root, text="Send Email", command=send_email_action) # send_email_action is also defined before use
send_button.grid(row=4, column=1, padx=10, pady=10, sticky="e")

# Row 5: Status Label
status_label_widget = ttk.Label(root, textvariable=status_var, relief=tk.SUNKEN, anchor="w")
status_label_widget.grid(row=5, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

to_entry.focus_set()
root.mainloop()