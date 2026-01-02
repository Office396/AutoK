"""
GUI About View
About page and application information
"""

import customtkinter as ctk
from gui_components import Colors


class AboutView(ctk.CTkFrame):
    """About view"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_DARK, **kwargs)
        
        self._create_layout()
    
    def _create_layout(self):
        """Create the layout"""
        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        icon = ctk.CTkLabel(
            center_frame,
            text="🗼",
            font=ctk.CTkFont(size=80)
        )
        icon.pack(pady=(0, 20))
        
        title = ctk.CTkLabel(
            center_frame,
            text="Autok",
            font=ctk.CTkFont(size=36, weight="bold"),
            text_color=Colors.PRIMARY
        )
        title.pack()
        
        subtitle = ctk.CTkLabel(
            center_frame,
            text="Telecom Alarm Automation System",
            font=ctk.CTkFont(size=16),
            text_color=Colors.TEXT_SECONDARY
        )
        subtitle.pack(pady=(5, 15))
        
        version = ctk.CTkLabel(
            center_frame,
            text="Version 1.0.0",
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_MUTED
        )
        version.pack(pady=(0, 30))
        
        info_frame = ctk.CTkFrame(center_frame, fg_color=Colors.BG_CARD, corner_radius=10)
        info_frame.pack(pady=10, padx=20, fill="x")
        
        inner = ctk.CTkFrame(info_frame, fg_color="transparent")
        inner.pack(padx=30, pady=20)
        
        developer_label = ctk.CTkLabel(
            inner,
            text="Developer",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        )
        developer_label.pack()
        
        developer_name = ctk.CTkLabel(
            inner,
            text="Taha Aslam",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        developer_name.pack(pady=(2, 15))
        
        powered_label = ctk.CTkLabel(
            inner,
            text="Powered by",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        )
        powered_label.pack()
        
        company_name = ctk.CTkLabel(
            inner,
            text="MTS Studios",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Colors.PRIMARY
        )
        company_name.pack(pady=(2, 0))
        
        copyright_label = ctk.CTkLabel(
            center_frame,
            text="© 2026 MTS Studios. All rights reserved.",
            font=ctk.CTkFont(size=10),
            text_color=Colors.TEXT_MUTED
        )
        copyright_label.pack(pady=(30, 0))
