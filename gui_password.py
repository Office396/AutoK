"""
Password Protection Dialog
Secure password dialog with hashing for Handle tab protection
"""

import customtkinter as ctk
import hashlib
import os
import json
from pathlib import Path
from gui_components import Colors

SECURITY_FILE = Path(__file__).parent / "data" / ".security"
DEFAULT_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()


class PasswordManager:
    """Manages password storage and verification with SHA-256 hashing"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._load_security()
    
    def _load_security(self):
        """Load security data from file"""
        try:
            if SECURITY_FILE.exists():
                with open(SECURITY_FILE, 'r') as f:
                    data = json.load(f)
                    self._password_hash = data.get('hash', '')
                    self._salt = data.get('salt', '')
                    if not self._password_hash:
                        self._set_default_password()
            else:
                self._set_default_password()
        except:
            self._set_default_password()
    
    def _set_default_password(self):
        """Set the default password (admin123)"""
        self._salt = os.urandom(16).hex()
        self._password_hash = self._hash_password("admin123")
        self._save_security()
    
    def _save_security(self):
        """Save security data to file"""
        try:
            SECURITY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SECURITY_FILE, 'w') as f:
                json.dump({
                    'hash': self._password_hash,
                    'salt': self._salt
                }, f)
        except:
            pass
    
    def _hash_password(self, password: str) -> str:
        """Hash password with salt using SHA-256"""
        salted = f"{self._salt}{password}{self._salt}"
        return hashlib.sha256(salted.encode()).hexdigest()
    
    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash"""
        if self._salt:
            return self._hash_password(password) == self._password_hash
        else:
            return hashlib.sha256(password.encode()).hexdigest() == self._password_hash
    
    def change_password(self, old_password: str, new_password: str) -> bool:
        """Change password if old password is correct"""
        if not self.verify_password(old_password):
            return False
        
        self._salt = os.urandom(16).hex()
        self._password_hash = self._hash_password(new_password)
        self._save_security()
        return True
    
    def set_password(self, new_password: str):
        """Set new password (use with caution)"""
        self._salt = os.urandom(16).hex()
        self._password_hash = self._hash_password(new_password)
        self._save_security()


password_manager = PasswordManager()


class PasswordDialog(ctk.CTkToplevel):
    """Beautiful password dialog with security features"""
    
    def __init__(self, parent, on_success=None, on_cancel=None):
        super().__init__(parent)
        
        self.on_success = on_success
        self.on_cancel = on_cancel
        self.result = False
        self.attempts = 0
        self.max_attempts = 5
        
        self.title("")
        self.geometry("420x380")
        self.resizable(False, False)
        self.configure(fg_color=Colors.BG_DARK)
        
        self.transient(parent)
        self.grab_set()
        
        self.overrideredirect(True)
        
        self._create_ui()
        
        self.after(10, self._center_on_parent)
        
        self.bind("<Return>", lambda e: self._on_submit())
        self.bind("<Escape>", lambda e: self._on_close())
    
    def _center_on_parent(self):
        """Center dialog on parent window"""
        self.update_idletasks()
        parent = self.master
        
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        
        w = self.winfo_width()
        h = self.winfo_height()
        
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        
        self.geometry(f"+{x}+{y}")
    
    def _create_ui(self):
        """Create the dialog UI"""
        main_frame = ctk.CTkFrame(self, fg_color=Colors.BG_CARD, corner_radius=15)
        main_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        border_frame = ctk.CTkFrame(
            main_frame, 
            fg_color=Colors.BG_MEDIUM,
            corner_radius=13
        )
        border_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        content = ctk.CTkFrame(border_frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=25, pady=25)
        
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        
        icon_frame = ctk.CTkFrame(
            header,
            fg_color=Colors.PRIMARY,
            corner_radius=30,
            width=60,
            height=60
        )
        icon_frame.pack()
        icon_frame.pack_propagate(False)
        
        lock_icon = ctk.CTkLabel(
            icon_frame,
            text="🔒",
            font=ctk.CTkFont(size=28)
        )
        lock_icon.place(relx=0.5, rely=0.5, anchor="center")
        
        title_label = ctk.CTkLabel(
            header,
            text="Protected Area",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title_label.pack(pady=(15, 5))
        
        subtitle_label = ctk.CTkLabel(
            header,
            text="Enter password to access Handle settings",
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_MUTED
        )
        subtitle_label.pack()
        
        input_frame = ctk.CTkFrame(content, fg_color="transparent")
        input_frame.pack(fill="x", pady=15)
        
        self.password_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Enter password...",
            show="●",
            height=48,
            font=ctk.CTkFont(size=14),
            fg_color=Colors.BG_DARK,
            border_color=Colors.BORDER,
            corner_radius=10
        )
        self.password_entry.pack(fill="x")
        self.password_entry.focus()
        
        self.show_password_var = ctk.BooleanVar(value=False)
        show_pass_check = ctk.CTkCheckBox(
            input_frame,
            text="Show password",
            variable=self.show_password_var,
            command=self._toggle_password_visibility,
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED,
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY,
            corner_radius=4,
            height=20
        )
        show_pass_check.pack(anchor="w", pady=(10, 0))
        
        self.error_label = ctk.CTkLabel(
            content,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=Colors.ERROR
        )
        self.error_label.pack(pady=(5, 10))
        
        button_frame = ctk.CTkFrame(content, fg_color="transparent")
        button_frame.pack(fill="x", pady=(10, 0))
        
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=self._on_close,
            width=120,
            height=42,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            border_width=1,
            border_color=Colors.BORDER,
            hover_color=Colors.BG_DARK,
            text_color=Colors.TEXT_SECONDARY
        )
        cancel_btn.pack(side="left", expand=True, padx=(0, 5))
        
        self.submit_btn = ctk.CTkButton(
            button_frame,
            text="Unlock",
            command=self._on_submit,
            width=120,
            height=42,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=Colors.PRIMARY,
            hover_color="#1a73c7"
        )
        self.submit_btn.pack(side="right", expand=True, padx=(5, 0))
    
    def _toggle_password_visibility(self):
        """Toggle password visibility"""
        if self.show_password_var.get():
            self.password_entry.configure(show="")
        else:
            self.password_entry.configure(show="●")
    
    def _on_submit(self):
        """Handle submit button"""
        password = self.password_entry.get()
        
        if not password:
            self._show_error("Please enter a password")
            return
        
        if password_manager.verify_password(password):
            self.result = True
            if self.on_success:
                self.on_success()
            self.destroy()
        else:
            self.attempts += 1
            remaining = self.max_attempts - self.attempts
            
            if remaining <= 0:
                self._show_error("Too many failed attempts. Access denied.")
                self.submit_btn.configure(state="disabled")
                self.after(3000, self._on_close)
            else:
                self._show_error(f"Incorrect password. {remaining} attempts remaining.")
                self.password_entry.delete(0, "end")
                
                self.password_entry.configure(border_color=Colors.ERROR)
                self.after(1000, lambda: self.password_entry.configure(border_color=Colors.BORDER))
    
    def _show_error(self, message: str):
        """Show error message with animation"""
        self.error_label.configure(text=message)
    
    def _on_close(self):
        """Handle close/cancel"""
        self.result = False
        if self.on_cancel:
            self.on_cancel()
        self.destroy()


class ChangePasswordDialog(ctk.CTkToplevel):
    """Dialog to change the Handle tab password"""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.title("")
        self.geometry("420x450")
        self.resizable(False, False)
        self.configure(fg_color=Colors.BG_DARK)
        
        self.transient(parent)
        self.grab_set()
        
        self.overrideredirect(True)
        
        self._create_ui()
        
        self.after(10, self._center_on_parent)
        
        self.bind("<Escape>", lambda e: self.destroy())
    
    def _center_on_parent(self):
        """Center dialog on parent window"""
        self.update_idletasks()
        parent = self.master
        
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        
        w = self.winfo_width()
        h = self.winfo_height()
        
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        
        self.geometry(f"+{x}+{y}")
    
    def _create_ui(self):
        """Create the dialog UI"""
        main_frame = ctk.CTkFrame(self, fg_color=Colors.BG_CARD, corner_radius=15)
        main_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        border_frame = ctk.CTkFrame(
            main_frame, 
            fg_color=Colors.BG_MEDIUM,
            corner_radius=13
        )
        border_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        content = ctk.CTkFrame(border_frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=25, pady=25)
        
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        
        icon_frame = ctk.CTkFrame(
            header,
            fg_color=Colors.WARNING,
            corner_radius=30,
            width=60,
            height=60
        )
        icon_frame.pack()
        icon_frame.pack_propagate(False)
        
        key_icon = ctk.CTkLabel(
            icon_frame,
            text="🔑",
            font=ctk.CTkFont(size=28)
        )
        key_icon.place(relx=0.5, rely=0.5, anchor="center")
        
        title_label = ctk.CTkLabel(
            header,
            text="Change Password",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title_label.pack(pady=(15, 5))
        
        ctk.CTkLabel(
            content,
            text="Current Password",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        ).pack(anchor="w")
        
        self.current_entry = ctk.CTkEntry(
            content,
            show="●",
            height=42,
            font=ctk.CTkFont(size=13),
            fg_color=Colors.BG_DARK,
            border_color=Colors.BORDER,
            corner_radius=8
        )
        self.current_entry.pack(fill="x", pady=(5, 15))
        
        ctk.CTkLabel(
            content,
            text="New Password",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        ).pack(anchor="w")
        
        self.new_entry = ctk.CTkEntry(
            content,
            show="●",
            height=42,
            font=ctk.CTkFont(size=13),
            fg_color=Colors.BG_DARK,
            border_color=Colors.BORDER,
            corner_radius=8
        )
        self.new_entry.pack(fill="x", pady=(5, 15))
        
        ctk.CTkLabel(
            content,
            text="Confirm New Password",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        ).pack(anchor="w")
        
        self.confirm_entry = ctk.CTkEntry(
            content,
            show="●",
            height=42,
            font=ctk.CTkFont(size=13),
            fg_color=Colors.BG_DARK,
            border_color=Colors.BORDER,
            corner_radius=8
        )
        self.confirm_entry.pack(fill="x", pady=(5, 10))
        
        self.error_label = ctk.CTkLabel(
            content,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=Colors.ERROR
        )
        self.error_label.pack(pady=5)
        
        button_frame = ctk.CTkFrame(content, fg_color="transparent")
        button_frame.pack(fill="x", pady=(10, 0))
        
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=self.destroy,
            width=120,
            height=42,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            border_width=1,
            border_color=Colors.BORDER,
            hover_color=Colors.BG_DARK,
            text_color=Colors.TEXT_SECONDARY
        )
        cancel_btn.pack(side="left", expand=True, padx=(0, 5))
        
        save_btn = ctk.CTkButton(
            button_frame,
            text="Save",
            command=self._on_save,
            width=120,
            height=42,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=Colors.SUCCESS,
            hover_color="#1a8a3e"
        )
        save_btn.pack(side="right", expand=True, padx=(5, 0))
    
    def _on_save(self):
        """Handle save button"""
        current = self.current_entry.get()
        new = self.new_entry.get()
        confirm = self.confirm_entry.get()
        
        if not current or not new or not confirm:
            self.error_label.configure(text="All fields are required")
            return
        
        if new != confirm:
            self.error_label.configure(text="New passwords do not match")
            return
        
        if len(new) < 4:
            self.error_label.configure(text="Password must be at least 4 characters")
            return
        
        if password_manager.change_password(current, new):
            self.destroy()
        else:
            self.error_label.configure(text="Current password is incorrect")
