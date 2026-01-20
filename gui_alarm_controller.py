import customtkinter as ctk
import threading
from typing import Dict, List
from gui_components import Colors
from config import settings
from whatsapp_handler import OrderedAlarmSender, whatsapp_handler
from alarm_scheduler import alarm_scheduler
from alarm_processor import alarm_processor
from logger_module import logger


class AlarmControllerView(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_DARK, **kwargs)
        self.on_save = None
        self.group_type_vars: Dict[str, Dict[str, Dict[str, ctk.BooleanVar]]] = {}
        self.skip_toggle_vars: Dict[str, ctk.BooleanVar] = {}  # NEW: Toggle alarm settings
        self._create_layout()
        self._load_state()

    def _normalize_alarm_label(self, name: str) -> str:
        n = (name or "").strip().lower()
        patterns = [
            "genset running",
            "genset operation",
            "dg running",
            "dg operation",
            "diesel generator running",
            "generator running"
        ]
        for p in patterns:
            if p in n:
                return "Genset Running"
        return name.strip()

    def _create_layout(self):
        # Make the entire view scrollable
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Create main scrollable container
        main_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent"
        )
        main_scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        main_scroll.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(
            main_scroll,
            fg_color=Colors.SURFACE_1,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        header.grid(row=0, column=0, sticky="ew", padx=25, pady=(25, 15))

        title = ctk.CTkLabel(
            header,
            text="🎛️ Alarm Controller",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title.pack(side="left", padx=25, pady=18)

        save_btn = ctk.CTkButton(
            header,
            text="💾 Save",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=Colors.SUCCESS,
            hover_color=Colors.SUCCESS_LIGHT,
            corner_radius=8,
            width=100,
            height=40,
            command=self._save_state
        )
        save_btn.pack(side="right", padx=25)

        # NEW: Toggle Alarm Settings Section - Modern styling
        toggle_section = ctk.CTkFrame(
            main_scroll,
            fg_color=Colors.SURFACE_1,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        toggle_section.grid(row=1, column=0, sticky="ew", padx=25, pady=(0, 15))
        toggle_inner = ctk.CTkFrame(toggle_section, fg_color="transparent")
        toggle_inner.pack(fill="x", padx=15, pady=12)
        
        toggle_title = ctk.CTkLabel(
            toggle_inner,
            text="🔄 Skip Toggle Alarms for MBUs",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        toggle_title.pack(anchor="w", pady=(0, 8))
        
        toggle_desc = ctk.CTkLabel(
            toggle_inner,
            text="Select MBUs where toggle alarms should NOT be sent:",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        )
        toggle_desc.pack(anchor="w", pady=(0, 8))
        
        toggle_grid = ctk.CTkFrame(toggle_inner, fg_color="transparent")
        toggle_grid.pack(fill="x")
        for i in range(4):
            toggle_grid.grid_columnconfigure(i, weight=1)
        
        # Create checkboxes for all MBUs
        mbu_list = list(settings.mbu_groups.mapping.keys())
        for idx, mbu in enumerate(mbu_list):
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(
                toggle_grid,
                text=mbu,
                variable=var,
                font=ctk.CTkFont(size=11),
                text_color=Colors.TEXT_SECONDARY,
                fg_color=Colors.PRIMARY,
                hover_color=Colors.PRIMARY_DARK
            )
            cb.grid(row=idx // 4, column=idx % 4, sticky="w", padx=5, pady=4)
            self.skip_toggle_vars[mbu] = var

        # Manual send section - Modern styling
        manual = ctk.CTkFrame(
            main_scroll,
            fg_color=Colors.SURFACE_1,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        manual.grid(row=2, column=0, sticky="ew", padx=25, pady=(0, 15))
        manual_inner = ctk.CTkFrame(manual, fg_color="transparent")
        manual_inner.pack(fill="x", padx=20, pady=18)
        manual_title = ctk.CTkLabel(
            manual_inner,
            text="📤 Send Selected Alarms",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        manual_title.pack(anchor="w")
        
        manual_desc = ctk.CTkLabel(
            manual_inner,
            text="Select alarm types and groups to send manually:",
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_MUTED
        )
        manual_desc.pack(anchor="w", pady=(2, 8))
        
        # Alarm Types Selection (Multi-select with checkboxes)
        alarm_types_label = ctk.CTkLabel(
            manual_inner,
            text="Alarm Types:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Colors.TEXT_SECONDARY
        )
        alarm_types_label.pack(anchor="w", pady=(8, 4))
        
        alarm_types_frame = ctk.CTkScrollableFrame(
            manual_inner,
            fg_color=Colors.BG_DARK,
            corner_radius=8,
            height=100
        )
        alarm_types_frame.pack(fill="x", pady=(0, 8))
        
        self._alarm_type_vars: Dict[str, ctk.BooleanVar] = {}
        alarm_types_grid = ctk.CTkFrame(alarm_types_frame, fg_color="transparent")
        alarm_types_grid.pack(fill="x", padx=8, pady=8)
        for i in range(3):
            alarm_types_grid.grid_columnconfigure(i, weight=1)
        
        # Dynamic alarm types for manual send
        manual_alarm_types = []
        seen_alarm_types = set()
        for t in OrderedAlarmSender.ALARM_TYPE_ORDER:
            label = self._normalize_alarm_label(t)
            key = label.strip().lower()
            if key and key not in seen_alarm_types:
                seen_alarm_types.add(key)
                manual_alarm_types.append(label)
        try:
            custom_types = set(settings.instant_alarms)
            for c_type in custom_types:
                label = self._normalize_alarm_label(c_type)
                key = label.strip().lower()
                if key and key not in seen_alarm_types:
                    seen_alarm_types.add(key)
                    manual_alarm_types.append(label)
        except:
            pass

        for idx, atype in enumerate(manual_alarm_types):
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(
                alarm_types_grid,
                text=atype,
                variable=var,
                font=ctk.CTkFont(size=11),
                text_color=Colors.TEXT_SECONDARY,
                fg_color=Colors.PRIMARY,
                hover_color=Colors.PRIMARY_DARK
            )
            cb.grid(row=idx // 3, column=idx % 3, sticky="w", padx=5, pady=3)
            self._alarm_type_vars[atype] = var
        
        # Groups Selection (All groups at once - no dropdown)
        controls = ctk.CTkFrame(manual_inner, fg_color="transparent")
        controls.pack(fill="x", pady=(8, 4))
        
        groups_label = ctk.CTkLabel(
            controls,
            text="Groups:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Colors.TEXT_SECONDARY
        )
        groups_label.pack(side="left")
        
        self.select_all_var = ctk.BooleanVar(value=False)
        select_all_cb = ctk.CTkCheckBox(
            controls,
            text="Select All Groups",
            variable=self.select_all_var,
            command=self._on_select_all_toggle,
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_SECONDARY,
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_DARK
        )
        select_all_cb.pack(side="left", padx=20)
        
        send_btn = ctk.CTkButton(
            controls,
            text="📤 Send Selected",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=Colors.ACCENT_PURPLE,
            hover_color=Colors.SECONDARY_DARK,
            corner_radius=8,
            width=140,
            height=40,
            command=self._on_send_selected
        )
        send_btn.pack(side="right")
        
        # Show ALL groups at once (MBU + B2S + OMO)
        self.manual_groups_frame = ctk.CTkScrollableFrame(
            manual_inner,
            fg_color=Colors.BG_DARK,
            corner_radius=8,
            height=150
        )
        self.manual_groups_frame.pack(fill="x", pady=(8, 8))
        self._manual_group_vars: Dict[str, tuple] = {}  # {display_name: (group_type, group_id, BooleanVar)}
        self._render_all_groups()

        # Alarm control tabs - now inside scrollable area with modern styling
        tabs_container = ctk.CTkFrame(
            main_scroll,
            fg_color=Colors.SURFACE_1,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        tabs_container.grid(row=3, column=0, sticky="ew", padx=25, pady=(0, 25))
        
        tabs = ctk.CTkTabview(tabs_container)
        tabs.pack(fill="both", expand=True, padx=15, pady=15)
        tabs.add("MBU")
        tabs.add("B2S")
        tabs.add("OMO")

        self._build_group_tab(tabs.tab("MBU"), "MBU", list(settings.mbu_groups.mapping.keys()))
        self._build_group_tab(tabs.tab("B2S"), "B2S", list(settings.b2s_groups.mapping.keys()))
        self._build_group_tab(tabs.tab("OMO"), "OMO", list(settings.omo_groups.mapping.keys()))

    def _build_group_tab(self, parent: ctk.CTkFrame, group_type: str, group_ids: List[str]):
        container = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        self.group_type_vars[group_type] = {}

        # Merge static list with any custom instant alarms defined in settings
        # This ensures user-defined alarms also appear in the controller
        alarm_types = []
        seen_alarm_types = set()
        for t in OrderedAlarmSender.ALARM_TYPE_ORDER:
            label = self._normalize_alarm_label(t)
            key = label.strip().lower()
            if key and key not in seen_alarm_types:
                seen_alarm_types.add(key)
                alarm_types.append(label)
        try:
            custom_types = set(settings.instant_alarms)
            for c_type in custom_types:
                label = self._normalize_alarm_label(c_type)
                key = label.strip().lower()
                if key and key not in seen_alarm_types:
                    seen_alarm_types.add(key)
                    alarm_types.append(label)
        except:
            pass
            
        # Sort for better UX (keep important ones at top if needed, but adding to end is safer for now)
        # alarm_types.sort()

        for gid in group_ids:
            frame = ctk.CTkFrame(container, fg_color=Colors.BG_CARD, corner_radius=10)
            frame.pack(fill="x", pady=8)

            header = ctk.CTkFrame(frame, fg_color="transparent")
            header.pack(fill="x", padx=15, pady=(10, 5))

            label = ctk.CTkLabel(
                header,
                text=f"{group_type}: {gid}",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=Colors.TEXT_PRIMARY
            )
            label.pack(side="left")

            grid = ctk.CTkFrame(frame, fg_color="transparent")
            grid.pack(fill="x", padx=15, pady=(0, 10))
            # Grid with 3 columns for neat layout
            for col in range(3):
                grid.grid_columnconfigure(col, weight=1)

            self.group_type_vars[group_type][gid] = {}

            for idx, atype in enumerate(alarm_types):
                var = ctk.BooleanVar(value=False)
                cb = ctk.CTkCheckBox(
                    grid,
                    text=f"Disable {atype}",
                    variable=var,
                    font=ctk.CTkFont(size=12),
                    text_color=Colors.TEXT_SECONDARY,
                    fg_color=Colors.PRIMARY,
                    hover_color=Colors.PRIMARY_DARK
                )
                row = idx // 3
                col = idx % 3
                cb.grid(row=row, column=col, sticky="w", padx=5, pady=4)
                self.group_type_vars[group_type][gid][atype] = var

    def _load_state(self):
        """Load settings from config"""
        ctrl = settings.send_control
        
        # Load alarm control settings
        for gtype, groups in self.group_type_vars.items():
            disabled_map = ctrl.get(gtype, {})
            for gid, types_vars in groups.items():
                disabled_list = [t.strip().lower() for t in disabled_map.get(gid, [])]
                for atype, var in types_vars.items():
                    var.set(atype.strip().lower() in disabled_list)
        
        # Load toggle alarm settings
        skip_mbus = settings.skip_toggle_mbus if hasattr(settings, 'skip_toggle_mbus') else []
        for mbu, var in self.skip_toggle_vars.items():
            var.set(mbu in skip_mbus)

    def _save_state(self):
        """Save settings to config"""
        # Save alarm control settings
        for gtype, groups in self.group_type_vars.items():
            settings.send_control.setdefault(gtype, {})
            for gid, types_vars in groups.items():
                disabled = []
                for atype, var in types_vars.items():
                    if var.get():
                        disabled.append(atype)
                settings.send_control[gtype][gid] = disabled
        
        # Save toggle alarm settings
        settings.skip_toggle_mbus = [mbu for mbu, var in self.skip_toggle_vars.items() if var.get()]
        
        settings.save()
        if self.on_save:
            try:
                self.on_save()
            except:
                pass

    def _render_all_groups(self):
        """Render all groups (MBU, B2S, OMO) at once - no dropdown needed"""
        for w in self.manual_groups_frame.winfo_children():
            w.destroy()
        self._manual_group_vars.clear()
        
        # Collect all groups from all types
        all_groups = []
        
        # MBU groups
        for gid in settings.mbu_groups.mapping.keys():
            all_groups.append(("MBU", gid, f"[MBU] {gid}"))
        
        # B2S groups
        for gid in settings.b2s_groups.mapping.keys():
            all_groups.append(("B2S", gid, f"[B2S] {gid}"))
        
        # OMO groups
        for gid in settings.omo_groups.mapping.keys():
            all_groups.append(("OMO", gid, f"[OMO] {gid}"))
        
        # Create grid layout
        grid = ctk.CTkFrame(self.manual_groups_frame, fg_color="transparent")
        grid.pack(fill="x", padx=8, pady=8)
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1)
        
        # Create checkboxes for all groups
        for idx, (gtype, gid, display_name) in enumerate(all_groups):
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(
                grid,
                text=display_name,
                variable=var,
                font=ctk.CTkFont(size=11),
                text_color=Colors.TEXT_SECONDARY,
                fg_color=Colors.PRIMARY,
                hover_color=Colors.PRIMARY_DARK
            )
            cb.grid(row=idx // 3, column=idx % 3, sticky="w", padx=5, pady=4)
            self._manual_group_vars[display_name] = (gtype, gid, var)

    def _on_send_selected(self):
        """Send selected alarm types to selected groups"""
        try:
            # Get selected alarm types (multi-select)
            selected_alarm_types = [atype for atype, var in self._alarm_type_vars.items() if var.get()]
            if not selected_alarm_types:
                logger.warning("No alarm types selected for manual send")
                return
            
            # Get selected groups (now includes type info)
            selected_groups = [(gtype, gid) for display_name, (gtype, gid, var) in self._manual_group_vars.items() if var.get()]
            if not selected_groups:
                logger.warning("No groups selected for manual send")
                return
            
            def _do_send():
                try:
                    total_queued = 0
                    
                    # Process each selected alarm type
                    for alarm_type in selected_alarm_types:
                        all_alarms = alarm_scheduler.get_pending_for_type(alarm_type)
                        atype_lower = alarm_type.lower()
                        filtered = [a for a in all_alarms if a.alarm_type.lower() == atype_lower]
                        
                        # Process each selected group
                        for gtype, gid in selected_groups:
                            if gtype == "MBU":
                                group_name = settings.get_whatsapp_group_name(gid)
                                group_alarms = [a for a in filtered if a.mbu == gid and not a.is_toggle]
                                toggle_alarms = [a for a in filtered if a.mbu == gid and a.is_toggle]
                                
                                if group_alarms:
                                    message = alarm_processor.format_mbu_message(group_alarms)
                                    if message.strip() and group_name:
                                        priority = 1 if atype_lower in [t.strip().lower() for t in settings.instant_alarms] else 2
                                        whatsapp_handler.queue_message(group_name, message, alarm_type, priority)
                                        total_queued += 1
                                
                                if toggle_alarms:
                                    toggle_message = alarm_processor.format_toggle_message(toggle_alarms)
                                    if toggle_message.strip() and group_name:
                                        whatsapp_handler.queue_message(group_name, toggle_message, f"{alarm_type} (Toggle)", 2)
                                        total_queued += 1
                            
                            elif gtype == "B2S":
                                group_name = settings.get_b2s_group_name(gid)
                                group_alarms = [a for a in filtered if a.is_b2s and a.b2s_company == gid]
                                if group_alarms and group_name:
                                    message = alarm_processor.format_b2s_message(group_alarms)
                                    if message.strip():
                                        whatsapp_handler.queue_message(group_name, message, alarm_type, 2)
                                        total_queued += 1
                            
                            else:  # OMO
                                group_name = settings.get_omo_group_name(gid)
                                group_alarms = [a for a in filtered if a.is_omo and a.omo_company == gid]
                                if group_alarms and group_name:
                                    message = alarm_processor.format_omo_message(group_alarms)
                                    if message.strip():
                                        whatsapp_handler.queue_message(group_name, message, alarm_type, 2)
                                        total_queued += 1
                    
                    if total_queued > 0:
                        logger.success(f"Manual send queued: {total_queued} message batches")
                    else:
                        logger.info("No matching alarms found for manual send")
                except Exception as e:
                    logger.error(f"Manual send error: {e}")
            
            thread = threading.Thread(target=_do_send, daemon=True)
            thread.start()
        except Exception as e:
            logger.error(f"Manual send error: {e}")
    
    def _on_select_all_toggle(self):
        """Toggle all group checkboxes"""
        try:
            state = self.select_all_var.get()
            for display_name, (gtype, gid, var) in self._manual_group_vars.items():
                var.set(state)
        except:
            pass
