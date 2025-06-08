import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import smtplib
from email.mime.text import MIMEText
import logging
import webbrowser
from typing import Optional, Dict, Any

# Keyring and DNS libraries (optional dependencies)
import keyring
import keyring.errors
try:
    import dns.resolver
    import dns.exception
    DNS_PYTHON_AVAILABLE = True
except ImportError:
    DNS_PYTHON_AVAILABLE = False

# --- Constants ---
APP_SETTINGS_FILE = "app_settings.json"
SERVICE_NAME = "zeemailer" # Unique name for the app in the system keyring

# --- Basic Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# -------------------------------------------------------------------------
# 1. DATA AND LOGIC CLASSES (Separation of Concerns)
# -------------------------------------------------------------------------

class ConfigManager:
    """Manages loading and saving of application configuration."""
    def __init__(self, settings_file: str, service_name: str):
        self.settings_file = settings_file
        self.service_name = service_name
        self.config: Dict[str, Any] = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Returns the default configuration dictionary."""
        return {
            "email": "",
            "app_password": None, # Loaded from keyring
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 465,
            "check_recipient_domain": DNS_PYTHON_AVAILABLE,
        }

    def load_configuration(self) -> None:
        """Loads settings from file and password from keyring."""
        self.config = self._get_default_config()
        try:
            with open(self.settings_file, "r") as f:
                settings = json.load(f)
                self.config.update(settings)
                # Ensure boolean setting is respected and dependent on dnspython
                if not DNS_PYTHON_AVAILABLE:
                    self.config["check_recipient_domain"] = False
                logging.info(f"Settings loaded from {self.settings_file}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.warning(f"Could not load settings file: {e}. Using defaults.")

        # Load password from keyring if an email is configured
        if self.config.get("email"):
            try:
                password = keyring.get_password(self.service_name, self.config["email"])
                if password:
                    self.config["app_password"] = password
                    logging.info(f"Password retrieved from keyring for {self.config['email']}.")
                else:
                    logging.warning(f"No password found in keyring for {self.config['email']}.")
            except keyring.errors.NoKeyringError:
                logging.error("Keyring backend not found. Cannot securely load password.")
                raise # Re-raise to be handled by the UI
            except Exception as e:
                logging.error(f"Error retrieving password from keyring: {e}", exc_info=True)
                raise # Re-raise to be handled by the UI

    def save_configuration(self, email: str, app_password: str, smtp_server: str, smtp_port: int, check_domain: bool) -> None:
        """Saves non-sensitive settings to file and password to keyring."""
        # 1. Save non-sensitive data to JSON file
        prefs_to_save = {
            "email": email,
            "smtp_server": smtp_server,
            "smtp_port": smtp_port,
            "check_recipient_domain": check_domain,
        }
        try:
            with open(self.settings_file, "w") as f:
                json.dump(prefs_to_save, f, indent=4)
            logging.info("Application preferences saved.")
        except Exception as e:
            logging.error(f"Could not save app preferences: {e}", exc_info=True)
            raise IOError(f"Could not save app preferences: {e}")

        # 2. Save password to keyring
        try:
            keyring.set_password(self.service_name, email, app_password)
            logging.info(f"Password for {email} saved to keyring.")
        except Exception as e:
            logging.error(f"Could not save password to keyring: {e}", exc_info=True)
            raise IOError(f"Could not save password to keyring: {e}")

        # 3. Update in-memory config
        self.config.update(prefs_to_save)
        self.config["app_password"] = app_password

class EmailSender:
    """Handles the logic of sending an email."""
    @staticmethod
    def check_domain_validity(email_address: str) -> bool:
        """Checks for MX records for the email's domain."""
        if not DNS_PYTHON_AVAILABLE:
            return True # Skip if library is missing
        try:
            domain = email_address.split('@')[-1]
            dns.resolver.resolve(domain, 'MX')
            logging.info(f"MX records found for domain '{domain}'.")
            return True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout, IndexError):
            logging.warning(f"MX record check failed for domain of '{email_address}'.")
            return False
        except Exception as e:
            logging.error(f"An unexpected error occurred during DNS check: {e}")
            return False # Fail safely

    def send(self, sender_cfg: Dict[str, Any], to: str, subject: str, body: str):
        """Connects to an SMTP server and sends the email."""
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = sender_cfg["email"]
        msg['To'] = to

        server, port = sender_cfg["smtp_server"], sender_cfg["smtp_port"]
        logging.info(f"Connecting to {server}:{port} to send email.")

        with smtplib.SMTP_SSL(server, port) as smtp_server:
            smtp_server.login(sender_cfg["email"], sender_cfg["app_password"])
            smtp_server.sendmail(sender_cfg["email"], to, msg.as_string())
        logging.info(f"Email sent successfully to {to}.")


# -------------------------------------------------------------------------
# 2. UI APPLICATION CLASS (Main Application Logic)
# -------------------------------------------------------------------------

class EmailApp:
    """Main application class for the ZeeMail GUI."""
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ZeeMail - An Email Sender")
        self.root.geometry("600x550")
        self.root.protocol("WM_DELETE_WINDOW", self.root.quit)

        # Initialize core components
        self.config_manager = ConfigManager(APP_SETTINGS_FILE, SERVICE_NAME)
        self.email_sender = EmailSender()
        self.app_icon = self._load_icon()

        # UI variables
        self.status_var = tk.StringVar(value="Initializing...")
        self.to_var = tk.StringVar()
        self.subject_var = tk.StringVar()

        self._create_widgets()
        self._load_initial_config()

    def _load_icon(self) -> Optional[tk.PhotoImage]:
        """Loads the application icon."""
        try:
            icon = tk.PhotoImage(file='logo.gif')
            self.root.iconphoto(False, icon)
            logging.info("App icon 'logo.gif' loaded successfully.")
            return icon
        except tk.TclError:
            logging.warning("Could not load 'logo.gif'. Ensure it's a valid GIF file.")
        return None

    def _load_initial_config(self):
        """Tries to load configuration on startup and updates the status."""
        try:
            self.config_manager.load_configuration()
            email = self.config_manager.config.get("email")
            password = self.config_manager.config.get("app_password")
            if email and password:
                self.status_var.set(f"Ready. Configured for {email}.")
            elif email:
                self.status_var.set(f"Config for {email} found, but password missing from keyring.")
                messagebox.showwarning(
                    "Password Missing",
                    f"Password for {email} not found in your system's keyring. Please re-configure.",
                    parent=self.root
                )
            else:
                self.status_var.set("Ready. Please configure your email account via the 'Account' menu.")
        except Exception as e:
            self.status_var.set("Error loading configuration. See logs.")
            messagebox.showerror("Configuration Error", f"An error occurred while loading settings: {e}", parent=self.root)

    def _create_widgets(self):
        """Creates and lays out all the widgets in the main window."""
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=1) # Row for the message body

        # --- Menu Bar ---
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Clear Form", command=self._clear_fields)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Account Menu
        account_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Account", menu=account_menu)
        account_menu.add_command(label="Configure...", command=self._open_config_window)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About ZeeMail", command=self._show_about_dialog)

        # --- Main Frame ---
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

        # Widgets
        ttk.Label(main_frame, text="To:").grid(row=0, column=0, sticky="w", pady=2)
        to_entry = ttk.Entry(main_frame, textvariable=self.to_var)
        to_entry.grid(row=0, column=1, sticky="ew", pady=2)
        to_entry.focus_set()

        ttk.Label(main_frame, text="Subject:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(main_frame, textvariable=self.subject_var).grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(main_frame, text="Message:").grid(row=2, column=0, sticky="nw", pady=2)
        self.message_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=15)
        self.message_text.grid(row=2, column=1, sticky="nsew", pady=2)

        # Button Frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=1, pady=(10, 0), sticky="e")
        ttk.Button(button_frame, text="Clear", command=self._clear_fields).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Send Email", command=self._send_email).pack(side=tk.LEFT)

        # Status Bar
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w", padding=5)
        status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

    def _clear_fields(self):
        """Clears the input fields."""
        self.to_var.set("")
        self.subject_var.set("")
        self.message_text.delete("1.0", tk.END)
        self.status_var.set("Fields cleared.")
        logging.info("Input fields cleared by user.")

    def _send_email(self):
        """Validates input and calls the EmailSender."""
        cfg = self.config_manager.config
        if not cfg.get("email") or not cfg.get("app_password"):
            messagebox.showerror("Configuration Error", "Email account is not fully configured.", parent=self.root)
            self.status_var.set("Configuration incomplete. Please use 'Account > Configure'.")
            return

        to_email = self.to_var.get().strip()
        subject = self.subject_var.get()
        body = self.message_text.get("1.0", tk.END).strip()

        if not all([to_email, subject, body]):
            messagebox.showwarning("Input Error", "To, Subject, and Message fields cannot be empty.", parent=self.root)
            return

        # Optional: Domain check
        if cfg.get("check_recipient_domain") and not self.email_sender.check_domain_validity(to_email):
            if not messagebox.askyesno("Domain Warning", f"The domain for '{to_email}' might not be valid. Send anyway?", parent=self.root):
                self.status_var.set("Send cancelled due to domain check.")
                return

        self.status_var.set(f"Sending to {to_email}...")
        self.root.update_idletasks()

        try:
            self.email_sender.send(cfg, to_email, subject, body)
            self.status_var.set(f"Email successfully sent to {to_email}!")
            messagebox.showinfo("Success", f"Email sent to {to_email}!", parent=self.root)
        except smtplib.SMTPAuthenticationError:
            messagebox.showerror("Authentication Error", "SMTP authentication failed. Check your email and App Password.", parent=self.root)
            self.status_var.set("Authentication failed. Please re-configure.")
        except Exception as e:
            messagebox.showerror("Sending Error", f"An error occurred: {e}", parent=self.root)
            self.status_var.set(f"Error: {e}")
            logging.error(f"Failed to send email: {e}", exc_info=True)
            
    def _open_config_window(self):
        """Opens a Toplevel window to configure all settings."""
        # This fixes the duplicated code bug and centralizes settings.
        config_win = tk.Toplevel(self.root)
        config_win.title("Configure Account & Settings")
        config_win.transient(self.root)
        config_win.grab_set()
        config_win.resizable(False, False)

        frame = ttk.Frame(config_win, padding="15")
        frame.pack(fill="both", expand=True)

        # Variables for the entry fields, pre-filled with current config
        cfg = self.config_manager.config
        email_var = tk.StringVar(value=cfg.get("email", ""))
        password_var = tk.StringVar() # Always empty for security
        server_var = tk.StringVar(value=cfg.get("smtp_server", "smtp.gmail.com"))
        port_var = tk.IntVar(value=cfg.get("smtp_port", 465))
        check_domain_var = tk.BooleanVar(value=cfg.get("check_recipient_domain", True))

        # Account Credentials
        cred_frame = ttk.LabelFrame(frame, text="Account Credentials", padding="10")
        cred_frame.pack(fill="x", expand=True, pady=5)
        cred_frame.columnconfigure(1, weight=1)
        ttk.Label(cred_frame, text="Email:").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(cred_frame, textvariable=email_var).grid(row=0, column=1, sticky="ew")
        ttk.Label(cred_frame, text="App Password:").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(cred_frame, textvariable=password_var, show="*").grid(row=1, column=1, sticky="ew")

        # SMTP Settings
        smtp_frame = ttk.LabelFrame(frame, text="SMTP Server", padding="10")
        smtp_frame.pack(fill="x", expand=True, pady=5)
        smtp_frame.columnconfigure(1, weight=1)
        ttk.Label(smtp_frame, text="Server Address:").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(smtp_frame, textvariable=server_var).grid(row=0, column=1, sticky="ew")
        ttk.Label(smtp_frame, text="Port (SSL):").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(smtp_frame, textvariable=port_var, width=10).grid(row=1, column=1, sticky="w")
        
        # Other Settings
        other_frame = ttk.LabelFrame(frame, text="Options", padding="10")
        other_frame.pack(fill="x", expand=True, pady=5)
        check_button = ttk.Checkbutton(other_frame, text="Check recipient domain validity before sending", variable=check_domain_var)
        check_button.pack(anchor="w")
        if not DNS_PYTHON_AVAILABLE:
            check_button.config(state=tk.DISABLED)
            ttk.Label(other_frame, text="(dnspython library not installed)", foreground="grey").pack(anchor="w", padx=20)


        def on_save():
            email = email_var.get().strip()
            password = password_var.get() # Don't strip password
            server = server_var.get().strip()
            
            if not email or "@" not in email:
                messagebox.showerror("Input Error", "Please enter a valid email.", parent=config_win)
                return
            if not password: # Password must be provided every time for saving
                messagebox.showerror("Input Error", "App Password is required to save settings.", parent=config_win)
                return

            try:
                port = port_var.get()
                self.config_manager.save_configuration(email, password, server, port, check_domain_var.get())
                messagebox.showinfo("Success", "Configuration saved securely.", parent=config_win)
                self._load_initial_config() # Reload to update status bar and in-memory state
                config_win.destroy()
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save configuration:\n{e}", parent=config_win)

        # Buttons
        btn_frame = ttk.Frame(frame, padding=(0, 10, 0, 0))
        btn_frame.pack(fill="x", expand=True)
        ttk.Button(btn_frame, text="Save", command=on_save).pack(side="right")
        ttk.Button(btn_frame, text="Cancel", command=config_win.destroy).pack(side="right", padx=5)

    def _show_about_dialog(self):
        """Displays the 'About' window."""
        webbrowser.open_new_tab("https://github.com/alexantSWE/zeemail")
        messagebox.showinfo(
            "About ZeeMail",
            "ZeeMail v1.1.0\n\n"
            "A simple email sender built with Python and Tkinter.\n"
            "by Alireza Rezaei (@alexantSWE)\n\n"
            "The project's GitHub page has been opened for you.",
            parent=self.root
        )

def main():
    """Application entry point."""
    if not DNS_PYTHON_AVAILABLE:
        print("Warning: dnspython library not found. Recipient domain check will be disabled.")
    
    root = tk.Tk()
    app = EmailApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()