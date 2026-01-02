"""
Main Window
The main application window with sidebar navigation
"""

import customtkinter as ctk
from typing import Optional, Dict
import threading
from datetime import datetime

from gui_components import Colors, TabButton, ToastNotification
from CTkMessagebox import CTkMessagebox
from gui_dashboard import DashboardView
from gui_settings import SettingsView
from gui_message_formats import MessageFormatsView
from gui_sites import SitesView
from gui_logs import LogsView
from gui_about import AboutView
from gui_password import PasswordDialog, ChangePasswordDialog

from automation_controller import (
    automation_controller, AutomationState, AutomationStats
)
from master_data import master_data
from config import settings
from logger_module import logger


class MainWindow(ctk.CTk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title("Autok - Telecom Alarm Automation")
        self.geometry("1400x800")
        self.minsize(1200, 700)
        
        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Configure colors
        self.configure(fg_color=Colors.BG_DARK)

        # Basic UI setup - keep it simple and stable
        self.configure(fg_color=Colors.BG_DARK)
        
        # DPI awareness commented out to prevent display issues
        # try:
        #     from ctypes import windll
        #     windll.shcore.SetProcessDpiAwareness(1)
        # except:
        #     pass
        # ===========
        
        # Views
        self.views: Dict[str, ctk.CTkFrame] = {}
        self.current_view: Optional[str] = None
        self._handle_unlocked = False  # Password protection state
        
        # Create layout
        self._create_layout()
        
        # Setup callbacks
        self._setup_callbacks()
        
        # Start update loop
        self._start_update_loop()
        
        # Handle close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_layout(self):
        """Create the main layout"""
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self._create_sidebar()
        
        # Content area
        self.content_frame = ctk.CTkFrame(self, fg_color=Colors.BG_DARK)
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
        
        # Create views
        self._create_views()
        
        # Show dashboard by default
        self._show_view("dashboard")
    
    def _create_sidebar(self):
        """Create the sidebar navigation"""
        sidebar = ctk.CTkFrame(self, fg_color=Colors.BG_MEDIUM, width=220, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        
        # Logo section
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=15, pady=20)
        
        logo_icon = ctk.CTkLabel(
            logo_frame,
            text="🗼",
            font=ctk.CTkFont(size=40)
        )
        logo_icon.pack()
        
        logo_text = ctk.CTkLabel(
            logo_frame,
            text="Alarm Automation",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        logo_text.pack(pady=(5, 0))
        
        # Separator
        sep = ctk.CTkFrame(sidebar, fg_color=Colors.BORDER, height=1)
        sep.pack(fill="x", padx=15, pady=10)
        
        # Navigation buttons
        self.nav_buttons: Dict[str, TabButton] = {}
        
        nav_items = [
            ("dashboard", "📊", "Dashboard"),
            ("formats", "📝", "Handle"),
            ("settings", "⚙️", "Settings"),
            ("sites", "📍", "Sites"),
            ("logs", "📜", "Logs"),
            ("about", "ℹ️", "About"),
        ]
        
        for view_id, icon, label in nav_items:
            btn = TabButton(
                sidebar,
                text=label,
                icon=icon,
                is_active=(view_id == "dashboard"),
                command=lambda v=view_id: self._show_view(v),
                width=190,
                height=40
            )
            btn.pack(padx=15, pady=3)
            self.nav_buttons[view_id] = btn
        
        # Bottom section - Status
        bottom_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=15, pady=20)
        
        self.status_label = ctk.CTkLabel(
            bottom_frame,
            text="● Stopped",
            font=ctk.CTkFont(size=11),
            text_color=Colors.ERROR
        )
        self.status_label.pack(anchor="w")
        
        self.uptime_label = ctk.CTkLabel(
            bottom_frame,
            text="Uptime: 00:00:00",
            font=ctk.CTkFont(size=10),
            text_color=Colors.TEXT_MUTED
        )
        self.uptime_label.pack(anchor="w", pady=(5, 0))
    
    def _create_views(self):
        """Create all views"""
        # Dashboard
        dashboard = DashboardView(self.content_frame)
        dashboard.on_start = self._on_start
        dashboard.on_stop = self._on_start  # Same button toggles
        dashboard.on_pause = self._on_pause
        dashboard.on_force_check = self._on_force_check
        dashboard.on_force_send = self._on_force_send
        self.views["dashboard"] = dashboard
        
        # Settings
        settings_view = SettingsView(self.content_frame)
        settings_view.on_save = self._on_settings_saved
        self.views["settings"] = settings_view
        
        # Message Formats
        formats_view = MessageFormatsView(self.content_frame)
        formats_view.on_save = self._on_settings_saved
        self.views["formats"] = formats_view
        
        # Sites
        sites_view = SitesView(self.content_frame)
        self.views["sites"] = sites_view
        
        # Logs
        logs_view = LogsView(self.content_frame)
        self.views["logs"] = logs_view
        
        # About
        about_view = AboutView(self.content_frame)
        self.views["about"] = about_view
    
    def _show_view(self, view_id: str):
        """Show a specific view"""
        # Check if trying to access Handle tab (formats) without password
        if view_id == "formats" and not self._handle_unlocked:
            self._request_password_for_handle()
            return
        
        # Hide current view
        if self.current_view and self.current_view in self.views:
            self.views[self.current_view].grid_forget()
        
        # Update nav buttons
        for vid, btn in self.nav_buttons.items():
            btn.set_active(vid == view_id)
        
        # Show new view
        if view_id in self.views:
            self.views[view_id].grid(row=0, column=0, sticky="nsew")
            self.current_view = view_id
    
    def _request_password_for_handle(self):
        """Show password dialog for Handle tab access"""
        def on_success():
            self._handle_unlocked = True
            self._show_view("formats")
            self._show_toast("Handle tab unlocked!", "success")
        
        def on_cancel():
            pass
        
        PasswordDialog(self, on_success=on_success, on_cancel=on_cancel)
    
    def _setup_callbacks(self):
        """Setup automation callbacks"""
        automation_controller.add_state_callback(self._on_state_change)
        automation_controller.add_stats_callback(self._on_stats_update)
        automation_controller.add_alarm_callback(self._on_new_alarms)
        
        # Register for error popups
        automation_controller.set_popup_callback(self._show_error_popup)
    
    def _show_error_popup(self, title: str, message: str, wait_event: threading.Event):
        """Show an interactive error popup that blocks the sender until OK is clicked"""
        def _show():
            CTkMessagebox(
                title=title,
                message=message,
                icon="warning",
                option_1="OK",
                font=ctk.CTkFont(size=13)
            )
            wait_event.set() # Resume the sender thread
            
        self.after(0, _show)
    
    def _start_update_loop(self):
        """Start the UI update loop"""
        self._update_ui()
    
    def _update_ui(self):
        """Periodic UI update"""
        try:
            # Update stats if running
            if automation_controller.is_running():
                stats = automation_controller.get_stats()
                self._update_dashboard_stats(stats)
        except Exception as e:
            pass
        
        # Schedule next update
        self.after(1000, self._update_ui)
    
    def _update_dashboard_stats(self, stats: AutomationStats):
        """Update dashboard with stats"""
        dashboard = self.views.get("dashboard")
        if not dashboard:
            return
        
        # Format uptime
        uptime_str = self._format_uptime(stats.uptime_seconds)
        
        dashboard.update_stats(
            uptime=uptime_str,
            alarms=stats.alarms_processed,
            messages=stats.messages_sent,
            queued=stats.messages_queued,
            sites=master_data.site_count,
            errors=stats.error_count
        )
        
        # Update sidebar
        self.uptime_label.configure(text=f"Uptime: {uptime_str}")
    
    def _format_uptime(self, seconds: int) -> str:
        """Format uptime as HH:MM:SS"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    # Event handlers
    def _on_start(self):
        """Handle start/stop button"""
        if automation_controller.is_running():
            # Stop
            automation_controller.stop()
        else:
            # Start
            dashboard = self.views.get("dashboard")
            if dashboard:
                dashboard.log("Starting automation...", "INFO")
            
            # Run in thread to not block UI
            thread = threading.Thread(target=self._start_automation)
            thread.daemon = True
            thread.start()
    
    def _start_automation(self):
        """Start automation in background thread"""
        success = automation_controller.start()
        
        if success:
            self.after(0, lambda: self._show_toast("Automation started successfully!", "success"))
        else:
            self.after(0, lambda: self._show_toast("Failed to start automation", "error"))
    
    def _on_pause(self):
        """Handle pause/resume button"""
        if automation_controller.get_state() == AutomationState.PAUSED:
            automation_controller.resume()
        else:
            automation_controller.pause()
    
    def _on_force_check(self):
        """Handle force check button"""
        thread = threading.Thread(target=automation_controller.force_check)
        thread.daemon = True
        thread.start()
        self._show_toast("Checking portals...", "info")
    
    def _on_force_send(self):
        """Handle force send button"""
        automation_controller.force_send_all()
        self._show_toast("Sending all pending alarms...", "info")
    
    def _on_settings_saved(self):
        """Handle settings saved"""
        self._show_toast("Settings saved successfully!", "success")
    
    def _on_state_change(self, state: AutomationState):
        """Handle automation state change"""
        def _update():
            dashboard = self.views.get("dashboard")
            
            if state == AutomationState.RUNNING:
                if dashboard:
                    dashboard.set_automation_running(True)
                    dashboard.log("Automation started", "SUCCESS")
                self.status_label.configure(text="● Running", text_color=Colors.SUCCESS)
            
            elif state == AutomationState.STOPPED:
                if dashboard:
                    dashboard.set_automation_running(False)
                    dashboard.log("Automation stopped", "INFO")
                self.status_label.configure(text="● Stopped", text_color=Colors.ERROR)
            
            elif state == AutomationState.PAUSED:
                if dashboard:
                    dashboard.set_automation_paused(True)
                    dashboard.log("Automation paused", "WARNING")
                self.status_label.configure(text="● Paused", text_color=Colors.WARNING)
            
            elif state == AutomationState.ERROR:
                if dashboard:
                    dashboard.log("Automation error occurred", "ERROR")
                self.status_label.configure(text="● Error", text_color=Colors.ERROR)
        
        self.after(0, _update)
    
    def _on_stats_update(self, stats: AutomationStats):
        """Handle stats update"""
        dashboard = self.views.get("dashboard")
        if dashboard:
            # Update portal status
            dashboard.update_portal_status(
                stats.portal_connected,
                stats.portal_logged_in
            )
            
            # Update WhatsApp status
            wa_status = "Connected" if stats.whatsapp_connected else "Disconnected"
            dashboard.update_whatsapp_status(wa_status)
    
    def _on_new_alarms(self, alarms, source: str = None):
        """Handle new alarms"""
        dashboard = self.views.get("dashboard")
        if not dashboard:
            return
            
        def _get_alarm_dict(alarm):
            return {
                'time': str(alarm.timestamp_str or datetime.now().strftime("%H:%M:%S")),
                'type': str(alarm.alarm_type or "Unknown"),
                'site_code': str(alarm.site_code or "Unknown"),
                'site_name': str(alarm.site_name or ""),
                'mbu': str(alarm.mbu or ""),
                'status': 'Pending'
            }
        
        if source:
            # Use replacement logic
            alarm_dicts = [_get_alarm_dict(a) for a in alarms]
            dashboard.update_alarms(alarm_dicts, source)
            
            # Add to log summary (just count or first few)
            dashboard.log(
                f"Updated {len(alarms)} active alarms from {source}",
                "INFO"
            )
        else:
            # Add additive logic (legacy)
            for alarm in alarms:
                # Add to table
                dashboard.add_alarm(_get_alarm_dict(alarm))
                
                # Add to log
                dashboard.log(
                    f"New alarm: {alarm.alarm_type} - {alarm.site_code}",
                    "ALARM" if "csl" in alarm.alarm_type.lower() else "INFO"
                )
    
    def _show_toast(self, message: str, toast_type: str = "info"):
        """Show a toast notification"""
        toast = ToastNotification(self, message, toast_type)
        toast.place(relx=0.5, rely=0.95, anchor="s")
    
    def _on_close(self):
        """Handle window close"""
        # Stop automation
        if automation_controller.is_running():
            automation_controller.stop()
        
        # Destroy window
        self.destroy()