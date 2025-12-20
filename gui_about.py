"""
GUI About View
About page and help information
"""

import customtkinter as ctk
from gui_components import Colors


class AboutView(ctk.CTkFrame):
    """About and help view"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_DARK, **kwargs)
        
        self._create_layout()
    
    def _create_layout(self):
        """Create the layout"""
        # Center content
        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Logo/Icon
        icon = ctk.CTkLabel(
            center_frame,
            text="🗼",
            font=ctk.CTkFont(size=80)
        )
        icon.pack(pady=(0, 20))
        
        # Title
        title = ctk.CTkLabel(
            center_frame,
            text="🖕 Telecom Alarm Automation 🖕",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack()

        title = ctk.CTkLabel(
            center_frame,
            text="😎 Made by Taha 😎",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=Colors.PRIMARY_DARK
        )
        title.pack(pady=(15, 10))
        # Version
        version = ctk.CTkLabel(
            center_frame,
            text="Version 1.0.0",
            font=ctk.CTkFont(size=14),
            text_color=Colors.TEXT_MUTED
        )
        version.pack(pady=(5, 20))
        
        # Description
        desc = ctk.CTkLabel(
            center_frame,
            text="Automated alarm monitoring and WhatsApp notification system\nfor telecom network operations.",
            font=ctk.CTkFont(size=13),
            text_color=Colors.TEXT_SECONDARY,
            justify="center"
        )
        desc.pack(pady=(0, 30))
        
        # Features box
        features_frame = ctk.CTkFrame(center_frame, fg_color=Colors.BG_CARD, corner_radius=10)
        features_frame.pack(pady=10, padx=20, fill="x")
        
        features_title = ctk.CTkLabel(
            features_frame,
            text="✨ Features",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.PRIMARY
        )
        features_title.pack(pady=(15, 10))
        
        features = [
            "🔔 Real-time alarm monitoring from MAE Portal",
            "📱 Automatic WhatsApp group notifications",
            "⏱️ Configurable timing for each alarm type",
            "🏢 Support for MBU, B2S, and OMO groups",
            "📊 Comprehensive statistics and logging",
            "🎨 Professional dark theme interface"
        ]
        
        for feature in features:
            feat_label = ctk.CTkLabel(
                features_frame,
                text=feature,
                font=ctk.CTkFont(size=12),
                text_color=Colors.TEXT_SECONDARY
            )
            feat_label.pack(pady=3, padx=20, anchor="w")
        
        # Bottom padding
        ctk.CTkFrame(features_frame, fg_color="transparent", height=15).pack()
        
        # Credits
        credits = ctk.CTkLabel(
            center_frame,
            text="Built for Network Operations Team",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        )
        credits.pack(pady=(30, 0))
        