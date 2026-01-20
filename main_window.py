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
        self.geometry("1450x850")  # Slightly larger for better spacing
        self.minsize(1280, 720)
        
        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Configure modern dark background
        self.configure(fg_color=Colors.BG_DARK)
        self.attributes("-topmost", False)
        self.bind("<FocusOut>", lambda e: self.attributes("-topmost", False))
        self.bind("<FocusIn>", lambda e: self.attributes("-topmost", False))
        
        # Views
        self.views: Dict[str, ctk.CTkFrame] = {}
        self.current_view: Optional[str] = None
        self._handle_unlocked = False  # Password protection state
        
        # CRITICAL: Initialize state flags BEFORE creating layout
        self._resize_in_progress = False
        self._is_minimized = False
        self._last_state = self.state()
        self._update_interval = 3000  # Start with 3 seconds, will adapt
        
        # Create layout
        self._create_layout()
        
        # Setup callbacks
        self._setup_callbacks()
        
        # Handle close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Bind window events
        self.bind('<Configure>', self._on_window_configure)
        
        # Start smart update loop (only updates when needed)
        self._start_smart_updates()
    
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
        """Create the modern sidebar navigation with enhanced styling"""
        sidebar = ctk.CTkFrame(
            self,
            fg_color=Colors.SURFACE_1,
            width=240,
            corner_radius=0,
            border_width=0
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        
        # Logo section with gradient-like effect
        logo_frame = ctk.CTkFrame(sidebar, fg_color=Colors.BG_MEDIUM, corner_radius=0)
        logo_frame.pack(fill="x", padx=0, pady=0)
        
        logo_inner = ctk.CTkFrame(logo_frame, fg_color="transparent")
        logo_inner.pack(fill="x", padx=20, pady=25)
        
        logo_icon = ctk.CTkLabel(
            logo_inner,
            text="🗼",
            font=ctk.CTkFont(size=42)
        )
        logo_icon.pack()
        
        logo_text = ctk.CTkLabel(
            logo_inner,
            text="Alarm Automation",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        logo_text.pack(pady=(8, 0))
        
        version_label = ctk.CTkLabel(
            logo_inner,
            text="v2.0",
            font=ctk.CTkFont(size=10),
            text_color=Colors.TEXT_MUTED
        )
        version_label.pack(pady=(2, 0))
        
        # Navigation section
        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.pack(fill="both", expand=True, padx=0, pady=15)
        
        # Navigation buttons
        self.nav_buttons: Dict[str, TabButton] = {}
        
        nav_items = [
            ("dashboard", "📊", "Dashboard"),
            ("alarms", "🔔", "Alarms"),
            ("formats", "📝", "Handler"),
            ("controller", "🛂", "Alarm Controller"),
            ("sites", "🗼", "Sites"),
            ("logs", "📜", "Logs"),
            ("settings", "⚙️", "Settings"),
            ("about", "ℹ️", "About"),
        ]
        
        for view_id, icon, label in nav_items:
            btn = TabButton(
                nav_frame,
                text=label,
                icon=icon,
                is_active=(view_id == "dashboard"),
                command=lambda v=view_id: self._show_view(v),
                width=200,
                height=44
            )
            btn.pack(padx=20, pady=4)
            self.nav_buttons[view_id] = btn
        
        # Bottom section with status and info
        bottom_frame = ctk.CTkFrame(sidebar, fg_color=Colors.BG_MEDIUM, corner_radius=0)
        bottom_frame.pack(side="bottom", fill="x", padx=0, pady=0)
        
        bottom_inner = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        bottom_inner.pack(fill="x", padx=20, pady=20)
        
        # Status indicator with modern dot
        status_frame = ctk.CTkFrame(bottom_inner, fg_color="transparent")
        status_frame.pack(fill="x")
        
        self.status_dot = ctk.CTkFrame(
            status_frame,
            width=10,
            height=10,
            corner_radius=5,
            fg_color=Colors.ERROR
        )
        self.status_dot.pack(side="left", padx=(0, 10))
        self.status_dot.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Stopped",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Colors.TEXT_SECONDARY
        )
        self.status_label.pack(side="left")
        
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
        
        # Alarms
        from gui_alarms import AlarmsView
        alarms_view = AlarmsView(self.content_frame)
        self.views["alarms"] = alarms_view
        
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
        
        # Alarm Controller
        from gui_alarm_controller import AlarmControllerView
        controller_view = AlarmControllerView(self.content_frame)
        controller_view.on_save = self._on_controller_saved
        self.views["controller"] = controller_view
        
        # About
        about_view = AboutView(self.content_frame)
        self.views["about"] = about_view
    
    def _show_view(self, view_id: str):
        """Show a specific view - FIXED: No widget destruction during tab switch"""
        # Check if trying to access Handle tab (formats) without password
        if view_id == "formats" and not self._handle_unlocked:
            self._request_password_for_handle()
            return
        
        # Already showing this view, no need to do anything
        if self.current_view == view_id:
            return
        
        # CRITICAL FIX: Use lower() to hide/show instead of grid_remove/grid
        # This prevents widget destruction/recreation that causes graphics issues
        try:
            # Hide current view using lower (move to back, invisible but not destroyed)
            if self.current_view and self.current_view in self.views:
                try:
                    current_view = self.views[self.current_view]
                    # Use lower instead of grid_remove to keep widgets intact
                    current_view.lower()
                    # Also use pack_forget if it was packed, but keep the widget alive
                    try:
                        current_view.grid_remove()
                    except:
                        pass
                except:
                    pass
            
            # Update nav buttons
            for vid, btn in self.nav_buttons.items():
                btn.set_active(vid == view_id)
            
            # Show new view
            if view_id in self.views:
                try:
                    new_view = self.views[view_id]
                    # Use grid instead of recreating - widget already exists
                    new_view.grid(row=0, column=0, sticky="nsew")
                    # Lift to front (make visible)
                    new_view.lift()
                    self.current_view = view_id
                    
                    # CRITICAL FIX: Update once after tab switch, but don't force
                    # Excel doesn't redraw everything on tab switch - it just shows what's there
                    self.update_idletasks()
                except Exception as e:
                    logger.debug(f"Error showing view {view_id}: {e}")
        except Exception as e:
            logger.debug(f"Error in _show_view: {e}")
    
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
    
    def _start_smart_updates(self):
        """Start smart update loop - only updates when automation is running and visible"""
        self._do_smart_update()
    
    def _do_smart_update(self):
        """Smart update - adaptive interval based on activity"""
        try:
            # --- SECURITY CHECK ---
            from security_manager import security_manager
            if security_manager.is_locked:
                self._handle_remote_lock()
                return
                
            # Check if minimized by comparing window state
            current_state = self.state()
            self._is_minimized = (current_state == 'iconic' or current_state == 'withdrawn')
            
            # Adaptive interval: faster when active, slower when idle
            is_running = automation_controller.is_running()
            state = automation_controller.get_state()
            
            # Only update if visible and not resizing
            if not self._is_minimized and not self._resize_in_progress:
                if is_running:
                    stats = automation_controller.get_stats()
                    self._update_dashboard_stats(stats)
                    
                    # Faster updates when running (3 seconds - reduced from 2 to prevent freezing)
                    self._update_interval = 3000
                elif state == AutomationState.STARTING:
                    # Much slower during startup to prevent blocking (10 seconds)
                    self._update_interval = 10000
                else:
                    # Slower updates when stopped (5 seconds)
                    self._update_interval = 5000
            else:
                # Much slower when minimized (10 seconds)
                self._update_interval = 10000
        except:
            pass
        
        # Reschedule with adaptive interval
        try:
            if self.winfo_exists():
                self.after(self._update_interval, self._do_smart_update)
        except:
            pass
    
    def _update_dashboard_stats(self, stats: AutomationStats):
        """Update dashboard with stats - EVENT DRIVEN with change detection"""
        # Skip if minimized or resizing
        if self._is_minimized or self._resize_in_progress:
            return
        
        dashboard = self.views.get("dashboard")
        if not dashboard:
            return
        
        # Check if stats actually changed (avoid unnecessary updates)
        if not hasattr(self, '_last_stats'):
            self._last_stats = {}
        
        current_stats = {
            'uptime': stats.uptime_seconds,
            'alarms': stats.alarms_processed,
            'messages': stats.messages_sent,
            'queued': stats.messages_queued,
            'errors': stats.error_count
        }
        
        # Only update if something changed
        if current_stats == self._last_stats:
            return
        
        self._last_stats = current_stats
        
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
        elif automation_controller.get_state() == AutomationState.STARTING:
            # Already starting, ignore multiple clicks
            return
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

    def _handle_remote_lock(self):
        """Handle remote lock signal by showing a locking overlay"""
        if hasattr(self, '_lock_overlay'):
            return
            
        # Stop everything
        automation_controller.stop()
        
        # Create full-screen dark overlay
        self._lock_overlay = ctk.CTkFrame(self, fg_color="#000000")
        self._lock_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        ctk.CTkLabel(
            self._lock_overlay,
            text="⚠️ SYSTEM LOCKED",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color="#FF4C4C"
        ).pack(expand=True, pady=(0, 10))
        
        ctk.CTkLabel(
            self._lock_overlay,
            text="This software has been remotely disabled by the owner.\nPlease contact the administrator.",
            font=ctk.CTkFont(size=14),
            text_color="white"
        ).pack(expand=True, pady=(0, 100))
        
        logger.warning("Application UI locked by remote signal")
        
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
    
    def _on_controller_saved(self):
        self._show_toast("Alarm Controller settings saved!", "success")
    
    def _on_state_change(self, state: AutomationState):
        """Handle automation state change"""
        def _update():
            dashboard = self.views.get("dashboard")
            
            if state == AutomationState.RUNNING:
                if dashboard:
                    dashboard.set_automation_running(True)
                    dashboard.log("Automation started", "SUCCESS")
                self.status_label.configure(text="Running", text_color=Colors.SUCCESS)
                self.status_dot.configure(fg_color=Colors.SUCCESS)
            
            elif state == AutomationState.STOPPED:
                if dashboard:
                    dashboard.set_automation_running(False)
                    dashboard.log("Automation stopped", "INFO")
                self.status_label.configure(text="Stopped", text_color=Colors.TEXT_SECONDARY)
                self.status_dot.configure(fg_color=Colors.ERROR)
            
            elif state == AutomationState.PAUSED:
                if dashboard:
                    dashboard.set_automation_paused(True)
                    dashboard.log("Automation paused", "WARNING")
                self.status_label.configure(text="Paused", text_color=Colors.WARNING)
                self.status_dot.configure(fg_color=Colors.WARNING)
            
            elif state == AutomationState.ERROR:
                if dashboard:
                    dashboard.log("Automation error occurred", "ERROR")
                    dashboard.set_automation_error()  # Re-enable start button
                self.status_label.configure(text="Error", text_color=Colors.ERROR)
                self.status_dot.configure(fg_color=Colors.ERROR)
        
        self.after(0, _update)
    
    def _on_stats_update(self, stats: AutomationStats):
        """Handle stats update - Thread Safe, EVENT DRIVEN"""
        # Skip if window is minimized or resizing
        if self._is_minimized or self._resize_in_progress:
            return
        
        def _update():
            # Double-check state before updating
            if self._is_minimized or self._resize_in_progress:
                return
            
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
                
                # Get detailed WhatsApp stats (queue/sent preview) - NON-BLOCKING
                try:
                    from whatsapp_handler import whatsapp_handler
                    
                    # Only get detailed stats if dashboard widgets exist
                    if hasattr(dashboard, 'queue_list') and hasattr(dashboard, 'recently_sent_list'):
                        detailed_stats = whatsapp_handler.get_detailed_stats()
                        
                        # Build stats data for dashboard
                        stats_data = {
                            'status': wa_status,
                            'messages_sent': stats.messages_sent,
                            'queue_size': stats.messages_queued,
                            'current': detailed_stats.get('current'),
                            'queue_preview': detailed_stats.get('queue_preview', []),
                            'sent_recent': detailed_stats.get('sent_recent', [])
                        }
                        
                        # Update stats bar with queue/sent data
                        dashboard.update_stats_bar_event(stats_data)
                except Exception as e:
                    # Don't log errors during startup
                    pass
                
                # Also update stats
                self._update_dashboard_stats(stats)
        
        self.after(0, _update)
    
    def _on_new_alarms(self, alarms, source: str = None):
        """Handle new alarms - Thread Safe, EVENT DRIVEN"""
        # Skip if minimized or resizing
        if self._is_minimized or self._resize_in_progress:
            return
        
        def _update():
            # Double-check state
            if self._is_minimized or self._resize_in_progress:
                return
            
            dashboard = self.views.get("dashboard")
            alarms_view = self.views.get("alarms")
                
            def _get_alarm_dict(alarm):
                return {
                    'time': str(alarm.timestamp_str or datetime.now().strftime("%H:%M:%S")),
                    'type': str(alarm.alarm_type or "Unknown"),
                    'site_code': str(alarm.site_code or "Unknown"),
                    'site_name': str(alarm.site_name or ""),
                    'mbu': str(alarm.mbu or ""),
                    'status': 'Pending'
                }
            
            # Update alarms view (not dashboard)
            if alarms_view:
                if source:
                    # Use replacement logic
                    try:
                        alarm_dicts = [_get_alarm_dict(a) for a in alarms]
                        alarms_view.update_alarms(alarm_dicts, source)
                    except:
                        pass
                else:
                    # Add individual alarms
                    try:
                        for alarm in alarms:
                            alarms_view.add_alarm(_get_alarm_dict(alarm))
                    except:
                        pass
            
            # Update alarm counts in dashboard
            if dashboard:
                try:
                    # Count alarms by type
                    alarm_counts = {}
                    for alarm in alarms:
                        alarm_type = alarm.alarm_type or "Unknown"
                        if alarm_type in alarm_counts:
                            alarm_counts[alarm_type] += 1
                        else:
                            alarm_counts[alarm_type] = 1
                    
                    # Update dashboard with counts
                    for alarm_type, count in alarm_counts.items():
                        dashboard.add_alarm_update(alarm_type, count)
                except:
                    pass
        
        self.after(0, _update)
    
    def _show_toast(self, message: str, toast_type: str = "info"):
        """Show a toast notification"""
        toast = ToastNotification(self, message, toast_type)
        toast.place(relx=0.5, rely=0.95, anchor="s")
    
    def _on_window_configure(self, event):
        """Handle window configuration changes (resize, maximize, etc.)"""
        # CRITICAL FIX: Only track resize, not maximize/minimize
        # Only process if this is the main window, not child widgets
        if event.widget == self:
            # Debounce resize events
            if hasattr(self, '_resize_timer'):
                self.after_cancel(self._resize_timer)
            
            self._resize_in_progress = True
            # Wait 150ms after last event before allowing updates
            self._resize_timer = self.after(150, self._on_resize_complete)
    
    def _on_resize_complete(self):
        """Called when resize is complete"""
        self._resize_in_progress = False
        # Trigger immediate update after resize
        if automation_controller.is_running() and not self._is_minimized:
            self._do_smart_update()
    
    def _on_close(self):
        """Handle window close"""
        # Stop automation
        if automation_controller.is_running():
            automation_controller.stop()
        
        # Destroy window
        self.destroy()
