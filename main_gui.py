# -*- coding: utf-8 -*-
"""
主程序：GUI界面搭建 + 业务逻辑（单一模型持续循环 + 双模型角色互换循环）
支持扩展新模型（只需在 config.AVAILABLE_MODELS 中添加名称，并在 browser_ai.py 中实现对应函数）
"""
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
import threading
import time
import os
import config
import Log_Export
import browser_ai


class AutoAskApp:
    def __init__(self, root):
        self.root = root
        root.title("AI 循环对谈 & 自动总结工具")
        root.geometry("1100x700")

        # 状态变量
        self.running = False          # 双模型主循环运行状态
        self.continue_running = False # 双模型继续创作运行状态
        self.single_running = False   # 单一模型循环运行状态
        self.full_history = []        # 主循环历史记录
        self.continue_history = []    # 继续创作历史记录
        self.single_history = []      # 单一模型历史记录

        self._init_layout()
        self.current_mode = "dual"
        self.show_dual_mode()

    def _init_layout(self):
        """初始化整体布局（左右分栏+底部状态栏）"""
        # ========== 左侧配置区（带滚动条） ==========
        left_frame = tk.Frame(self.root, width=320, relief=tk.SUNKEN, borderwidth=1)
        left_frame.grid(row=0, column=0, sticky="ns", padx=5, pady=5)
        left_frame.grid_propagate(False)
        left_frame.config(width=320)

        left_canvas = tk.Canvas(left_frame, highlightthickness=0)
        left_scrollbar = tk.Scrollbar(left_frame, orient=tk.VERTICAL, command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner_left = tk.Frame(left_canvas)
        left_canvas.create_window((0, 0), window=inner_left, anchor=tk.NW, width=left_canvas.winfo_reqwidth())
        inner_left.bind("<Configure>", lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")))

        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ========== 模式切换按钮（左上角） ==========
        mode_switch_frame = tk.Frame(inner_left)
        mode_switch_frame.pack(fill=tk.X, pady=5, padx=5)
        self.btn_single_mode = tk.Button(mode_switch_frame, text="单一模型持续循环模式",
                                         command=self.show_single_mode, bg="#E0E0E0", width=18)
        self.btn_single_mode.pack(side=tk.LEFT, padx=2)
        self.btn_dual_mode = tk.Button(mode_switch_frame, text="双模型循环对话创作模式",
                                       command=self.show_dual_mode, bg="#BBDEFB", width=18)
        self.btn_dual_mode.pack(side=tk.LEFT, padx=2)

        # 创建两个模式对应的配置面板
        self.frame_single = tk.Frame(inner_left)
        self.frame_dual = tk.Frame(inner_left)

        self._build_single_mode_ui()
        self._build_dual_mode_ui()

        # ========== 右侧输出区 ==========
        right_frame = tk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        top_frame = tk.Frame(right_frame)
        top_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        bottom_frame = tk.Frame(right_frame)
        bottom_frame.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)

        right_frame.grid_rowconfigure(0, weight=7)
        right_frame.grid_rowconfigure(1, weight=3)
        right_frame.grid_columnconfigure(0, weight=1)

        tk.Label(top_frame, text="对话流水记录:", font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=5, pady=2)
        self.output_text = scrolledtext.ScrolledText(top_frame, font=("Arial", 9))
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

        tk.Label(bottom_frame, text="系统日志:", font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=5, pady=2)
        self.log_text = scrolledtext.ScrolledText(bottom_frame, font=("Arial", 7), fg="blue")
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

        # 底部状态栏
        bottom_status = tk.Frame(self.root)
        bottom_status.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        self.status_label = tk.Label(bottom_status, text="就绪", relief=tk.SUNKEN, anchor=tk.W, font=("Arial", 8))
        self.status_label.pack(fill=tk.X)

        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

    # --------------------------------------------------------------------------
    # 单一模型模式界面
    # --------------------------------------------------------------------------
    def _build_single_mode_ui(self):
        for widget in self.frame_single.winfo_children():
            widget.destroy()

        tk.Label(self.frame_single, text="1. 选择AI模型:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10,0))
        self.single_model_var = tk.StringVar(value=config.AVAILABLE_MODELS[0] if config.AVAILABLE_MODELS else "DeepSeek")
        model_frame = tk.Frame(self.frame_single)
        model_frame.pack(anchor=tk.W, padx=10, pady=2)
        for model in config.AVAILABLE_MODELS:
            tk.Radiobutton(model_frame, text=model, variable=self.single_model_var, value=model).pack(side=tk.LEFT, padx=5)

        tk.Label(self.frame_single, text="2. 初始提问:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10,0))
        self.single_initial_prompt = tk.Text(self.frame_single, height=3, font=("Arial", 9))
        self.single_initial_prompt.pack(fill=tk.X, padx=5, pady=3)
        self.single_initial_prompt.insert(tk.END, config.DEFAULT_INITIAL_PROMPT)

        tk.Label(self.frame_single, text="3. 中间提示词 (每轮发送，引导强化历史记忆):",
                 font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10,0))
        self.single_mid_prompt = tk.Text(self.frame_single, height=3, font=("Arial", 9))
        self.single_mid_prompt.pack(fill=tk.X, padx=5, pady=3)
        self.single_mid_prompt.insert(tk.END, config.DEFAULT_SINGLE_MID_PROMPT)
        tk.Label(self.frame_single, text="提示：每轮AI回答后，下一轮将发送此提示词，可自定义强调连贯性、人物设定等。",
                 fg="gray", font=("Arial", 7)).pack(anchor=tk.W, padx=5)

        param_frame = tk.Frame(self.frame_single)
        param_frame.pack(fill=tk.X, pady=5, padx=5)
        tk.Label(param_frame, text="4. 循环轮数:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.single_rounds_entry = tk.Entry(param_frame, width=4)
        self.single_rounds_entry.pack(side=tk.LEFT, padx=3)
        self.single_rounds_entry.insert(0, "5")
        tk.Label(param_frame, text="  端口:", font=("Arial", 9)).pack(side=tk.LEFT, padx=(10,0))
        self.single_port_entry = tk.Entry(param_frame, width=5)
        self.single_port_entry.pack(side=tk.LEFT, padx=3)
        self.single_port_entry.insert(0, str(config.DEFAULT_PORT))

        btn_frame = tk.Frame(self.frame_single)
        btn_frame.pack(fill=tk.X, pady=10, padx=5)
        self.btn_single_start = tk.Button(btn_frame, text="开始单一模型循环", command=self.start_single_loop,
                                          bg="#4CAF50", fg="white", width=15)
        self.btn_single_start.pack(side=tk.LEFT, padx=2)
        self.btn_single_stop = tk.Button(btn_frame, text="停止", command=self.stop_single_loop,
                                         bg="#f44336", fg="white", width=8)
        self.btn_single_stop.pack(side=tk.LEFT, padx=2)
        self.btn_single_export = tk.Button(btn_frame, text="导出记录", command=self.export_single_history,
                                           bg="#9C27B0", fg="white", width=8)
        self.btn_single_export.pack(side=tk.LEFT, padx=2)

        info = tk.Label(self.frame_single,
                        text="说明：每轮向所选模型发送提示词（第一轮为初始提问，之后为中间提示词），AI会基于当前对话历史继续生成。",
                        fg="gray", font=("Arial", 7), wraplength=300, justify=tk.LEFT)
        info.pack(anchor=tk.W, pady=10, padx=5)

    # --------------------------------------------------------------------------
    # 双模型模式界面（包含主创作者/评价者选择）
    # --------------------------------------------------------------------------
    def _build_dual_mode_ui(self):
        for widget in self.frame_dual.winfo_children():
            widget.destroy()

        # ----- 模型角色配置 -----
        model_frame = tk.LabelFrame(self.frame_dual, text="模型角色配置", padx=5, pady=3, font=("Arial", 9))
        model_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(model_frame, text="主创作者 (先发言):", font=("Arial", 8)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.creator_model = ttk.Combobox(model_frame, values=config.AVAILABLE_MODELS, state="readonly", width=12)
        self.creator_model.grid(row=0, column=1, padx=5, pady=2)
        self.creator_model.set(config.AVAILABLE_MODELS[0] if config.AVAILABLE_MODELS else "DeepSeek")

        tk.Label(model_frame, text="评价者 (后发言):", font=("Arial", 8)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.critic_model = ttk.Combobox(model_frame, values=config.AVAILABLE_MODELS, state="readonly", width=12)
        self.critic_model.grid(row=1, column=1, padx=5, pady=2)
        if len(config.AVAILABLE_MODELS) > 1:
            self.critic_model.set(config.AVAILABLE_MODELS[1])
        else:
            self.critic_model.set(config.AVAILABLE_MODELS[0])

        tk.Label(model_frame, text="可互换角色，支持扩展模型（需在browser_ai中注册）",
                 fg="gray", font=("Arial", 7)).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5)

        # ----- 初始提问 -----
        tk.Label(self.frame_dual, text="1. 初始提问 (主循环):", font=("Arial", 9, "bold")).pack(pady=(5,0), anchor=tk.W)
        self.initial_prompt_text = tk.Text(self.frame_dual, height=2, font=("Arial", 9))
        self.initial_prompt_text.pack(fill=tk.X, padx=5, pady=3)
        self.initial_prompt_text.insert(tk.END, config.DEFAULT_INITIAL_PROMPT)

        # ----- 小说风格预设（兼容空配置）-----
        style_frame = tk.LabelFrame(self.frame_dual, text="小说风格预设 (可选)", padx=5, pady=3, font=("Arial", 9))
        style_frame.pack(fill=tk.X, padx=5, pady=5)

        if config.CATEGORIES:
            cat_frame = tk.Frame(style_frame)
            cat_frame.pack(fill=tk.X, pady=2)
            tk.Label(cat_frame, text="分类:", font=("Arial", 8)).pack(side=tk.LEFT)
            self.category_var = tk.StringVar(value=config.CATEGORIES[0])
            self.category_combo = ttk.Combobox(cat_frame, textvariable=self.category_var,
                                               values=config.CATEGORIES, state="readonly", width=10)
            self.category_combo.pack(side=tk.LEFT, padx=5)
            self.category_combo.bind("<<ComboboxSelected>>", self.on_category_change)
        else:
            self.category_var = tk.StringVar(value="")
            tk.Label(style_frame, text="(无预设分类)", fg="gray", font=("Arial", 8)).pack(anchor=tk.W, pady=2)

        type_frame = tk.Frame(style_frame)
        type_frame.pack(fill=tk.X, pady=2)
        tk.Label(type_frame, text="类型:", font=("Arial", 8)).pack(side=tk.LEFT)
        self.type_var = tk.StringVar()
        self.type_combo = ttk.Combobox(type_frame, textvariable=self.type_var,
                                       values=[], state="readonly", width=12)
        self.type_combo.pack(side=tk.LEFT, padx=5)
        if not config.CATEGORIES or not config.CATEGORY_TYPE_MAP:
            self.type_combo.config(state=tk.DISABLED)
            self.type_var.set("(无预设类型)")

        if config.STYLE_LIST:
            style_label_frame = tk.Frame(style_frame)
            style_label_frame.pack(fill=tk.X, pady=2)
            tk.Label(style_label_frame, text=f"文风 (最多可选{config.MAX_STYLE_SELECT}种):", font=("Arial", 8)).pack(anchor=tk.W)
            listbox_frame = tk.Frame(style_frame)
            listbox_frame.pack(fill=tk.BOTH, expand=True, pady=2)
            self.styles_listbox = tk.Listbox(listbox_frame, selectmode=tk.MULTIPLE, height=5, font=("Arial", 8))
            self.styles_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_styles = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.styles_listbox.yview)
            scrollbar_styles.pack(side=tk.RIGHT, fill=tk.Y)
            self.styles_listbox.config(yscrollcommand=scrollbar_styles.set)
            for style in config.STYLE_LIST:
                self.styles_listbox.insert(tk.END, style)
            self.styles_listbox.bind("<<ListboxSelect>>", self.on_style_select)
            self.style_warning_label = tk.Label(style_frame, text="", fg="red", font=("Arial", 7))
            self.style_warning_label.pack(anchor=tk.W)
        else:
            tk.Label(style_frame, text="(无预设文风)", fg="gray", font=("Arial", 8)).pack(anchor=tk.W, pady=2)
            self.styles_listbox = None

        if config.CATEGORIES and config.CATEGORY_TYPE_MAP:
            self.on_category_change()

        # ----- 对话前缀配置 -----
        prefix_frame = tk.LabelFrame(self.frame_dual, text="2. 对话前缀配置", padx=5, pady=3, font=("Arial", 9))
        prefix_frame.pack(fill=tk.X, padx=5, pady=3)
        tk.Label(prefix_frame, text="给主创作者的前缀 (基于评价者反馈):", font=("Arial", 8)).pack(anchor=tk.W)
        self.creator_prefix_entry = tk.Entry(prefix_frame, font=("Arial", 8))
        self.creator_prefix_entry.pack(fill=tk.X, pady=2)
        self.creator_prefix_entry.insert(0, config.DEFAULT_DS_PREFIX)

        tk.Label(prefix_frame, text="给评价者的前缀 (基于主创作者内容):", font=("Arial", 8)).pack(anchor=tk.W)
        self.critic_prefix_entry = tk.Entry(prefix_frame, font=("Arial", 8))
        self.critic_prefix_entry.pack(fill=tk.X, pady=2)
        self.critic_prefix_entry.insert(0, config.DEFAULT_QW_PREFIX)

        # ----- 结束总结配置 -----
        summary_frame = tk.LabelFrame(self.frame_dual, text="3. 结束总结配置 (仅主循环)", padx=5, pady=3, font=("Arial", 9))
        summary_frame.pack(fill=tk.X, padx=5, pady=3)
        tk.Label(summary_frame, text="总结提示词:", font=("Arial", 8)).pack(anchor=tk.W)
        self.summary_prompt_text = tk.Text(summary_frame, height=2, font=("Arial", 8))
        self.summary_prompt_text.pack(fill=tk.X, pady=3)
        self.summary_prompt_text.insert(tk.END, config.DEFAULT_SUMMARY_PROMPT)

        # ----- 主循环控制 -----
        ctrl_frame = tk.LabelFrame(self.frame_dual, text="4. 主循环控制", padx=5, pady=3, font=("Arial", 9))
        ctrl_frame.pack(fill=tk.X, padx=5, pady=3)
        row_frame = tk.Frame(ctrl_frame)
        row_frame.pack(fill=tk.X)
        tk.Label(row_frame, text="轮数:", font=("Arial", 8)).pack(side=tk.LEFT)
        self.loop_count_entry = tk.Entry(row_frame, width=4, font=("Arial", 8))
        self.loop_count_entry.pack(side=tk.LEFT, padx=3)
        self.loop_count_entry.insert(0, "3")
        self.btn_start = tk.Button(row_frame, text="开始主循环", command=self.start_loop_thread,
                                   bg="#4CAF50", fg="white", font=("Arial", 8, "bold"), width=10)
        self.btn_start.pack(side=tk.LEFT, padx=3)
        self.btn_stop = tk.Button(row_frame, text="停止", command=self.stop_task,
                                  bg="#f44336", fg="white", font=("Arial", 8), width=5)
        self.btn_stop.pack(side=tk.LEFT, padx=3)

        # ----- 继续创作模块 -----
        continue_frame = tk.LabelFrame(self.frame_dual, text="5. 继续创作 (双模型交替)", padx=5, pady=3, font=("Arial", 9))
        continue_frame.pack(fill=tk.X, padx=5, pady=3)
        tk.Label(continue_frame, text="起始提示词:", font=("Arial", 8)).pack(anchor=tk.W)
        self.continue_start_prompt = tk.Text(continue_frame, height=2, width=50, font=("Arial", 8))
        self.continue_start_prompt.pack(fill=tk.X, pady=2)
        self.continue_start_prompt.insert(tk.END, config.DEFAULT_CONTINUE_PROMPT)
        row2 = tk.Frame(continue_frame)
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="轮数:", font=("Arial", 8)).pack(side=tk.LEFT)
        self.continue_round_entry = tk.Entry(row2, width=3, font=("Arial", 8))
        self.continue_round_entry.pack(side=tk.LEFT, padx=3)
        self.continue_round_entry.insert(0, "3")
        tk.Label(row2, text="端口:", font=("Arial", 8)).pack(side=tk.LEFT, padx=(5,0))
        self.port_entry = tk.Entry(row2, width=5, font=("Arial", 8))
        self.port_entry.pack(side=tk.LEFT, padx=3)
        self.port_entry.insert(0, str(config.DEFAULT_PORT))
        btn_frame2 = tk.Frame(continue_frame)
        btn_frame2.pack(fill=tk.X, pady=3)
        self.btn_continue_start = tk.Button(btn_frame2, text="开始继续", command=self.start_continue_thread,
                                            bg="#2196F3", fg="white", font=("Arial", 8), width=8)
        self.btn_continue_start.pack(side=tk.LEFT, padx=2)
        self.btn_continue_stop = tk.Button(btn_frame2, text="停止", command=self.stop_continue_task,
                                           bg="#ff9800", fg="white", font=("Arial", 8), width=5)
        self.btn_continue_stop.pack(side=tk.LEFT, padx=2)
        self.btn_export_continue = tk.Button(btn_frame2, text="导出记录", command=self.export_continue_history,
                                             bg="#9C27B0", fg="white", font=("Arial", 8), width=8)
        self.btn_export_continue.pack(side=tk.LEFT, padx=2)
        info_label = tk.Label(continue_frame, text="说明: 每轮主创作者生成内容 → 评价者评价 → 下一轮",
                              fg="gray", font=("Arial", 7), wraplength=300, justify=tk.LEFT)
        info_label.pack(anchor=tk.W, pady=2)

    # --------------------------------------------------------------------------
    # 通用辅助方法
    # --------------------------------------------------------------------------
    def show_single_mode(self):
        if self.current_mode == "single":
            return
        self._stop_all_tasks()
        self.frame_dual.pack_forget()
        self.frame_single.pack(fill=tk.BOTH, expand=True)
        self.current_mode = "single"
        self.btn_single_mode.config(bg="#BBDEFB")
        self.btn_dual_mode.config(bg="#E0E0E0")
        self.update_status("已切换到【单一模型持续循环】模式")

    def show_dual_mode(self):
        if self.current_mode == "dual":
            return
        self._stop_all_tasks()
        self.frame_single.pack_forget()
        self.frame_dual.pack(fill=tk.BOTH, expand=True)
        self.current_mode = "dual"
        self.btn_dual_mode.config(bg="#BBDEFB")
        self.btn_single_mode.config(bg="#E0E0E0")
        self.update_status("已切换到【双模型循环对话创作】模式")

    def _stop_all_tasks(self):
        if self.running:
            self.running = False
        if self.continue_running:
            self.continue_running = False
        if self.single_running:
            self.single_running = False

    def update_status(self, msg):
        Log_Export.update_status(self.status_label, self.log_text, msg)

    def update_output(self, text, role="", target_history="main"):
        history_list = None
        if target_history == "main":
            history_list = self.full_history
        elif target_history == "continue":
            history_list = self.continue_history
        elif target_history == "single":
            history_list = self.single_history
        Log_Export.update_output(self.output_text, text, role, history_list, target_history)

    # 风格预设回调
    def on_category_change(self, event=None):
        if not hasattr(self, 'category_combo') or not config.CATEGORY_TYPE_MAP:
            return
        cat = self.category_var.get()
        type_list = config.CATEGORY_TYPE_MAP.get(cat, [])
        self.type_combo['values'] = type_list
        if type_list:
            self.type_var.set(type_list[0])
        else:
            self.type_var.set("(无类型)")

    def on_style_select(self, event=None):
        if not hasattr(self, 'styles_listbox') or self.styles_listbox is None:
            return
        selected = self.styles_listbox.curselection()
        if len(selected) > config.MAX_STYLE_SELECT:
            last = selected[-1]
            self.styles_listbox.selection_clear(last)
            self.style_warning_label.config(text=f"最多只能选择{config.MAX_STYLE_SELECT}种文风！", fg="red")
            self.root.after(2000, lambda: self.style_warning_label.config(text=""))

    def build_style_prompt(self):
        if not hasattr(self, 'category_var') or not config.CATEGORY_TYPE_MAP:
            return ""
        cat = self.category_var.get()
        genre = ""
        if hasattr(self, 'type_var'):
            genre = self.type_var.get()
            if genre in ("(无类型)", "(无预设类型)"):
                genre = ""
        selected_styles = []
        if hasattr(self, 'styles_listbox') and self.styles_listbox is not None:
            selected_indices = self.styles_listbox.curselection()
            selected_styles = [self.styles_listbox.get(i) for i in selected_indices]
        if not genre and not selected_styles:
            return ""
        parts = []
        if genre:
            parts.append(f"- 类型：{genre}")
        if selected_styles:
            parts.append(f"- 文风：{'、'.join(selected_styles)}")
        return "【小说创作要求】\n" + "\n".join(parts) + "\n\n请严格按照以上要求进行创作。"

    # --------------------------------------------------------------------------
    # 双模型主循环（使用 ask_model 通用接口）
    # --------------------------------------------------------------------------
    def start_loop_thread(self):
        if self.running:
            self.update_status("主循环已在运行中")
            return
        if self.continue_running:
            messagebox.showwarning("提示", "请先停止继续创作任务")
            return
        if self.current_mode != "dual":
            messagebox.showwarning("提示", "请先切换到【双模型模式】")
            return
        self.running = True
        self.full_history = []
        self.output_text.delete("1.0", tk.END)
        self.btn_start.config(state=tk.DISABLED)
        threading.Thread(target=self._run_loop_logic, daemon=True).start()

    def _run_loop_logic(self):
        try:
            loop_limit = int(self.loop_count_entry.get())
            base_prompt = self.initial_prompt_text.get("1.0", tk.END).strip()
            style_prompt = self.build_style_prompt()
            current_input = f"{base_prompt}\n\n{style_prompt}" if style_prompt else base_prompt
            if style_prompt:
                self.update_status("已附加小说风格预设到初始提问")

            creator = self.creator_model.get()
            critic = self.critic_model.get()
            prefix_creator = self.creator_prefix_entry.get()
            prefix_critic = self.critic_prefix_entry.get()

            for i in range(loop_limit):
                if not self.running:
                    break
                self.update_status(f"第 {i+1} 轮: 呼叫 {creator} (主创作者)")
                creator_reply = browser_ai.ask_model(
                    creator, current_input, self.update_status,
                    lambda t: self.update_output(t, creator, target_history="main"),
                    new_chat=(i==0)
                )
                if not creator_reply:
                    break
                critic_input = f"{prefix_critic}\n{creator_reply}"
                self.update_status(f"第 {i+1} 轮: 呼叫 {critic} (评价者)")
                critic_reply = browser_ai.ask_model(
                    critic, critic_input, self.update_status,
                    lambda t: self.update_output(t, critic, target_history="main"),
                    new_chat=(i==0)
                )
                if not critic_reply:
                    break
                current_input = f"{prefix_creator}\n{critic_reply}"

            if self.running:
                self.update_status("正在进行最终总结...")
                summary_prompt_base = self.summary_prompt_text.get("1.0", tk.END).strip()
                full_context = "\n\n".join(self.full_history)
                final_summary_prompt = f"{summary_prompt_base}\n\n以下是原始对话记录：\n{full_context}"
                # 总结固定使用 DeepSeek (如果可用，否则使用第一个模型)
                summary_model = "DeepSeek" if "DeepSeek" in config.AVAILABLE_MODELS else config.AVAILABLE_MODELS[0]
                summary_result = browser_ai.ask_model(
                    summary_model, final_summary_prompt, self.update_status, lambda t: None, new_chat=False
                )
                if summary_result:
                    self.update_output(summary_result, "【最终总结文章】", target_history="main")
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    path1 = Log_Export.export_to_word(f"对话流水_{timestamp}.docx", "对话流水记录", self.full_history[:-1], "/tmp")
                    path2 = Log_Export.export_to_word(f"最终总结_{timestamp}.docx", "AI 总结文章", [summary_result], "/tmp")
                    messagebox.showinfo("完成", f"任务已结束！\n\n流水存档：{path1}\n总结存档：{path2}")
                else:
                    messagebox.showwarning("总结失败", "对话已结束，但总结过程出错。")
            self.update_status("所有任务已完成")
        except Exception as e:
            self.update_status(f"发生错误: {e}")
        finally:
            self.running = False
            self.btn_start.config(state=tk.NORMAL)

    # --------------------------------------------------------------------------
    # 双模型继续创作
    # --------------------------------------------------------------------------
    def start_continue_thread(self):
        if self.continue_running:
            self.update_status("继续创作已在运行中")
            return
        if self.running:
            messagebox.showwarning("提示", "请先停止主对话循环")
            return
        if self.current_mode != "dual":
            messagebox.showwarning("提示", "请先切换到【双模型模式】")
            return
        try:
            rounds = int(self.continue_round_entry.get())
            port = int(self.port_entry.get())
            start_prompt = self.continue_start_prompt.get("1.0", tk.END).strip()
            if not start_prompt:
                messagebox.showerror("错误", "请输入起始提示词")
                return
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
            return

        self.continue_running = True
        self.btn_continue_start.config(state=tk.DISABLED)
        self.continue_history = []
        threading.Thread(target=self._run_continue_logic, args=(rounds, start_prompt, port), daemon=True).start()

    def _run_continue_logic(self, rounds, start_prompt, port):
        try:
            current_input = start_prompt
            creator = self.creator_model.get()
            critic = self.critic_model.get()
            prefix_creator = self.creator_prefix_entry.get()
            prefix_critic = self.critic_prefix_entry.get()

            for i in range(1, rounds + 1):
                if not self.continue_running:
                    break
                self.update_status(f"继续创作第 {i}/{rounds} 轮: {creator}")
                creator_reply = browser_ai.ask_model(
                    creator, current_input, self.update_status,
                    lambda t: self.update_output(t, f"{creator}(轮{i})", target_history="continue"),
                    new_chat=False, port=port
                )
                if not creator_reply:
                    break
                critic_input = f"{prefix_critic}\n{creator_reply}"
                self.update_status(f"继续创作第 {i}/{rounds} 轮: {critic}")
                critic_reply = browser_ai.ask_model(
                    critic, critic_input, self.update_status,
                    lambda t: self.update_output(t, f"{critic}(轮{i})", target_history="continue"),
                    new_chat=False, port=port
                )
                if not critic_reply:
                    break
                current_input = f"{prefix_creator}\n{critic_reply}"
                time.sleep(1)

            if self.continue_running:
                self.update_status(f"继续创作完成，共 {rounds} 轮")
                messagebox.showinfo("完成", f"交替创作已完成 {rounds} 轮\n可点击「导出记录」保存。")
            else:
                self.update_status("继续创作已手动停止")
        except Exception as e:
            self.update_status(f"继续创作错误: {e}")
            messagebox.showerror("错误", f"继续创作出错: {e}")
        finally:
            self.continue_running = False
            self.btn_continue_start.config(state=tk.NORMAL)

    def stop_task(self):
        self.running = False
        self.update_status("主循环停止")

    def stop_continue_task(self):
        self.continue_running = False
        self.update_status("继续创作已停止")
        self.btn_continue_start.config(state=tk.NORMAL)

    def export_continue_history(self):
        Log_Export.export_history(self.continue_history, "/tmp" , "继续")

    # --------------------------------------------------------------------------
    # 单一模型循环
    # --------------------------------------------------------------------------
    def start_single_loop(self):
        if self.single_running:
            self.update_status("单一模型循环已在运行中")
            return
        if self.running or self.continue_running:
            messagebox.showwarning("提示", "请先停止双模型模式下的任务")
            return
        if self.current_mode != "single":
            messagebox.showwarning("提示", "请先切换到【单一模型模式】")
            return
        try:
            rounds = int(self.single_rounds_entry.get())
            port = int(self.single_port_entry.get())
            model = self.single_model_var.get()
            initial_prompt = self.single_initial_prompt.get("1.0", tk.END).strip()
            mid_prompt = self.single_mid_prompt.get("1.0", tk.END).strip()
            if not initial_prompt:
                messagebox.showerror("错误", "请输入初始提问")
                return
            if not mid_prompt:
                messagebox.showerror("错误", "请输入中间提示词")
                return
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
            return

        self.single_running = True
        self.single_history = []
        self.output_text.delete("1.0", tk.END)
        self.btn_single_start.config(state=tk.DISABLED)
        threading.Thread(target=self._run_single_loop, args=(rounds, model, initial_prompt, mid_prompt, port), daemon=True).start()

    def _run_single_loop(self, rounds, model, initial_prompt, mid_prompt, port):
        try:
            current_prompt = initial_prompt
            for i in range(1, rounds + 1):
                if not self.single_running:
                    break
                self.update_status(f"单一模型循环第 {i}/{rounds} 轮，调用 {model}...")
                reply = browser_ai.ask_model(
                    model, current_prompt, self.update_status,
                    lambda t: self.update_output(t, f"{model}(轮{i})", target_history="single"),
                    new_chat=(i==1), port=port
                )
                if not reply:
                    self.update_status(f"第{i}轮调用失败，终止循环")
                    break
                current_prompt = mid_prompt
                time.sleep(1)
            if self.single_running:
                self.update_status(f"单一模型循环完成，共 {rounds} 轮")
                messagebox.showinfo("完成", f"单一模型持续循环已完成 {rounds} 轮\n可点击「导出记录」保存对话。")
            else:
                self.update_status("单一模型循环已手动停止")
        except Exception as e:
            self.update_status(f"单一模型循环错误: {e}")
            messagebox.showerror("错误", f"单一模型循环出错: {e}")
        finally:
            self.single_running = False
            self.btn_single_start.config(state=tk.NORMAL)

    def stop_single_loop(self):
        self.single_running = False
        self.update_status("单一模型循环停止")

    def export_single_history(self):
        if not self.single_history:
            messagebox.showwarning("无记录", "没有单一模型循环的记录可供导出。")
            return
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"单一模型循环记录_{timestamp}.docx"
        title = "AI 单一模型持续循环记录"
        path = Log_Export.export_to_word(filename, title, self.single_history, "/tmp")
        if os.path.exists(path):
            messagebox.showinfo("导出成功", f"已导出至：{path}")
        else:
            messagebox.showerror("导出失败", f"导出出错：{path}")


if __name__ == "__main__":
    root = tk.Tk()
    app = AutoAskApp(root)
    root.mainloop()