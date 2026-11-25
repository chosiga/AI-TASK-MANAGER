import json
import queue
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox, ttk
from typing import Any

from ollama import RequestError, ResponseError

import assistant
import task_manager


SIDEBAR = "#ECEEF3"
SIDEBAR_HOVER = "#E1E3EB"
BACKGROUND = "#F5F6F8"
CARD = "#FFFFFF"
CHAT_BACKGROUND = "#F1F2F5"
TEXT = "#202637"
SUBTLE = "#7D8492"
BORDER = "#E7E8ED"
ACCENT = "#756BEA"
ACCENT_PALE = "#EEECFF"
PINK = "#E8A6C8"
BLUE = "#4B8FE8"
GREEN = "#65B77A"
ORANGE = "#E5A649"
RED = "#D66B70"
SEARCH_PLACEHOLDER = "Search tasks..."


class TaskManagerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Taskflow | AI Task Manager")
        self.root.geometry("1440x900")
        self.root.minsize(1000, 680)
        self.root.configure(bg=BACKGROUND)

        self.result_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.busy = False
        self.active_page = "Dashboard"
        self.search_value = tk.StringVar()
        self.global_search_value = tk.StringVar(value=SEARCH_PLACEHOLDER)
        self.filter_value = tk.StringVar(value="All tasks")
        self.input_value = tk.StringVar()
        self.status_value = tk.StringVar(value="Ready")
        self.chat_history: list[tuple[str, str]] = []

        self.nav_buttons: dict[str, tk.Button] = {}
        self.nav_indicators: dict[str, tk.Frame] = {}
        self.task_tree: ttk.Treeview | None = None
        self.transcript: tk.Frame | None = None
        self.chat_canvas: tk.Canvas | None = None
        self.chat_window: int | None = None
        self.send_button: ttk.Button | None = None
        self.stat_values: dict[str, tk.Label] = {}
        self.due_items: tk.Frame | None = None
        self.recent_items: tk.Frame | None = None
        self.progress_bar: ttk.Progressbar | None = None
        self.progress_text: tk.Label | None = None
        self.pending_nav_label: tk.Label | None = None

        self._configure_styles()
        self._build_shell()
        self._show_page("Dashboard")
        self._append_message(
            "Assistant",
            "Good morning! I can help organize your tasks. Try “Add study Python tomorrow”.",
        )
        self.refresh_tasks()
        self.root.after(100, self._poll_results)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Taskflow.Treeview",
            background=CARD,
            fieldbackground=CARD,
            foreground=TEXT,
            rowheight=39,
            borderwidth=0,
            font=("Helvetica", 10),
        )
        style.configure(
            "Taskflow.Treeview.Heading",
            background=CARD,
            foreground=SUBTLE,
            font=("Helvetica", 9, "bold"),
            relief="flat",
            padding=(8, 10),
        )
        style.map(
            "Taskflow.Treeview",
            background=[("selected", ACCENT_PALE)],
            foreground=[("selected", TEXT)],
        )
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#FFFFFF",
            padding=(13, 9),
            borderwidth=0,
            font=("Helvetica", 10, "bold"),
        )
        style.map("Accent.TButton", background=[("active", "#6258D3")])
        style.configure(
            "Quiet.TButton",
            background="#F0F1F5",
            foreground=TEXT,
            padding=(10, 8),
            borderwidth=0,
            font=("Helvetica", 9, "bold"),
        )
        style.map("Quiet.TButton", background=[("active", "#E6E7ED")])
        style.configure(
            "Taskflow.TCombobox",
            padding=(8, 6),
            fieldbackground=CARD,
            background=CARD,
        )
        style.configure(
            "Taskflow.Horizontal.TProgressbar",
            troughcolor="#ECEEF3",
            background=GREEN,
            bordercolor="#ECEEF3",
            lightcolor=GREEN,
            darkcolor=GREEN,
        )

    def _build_shell(self) -> None:
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        self.sidebar = tk.Frame(self.root, bg=SIDEBAR, width=190)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        self.main_area = tk.Frame(self.root, bg=BACKGROUND)
        self.main_area.grid(row=0, column=1, sticky="nsew")
        self.main_area.grid_rowconfigure(1, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)
        self._build_topbar()

        self.page_content = tk.Frame(self.main_area, bg=BACKGROUND, padx=22)
        self.page_content.grid(row=1, column=0, sticky="nsew", pady=(0, 18))
        self.page_content.grid_columnconfigure(0, weight=1)
        self.page_content.grid_rowconfigure(0, weight=1)

    def _build_sidebar(self) -> None:
        brand = tk.Frame(self.sidebar, bg=SIDEBAR, padx=19, pady=23)
        brand.pack(fill="x")
        tk.Label(
            brand,
            text="✦",
            bg=SIDEBAR,
            fg=ACCENT,
            font=("Helvetica", 18, "bold"),
        ).pack(side="left")
        tk.Label(
            brand,
            text="TASKFLOW",
            bg=SIDEBAR,
            fg=TEXT,
            font=("Helvetica", 12, "bold"),
        ).pack(side="left", padx=(7, 0))

        new_chat = tk.Button(
            self.sidebar,
            text="+    New Chat",
            anchor="w",
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=11,
            bg="#FFFFFF",
            fg=ACCENT,
            activebackground="#F8F7FF",
            activeforeground=ACCENT,
            font=("Helvetica", 10, "bold"),
            command=self.new_chat,
        )
        new_chat.pack(fill="x", padx=12, pady=(8, 20))

        tk.Label(
            self.sidebar,
            text="WORKSPACE",
            bg=SIDEBAR,
            fg="#9A9EAA",
            font=("Helvetica", 8, "bold"),
            anchor="w",
        ).pack(fill="x", padx=21, pady=(0, 8))

        for title, icon in (
            ("Dashboard", "▦"),
            ("My Tasks", "☷"),
            ("AI Assistant", "✧"),
        ):
            row = tk.Frame(self.sidebar, bg=SIDEBAR)
            row.pack(fill="x", padx=10, pady=2)
            indicator = tk.Frame(row, bg=SIDEBAR, width=3)
            indicator.pack(side="left", fill="y", padx=(0, 5), pady=4)
            button = tk.Button(
                row,
                text=f"{icon}   {title}",
                anchor="w",
                relief="flat",
                borderwidth=0,
                padx=11,
                pady=10,
                bg=SIDEBAR,
                fg="#606979",
                activebackground=SIDEBAR_HOVER,
                activeforeground=TEXT,
                font=("Helvetica", 10),
                command=lambda page=title: self._show_page(page),
            )
            button.pack(side="left", fill="x", expand=True)
            self.nav_buttons[title] = button
            self.nav_indicators[title] = indicator

        spacer = tk.Frame(self.sidebar, bg=SIDEBAR)
        spacer.pack(fill="both", expand=True)
        tk.Frame(self.sidebar, bg="#DADDE5", height=1).pack(fill="x", padx=18)
        local_status = tk.Frame(self.sidebar, bg=SIDEBAR, padx=18, pady=16)
        local_status.pack(fill="x")
        tk.Label(
            local_status,
            text="LOCAL AI",
            bg=SIDEBAR,
            fg="#9A9EAA",
            font=("Helvetica", 8, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            local_status,
            text=f"●  Ollama · {assistant.MODEL}",
            bg=SIDEBAR,
            fg="#596273",
            font=("Helvetica", 9),
            anchor="w",
        ).pack(fill="x", pady=(6, 0))
        self.pending_nav_label = tk.Label(
            local_status,
            text="",
            bg=SIDEBAR,
            fg=SUBTLE,
            font=("Helvetica", 9),
            anchor="w",
        )
        self.pending_nav_label.pack(fill="x", pady=(7, 0))

    def _build_topbar(self) -> None:
        topbar = tk.Frame(self.main_area, bg=BACKGROUND, padx=24, pady=15)
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_columnconfigure(1, weight=1)

        greeting = tk.Frame(topbar, bg=BACKGROUND)
        greeting.grid(row=0, column=0, sticky="w", padx=(0, 22))
        hour = datetime.now().hour
        greeting_text = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        tk.Label(
            greeting,
            text=f"{greeting_text},",
            bg=BACKGROUND,
            fg=TEXT,
            font=("Helvetica", 14, "bold"),
        ).pack(anchor="w")
        tk.Label(
            greeting,
            text="Here is your task overview",
            bg=BACKGROUND,
            fg=SUBTLE,
            font=("Helvetica", 9),
        ).pack(anchor="w", pady=(3, 0))

        search_card = tk.Frame(
            topbar,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        search_card.grid(row=0, column=1, sticky="ew", padx=(0, 18))
        search_card.grid_columnconfigure(1, weight=1)
        tk.Label(
            search_card,
            text="⌕",
            bg=CARD,
            fg=SUBTLE,
            font=("Helvetica", 17),
        ).grid(row=0, column=0, padx=(12, 4), pady=6)
        self.global_search = ttk.Entry(
            search_card,
            textvariable=self.global_search_value,
            font=("Helvetica", 10),
        )
        self.global_search.grid(row=0, column=1, sticky="ew", padx=(2, 12), pady=8)
        self.global_search.configure(cursor="xterm", foreground=SUBTLE)
        self.global_search.bind("<Return>", self._submit_search)
        self.global_search.bind("<FocusIn>", self._clear_search_placeholder)
        self.global_search.bind("<FocusOut>", self._restore_search_placeholder)

        account = tk.Frame(topbar, bg=BACKGROUND)
        account.grid(row=0, column=2, sticky="e")
        tk.Label(
            account,
            text="●",
            bg=BACKGROUND,
            fg=GREEN,
            font=("Helvetica", 9),
        ).pack(side="left", padx=(0, 5))
        tk.Label(
            account,
            textvariable=self.status_value,
            bg=BACKGROUND,
            fg=SUBTLE,
            font=("Helvetica", 9),
        ).pack(side="left", padx=(0, 10))
        avatar = tk.Label(
            account,
            text="A",
            bg="#E8E6FA",
            fg=ACCENT,
            width=3,
            height=1,
            font=("Helvetica", 10, "bold"),
        )
        avatar.pack(side="left")
        tk.Label(
            account,
            text="My workspace",
            bg=BACKGROUND,
            fg=TEXT,
            font=("Helvetica", 9, "bold"),
        ).pack(side="left", padx=(7, 0))

    def _card(self, parent: tk.Widget, **grid_options: Any) -> tk.Frame:
        background = parent.cget("bg")
        outer = tk.Frame(parent, bg=background, borderwidth=0, highlightthickness=0)
        outer.grid(**grid_options)
        canvas = tk.Canvas(
            outer,
            bg=background,
            borderwidth=0,
            highlightthickness=0,
        )
        canvas.place(relwidth=1, relheight=1)

        def draw_card(event: tk.Event) -> None:
            width = max(event.width, 1)
            height = max(event.height, 1)
            radius = min(13, width / 2, height / 2)
            points = (
                radius, 0,
                width - radius, 0,
                width, 0,
                width, radius,
                width, height - radius,
                width, height,
                width - radius, height,
                radius, height,
                0, height,
                0, height - radius,
                0, radius,
                0, 0,
                radius, 0,
            )
            canvas.delete("card")
            canvas.create_polygon(
                points,
                smooth=True,
                splinesteps=12,
                fill=CARD,
                outline=BORDER,
                width=1,
                tags="card",
            )

        outer.bind("<Configure>", draw_card)
        content = tk.Frame(outer, bg=CARD)
        content.pack(fill="both", expand=True, padx=7, pady=7)
        return content

    def _show_page(self, page: str) -> None:
        self.active_page = page
        for name, button in self.nav_buttons.items():
            active = name == page
            button.configure(
                bg=ACCENT_PALE if active else SIDEBAR,
                fg=TEXT if active else "#606979",
                activebackground=ACCENT_PALE if active else SIDEBAR_HOVER,
            )
            self.nav_indicators[name].configure(bg=PINK if active else SIDEBAR)

        self.task_tree = None
        self.transcript = None
        self.chat_canvas = None
        self.chat_window = None
        self.send_button = None
        self.stat_values = {}
        self.due_items = None
        self.recent_items = None
        self.progress_bar = None
        self.progress_text = None
        for widget in self.page_content.winfo_children():
            widget.destroy()

        if page == "Dashboard":
            self._build_dashboard()
        elif page == "My Tasks":
            self._build_tasks_page()
        else:
            self._build_assistant_page()
        self.refresh_tasks()

    def _submit_search(self, _event: tk.Event | None = None) -> None:
        query = self.global_search_value.get().strip()
        if query != SEARCH_PLACEHOLDER:
            self.search_value.set(query)
        self._show_page("My Tasks")
        self.refresh_tasks()
        if self.task_tree is not None:
            self.task_tree.focus_set()

    def _clear_search_placeholder(self, _event: tk.Event | None = None) -> None:
        if self.global_search_value.get() == SEARCH_PLACEHOLDER:
            self.global_search_value.set("")
            self.global_search.configure(foreground=TEXT)

    def _restore_search_placeholder(self, _event: tk.Event | None = None) -> None:
        if not self.global_search_value.get().strip():
            self.global_search_value.set(SEARCH_PLACEHOLDER)
            self.global_search.configure(foreground=SUBTLE)

    def new_chat(self) -> None:
        self.chat_history.clear()
        self._append_message(
            "Assistant",
            "New conversation started. What would you like to do with your tasks?",
        )
        self._show_page("AI Assistant")

    def _build_dashboard(self) -> None:
        self.page_content.grid_rowconfigure(0, weight=0)
        self.page_content.grid_rowconfigure(1, weight=1)
        self.page_content.grid_columnconfigure(0, weight=1)

        overview = tk.Frame(self.page_content, bg=BACKGROUND)
        overview.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        for column in range(4):
            overview.grid_columnconfigure(column, weight=1, uniform="stats")
        self._build_stat_card(overview, 0, "TOTAL TASKS", "0", ACCENT, "▣")
        self._build_stat_card(overview, 1, "PENDING", "0", ORANGE, "◷")
        self._build_stat_card(overview, 2, "COMPLETED", "0", GREEN, "✓")
        self._build_stat_card(overview, 3, "OVERDUE", "0", RED, "!")

        body = tk.Frame(self.page_content, bg=BACKGROUND)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=7, uniform="dashboard")
        body.grid_columnconfigure(1, weight=3, uniform="dashboard")
        self._build_chat_panel(body, row=0, column=0, padx=(0, 9))
        self._build_dashboard_sidebar(body)

    def _build_stat_card(
        self,
        parent: tk.Frame,
        column: int,
        title: str,
        value: str,
        accent: str,
        icon: str,
    ) -> None:
        card = self._card(
            parent,
            row=0,
            column=column,
            sticky="nsew",
            padx=(0, 9) if column < 3 else 0,
        )
        inner = tk.Frame(card, bg=CARD, padx=11, pady=10)
        inner.pack(fill="both", expand=True)
        icon_bg = "#F0EEFF" if accent == ACCENT else "#F8F0E2" if accent == ORANGE else "#EAF5EC" if accent == GREEN else "#F9ECEE"
        tk.Label(
            inner,
            text=icon,
            bg=icon_bg,
            fg=accent,
            width=2,
            height=1,
            font=("Helvetica", 11, "bold"),
        ).pack(side="left", padx=(0, 9))
        labels = tk.Frame(inner, bg=CARD)
        labels.pack(side="left", fill="x", expand=True)
        tk.Label(
            labels,
            text=title,
            bg=CARD,
            fg=SUBTLE,
            font=("Helvetica", 8, "bold"),
            anchor="w",
        ).pack(fill="x")
        value_label = tk.Label(
            labels,
            text=value,
            bg=CARD,
            fg=TEXT,
            font=("Helvetica", 19, "bold"),
            anchor="w",
        )
        value_label.pack(fill="x", pady=(3, 0))
        self.stat_values[title] = value_label

    def _build_dashboard_sidebar(self, parent: tk.Frame) -> None:
        sidebar = tk.Frame(parent, bg=BACKGROUND)
        sidebar.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(2, weight=1)

        due_card = self._card(sidebar, row=0, column=0, sticky="ew", pady=(0, 12))
        due_inner = tk.Frame(due_card, bg=CARD, padx=15, pady=13)
        due_inner.pack(fill="both", expand=True)
        self._section_heading(due_inner, "Coming up", "View all", self._open_tasks)
        self.due_items = tk.Frame(due_inner, bg=CARD)
        self.due_items.pack(fill="x", pady=(8, 0))

        progress_card = self._card(sidebar, row=1, column=0, sticky="ew", pady=(0, 12))
        progress_inner = tk.Frame(progress_card, bg=CARD, padx=15, pady=13)
        progress_inner.pack(fill="x")
        tk.Label(
            progress_inner,
            text="Task progress",
            bg=CARD,
            fg=TEXT,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w")
        progress_row = tk.Frame(progress_inner, bg=CARD)
        progress_row.pack(fill="x", pady=(10, 0))
        progress_row.grid_columnconfigure(0, weight=1)
        self.progress_text = tk.Label(
            progress_row,
            text="0% completed",
            bg=CARD,
            fg=SUBTLE,
            font=("Helvetica", 9),
        )
        self.progress_text.grid(row=0, column=0, sticky="w")
        self.progress_bar = ttk.Progressbar(
            progress_inner,
            style="Taskflow.Horizontal.TProgressbar",
            mode="determinate",
            maximum=100,
        )
        self.progress_bar.pack(fill="x", pady=(8, 6))
        self.progress_counts = tk.Label(
            progress_inner,
            text="0 completed · 0 pending",
            bg=CARD,
            fg=SUBTLE,
            font=("Helvetica", 8),
        )
        self.progress_counts.pack(anchor="w")

        recent_card = self._card(sidebar, row=2, column=0, sticky="nsew")
        recent_inner = tk.Frame(recent_card, bg=CARD, padx=15, pady=13)
        recent_inner.pack(fill="both", expand=True)
        self._section_heading(recent_inner, "Latest tasks", "View all", self._open_tasks)
        self.recent_items = tk.Frame(recent_inner, bg=CARD)
        self.recent_items.pack(fill="both", expand=True, pady=(7, 0))

    def _section_heading(
        self,
        parent: tk.Frame,
        title: str,
        action: str,
        command: Any,
    ) -> None:
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x")
        tk.Label(
            row,
            text=title,
            bg=CARD,
            fg=TEXT,
            font=("Helvetica", 11, "bold"),
        ).pack(side="left")
        tk.Button(
            row,
            text=action,
            bg=CARD,
            fg=ACCENT,
            activebackground=CARD,
            activeforeground=ACCENT,
            relief="flat",
            borderwidth=0,
            font=("Helvetica", 8, "bold"),
            command=command,
        ).pack(side="right")

    def _build_tasks_page(self) -> None:
        self.page_content.grid_rowconfigure(0, weight=1)
        self._build_task_section(self.page_content, row=0, column=0)

    def _build_task_section(
        self,
        parent: tk.Widget,
        row: int,
        column: int,
        padx: Any = 0,
    ) -> None:
        card = self._card(parent, row=row, column=column, sticky="nsew", padx=padx)
        inner = tk.Frame(card, bg=CARD, padx=18, pady=16)
        inner.pack(fill="both", expand=True)
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_rowconfigure(2, weight=1)

        heading = tk.Frame(inner, bg=CARD)
        heading.grid(row=0, column=0, sticky="ew")
        tk.Label(
            heading,
            text="All tasks",
            bg=CARD,
            fg=TEXT,
            font=("Helvetica", 15, "bold"),
        ).pack(side="left")
        ttk.Button(
            heading,
            text="+ Add task",
            style="Accent.TButton",
            command=self.open_add_dialog,
        ).pack(side="right")

        toolbar = tk.Frame(inner, bg=CARD)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(12, 10))
        toolbar.grid_columnconfigure(0, weight=1)
        search = ttk.Entry(toolbar, textvariable=self.search_value, font=("Helvetica", 10))
        search.grid(row=0, column=0, sticky="ew", ipady=6, padx=(0, 8))
        search.bind("<KeyRelease>", lambda _event: self.refresh_tasks())
        status_filter = ttk.Combobox(
            toolbar,
            textvariable=self.filter_value,
            values=("All tasks", "Pending", "Completed"),
            state="readonly",
            width=12,
            style="Taskflow.TCombobox",
        )
        status_filter.grid(row=0, column=1, sticky="e")
        status_filter.bind("<<ComboboxSelected>>", lambda _event: self.refresh_tasks())

        table_frame = tk.Frame(inner, bg=CARD)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        self.task_tree = ttk.Treeview(
            table_frame,
            columns=("id", "task", "status", "schedule", "due"),
            show="headings",
            selectmode="browse",
            style="Taskflow.Treeview",
        )
        for key, label in (
            ("id", "ID"),
            ("task", "TASK DESCRIPTION"),
            ("status", "STATUS"),
            ("schedule", "SCHEDULE"),
            ("due", "DUE DATE"),
        ):
            self.task_tree.heading(key, text=label)
        self.task_tree.column("id", width=55, anchor="center", stretch=False)
        self.task_tree.column("task", width=340, anchor="w")
        self.task_tree.column("status", width=95, anchor="center", stretch=False)
        self.task_tree.column("schedule", width=185, anchor="center", stretch=False)
        self.task_tree.column("due", width=110, anchor="center", stretch=False)
        self.task_tree.tag_configure("completed", foreground="#9399A5")
        self.task_tree.tag_configure("pending", foreground=TEXT)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=scrollbar.set)
        self.task_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.task_tree.bind("<Double-1>", lambda _event: self.complete_selected())

        actions = tk.Frame(inner, bg=CARD)
        actions.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.complete_button = ttk.Button(
            actions,
            text="Mark complete",
            style="Quiet.TButton",
            command=self.complete_selected,
        )
        self.complete_button.pack(side="left")
        self.delete_button = ttk.Button(
            actions,
            text="Delete",
            style="Quiet.TButton",
            command=self.delete_selected,
        )
        self.delete_button.pack(side="left", padx=(8, 0))
        tk.Label(
            actions,
            text="Double-click a task to mark it complete",
            bg=CARD,
            fg=SUBTLE,
            font=("Helvetica", 9),
        ).pack(side="right")

    def _build_assistant_page(self) -> None:
        self.page_content.grid_rowconfigure(0, weight=1)
        self.page_content.grid_columnconfigure(0, weight=1)
        self._build_chat_panel(self.page_content, row=0, column=0)

    def _build_chat_panel(
        self,
        parent: tk.Widget,
        row: int,
        column: int,
        padx: Any = 0,
    ) -> None:
        card = self._card(parent, row=row, column=column, sticky="nsew", padx=padx)
        inner = tk.Frame(card, bg=CARD, padx=17, pady=15)
        inner.pack(fill="both", expand=True)
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_rowconfigure(1, weight=1)

        heading = tk.Frame(inner, bg=CARD)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 11))
        avatar = tk.Label(
            heading,
            text="✦",
            bg=ACCENT_PALE,
            fg=ACCENT,
            width=3,
            height=2,
            font=("Helvetica", 11, "bold"),
        )
        avatar.pack(side="left", padx=(0, 9))
        title_block = tk.Frame(heading, bg=CARD)
        title_block.pack(side="left")
        tk.Label(
            title_block,
            text="Lina",
            bg=CARD,
            fg=TEXT,
            font=("Helvetica", 12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_block,
            text=f"AI assistant · {assistant.MODEL}",
            bg=CARD,
            fg=SUBTLE,
            font=("Helvetica", 8),
        ).pack(anchor="w", pady=(2, 0))
        tk.Label(
            heading,
            text="LOCAL",
            bg="#F0EFFA",
            fg=ACCENT,
            padx=8,
            pady=4,
            font=("Helvetica", 8, "bold"),
        ).pack(side="right")

        conversation = tk.Frame(inner, bg=CHAT_BACKGROUND)
        conversation.grid(row=1, column=0, sticky="nsew")
        conversation.grid_rowconfigure(0, weight=1)
        conversation.grid_columnconfigure(0, weight=1)
        canvas = tk.Canvas(
            conversation,
            bg=CHAT_BACKGROUND,
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(conversation, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        message_frame = tk.Frame(canvas, bg=CHAT_BACKGROUND)
        window_id = canvas.create_window((0, 0), window=message_frame, anchor="nw")
        message_frame.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window_id, width=event.width),
        )
        self.transcript = message_frame
        self.chat_canvas = canvas
        self.chat_window = window_id
        self._render_chat_history()

        composer = tk.Frame(inner, bg=CARD)
        composer.grid(row=2, column=0, sticky="ew", pady=(11, 0))
        composer.grid_columnconfigure(0, weight=1)
        entry = ttk.Entry(composer, textvariable=self.input_value, font=("Helvetica", 11))
        entry.grid(row=0, column=0, sticky="ew", ipady=8, padx=(0, 8))
        entry.bind("<Return>", self.send_request)
        button = ttk.Button(
            composer,
            text="Send  ➤",
            style="Accent.TButton",
            command=self.send_request,
            state="disabled" if self.busy else "normal",
        )
        button.grid(row=0, column=1)
        self.send_button = button
        tk.Label(
            inner,
            text="Try “Study Python tomorrow from 14:00 to 16:00” · “Show pending tasks”",
            bg=CARD,
            fg=SUBTLE,
            font=("Helvetica", 8),
            anchor="w",
        ).grid(row=3, column=0, sticky="ew", pady=(8, 0))

    def _add_chat_bubble(self, speaker: str, message: str) -> None:
        if self.transcript is None:
            return
        row = tk.Frame(self.transcript, bg=CHAT_BACKGROUND)
        row.pack(fill="x", padx=14, pady=8)
        if speaker == "You":
            tk.Label(
                row,
                text="A",
                bg="#E8E6FA",
                fg=ACCENT,
                width=3,
                height=2,
                font=("Helvetica", 9, "bold"),
            ).pack(side="right", padx=(9, 0), anchor="n")
            bubble = tk.Label(
                row,
                text=message,
                bg="#E8E7F5",
                fg=TEXT,
                justify="left",
                anchor="w",
                wraplength=430,
                padx=14,
                pady=10,
                font=("Helvetica", 10),
            )
            bubble.pack(side="right", anchor="e")
            return

        tk.Label(
            row,
            text="✦",
            bg="#E7E6FA",
            fg=ACCENT,
            width=3,
            height=2,
            font=("Helvetica", 10, "bold"),
        ).pack(side="left", padx=(0, 9), anchor="n")
        bubble = tk.Label(
            row,
            text=message,
            bg=CARD,
            fg=TEXT,
            justify="left",
            anchor="w",
            wraplength=440,
            padx=14,
            pady=10,
            font=("Helvetica", 10),
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        bubble.pack(side="left", anchor="w")

    def _render_chat_history(self) -> None:
        if self.transcript is None:
            return
        for widget in self.transcript.winfo_children():
            widget.destroy()
        for speaker, text in self.chat_history:
            self._add_chat_bubble(speaker, text)
        self.transcript.update_idletasks()
        if self.chat_canvas is not None and self.chat_canvas.winfo_exists():
            self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
            self.chat_canvas.yview_moveto(1.0)

    def _append_message(self, speaker: str, message: str) -> None:
        self.chat_history.append((speaker, message))
        if self.transcript is not None and self.transcript.winfo_exists():
            self._add_chat_bubble(speaker, message)
            self.transcript.update_idletasks()
            if self.chat_canvas is not None and self.chat_canvas.winfo_exists():
                self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
                self.chat_canvas.yview_moveto(1.0)

    def _update_dashboard_sidebars(self, tasks: list[task_manager.Task]) -> None:
        today = date.today()
        due_tasks: list[tuple[date, task_manager.Task]] = []
        for task in tasks:
            schedule_date = task.get("schedule_date")
            due_date = task.get("due_date")
            display_date = schedule_date or due_date
            if task["completed"] or not display_date:
                continue
            parsed_date = date.fromisoformat(display_date)
            if parsed_date <= today + timedelta(days=7):
                due_tasks.append((parsed_date, task))
        due_tasks.sort(key=lambda item: item[0])

        if self.due_items is not None and self.due_items.winfo_exists():
            for widget in self.due_items.winfo_children():
                widget.destroy()
            if not due_tasks:
                tk.Label(
                    self.due_items,
                    text="No upcoming deadlines",
                    bg=CARD,
                    fg=SUBTLE,
                    font=("Helvetica", 9),
                    anchor="w",
                ).pack(fill="x", pady=6)
            for due_date, task in due_tasks[:4]:
                row = tk.Frame(self.due_items, bg=CARD)
                row.pack(fill="x", pady=5)
                color = RED if due_date < today else BLUE
                tk.Label(
                    row,
                    text="●",
                    bg=CARD,
                    fg=color,
                    font=("Helvetica", 8),
                ).pack(side="left", padx=(0, 7))
                details = tk.Frame(row, bg=CARD)
                details.pack(side="left", fill="x", expand=True)
                title = task["task"]
                if len(title) > 24:
                    title = title[:23] + "…"
                tk.Label(
                    details,
                    text=title,
                    bg=CARD,
                    fg=TEXT,
                    font=("Helvetica", 9),
                    anchor="w",
                ).pack(fill="x")
                schedule_date = task.get("schedule_date")
                start_time = task.get("start_time")
                end_time = task.get("end_time")
                time_range = f"{start_time}–{end_time}" if start_time and end_time else ""
                when = "Scheduled" if schedule_date else "Due"
                date_label = "Overdue" if due_date < today and not schedule_date else due_date.strftime("%b %d")
                subtitle = f"{when} · {date_label}"
                if time_range:
                    subtitle += f" · {time_range}"
                tk.Label(
                    details,
                    text=subtitle,
                    bg=CARD,
                    fg=RED if due_date < today and not schedule_date else SUBTLE,
                    font=("Helvetica", 8),
                    anchor="w",
                ).pack(fill="x", pady=(2, 0))

        if self.recent_items is not None and self.recent_items.winfo_exists():
            for widget in self.recent_items.winfo_children():
                widget.destroy()
            if not tasks:
                tk.Label(
                    self.recent_items,
                    text="Your task list is empty.",
                    bg=CARD,
                    fg=SUBTLE,
                    font=("Helvetica", 9),
                    anchor="w",
                ).pack(fill="x", pady=6)
            for task in sorted(tasks, key=lambda item: item["id"], reverse=True)[:4]:
                row = tk.Frame(self.recent_items, bg=CARD)
                row.pack(fill="x", pady=4)
                marker = GREEN if task["completed"] else ACCENT
                tk.Label(
                    row,
                    text="●",
                    bg=CARD,
                    fg=marker,
                    font=("Helvetica", 8),
                ).pack(side="left", padx=(0, 7))
                name = task["task"]
                if len(name) > 27:
                    name = name[:26] + "…"
                tk.Label(
                    row,
                    text=name,
                    bg=CARD,
                    fg=TEXT,
                    font=("Helvetica", 9),
                    anchor="w",
                ).pack(side="left", fill="x", expand=True)
                tk.Label(
                    row,
                    text="Done" if task["completed"] else "Open",
                    bg=CARD,
                    fg=GREEN if task["completed"] else SUBTLE,
                    font=("Helvetica", 8),
                ).pack(side="right")

    def refresh_tasks(self) -> None:
        try:
            tasks = task_manager.load_tasks()
        except (json.JSONDecodeError, OSError, ValueError) as error:
            self.status_value.set("Task data error")
            messagebox.showerror("Could not load tasks", str(error))
            return

        total = len(tasks)
        completed = sum(task["completed"] for task in tasks)
        pending = total - completed
        today = date.today()
        overdue = sum(
            not task["completed"]
            and bool(task.get("due_date"))
            and date.fromisoformat(task["due_date"]) < today
            for task in tasks
        )
        metrics = {
            "TOTAL TASKS": total,
            "PENDING": pending,
            "COMPLETED": completed,
            "OVERDUE": overdue,
        }
        for title, label in self.stat_values.items():
            label.configure(text=str(metrics[title]))
        if self.progress_bar is not None and self.progress_text is not None:
            percent = round(completed / total * 100) if total else 0
            self.progress_bar.configure(value=percent)
            self.progress_text.configure(text=f"{percent}% completed")
            if hasattr(self, "progress_counts"):
                self.progress_counts.configure(text=f"{completed} completed · {pending} pending")
        if self.pending_nav_label is not None:
            self.pending_nav_label.configure(text=f"{pending} pending")
        self._update_dashboard_sidebars(tasks)

        if self.task_tree is None or not self.task_tree.winfo_exists():
            return
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        query = self.search_value.get().strip().casefold()
        selected_filter = self.filter_value.get()
        for task in tasks:
            if selected_filter == "Pending" and task["completed"]:
                continue
            if selected_filter == "Completed" and not task["completed"]:
                continue
            searchable = " ".join(
                str(value)
                for value in (
                    task["id"],
                    task["task"],
                    task.get("schedule_date"),
                    task.get("start_time"),
                    task.get("end_time"),
                    task.get("due_date"),
                )
                if value is not None
            ).casefold()
            if query and query not in searchable:
                continue
            status = "Completed" if task["completed"] else "Pending"
            schedule_date = task.get("schedule_date")
            start_time = task.get("start_time")
            end_time = task.get("end_time")
            time_range = f"{start_time}–{end_time}" if start_time and end_time else ""
            schedule = schedule_date or ""
            if time_range:
                schedule = f"{schedule} · {time_range}" if schedule else time_range
            schedule = schedule or "—"
            self.task_tree.insert(
                "",
                "end",
                iid=str(task["id"]),
                values=(
                    task["id"],
                    task["task"],
                    status,
                    schedule,
                    task.get("due_date") or "—",
                ),
                tags=("completed" if task["completed"] else "pending",),
            )

    def _open_tasks(self) -> None:
        self._show_page("My Tasks")

    def open_add_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Add a task")
        dialog.configure(bg=BACKGROUND)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("540x500")

        panel = tk.Frame(dialog, bg=CARD, padx=26, pady=24)
        panel.pack(fill="both", expand=True, padx=12, pady=12)
        tk.Label(
            panel,
            text="Create a task",
            bg=CARD,
            fg=TEXT,
            font=("Helvetica", 18, "bold"),
        ).pack(anchor="w")
        tk.Label(
            panel,
            text="Set when you plan to work and, optionally, when it is due.",
            bg=CARD,
            fg=SUBTLE,
            font=("Helvetica", 10),
        ).pack(anchor="w", pady=(5, 14))

        task_value = tk.StringVar()
        schedule_date_value = tk.StringVar()
        start_time_value = tk.StringVar()
        end_time_value = tk.StringVar()
        due_value = tk.StringVar()
        tk.Label(
            panel,
            text="TASK DESCRIPTION",
            bg=CARD,
            fg=SUBTLE,
            font=("Helvetica", 8, "bold"),
        ).pack(anchor="w")
        task_entry = ttk.Entry(panel, textvariable=task_value, font=("Helvetica", 11))
        task_entry.pack(fill="x", ipady=6, pady=(5, 13))

        tk.Label(
            panel,
            text="SCHEDULE DATE (OPTIONAL · YYYY-MM-DD)",
            bg=CARD,
            fg=SUBTLE,
            font=("Helvetica", 8, "bold"),
        ).pack(anchor="w")
        schedule_entry = ttk.Entry(
            panel,
            textvariable=schedule_date_value,
            font=("Helvetica", 11),
        )
        schedule_entry.pack(fill="x", ipady=6, pady=(5, 11))

        time_fields = tk.Frame(panel, bg=CARD)
        time_fields.pack(fill="x", pady=(0, 12))
        time_fields.grid_columnconfigure(0, weight=1)
        time_fields.grid_columnconfigure(1, weight=1)
        tk.Label(
            time_fields,
            text="START TIME (24-HOUR)",
            bg=CARD,
            fg=SUBTLE,
            font=("Helvetica", 8, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        tk.Label(
            time_fields,
            text="END TIME (24-HOUR)",
            bg=CARD,
            fg=SUBTLE,
            font=("Helvetica", 8, "bold"),
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Entry(
            time_fields,
            textvariable=start_time_value,
            font=("Helvetica", 11),
        ).grid(row=1, column=0, sticky="ew", ipady=6, padx=(0, 8), pady=(5, 0))
        ttk.Entry(
            time_fields,
            textvariable=end_time_value,
            font=("Helvetica", 11),
        ).grid(row=1, column=1, sticky="ew", ipady=6, padx=(8, 0), pady=(5, 0))

        tk.Label(
            panel,
            text="DEADLINE (OPTIONAL · YYYY-MM-DD)",
            bg=CARD,
            fg=SUBTLE,
            font=("Helvetica", 8, "bold"),
        ).pack(anchor="w")
        due_entry = ttk.Entry(panel, textvariable=due_value, font=("Helvetica", 11))
        due_entry.pack(fill="x", ipady=6, pady=(5, 14))
        buttons = tk.Frame(panel, bg=CARD)
        buttons.pack(fill="x")

        def save_task() -> None:
            title = task_value.get().strip()
            if not title:
                messagebox.showerror(
                    "Missing description",
                    "Enter a description for the task.",
                    parent=dialog,
                )
                task_entry.focus_set()
                return
            try:
                result = task_manager.add_task(
                    title,
                    due_date=due_value.get().strip() or None,
                    schedule_date=schedule_date_value.get().strip() or None,
                    start_time=start_time_value.get().strip() or None,
                    end_time=end_time_value.get().strip() or None,
                )
            except (json.JSONDecodeError, OSError, ValueError) as error:
                messagebox.showerror("Could not add task", str(error), parent=dialog)
                return
            dialog.destroy()
            self.refresh_tasks()
            self._append_message("Assistant", result)

        ttk.Button(buttons, text="Cancel", style="Quiet.TButton", command=dialog.destroy).pack(
            side="right",
        )
        ttk.Button(buttons, text="Add task", style="Accent.TButton", command=save_task).pack(
            side="right",
            padx=(0, 8),
        )
        task_entry.focus_set()
        dialog.bind("<Return>", lambda _event: save_task())

    def _selected_task(self) -> task_manager.Task | None:
        if self.task_tree is None:
            return None
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showinfo("Select a task", "Choose a task from the table first.")
            return None
        task_id = int(selected[0])
        try:
            return next(task for task in task_manager.load_tasks() if task["id"] == task_id)
        except StopIteration:
            messagebox.showinfo("Task not found", "Refresh the list and select a current task.")
            self.refresh_tasks()
            return None
        except (json.JSONDecodeError, OSError, ValueError) as error:
            messagebox.showerror("Could not read tasks", str(error))
            return None

    def complete_selected(self) -> None:
        task = self._selected_task()
        if task is None:
            return
        try:
            result = task_manager.complete_task(task["id"])
        except (json.JSONDecodeError, OSError, ValueError) as error:
            messagebox.showerror("Could not complete task", str(error))
            return
        self.refresh_tasks()
        self._append_message("Assistant", result)

    def delete_selected(self) -> None:
        task = self._selected_task()
        if task is None:
            return
        confirmed = messagebox.askyesno(
            "Confirm deletion",
            f"Delete task {task['id']}: {task['task']}?",
            parent=self.root,
        )
        if not confirmed:
            return
        try:
            result = task_manager.delete_task(task["id"])
        except (json.JSONDecodeError, OSError, ValueError) as error:
            messagebox.showerror("Could not delete task", str(error))
            return
        self.refresh_tasks()
        self._append_message("Assistant", result)

    def send_request(self, _event: tk.Event | None = None) -> None:
        request = self.input_value.get().strip()
        if not request or self.busy:
            return
        self.input_value.set("")
        self._append_message("You", request)
        self.busy = True
        self.status_value.set("Thinking…")
        if self.send_button is not None:
            self.send_button.configure(state="disabled")
        threading.Thread(target=self._run_request, args=(request,), daemon=True).start()

    def _confirm_delete_in_worker(self, task_id: int) -> bool:
        response: queue.Queue[bool] = queue.Queue(maxsize=1)
        self.result_queue.put(("confirm_delete", (task_id, response)))
        return response.get()

    def _run_request(self, request: str) -> None:
        try:
            answer = assistant.handle_request(
                request,
                confirm_delete=self._confirm_delete_in_worker,
            )
        except (
            ConnectionError,
            RequestError,
            ResponseError,
            json.JSONDecodeError,
            OSError,
            ValueError,
        ) as error:
            self.result_queue.put(("error", str(error)))
        else:
            self.result_queue.put(("answer", answer))

    def _handle_delete_confirmation(
        self,
        request: tuple[int, queue.Queue[bool]],
    ) -> None:
        task_id, response = request
        try:
            task = next(task for task in task_manager.load_tasks() if task["id"] == task_id)
        except StopIteration:
            messagebox.showinfo("Task not found", "That task no longer exists.")
            response.put(False)
            return
        except (json.JSONDecodeError, OSError, ValueError) as error:
            messagebox.showerror("Could not read tasks", str(error))
            response.put(False)
            return

        confirmed = messagebox.askyesno(
            "Confirm deletion",
            f"The assistant wants to delete task {task['id']}: {task['task']}. Continue?",
            parent=self.root,
        )
        response.put(confirmed)

    def _poll_results(self) -> None:
        while True:
            try:
                result_type, result = self.result_queue.get_nowait()
            except queue.Empty:
                break

            if result_type == "confirm_delete":
                self._handle_delete_confirmation(result)
                continue

            if result_type == "answer":
                self._append_message("Assistant", result)
                self.status_value.set("Ready")
                self.refresh_tasks()
            else:
                self.status_value.set("Needs attention")
                self._append_message(
                    "Assistant",
                    f"I couldn't complete that request: {result}",
                )
            self.busy = False
            if self.send_button is not None and self.send_button.winfo_exists():
                self.send_button.configure(state="normal")
        self.root.after(100, self._poll_results)


def main() -> None:
    root = tk.Tk()
    TaskManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
