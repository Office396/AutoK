import json
import tkinter as tk
import customtkinter as ctk
from pathlib import Path
from datetime import datetime

# Path configuration
BASE_DIR = Path(__file__).parent.absolute()
REG_FILE = BASE_DIR / "data" / "registrations.json"
CONTROL_FILE = BASE_DIR / "data" / ".remote_control"

class AdminPanel(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Admin Control Panel - Security Monitor")
        self.geometry("900x600")
        
        # Colors & Theme
        ctk.set_appearance_mode("dark")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self._create_header()
        self._create_main_content()
        self._refresh_data()
        
    def _create_header(self):
        header = ctk.CTkFrame(self, fg_color="#1a1a1a", height=80, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        
        title = ctk.CTkLabel(
            header,
            text="🔐 Security Administration",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="white"
        )
        title.pack(side="left", padx=30, pady=20)
        
        refresh_btn = ctk.CTkButton(
            header,
            text="🔄 Refresh Data",
            command=self._refresh_data,
            width=120
        )
        refresh_btn.pack(side="right", padx=30, pady=20)

    def _create_main_content(self):
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)

    def _refresh_data(self):
        # Clear existing
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
        # Load or create registrations
        if not REG_FILE.parent.exists():
            REG_FILE.parent.mkdir(parents=True, exist_ok=True)
            
        data = {}
        if REG_FILE.exists():
            try:
                with open(REG_FILE, 'r') as f:
                    data = json.load(f)
            except:
                pass
        
        if not data:
            ctk.CTkLabel(self.scroll_frame, text="No machines registered yet.", font=ctk.CTkFont(size=16)).pack(pady=50)
            return

        # Load currently pending commands
        commands = {}
        if CONTROL_FILE.exists():
            try:
                with open(CONTROL_FILE, 'r') as f:
                    commands = json.load(f)
            except:
                pass

        # Display machines
        for mac, info in data.items():
            card = ctk.CTkFrame(self.scroll_frame, fg_color="#2b2b2b", corner_radius=10)
            card.pack(fill="x", pady=10, padx=5)
            
            # Left side: Info
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", padx=20, pady=15)
            
            ctk.CTkLabel(info_frame, text=f"💻 {info.get('pc_name')}", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(info_frame, text=f"User: {info.get('username')} | IP: {info.get('public_ip')}", text_color="#aaaaaa").pack(anchor="w")
            ctk.CTkLabel(info_frame, text=f"MAC: {mac} | Last Seen: {info.get('last_seen')[:19]}", text_color="#888888", font=ctk.CTkFont(size=10)).pack(anchor="w")
            
            # Status badge
            status = info.get("status", "ACTIVE")
            pending_cmd = commands.get(mac)
            if pending_cmd:
                status = f"PENDING: {pending_cmd}"
            
            color = "#4CAF50" # Green
            if "LOCK" in status: color = "#FF9800" # Orange
            if "DESTRUCT" in status: color = "#F44336" # Red
            
            badge = ctk.CTkLabel(card, text=status, fg_color=color, corner_radius=5, padx=8, width=120)
            badge.pack(side="left", padx=20)
            
            # Right side: Controls
            btn_frame = ctk.CTkFrame(card, fg_color="transparent")
            btn_frame.pack(side="right", padx=20)
            
            # Lock/Unlock Toggle
            is_locked = (pending_cmd == "LOCK" or info.get("status") == "LOCKED")
            lock_text = "🔓 Unlock" if is_locked else "🔒 Lock Machine"
            lock_cmd = "UNLOCK" if is_locked else "LOCK"
            
            ctk.CTkButton(
                btn_frame, 
                text=lock_text, 
                width=120, 
                fg_color="#3d3d3d" if is_locked else "#E65100",
                command=lambda m=mac, c=lock_cmd: self._send_command(m, c)
            ).pack(side="left", padx=5)
            
            # Destruct Button
            ctk.CTkButton(
                btn_frame, 
                text="💣 Destruct", 
                width=100, 
                fg_color="#B71C1C", 
                hover_color="#D32F2F",
                command=lambda m=mac: self._confirm_destruct(m)
            ).pack(side="left", padx=5)

    def _send_command(self, mac_address, command):
        commands = {}
        if CONTROL_FILE.exists():
            try:
                with open(CONTROL_FILE, 'r') as f:
                    commands = json.load(f)
            except:
                pass
        
        commands[mac_address] = command
        
        with open(CONTROL_FILE, 'w') as f:
            json.dump(commands, f, indent=4)
        
        self._refresh_data()

    def _confirm_destruct(self, mac):
        # In a real app, use a popup. Here we just send the command.
        self._send_command(mac, "DESTRUCT")
        print(f"Destruct signal sent to {mac}")

if __name__ == "__main__":
    app = AdminPanel()
    app.mainloop()
