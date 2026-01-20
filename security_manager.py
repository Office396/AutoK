import os
import socket
import uuid
import requests
import threading
import time
import subprocess
import getpass
from datetime import datetime
from pathlib import Path
from logger_module import logger

class SecurityManager:
    """
    Handles software security, PC identity tracking, and remote kill-switch/self-destruct logic.
    """
    def __init__(self):
        self.pc_name = socket.gethostname()
        self.username = getpass.getuser()
        self.mac_address = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0,8*6,8)][::-1])
        self.public_ip = self._get_public_ip()
        self.is_locked = False
        self.running = True
        
        # In a real production app, this would be a URL to your server/Firebase
        # For development, we'll use a local 'data/.control' file as a "remote" mock
        self.control_path = Path(__file__).parent / "data" / ".remote_control"
        
        # Start heartbeat/checker thread
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        
    def start(self):
        """Start the security monitor"""
        logger.info(f"Security Manager started for PC: {self.pc_name} ({self.public_ip})")
        self.monitor_thread.start()
        
    def _get_public_ip(self):
        """Get public IP address"""
        try:
            return requests.get('https://api.ipify.org', timeout=5).text
        except:
            return "Unknown"

    def _monitor_loop(self):
        """Periodically check for remote signals"""
        while self.running:
            try:
                # 1. Report identity (Heartbeat)
                self._report_status()
                
                # 2. Check for remote signals
                self._check_remote_signals()
                
                # Wait 30 seconds between checks
                time.sleep(30)
            except Exception as e:
                logger.error(f"Error in security monitor: {e}")
                time.sleep(60)

    def _report_status(self):
        """Report current machine status to the 'Control Center'"""
        # In production: requests.post(SERVER_URL, data=...)
        # Mocking by updating a registration file
        reg_file = Path(__file__).parent / "data" / "registrations.json"
        
        import json
        data = {}
        if reg_file.exists():
            try:
                with open(reg_file, 'r') as f:
                    data = json.load(f)
            except:
                pass
        
        data[self.mac_address] = {
            "pc_name": self.pc_name,
            "username": self.username,
            "public_ip": self.public_ip,
            "last_seen": datetime.now().isoformat(),
            "status": "LOCKED" if self.is_locked else "ACTIVE"
        }
        
        try:
            reg_file.parent.mkdir(parents=True, exist_ok=True)
            with open(reg_file, 'w') as f:
                json.dump(data, f, indent=4)
        except:
            pass

    def _check_remote_signals(self):
        """Check for lock or destruct signals"""
        if not self.control_path.exists():
            return
            
        try:
            import json
            with open(self.control_path, 'r') as f:
                commands = json.load(f)
            
            # Check command for THIS machine (using MAC as unique ID)
            machine_cmd = commands.get(self.mac_address)
            if machine_cmd:
                if machine_cmd == "LOCK":
                    self.is_locked = True
                    logger.warning("REMOTE LOCK SIGNAL RECEIVED!")
                elif machine_cmd == "DESTRUCT":
                    logger.critical("REMOTE SELF-DESTRUCT SIGNAL RECEIVED!")
                    self.self_destruct()
                elif machine_cmd == "UNLOCK":
                    self.is_locked = False
        except Exception as e:
            logger.error(f"Error checking remote signals: {e}")

    def self_destruct(self):
        """Execute self-destruct sequence"""
        logger.critical("Initiating self-destruct sequence...")
        
        # Create a batch file that waits, deletes everything, then deletes itself
        app_dir = Path(__file__).parent.absolute()
        bat_content = f"""
@echo off
timeout /t 5 /nobreak > nul
echo Deleting software logic...
rd /s /q "{app_dir}"
echo Done.
del "%~f0"
"""
        bat_path = Path.home() / "destruct.bat"
        with open(bat_path, "w") as f:
            f.write(bat_content)
        
        # Run it and exit the program
        subprocess.Popen(["cmd.exe", "/c", str(bat_path)], shell=True)
        os._exit(0)

# Global instance
security_manager = SecurityManager()
