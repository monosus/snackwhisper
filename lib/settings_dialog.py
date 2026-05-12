import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from lib.model_profile import (
    DEFAULT_PROMPTS,
    PROVIDER_PRESETS,
    ModelProfile,
    ProfileRegistry,
)


class SettingsDialog:
    """モデル+APIキー+プロンプトのプロファイルを管理するモーダルダイアログ"""

    def __init__(
        self,
        parent: tk.Misc,
        registry: ProfileRegistry,
        on_save: Callable[[ProfileRegistry], None],
    ):
        self.parent = parent
        self.registry = registry
        self.on_save = on_save

        self.window = tk.Toplevel(parent)
        self.window.title("モデル設定")
        self.window.transient(parent)  # type: ignore[arg-type]
        self.window.resizable(False, False)
        self.window.withdraw()

        self._editing_original_name: Optional[str] = None

        self._build_ui()
        self._refresh_listbox()
        self._center_on_parent()
        self.window.deiconify()
        self.window.grab_set()

        if self.registry.profiles:
            self.listbox.selection_set(0)
            self._on_select(None)
        else:
            self._clear_form()

    def _center_on_parent(self):
        self.window.update_idletasks()
        try:
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_w = self.parent.winfo_width()
            parent_h = self.parent.winfo_height()
        except Exception:
            return

        dialog_w = self.window.winfo_reqwidth()
        dialog_h = self.window.winfo_reqheight()
        x = parent_x + max(0, (parent_w - dialog_w) // 2)
        y = parent_y + max(0, (parent_h - dialog_h) // 2)
        self.window.geometry(f"+{x}+{y}")

    def _build_ui(self):
        outer = ttk.Frame(self.window, padding=(14, 14))
        outer.pack(fill=tk.BOTH, expand=True)

        # 左: プロファイル一覧
        list_wrapper = ttk.Frame(outer)
        list_wrapper.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        ttk.Label(list_wrapper, text="プロファイル一覧", style="Section.TLabel").pack(
            anchor="w", pady=(0, 4)
        )
        list_section = ttk.Frame(list_wrapper)
        list_section.pack(fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(
            list_section,
            width=22,
            height=14,
            exportselection=False,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#cccccc",
            activestyle="none",
        )
        self.listbox.pack(side=tk.TOP, fill=tk.Y, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        list_btns = ttk.Frame(list_section)
        list_btns.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))
        ttk.Button(list_btns, text="新規", command=self._on_new).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(list_btns, text="削除", command=self._on_delete).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 右: 編集フォーム
        form_wrapper = ttk.Frame(outer)
        form_wrapper.grid(row=0, column=1, sticky="nsew")
        ttk.Label(form_wrapper, text="プロファイル編集", style="Section.TLabel").pack(
            anchor="w", pady=(0, 4)
        )
        form = ttk.Frame(form_wrapper)
        form.pack(fill=tk.BOTH, expand=True)
        form.columnconfigure(0, minsize=80)
        form.columnconfigure(1, weight=1)

        label_opts = {"sticky": "e", "padx": (0, 10), "pady": 4}
        field_opts = {"sticky": "ew", "pady": 4}

        ttk.Label(form, text="表示名").grid(row=0, column=0, **label_opts)
        self.name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, width=42).grid(row=0, column=1, **field_opts)

        ttk.Label(form, text="プロバイダ").grid(row=1, column=0, **label_opts)
        self.provider_var = tk.StringVar(value="openai")
        provider_menu = ttk.Combobox(
            form,
            textvariable=self.provider_var,
            values=list(PROVIDER_PRESETS.keys()),
            state="readonly",
            width=18,
        )
        provider_menu.grid(row=1, column=1, **field_opts)
        provider_menu.bind("<<ComboboxSelected>>", self._on_provider_change)

        ttk.Label(form, text="モデル").grid(row=2, column=0, **label_opts)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            form,
            textvariable=self.model_var,
            values=PROVIDER_PRESETS["openai"],
            width=28,
        )
        self.model_combo.grid(row=2, column=1, **field_opts)

        ttk.Label(form, text="APIキー").grid(row=3, column=0, **label_opts)
        self.api_key_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.api_key_var, width=42, show="•").grid(
            row=3, column=1, **field_opts
        )

        # プロンプト欄（ヘッダ + Text + 「デフォルトに戻す」）
        prompt_header = ttk.Frame(form)
        prompt_header.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 2))
        prompt_header.columnconfigure(0, weight=1)
        ttk.Label(prompt_header, text="プロンプト", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(
            prompt_header,
            text="デフォルトに戻す",
            command=self._on_restore_default_prompt,
        ).grid(row=0, column=1, sticky="e")

        prompt_box = ttk.Frame(form)
        prompt_box.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(0, 4))
        prompt_box.columnconfigure(0, weight=1)
        prompt_box.rowconfigure(0, weight=1)

        self.prompt_text = tk.Text(
            prompt_box,
            height=7,
            wrap="word",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#cccccc",
            highlightcolor="#0078d4",
            padx=8,
            pady=6,
            background="#fafafa",
        )
        self.prompt_text.grid(row=0, column=0, sticky="nsew")
        prompt_scroll = ttk.Scrollbar(prompt_box, orient="vertical", command=self.prompt_text.yview)
        prompt_scroll.grid(row=0, column=1, sticky="ns")
        self.prompt_text.config(yscrollcommand=prompt_scroll.set)

        form_btns = ttk.Frame(form)
        form_btns.grid(row=6, column=0, columnspan=2, pady=(8, 0), sticky="e")
        ttk.Button(form_btns, text="このプロファイルを保存", command=self._on_apply).pack(side=tk.LEFT)

        # 下部: OK/キャンセル
        bottom = ttk.Frame(outer)
        bottom.grid(row=1, column=0, columnspan=2, pady=(14, 0), sticky="e")
        ttk.Button(bottom, text="OK", style="Accent.TButton", command=self._on_ok).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bottom, text="キャンセル", command=self.window.destroy).pack(side=tk.LEFT)

    def _refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for p in self.registry.profiles:
            self.listbox.insert(tk.END, p.name)

    def _on_select(self, _event):
        sel = self.listbox.curselection()
        if not sel:
            return
        profile = self.registry.profiles[sel[0]]
        self._load_form(profile)

    def _set_prompt_text(self, text: str):
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", text)

    def _get_prompt_text(self) -> str:
        return self.prompt_text.get("1.0", tk.END).rstrip("\n")

    def _load_form(self, profile: ModelProfile):
        self._editing_original_name = profile.name
        self.name_var.set(profile.name)
        self.provider_var.set(profile.provider)
        self.model_combo.config(values=PROVIDER_PRESETS.get(profile.provider, []))
        self.model_var.set(profile.model)
        self.api_key_var.set(profile.api_key)
        # 空ならプロバイダのデフォルトを表示
        prompt = profile.prompt if profile.prompt else DEFAULT_PROMPTS.get(profile.provider, "")
        self._set_prompt_text(prompt)

    def _clear_form(self):
        self._editing_original_name = None
        self.name_var.set("")
        self.provider_var.set("openai")
        self.model_combo.config(values=PROVIDER_PRESETS["openai"])
        self.model_var.set("")
        self.api_key_var.set("")
        self._set_prompt_text(DEFAULT_PROMPTS.get("openai", ""))

    def _on_provider_change(self, _event):
        provider = self.provider_var.get()
        presets = PROVIDER_PRESETS.get(provider, [])
        self.model_combo.config(values=presets)
        if presets and self.model_var.get() not in presets:
            self.model_var.set(presets[0])

        # 現在のプロンプト内容が空 or 他プロバイダのデフォルトと一致するなら、
        # 新プロバイダのデフォルトに置き換える（ユーザ編集は触らない）
        current = self._get_prompt_text().strip()
        is_default_for_other = any(
            current == DEFAULT_PROMPTS.get(p, "").strip()
            for p in DEFAULT_PROMPTS.keys()
        )
        if not current or is_default_for_other:
            self._set_prompt_text(DEFAULT_PROMPTS.get(provider, ""))

    def _on_restore_default_prompt(self):
        provider = self.provider_var.get()
        self._set_prompt_text(DEFAULT_PROMPTS.get(provider, ""))

    def _on_new(self):
        self.listbox.selection_clear(0, tk.END)
        self._clear_form()

    def _on_delete(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        profile = self.registry.profiles[sel[0]]
        if not messagebox.askyesno("削除", f"プロファイル「{profile.name}」を削除しますか？", parent=self.window):
            return
        self.registry.remove(profile.name)
        self._refresh_listbox()
        self._clear_form()

    def _collect_form(self) -> Optional[ModelProfile]:
        name = self.name_var.get().strip()
        provider = self.provider_var.get().strip()
        model = self.model_var.get().strip()
        api_key = self.api_key_var.get().strip()
        prompt = self._get_prompt_text()

        if not name:
            messagebox.showerror("入力エラー", "表示名を入力してください。", parent=self.window)
            return None
        if not provider:
            messagebox.showerror("入力エラー", "プロバイダを選択してください。", parent=self.window)
            return None
        if not model:
            messagebox.showerror("入力エラー", "モデルを入力または選択してください。", parent=self.window)
            return None

        return ModelProfile(
            name=name, provider=provider, model=model, api_key=api_key, prompt=prompt
        )

    def _on_apply(self):
        profile = self._collect_form()
        if profile is None:
            return

        if (
            self._editing_original_name != profile.name
            and self.registry.find(profile.name) is not None
        ):
            messagebox.showerror(
                "重複", f"表示名「{profile.name}」は既に存在します。", parent=self.window
            )
            return

        self.registry.upsert(profile, original_name=self._editing_original_name)
        self._refresh_listbox()

        for i, p in enumerate(self.registry.profiles):
            if p.name == profile.name:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(i)
                break
        self._editing_original_name = profile.name

    def _on_ok(self):
        if self.name_var.get().strip() and self._collect_form() is not None:
            current = self._collect_form()
            if current is not None and (
                self._editing_original_name is None
                or self._editing_original_name == current.name
                or self.registry.find(current.name) is None
            ):
                self.registry.upsert(current, original_name=self._editing_original_name)

        self.on_save(self.registry)
        self.window.destroy()
