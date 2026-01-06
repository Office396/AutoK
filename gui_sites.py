"""
GUI Sites View
View and search master site data
"""

import customtkinter as ctk
from typing import Optional, Callable, Dict, List
import threading

from gui_components import (
    Colors, SearchBox, ActionButton, StatCard
)
from master_data import master_data, SiteInfo
from config import settings


class SitesView(ctk.CTkFrame):
    """View for browsing and searching site data"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_DARK, **kwargs)
        
        self._create_layout()
        self._load_data()
    
    def _create_layout(self):
        """Create the layout"""
        # Configure grid - 3 rows: header, main content, and duplicates
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # Main content area
        self.grid_rowconfigure(2, weight=0)  # Duplicates section (if any)
            
        # Header
        self._create_header()
            
        # Main content
        self._create_content()
            
        # Duplicate sites section
        self._create_duplicates_section()
    
    def _create_header(self):
        """Create header with search and stats"""
        header = ctk.CTkFrame(self, fg_color=Colors.BG_MEDIUM, corner_radius=10)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        
        # Title and search
        top_row = ctk.CTkFrame(header, fg_color="transparent")
        top_row.pack(fill="x", padx=20, pady=15)
        
        title = ctk.CTkLabel(
            top_row,
            text="📍 Site Database",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(side="left")
        
        # Search box
        self.search_box = SearchBox(
            top_row,
            placeholder="Search sites by code or name...",
            on_search=self._on_search
        )
        self.search_box.pack(side="right")
        
        # Stats row
        stats_row = ctk.CTkFrame(header, fg_color="transparent")
        stats_row.pack(fill="x", padx=20, pady=(0, 15))
        
        self.total_sites_label = ctk.CTkLabel(
            stats_row,
            text="Total Sites: 0",
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_SECONDARY
        )
        self.total_sites_label.pack(side="left", padx=(0, 30))
        
        self.b2s_sites_label = ctk.CTkLabel(
            stats_row,
            text="B2S Sites: 0",
            font=ctk.CTkFont(size=12),
            text_color=Colors.ACCENT_BLUE
        )
        self.b2s_sites_label.pack(side="left", padx=(0, 30))
        
        self.omo_sites_label = ctk.CTkLabel(
            stats_row,
            text="OMO Sites: 0",
            font=ctk.CTkFont(size=12),
            text_color=Colors.ACCENT_GREEN
        )
        self.omo_sites_label.pack(side="left", padx=(0, 30))
        
        # Reload button
        reload_btn = ActionButton(
            stats_row,
            text="Reload Data",
            icon="🔄",
            color=Colors.INFO,
            command=self._reload_data,
            width=120,
            height=32
        )
        reload_btn.pack(side="right")
    
    def _create_content(self):
        """Create main content area"""
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        
        # Configure content grid to have 2 rows: main content and duplicates
        content.grid_columnconfigure(0, weight=2)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)  # Main content (sites table + details)
        
        # Sites table
        table_container = ctk.CTkFrame(content, fg_color=Colors.BG_CARD, corner_radius=10)
        table_container.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # Table header
        table_header = ctk.CTkFrame(table_container, fg_color=Colors.BG_LIGHT, corner_radius=5)
        table_header.pack(fill="x", padx=10, pady=10)
        
        headers = [
            ("Site Code", 100),
            ("Site Name", 250),
            ("MBU", 100),
            ("Power Status", 150),
            ("B2S/OMO", 100),
        ]
        
        for header_text, width in headers:
            label = ctk.CTkLabel(
                table_header,
                text=header_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=Colors.TEXT_PRIMARY,
                width=width
            )
            label.pack(side="left", padx=5, pady=8)
        
        # Scrollable site list
        self.site_list = ctk.CTkScrollableFrame(
            table_container,
            fg_color="transparent"
        )
        self.site_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Site details panel
        self.details_panel = SiteDetailsPanel(content)
        self.details_panel.grid(row=0, column=1, sticky="nsew")
    
    def _create_duplicates_section(self):
        """Create section to display duplicate sites"""
        # Check if there are duplicates
        if master_data.duplicate_count == 0:
            return
        
        # Create duplicate sites section
        duplicates_frame = ctk.CTkFrame(self, fg_color=Colors.BG_CARD, corner_radius=10)
        duplicates_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        
        # Header for duplicates section
        dup_header = ctk.CTkFrame(duplicates_frame, fg_color=Colors.BG_LIGHT, corner_radius=5)
        dup_header.pack(fill="x", padx=10, pady=10)
        
        dup_title = ctk.CTkLabel(
            dup_header,
            text=f"⚠️ Duplicate Sites Found ({master_data.duplicate_count})",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Colors.WARNING
        )
        dup_title.pack(side="left", padx=5, pady=8)
        
        # Scrollable duplicate list
        self.duplicate_list = ctk.CTkScrollableFrame(
            duplicates_frame,
            fg_color="transparent",
            height=150
        )
        self.duplicate_list.pack(fill="x", padx=10, pady=(0, 10))
        
        # Add duplicate sites to the list
        for dup in master_data.get_duplicate_sites():
            dup_row = ctk.CTkFrame(self.duplicate_list, fg_color=Colors.BG_MEDIUM, corner_radius=5)
            dup_row.pack(fill="x", pady=2)
            
            dup_info = ctk.CTkLabel(
                dup_row,
                text=f"Site: {dup['site_code']} | Row: {dup['row_number']} | New: {dup['new_name'][:30]}... | Existing: {dup['existing_name'][:30]}...",
                font=ctk.CTkFont(size=10),
                text_color=Colors.WARNING,
                anchor="w"
            )
            dup_info.pack(fill="x", padx=5, pady=3)
    
    def _load_data(self):
        """Load site data"""
        if not master_data.is_loaded:
            master_data.load()
        
        self._update_stats()
        self._display_sites(list(master_data.sites.values())[:100])  # Show first 100
    
    def _reload_data(self):
        """Reload master data"""
        master_data.reload()
        self._update_stats()
        self._display_sites(list(master_data.sites.values())[:100])
    
    def _update_stats(self):
        """Update statistics labels"""
        total = master_data.site_count
        b2s = len(master_data.get_b2s_sites())
        omo = len(master_data.get_omo_sites())
        
        self.total_sites_label.configure(text=f"Total Sites: {total}")
        self.b2s_sites_label.configure(text=f"B2S Sites: {b2s}")
        self.omo_sites_label.configure(text=f"OMO Sites: {omo}")
    
    def _on_search(self, query: str):
        """Handle search"""
        if not query:
            self._display_sites(list(master_data.sites.values())[:100])
        else:
            results = master_data.search_sites(query)
            self._display_sites(results[:100])
    
    def _display_sites(self, sites: List[SiteInfo]):
        """Display sites in the list"""
        # Clear existing
        for widget in self.site_list.winfo_children():
            widget.destroy()
        
        # Add sites
        for i, site in enumerate(sites):
            row = SiteRow(
                self.site_list,
                site,
                on_click=lambda s=site: self._show_site_details(s)
            )
            row.pack(fill="x", pady=1)
            
            # Alternate colors
            if i % 2 == 0:
                row.configure(fg_color=Colors.BG_MEDIUM)
    
    def _show_site_details(self, site: SiteInfo):
        """Show site details in panel"""
        self.details_panel.show_site(site)


class SiteRow(ctk.CTkFrame):
    """A row in the sites table"""
    
    def __init__(self, parent, site: SiteInfo, on_click: Callable = None, **kwargs):
        super().__init__(parent, fg_color="transparent", height=35, **kwargs)
        self.pack_propagate(False)
        
        self.site = site
        self.on_click = on_click
        
        # Bind click
        self.bind("<Button-1>", self._on_click)
        
        # Site Code
        code_label = ctk.CTkLabel(
            self,
            text=site.site_code,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=Colors.ACCENT_BLUE,
            width=100
        )
        code_label.pack(side="left", padx=5)
        code_label.bind("<Button-1>", self._on_click)
        
        # Site Name
        name = site.site_name[:35] + "..." if len(site.site_name) > 35 else site.site_name
        name_label = ctk.CTkLabel(
            self,
            text=name,
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_SECONDARY,
            width=250,
            anchor="w"
        )
        name_label.pack(side="left", padx=5)
        name_label.bind("<Button-1>", self._on_click)
        
        # MBU
        mbu_label = ctk.CTkLabel(
            self,
            text=site.new_mbu or "-",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_PRIMARY,
            width=100
        )
        mbu_label.pack(side="left", padx=5)
        mbu_label.bind("<Button-1>", self._on_click)
        
        # Power Status
        status = site.power_status[:20] if site.power_status else "-"
        status_label = ctk.CTkLabel(
            self,
            text=status,
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED,
            width=150
        )
        status_label.pack(side="left", padx=5)
        status_label.bind("<Button-1>", self._on_click)
        
        # B2S/OMO indicator
        if site.is_b2s:
            type_text = f"B2S: {site.b2s_company}"
            type_color = Colors.WARNING
        elif site.is_omo:
            type_text = f"OMO: {site.omo_company}"
            type_color = Colors.ACCENT_GREEN
        else:
            type_text = "Jazz"
            type_color = Colors.TEXT_MUTED
        
        type_label = ctk.CTkLabel(
            self,
            text=type_text,
            font=ctk.CTkFont(size=11),
            text_color=type_color,
            width=100
        )
        type_label.pack(side="left", padx=5)
        type_label.bind("<Button-1>", self._on_click)
    
    def _on_click(self, event=None):
        if self.on_click:
            self.on_click()


class SiteDetailsPanel(ctk.CTkFrame):
    """Panel showing detailed site information"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_CARD, corner_radius=10, **kwargs)
        
        # Title
        self.title_label = ctk.CTkLabel(
            self,
            text="📋 Site Details",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        self.title_label.pack(padx=15, pady=(15, 10), anchor="w")
        
        # Content
        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Placeholder
        self.placeholder = ctk.CTkLabel(
            self.content,
            text="Click on a site to view details",
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_MUTED
        )
        self.placeholder.pack(pady=50)
    
    def show_site(self, site: SiteInfo):
        """Display site details"""
        # Clear content
        for widget in self.content.winfo_children():
            widget.destroy()
        
        # Site code header
        code_frame = ctk.CTkFrame(self.content, fg_color=Colors.BG_LIGHT, corner_radius=5)
        code_frame.pack(fill="x", pady=(0, 15))
        
        code_label = ctk.CTkLabel(
            code_frame,
            text=site.site_code,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=Colors.PRIMARY
        )
        code_label.pack(pady=10)
        
        # Details
        details = [
            ("Site Name", site.site_name),
            ("Site ID", site.site_id),
            ("Technology", site.technology),
            ("MBU (New)", site.new_mbu),
            ("MBU (Old)", site.old_mbu),
            ("Power Status", site.power_status),
            ("Latitude", str(site.latitude) if site.latitude else "-"),
            ("Longitude", str(site.longitude) if site.longitude else "-"),
            ("Dependent Sites", site.dependent_sites),
            ("", ""),  # Separator
            ("B2S/OMO Name", site.omo_b2s_name or "-"),
            ("B2S/OMO ID", site.omo_b2s_id or "-"),
            ("FTTS Ring ID", site.ftts_ring_id or "-"),
            ("", ""),  # Separator
            ("HW MBU Lead", site.hw_mbu_lead or "-"),
            ("Day Tech", site.day_tech or "-"),
            ("Night Tech", site.night_tech or "-"),
            ("Jazz MBU Tech", site.jazz_mbu_tech or "-"),
            ("Jazz MBU Lead", site.jazz_mbu_lead or "-"),
        ]
        
        for label, value in details:
            if not label:  # Separator
                sep = ctk.CTkFrame(self.content, fg_color=Colors.BORDER, height=1)
                sep.pack(fill="x", pady=10)
                continue
            
            row = ctk.CTkFrame(self.content, fg_color="transparent")
            row.pack(fill="x", pady=3)
            
            label_widget = ctk.CTkLabel(
                row,
                text=f"{label}:",
                font=ctk.CTkFont(size=11),
                text_color=Colors.TEXT_MUTED,
                width=120,
                anchor="w"
            )
            label_widget.pack(side="left")
            
            value_widget = ctk.CTkLabel(
                row,
                text=str(value) if value else "-",
                font=ctk.CTkFont(size=11),
                text_color=Colors.TEXT_PRIMARY,
                wraplength=180,
                anchor="w",
                justify="left"
            )
            value_widget.pack(side="left", fill="x", expand=True)