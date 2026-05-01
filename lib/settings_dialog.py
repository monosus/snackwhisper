import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from lib.model_profile import PROVIDER_PRESETS, ModelProfile, ProfileRegistry


class SettingsDialog:
    """モデル+APIキーのプロファイルを管理するモーダルダイアログ"""

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
        self.window.grab_set()
        self.window.resizable(False, False)

        self._editing_original_name: Optional[str] = None

        self._build_ui()
        self._refresh_listbox()

        if self.registry.profiles:
            self.listbox.selection_set(0)
            self._on_select(None)
        else:
            self._clear_form()

    def _build_ui(self):
        outer = tk.Frame(self.window, padx=12, pady=12)
        outer.pack(fill=tk.BOTH, expand=True)

        list_frame = tk.LabelFrame(outer, text="プロファイル一覧", padx=8, pady=8)
        list_frame.grid(row=0, column=0, sticky="ns", padx=(0, 12))

        self.listbox = tk.Listbox(list_frame, width=24, height=10, exportselection=False)
        self.listbox.pack(side=tk.TOP, fill=tk.Y, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        list_btns = tk.Frame(list_frame)
        list_btns.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))
        tk.Button(list_btns, text="新規", width=6, command=self._on_new).pack(side=tk.LEFT)
        tk.Button(list_btns, text="削除", width=6, command=self._on_delete).pack(side=tk.LEFT, padx=(4, 0))

        form = tk.LabelFrame(outer, text="プロファイル編集", padx=8, pady=8)
        form.grid(row=0, column=1, sticky="nsew")

        tk.Label(form, text="表示名").grid(row=0, column=0, sticky="w", pady=4)
        self.name_var = tk.StringVar()
        tk.Entry(form, textvariable=self.name_var, width=36).grid(row=0, column=1, padx=4, pady=4)

        tk.Label(form, text="プロバイダ").grid(row=1, column=0, sticky="w", pady=4)
        self.provider_var = tk.StringVar(value="openai")
        provider_menu = ttk.Combobox(
            form,
            textvariable=self.provider_var,
            values=list(PROVIDER_PRESETS.keys()),
            state="readonly",
            width=33,
        )
        provider_menu.grid(row=1, column=1, padx=4, pady=4)
        provider_menu.bind("<<ComboboxSelected>>", self._on_provider_change)

        tk.Label(form, text="モデル").grid(row=2, column=0, sticky="w", pady=4)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            form,
            textvariable=self.model_var,
            values=PROVIDER_PRESETS["openai"],
            width=33,
        )
        self.model_combo.grid(row=2, column=1, padx=4, pady=4)

        tk.Label(form, text="APIキー").grid(row=3, column=0, sticky="w", pady=4)
        self.api_key_var = tk.StringVar()
        tk.Entry(form, textvariable=self.api_key_var, width=36, show="*").grid(
            row=3, column=1, padx=4, pady=4
        )

        form_btns = tk.Frame(form)
        form_btns.grid(row=4, column=0, columnspan=2, pady=(8, 0), sticky="e")
        tk.Button(form_btns, text="このプロファイルを保存", command=self._on_apply).pack(side=tk.LEFT)

        bottom = tk.Frame(outer)
        bottom.grid(row=1, column=0, columnspan=2, pady=(12, 0), sticky="e")
        tk.Button(bottom, text="OK", width=8, command=self._on_ok).pack(side=tk.LEFT)
        tk.Button(bottom, text="キャンセル", width=8, command=self.window.destroy).pack(
            side=tk.LEFT, padx=(8, 0)
        )

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

    def _load_form(self, profile: ModelProfile):
        self._editing_original_name = profile.name
        self.name_var.set(profile.name)
        self.provider_var.set(profile.provider)
        self.model_combo.config(values=PROVIDER_PRESETS.get(profile.provider, []))
        self.model_var.set(profile.model)
        self.api_key_var.set(profile.api_key)

    def _clear_form(self):
        self._editing_original_name = None
        self.name_var.set("")
        self.provider_var.set("openai")
        self.model_combo.config(values=PROVIDER_PRESETS["openai"])
        self.model_var.set("")
        self.api_key_var.set("")

    def _on_provider_change(self, _event):
        provider = self.provider_var.get()
        presets = PROVIDER_PRESETS.get(provider, [])
        self.model_combo.config(values=presets)
        if presets and self.model_var.get() not in presets:
            self.model_var.set(presets[0])

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

        if not name:
            messagebox.showerror("入力エラー", "表示名を入力してください。", parent=self.window)
            return None
        if not provider:
            messagebox.showerror("入力エラー", "プロバイダを選択してください。", parent=self.window)
            return None
        if not model:
            messagebox.showerror("入力エラー", "モデルを入力または選択してください。", parent=self.window)
            return None

        return ModelProfile(name=name, provider=provider, model=model, api_key=api_key)

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
