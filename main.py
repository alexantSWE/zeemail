import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from tkinter import messagebox
import json
import smtplib
from email.mime.text import MIMEText
import logging

# Keyring and DNS libraries
import keyring
import keyring.errors
try:
    import dns.resolver
    import dns.exception
    DNS_PYTHON_AVAILABLE = True
except ImportError:
    DNS_PYTHON_AVAILABLE = False
    print("Warning: dnspython library not found. Recipient email domain check will be disabled.")

# --- Constants ---
APP_SETTINGS_FILE = "app_settings.json"  # Stores non-sensitive settings
SERVICE_NAME = "zeemailer"    # Unique name for our app in keyring, let's set something that makes sense?

# --- Global Configuration Holder ---
# Initialize with defaults
current_config = {
    "email": "",
    "app_password": None,  # Loaded from keyring
    "check_recipient_existence": True if DNS_PYTHON_AVAILABLE else False
}

# --- Main Window Setup ---
root = tk.Tk()
_is_root_fully_initialized = False # Flag
root.title("ZeeMail - an email sender")
# Adjust geometry as needed, slightly taller for menu and status
root.geometry("600x550")

# --- StringVars for Entry Fields ---
status_var = tk.StringVar()
to_entry_var = tk.StringVar()
subject_entry_var = tk.StringVar()

# -------------------------------------------------------------------------
# HELPER & CORE LOGIC FUNCTIONS
# -------------------------------------------------------------------------

def save_app_preferences():
    """Saves non-sensitive application preferences to APP_SETTINGS_FILE."""
    global current_config
    prefs_to_save = {
        "email": current_config.get("email", ""),
        "check_recipient_existence": current_config.get("check_recipient_existence", True if DNS_PYTHON_AVAILABLE else False)
        # Add other non-sensitive settings here in the future
    }
    try:
        with open(APP_SETTINGS_FILE, "w") as f:
            json.dump(prefs_to_save, f, indent=4)
        print("App preferences saved.")
        return True
    except Exception as e:
        messagebox.showerror("Error", f"Could not save app preferences: {e}", parent=root)
        print(f"Error saving app preferences: {e}")
        return False

# OLD_SERVICE_NAME = "MyPythonSimpleMailer"
SERVICE_NAME = "zeemailer"  # Your NEW, current service name

# ... (other imports and constants) ...

      
      
def load_config_keyring():
    """Loads email and settings from APP_SETTINGS_FILE, and App Password from keyring."""
    global current_config
    # Reset to defaults
    current_config["email"] = ""
    current_config["app_password"] = None
    current_config["check_recipient_existence"] = True if DNS_PYTHON_AVAILABLE else False
    
    logging.info(f"Attempting to load configuration. Current SERVICE_NAME: '{SERVICE_NAME}'")

    settings_file_found_and_parsed = False
    try:
        with open(APP_SETTINGS_FILE, "r") as f:
            settings = json.load(f)
            if isinstance(settings, dict):
                current_config["email"] = settings.get("email", "")
                check_setting = settings.get("check_recipient_existence")
                if isinstance(check_setting, bool):
                    current_config["check_recipient_existence"] = check_setting and DNS_PYTHON_AVAILABLE
                elif check_setting is not None and DNS_PYTHON_AVAILABLE: # Handles non-bool existing setting
                     logging.warning(f"'check_recipient_existence' in {APP_SETTINGS_FILE} is not a boolean. Using default True (if DNS available).")
                     current_config["check_recipient_existence"] = True # Default to True if DNS available, even if setting was bad
                # If DNS_PYTHON_AVAILABLE is False, current_config["check_recipient_existence"] remains False
                
                settings_file_found_and_parsed = True # Mark as successfully parsed
                logging.info(f"App settings loaded from {APP_SETTINGS_FILE}. Email: '{current_config['email']}', CheckRec: {current_config['check_recipient_existence']}")
            else: # File exists, but content is not a dict
                status_var.set("App settings file has incorrect format. Please re-configure.")
                logging.warning(f"App settings file '{APP_SETTINGS_FILE}' has incorrect format (not a dictionary).")
    except FileNotFoundError:
        # This is an expected condition on first run or if file is deleted
        status_var.set("App settings not found. Please configure your account.")
        logging.info(f"App settings file '{APP_SETTINGS_FILE}' not found. This is normal for a first run.")
        # No further action needed here, defaults will be used, settings_file_found_and_parsed remains False
    except json.JSONDecodeError:
        # File exists but is not valid JSON
        status_var.set("Error: App settings file is corrupted. Please re-configure.")
        logging.warning(f"Failed to decode JSON from app settings file: {APP_SETTINGS_FILE}", exc_info=True)
        # settings_file_found_and_parsed remains False
    except Exception as e:
        # Other unexpected errors during file reading/parsing
        status_var.set(f"Error loading app settings: {e}")
        logging.error(f"Unexpected error loading app settings from {APP_SETTINGS_FILE}: {e}", exc_info=True)
        # settings_file_found_and_parsed remains False

    # --- Keyring part ---
    if current_config["email"]: # Only try keyring if we have an email (from settings file or potentially old config)
        logging.info(f"Attempting to retrieve password from keyring for email '{current_config['email']}' using service '{SERVICE_NAME}'.")
        try:
            retrieved_password = keyring.get_password(SERVICE_NAME, current_config["email"])
            
            if retrieved_password:
                current_config["app_password"] = retrieved_password
                status_var.set(
                    f"Configured for {current_config['email']} (Pwd from keyring, Check Rec: {current_config['check_recipient_existence']})"
                )
                logging.info(f"Password successfully retrieved from keyring for {current_config['email']}.")
                return True 
            else: # Password not found in keyring for this email/service combination
                logging.warning(f"No password found in keyring for '{current_config['email']}' under service '{SERVICE_NAME}'.")
                status_var.set(f"App Password for {current_config['email']} not in keyring. Please re-configure.")
                if _is_root_fully_initialized: # Only show messagebox if root is ready
                    messagebox.showwarning(
                        "Re-configuration Needed",
                        f"The App Password for '{current_config['email']}' was not found in your system keyring "
                        f"for this application ('{SERVICE_NAME}').\n\n"
                        "Please re-configure your account.",
                        parent=root
                    )
                else:
                    print(f"CRITICAL STARTUP INFO: App Password for {current_config['email']} not in keyring. Please re-configure via UI.")


        except keyring.errors.NoKeyringError:
            status_var.set("Error: Keyring backend not found. Cannot securely load/store password.")
            logging.error("Keyring backend not found during password retrieval.", exc_info=True)
            if _is_root_fully_initialized:
                messagebox.showerror("Keyring Error", "No system keyring backend found. Please ensure one is installed and configured.", parent=root)
            else:
                print("CRITICAL STARTUP ERROR: Keyring backend not found. Check logs.")
        except Exception as e: 
            status_var.set(f"Error retrieving password from keyring: {e}")
            logging.error(f"Unexpected error retrieving password from keyring: {e}", exc_info=True)
            if _is_root_fully_initialized: 
                messagebox.showerror("Keyring Error", f"Could not retrieve password from keyring: {e}", parent=root)
            else:
                print(f"CRITICAL STARTUP ERROR: Keyring failed: {e}. Check logs and status bar.")
    
    elif settings_file_found_and_parsed and not current_config["email"]:
        # Settings file was read, but it didn't contain an email address.
        status_var.set("App settings found but no email specified. Please configure.")
        logging.info(f"App settings file '{APP_SETTINGS_FILE}' loaded, but no 'email' key found or email is empty.")
    
    # If not returned True by now, full config is not complete.
    # Set a general status if no specific error message has already been set.
    if not status_var.get(): 
        status_var.set("Ready. Please configure your email account.")
    
    return False

    
    


def save_config_keyring(email, app_password):
    """Saves email to APP_SETTINGS_FILE (via save_app_preferences) and App Password to keyring."""
    global current_config
    
    # Update current_config email before saving preferences
    current_config["email"] = email
    
    if not save_app_preferences(): # This saves email and check_recipient_existence
        # Error message already shown by save_app_preferences
        return False

    # Save password to keyring
    try:
        keyring.set_password(SERVICE_NAME, email, app_password)
        current_config["app_password"] = app_password # Update in-memory
        status_var.set(f"Config saved for {email} (Pwd in keyring, Check Rec: {current_config['check_recipient_existence']})")
        messagebox.showinfo("Configuration Saved", "Email account configuration has been saved securely.", parent=root)
        return True
    except keyring.errors.NoKeyringError:
        status_var.set("Error: Keyring backend not found. Password NOT saved securely.")
        messagebox.showerror("Keyring Error", "No system keyring. Password NOT saved securely. Install/configure a keyring.", parent=root)
    except keyring.errors.PasswordSetError:
        status_var.set("Error: Could not set password in keyring.")
        messagebox.showerror("Keyring Error", "Failed to set the password in the system keyring.", parent=root)
    except Exception as e:
        status_var.set(f"Error saving password to keyring: {e}")
        messagebox.showerror("Error", f"Could not save password to keyring: {e}", parent=root)
    return False

def check_email_domain_validity(email_address):
    """Checks for MX records (and A as fallback) for the email's domain."""
    if not DNS_PYTHON_AVAILABLE:
        print("DNS check skipped: dnspython library not available.")
        return True # Skip check if library is missing, assume valid

    if not email_address or "@" not in email_address:
        return False 

    domain = email_address.split('@')[-1]
    if not domain:
        return False

    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        if mx_records:
            print(f"MX records found for {domain}: {[r.exchange.to_text() for r in mx_records]}")
            return True
    except dns.resolver.NXDOMAIN:
        print(f"Domain {domain} does not exist (NXDOMAIN).")
        return False
    except dns.resolver.NoAnswer:
        print(f"No MX records found for {domain}. Trying A record...")
    except dns.exception.Timeout:
        print(f"DNS query for MX for {domain} timed out.")
        return False 
    except Exception as e:
        print(f"Error resolving MX for {domain}: {e}")

    try:
        a_records = dns.resolver.resolve(domain, 'A')
        if a_records:
            print(f"A records found for {domain} (fallback): {[r.to_text() for r in a_records]}")
            return True
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        print(f"No A records found for {domain} either.")
        return False
    except dns.exception.Timeout:
        print(f"DNS query for A for {domain} timed out.")
        return False
    except Exception as e:
        print(f"Error resolving A for {domain}: {e}")
        return False
    return False

# -------------------------------------------------------------------------
# UI FUNCTIONS (for Toplevel Windows)
# -------------------------------------------------------------------------

def open_config_window():
    """Opens a Toplevel window to configure email account using keyring."""
    config_window = tk.Toplevel(root)
    config_window.title("Configure Email Account (Secure)")
    config_window.geometry("450x350")
    config_window.transient(root)
    config_window.grab_set()

    ttk.Label(config_window, text="Credentials stored in your system's secure keyring.", wraplength=430).pack(pady=5)
    instructions = (
        "For Gmail, generate an 'App Password':\n"
        "1. Google Account > Security > 2-Step Verification (must be ON).\n"
        "2. Then, App passwords > Select app: Mail, Select device: Other.\n"
        "3. Name it (e.g., MyPythonMailer) > Generate.\n"
        "4. Copy the 16-character password (no spaces) below."
    )
    ttk.Label(config_window, text=instructions, justify=tk.LEFT, wraplength=430).pack(pady=(5,10))

    form_frame = ttk.Frame(config_window)
    form_frame.pack(padx=10, pady=5, fill="x", expand=True)

    ttk.Label(form_frame, text="Email Address:").grid(row=0, column=0, sticky="w", pady=2)
    email_var_cfg = tk.StringVar(value=current_config.get("email", ""))
    email_entry_cfg = ttk.Entry(form_frame, textvariable=email_var_cfg, width=40)
    email_entry_cfg.grid(row=0, column=1, sticky="ew", pady=2)

    ttk.Label(form_frame, text="App Password:").grid(row=1, column=0, sticky="w", pady=2)
    password_var_cfg = tk.StringVar() # For entry only
    password_entry_cfg = ttk.Entry(form_frame, textvariable=password_var_cfg, show="*", width=40)
    password_entry_cfg.grid(row=1, column=1, sticky="ew", pady=2)
    form_frame.columnconfigure(1, weight=1)

    def on_save_cfg():
        email = email_var_cfg.get()
        app_pwd = password_var_cfg.get()
        if not email or "@" not in email:
            messagebox.showerror("Input Error", "Please enter a valid email address.", parent=config_window)
            return
        if not app_pwd:
            messagebox.showerror("Input Error", "Please enter the App Password.", parent=config_window)
            return
        if save_config_keyring(email, app_pwd):
            config_window.destroy()

    button_frame = ttk.Frame(config_window)
    button_frame.pack(pady=10)
    ttk.Button(button_frame, text="Save to Keyring", command=on_save_cfg).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=config_window.destroy).pack(side=tk.LEFT, padx=5)
    email_entry_cfg.focus_set()
    config_window.wait_window()

def open_settings_window():
    """Opens a Toplevel window for application settings."""
    settings_window = tk.Toplevel(root)
    settings_window.title("Application Settings")
    settings_window.geometry("420x200") # Ensure this is large enough
    settings_window.transient(root)
    settings_window.grab_set()

    # This LabelFrame is the main container for settings inside the window
    settings_frame = ttk.LabelFrame(settings_window, text="Email Sending", padding="10")
    # Make sure settings_frame itself is packed into settings_window
    settings_frame.pack(padx=10, pady=10, fill="both", expand=True) # Use fill="both" and expand=True

    check_recipient_var_settings = tk.BooleanVar(value=current_config.get("check_recipient_existence", True))
    
    check_button_state = tk.NORMAL if DNS_PYTHON_AVAILABLE else tk.DISABLED
    
    # Manually add a newline for better wrapping in the checkbutton
    check_button_text_line1 = "Check recipient email domain existence before sending"
    check_button_text_line2 = "(via DNS MX records)"
    if not DNS_PYTHON_AVAILABLE:
        check_button_text_line2 += "\n(dnspython library not found)" # Add another newline for clarity
    
    check_button_full_text = f"{check_button_text_line1}\n{check_button_text_line2}"

    check_button = ttk.Checkbutton(
        settings_frame, # Parent is settings_frame
        text=check_button_full_text,
        variable=check_recipient_var_settings,
        state=check_button_state
    )
    # Make sure check_button is packed into settings_frame
    check_button.pack(pady=5, padx=5, anchor="w") # Added padx

    def on_save_app_settings():
        global current_config
        if DNS_PYTHON_AVAILABLE:
            current_config["check_recipient_existence"] = check_recipient_var_settings.get()
        
        if save_app_preferences():
            status_var.set(f"Settings updated. Check Recipient: {current_config['check_recipient_existence']}")
            messagebox.showinfo("Settings Saved", "Application settings have been saved.", parent=settings_window)
            settings_window.destroy()

    # Frame for buttons, parented to settings_window
    button_frame = ttk.Frame(settings_window)
    button_frame.pack(pady=(0,10), padx=10, fill="x") # Pack it below the settings_frame

    ttk.Button(button_frame, text="Save Settings", command=on_save_app_settings).pack(side=tk.RIGHT, padx=5) # Align right
    ttk.Button(button_frame, text="Cancel", command=settings_window.destroy).pack(side=tk.RIGHT) # Align right

    settings_window.wait_window()

# -------------------------------------------------------------------------
# MAIN ACTION FUNCTION (SEND EMAIL)
# -------------------------------------------------------------------------

def send_email_action():
    if not current_config.get("email") or not current_config.get("app_password"):
        status_var.set("Error: Email account not fully configured.")
        messagebox.showerror("Config Error", "Email account not configured or password not loaded. Use 'Account > Configure'.", parent=root)
        load_config_keyring() # Attempt to reload
        return

    sender_email = current_config["email"]
    app_password = current_config["app_password"]
    to_email = to_entry_var.get()
    subject = subject_entry_var.get()
    message_body = message_text.get("1.0", f"{tk.END}-1c") # Correct way to get text

    if not to_email or "@" not in to_email:
        messagebox.showwarning("Input Error", "Valid 'To' email required.", parent=root)
        return
    if not subject:
        messagebox.showwarning("Input Error", "Subject required.", parent=root)
        return
    if not message_body:
        messagebox.showwarning("Input Error", "Message body required.", parent=root)
        return

    # Recipient Email Domain Existence Check
    if DNS_PYTHON_AVAILABLE and current_config.get("check_recipient_existence", False):
        status_var.set(f"Checking domain for {to_email}...")
        root.update_idletasks()
        if not check_email_domain_validity(to_email):
            proceed = messagebox.askyesno(
                "Domain Validity Warning",
                f"The domain for '{to_email}' might not exist or accept emails.\n"
                "Proceed with sending?",
                parent=root
            )
            if not proceed:
                status_var.set("Sending cancelled due to domain check.")
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
        # Optionally clear fields:
        # to_entry_var.set("")
        # subject_entry_var.set("")
        # message_text.delete("1.0", tk.END)

    except smtplib.SMTPAuthenticationError:
        status_var.set("Error: SMTP Auth failed. Check email/App Password in keyring.")
        messagebox.showerror("Auth Error", "Gmail Auth Failed. Check email & App Password in keyring. Ensure 2-Step is ON.", parent=root)
    except smtplib.SMTPConnectError:
        status_var.set("Error: Could not connect to Gmail SMTP server.")
        messagebox.showerror("Connection Error", "Cannot connect to Gmail SMTP. Check internet.", parent=root)
    except keyring.errors.NoKeyringError: # Should be caught earlier, but defensive
        status_var.set("Error: Keyring backend not found. Cannot retrieve password.")
        messagebox.showerror("Keyring Error", "No system keyring. Cannot retrieve password to send.", parent=root)
    except Exception as e:
        status_var.set(f"Error sending email: {e}")
        messagebox.showerror("Sending Error", f"An unexpected error occurred: {e}", parent=root)

# --- SET THE WINDOW ICON / LOGO ---
try:
    app_icon = tk.PhotoImage(file='logo.gif')
    root.iconphoto(False, app_icon)
except tk.TclError as e: # More specific error for Tkinter image issues
    print(f"Could not load logo.gif (TclError): {e}. Ensure it's a valid GIF.")
except Exception as e:
    print(f"Could not load logo.gif: {e}")

# --- Load initial configuration ---
load_config_keyring() # This will also set an initial status_var message

# --- Main Menu ---
menubar = tk.Menu(root)
root.config(menu=menubar)

account_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Account", menu=account_menu)
account_menu.add_command(label="Configure Email Account", command=open_config_window)

options_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Options", menu=options_menu)
options_menu.add_command(label="Settings", command=open_settings_window)

file_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Exit", command=root.quit)

# --- Configure Grid Layout for Main Window ---
root.columnconfigure(1, weight=1) # Column with entry fields and message body
root.rowconfigure(3, weight=1)    # Row with the message body

# --- WIDGETS for Main Window ---

# Row 1 (shifted due to menu): "To" field
to_label = ttk.Label(root, text="To:")
to_label.grid(row=1, column=0, padx=10, pady=(10,5), sticky="w") # More top padding for first field
to_entry = ttk.Entry(root, textvariable=to_entry_var, width=50)
to_entry.grid(row=1, column=1, padx=10, pady=(10,5), sticky="ew")

# Row 2: "Subject" field
subject_label = ttk.Label(root, text="Subject:")
subject_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
subject_entry = ttk.Entry(root, textvariable=subject_entry_var, width=50)
subject_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

# Row 3: "Message" Label and Text Area
message_label = ttk.Label(root, text="Message:")
message_label.grid(row=3, column=0, padx=10, pady=5, sticky="nw") # North-West for label
message_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=60, height=15)
message_text.grid(row=3, column=1, padx=10, pady=5, sticky="nsew") # Stretchy

# Row 4: "Send" Button
send_button = ttk.Button(root, text="Send Email", command=send_email_action)
send_button.grid(row=4, column=1, padx=10, pady=10, sticky="e") # Align to the right

# Row 5: Status Label
status_label_widget = ttk.Label(root, textvariable=status_var, relief=tk.SUNKEN, anchor="w")
status_label_widget.grid(row=5, column=0, columnspan=2, padx=10, pady=(5,10), sticky="ew")


to_entry.focus_set()
_is_root_fully_initialized = True # Set the flag just before starting the main loop

logging.info("Starting Tkinter main event loop.")
root.mainloop()
logging.info("Application event loop finished.") # This logs when mainloop exits