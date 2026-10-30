from __future__ import annotations

import json
import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk


APP_DIR = Path(__file__).resolve().parent
ENEMY_DIR = APP_DIR / "enemies"
LEVEL_DIR = APP_DIR / "levels"


def make_default_enemy_data() -> dict:
    return {
        "id": "new_enemy",
        "name": "New Enemy",
        "size": 35,
        "health": 1,
        "speed": 2.0,
        "color": [220, 50, 50],
        "movement": "fall",
        "unlock_level": 1,
        "spawn_priority": 100,
        "clusterable": True,
        "segments": 1,
        "sway_distance": 0,
        "segment_phase_offset": 0.3,
        "wave_speed": 0.08,
        "spawn": {"chance": 0.0, "chance_per_level": 0.05, "max_chance": 0.3},
        "attack": {"speed": 0.0, "interval": 0, "size": 0},
    }


def make_default_level_data() -> dict:
    return {
        "level": 1,
        "name": "New Level",
        "target_score": 10,
        "spawn_interval_ms": 850,
        "enemy_weights": {"enemy": 1},
        "boss": False,
    }


def load_json_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} does not contain a JSON object.")
    return data


class ModEditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ModShooter Mod Editor")
        self.geometry("1200x760")
        self.minsize(1100, 700)

        self.enemy_list: list[str] = []
        self.level_list: list[str] = []
        self.current_enemy_id: str | None = None
        self.current_level_id: str | None = None

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        self.enemy_tab = ttk.Frame(notebook)
        self.level_tab = ttk.Frame(notebook)
        notebook.add(self.enemy_tab, text="Enemy Editor")
        notebook.add(self.level_tab, text="Level Editor")

        self.setup_enemy_tab()
        self.setup_level_tab()
        self.reload_definitions()

    def setup_enemy_tab(self):
        left = ttk.Frame(self.enemy_tab)
        left.pack(side="left", fill="y", padx=(12, 8), pady=12)

        ttk.Label(left, text="Enemy definitions").pack(anchor="w")
        self.enemy_listbox = tk.Listbox(left, width=28, height=22)
        self.enemy_listbox.bind("<<ListboxSelect>>", self.on_enemy_select)
        self.enemy_listbox.pack(fill="both", expand=True, pady=(6, 10))

        button_row = ttk.Frame(left)
        button_row.pack(fill="x")
        ttk.Button(button_row, text="New", command=self.new_enemy).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Save", command=self.save_enemy).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Delete", command=self.delete_enemy).pack(side="left")

        form = ttk.Frame(self.enemy_tab)
        form.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=12)

        canvas_frame = ttk.LabelFrame(form, text="Preview")
        canvas_frame.pack(fill="x", pady=(0, 10))
        self.enemy_canvas = tk.Canvas(canvas_frame, width=360, height=220, bg="#111111", highlightthickness=0)
        self.enemy_canvas.pack(fill="both", expand=True, padx=8, pady=8)

        property_frame = ttk.LabelFrame(form, text="Properties")
        property_frame.pack(fill="both", expand=True)

        self.enemy_fields: dict[str, tk.Variable] = {}
        row = 0
        for label, key, value_type in [
            ("ID", "id", "str"),
            ("Name", "name", "str"),
            ("Size", "size", "int"),
            ("Health", "health", "int"),
            ("Speed", "speed", "float"),
            ("Movement", "movement", "choice"),
            ("Unlock Level", "unlock_level", "int"),
            ("Spawn Priority", "spawn_priority", "int"),
            ("Clusterable", "clusterable", "bool"),
            ("Segments", "segments", "int"),
            ("Sway Distance", "sway_distance", "int"),
            ("Phase Offset", "segment_phase_offset", "float"),
            ("Wave Speed", "wave_speed", "float"),
        ]:
            ttk.Label(property_frame, text=label).grid(row=row, column=0, sticky="w", padx=(12, 8), pady=4)
            if value_type == "choice":
                var = tk.StringVar()
                combo = ttk.Combobox(property_frame, textvariable=var, values=["fall", "weave", "boss"], state="readonly", width=16)
                combo.grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=4)
                self.enemy_fields[key] = var
            else:
                var = tk.StringVar()
                ttk.Entry(property_frame, textvariable=var, width=20).grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=4)
                self.enemy_fields[key] = var
            row += 1

        color_frame = ttk.Frame(property_frame)
        color_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
        ttk.Label(color_frame, text="Color (R, G, B)").pack(anchor="w")
        self.enemy_color_vars = [tk.StringVar(value="220"), tk.StringVar(value="50"), tk.StringVar(value="50")]
        for index, var in enumerate(self.enemy_color_vars):
            ttk.Entry(color_frame, textvariable=var, width=6).pack(side="left", padx=(0, 6))
        row += 1

        spawn_frame = ttk.LabelFrame(property_frame, text="Spawn")
        spawn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
        self.enemy_spawn_vars = {
            "chance": tk.StringVar(value="0.0"),
            "chance_per_level": tk.StringVar(value="0.05"),
            "max_chance": tk.StringVar(value="0.3"),
        }
        for i, (key, label) in enumerate([("chance", "Chance"), ("chance_per_level", "Chance / Level"), ("max_chance", "Max Chance")]):
            ttk.Label(spawn_frame, text=label).grid(row=0, column=i * 2, sticky="w", padx=(10, 4), pady=4)
            ttk.Entry(spawn_frame, textvariable=self.enemy_spawn_vars[key], width=12).grid(row=1, column=i * 2, sticky="ew", padx=(10, 4), pady=4)

        row += 1
        attack_frame = ttk.LabelFrame(property_frame, text="Attack")
        attack_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
        self.enemy_attack_vars = {
            "speed": tk.StringVar(value="0"),
            "interval": tk.StringVar(value="0"),
            "size": tk.StringVar(value="0"),
        }
        for i, (key, label) in enumerate([("speed", "Speed"), ("interval", "Interval"), ("size", "Size")]):
            ttk.Label(attack_frame, text=label).grid(row=0, column=i * 2, sticky="w", padx=(10, 4), pady=4)
            ttk.Entry(attack_frame, textvariable=self.enemy_attack_vars[key], width=12).grid(row=1, column=i * 2, sticky="ew", padx=(10, 4), pady=4)

        property_frame.columnconfigure(1, weight=1)

    def setup_level_tab(self):
        left = ttk.Frame(self.level_tab)
        left.pack(side="left", fill="y", padx=(12, 8), pady=12)

        ttk.Label(left, text="Level definitions").pack(anchor="w")
        self.level_listbox = tk.Listbox(left, width=28, height=22)
        self.level_listbox.bind("<<ListboxSelect>>", self.on_level_select)
        self.level_listbox.pack(fill="both", expand=True, pady=(6, 10))

        button_row = ttk.Frame(left)
        button_row.pack(fill="x")
        ttk.Button(button_row, text="New", command=self.new_level).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Save", command=self.save_level).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Delete", command=self.delete_level).pack(side="left")

        form = ttk.Frame(self.level_tab)
        form.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=12)

        canvas_frame = ttk.LabelFrame(form, text="Preview")
        canvas_frame.pack(fill="x", pady=(0, 10))
        self.level_canvas = tk.Canvas(canvas_frame, width=360, height=220, bg="#111111", highlightthickness=0)
        self.level_canvas.pack(fill="both", expand=True, padx=8, pady=8)

        level_form = ttk.LabelFrame(form, text="Properties")
        level_form.pack(fill="both", expand=True)

        self.level_fields: dict[str, tk.Variable] = {}
        for row, (label, key, value_type) in enumerate([
            ("Level", "level", "int"),
            ("Name", "name", "str"),
            ("Target Score", "target_score", "int"),
            ("Spawn Interval (ms)", "spawn_interval_ms", "int"),
            ("Boss Round", "boss", "bool"),
        ]):
            ttk.Label(level_form, text=label).grid(row=row, column=0, sticky="w", padx=(12, 8), pady=5)
            var = tk.StringVar()
            if value_type == "bool":
                combo = ttk.Combobox(level_form, textvariable=var, values=["False", "True"], state="readonly", width=16)
                combo.grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=5)
            else:
                ttk.Entry(level_form, textvariable=var, width=20).grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=5)
            self.level_fields[key] = var

        enemy_weights_frame = ttk.LabelFrame(level_form, text="Enemy Weights")
        enemy_weights_frame.grid(row=10, column=0, columnspan=2, sticky="ew", padx=12, pady=10)

        self.level_weights_rows: list[tuple[tk.StringVar, tk.StringVar, ttk.Button]] = []
        self.level_weights_frame = enemy_weights_frame
        ttk.Button(enemy_weights_frame, text="Add Weight", command=self.add_level_weight_row).pack(anchor="w", padx=8, pady=(8, 4))

    def reload_definitions(self):
        self.enemy_list = sorted([p.stem for p in ENEMY_DIR.glob("*.enemy") if p.is_file()])
        self.level_list = sorted([p.stem for p in LEVEL_DIR.glob("*.lvl") if p.is_file()])
        self.enemy_listbox.delete(0, tk.END)
        for enemy_name in self.enemy_list:
            self.enemy_listbox.insert(tk.END, enemy_name)
        self.level_listbox.delete(0, tk.END)
        for level_name in self.level_list:
            self.level_listbox.insert(tk.END, level_name)

        if self.enemy_list:
            self.enemy_listbox.select_set(0)
            self.on_enemy_select()
        else:
            self.clear_enemy_form()

        if self.level_list:
            self.level_listbox.select_set(0)
            self.on_level_select()
        else:
            self.clear_level_form()

    def clear_enemy_form(self):
        data = make_default_enemy_data()
        self.populate_enemy_form(data)

    def populate_enemy_form(self, data: dict):
        for field in ["id", "name", "size", "health", "speed", "movement", "unlock_level", "spawn_priority", "clusterable", "segments", "sway_distance", "segment_phase_offset", "wave_speed"]:
            self.enemy_fields[field].set(str(data.get(field, "")))
        self.enemy_color_vars[0].set(str(data.get("color", [0, 0, 0])[0]))
        self.enemy_color_vars[1].set(str(data.get("color", [0, 0, 0])[1]))
        self.enemy_color_vars[2].set(str(data.get("color", [0, 0, 0])[2]))
        spawn = data.get("spawn", {"chance": 0.0, "chance_per_level": 0.05, "max_chance": 0.3})
        for key, value in spawn.items():
            self.enemy_spawn_vars[key].set(str(value))
        attack = data.get("attack", {"speed": 0.0, "interval": 0, "size": 0})
        for key, value in attack.items():
            self.enemy_attack_vars[key].set(str(value))
        self.update_enemy_preview(data)

    def update_enemy_preview(self, data: dict):
        self.enemy_canvas.delete("all")
        size = max(10, int(data.get("size", 35)))
        color = [int(v) for v in [self.enemy_color_vars[0].get(), self.enemy_color_vars[1].get(), self.enemy_color_vars[2].get()]]
        origin_x = 180 - size / 2
        origin_y = 110 - size / 2
        movement = str(data.get("movement", "fall"))
        if movement == "weave":
            segments = max(1, int(data.get("segments", 1)))
            phase = float(data.get("segment_phase_offset", 0.3))
            for i in range(segments):
                x = int(origin_x + i * 12) + 6
                y = int(origin_y + (i * 10) % 70)
                self.enemy_canvas.create_rectangle(x, y, x + size, y + size, fill="#%02x%02x%02x" % tuple(color), outline="white")
        else:
            self.enemy_canvas.create_rectangle(origin_x, origin_y, origin_x + size, origin_y + size, fill="#%02x%02x%02x" % tuple(color), outline="white")
        self.enemy_canvas.create_text(180, 190, text=data.get("name", "Enemy"), fill="white", font=("TkDefaultFont", 11, "bold"))

    def on_enemy_select(self, event=None):
        selection = self.enemy_listbox.curselection()
        if not selection:
            return
        enemy_name = self.enemy_listbox.get(selection[0])
        path = ENEMY_DIR / f"{enemy_name}.enemy"
        try:
            data = load_json_file(path)
        except Exception as exc:
            messagebox = tk.messagebox if hasattr(tk, "messagebox") else None
            if messagebox:
                messagebox.showerror("Load Error", str(exc))
            return
        self.current_enemy_id = enemy_name
        self.populate_enemy_form(data)

    def new_enemy(self):
        self.current_enemy_id = None
        self.clear_enemy_form()

    def save_enemy(self):
        try:
            data = self.collect_enemy_data()
        except ValueError as exc:
            tk.messagebox.showerror("Validation Error", str(exc))
            return

        filename = f"{data['id']}.enemy"
        target = ENEMY_DIR / filename
        if not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")

        self.reload_definitions()
        try:
            selection_index = self.enemy_list.index(data["id"])
            self.enemy_listbox.select_clear(0, tk.END)
            self.enemy_listbox.select_set(selection_index)
        except ValueError:
            pass

    def collect_enemy_data(self) -> dict:
        def parse_int(name: str, value: str):
            try:
                return int(value)
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer.") from exc

        def parse_float(name: str, value: str):
            try:
                return float(value)
            except ValueError as exc:
                raise ValueError(f"{name} must be a number.") from exc

        enemy_id = self.enemy_fields["id"].get().strip()
        if not enemy_id or not re.match(r"^[a-z_][a-z0-9_]*$", enemy_id):
            raise ValueError("Enemy ID must be lowercase snake_case.")

        color = [
            parse_int("R", self.enemy_color_vars[0].get()),
            parse_int("G", self.enemy_color_vars[1].get()),
            parse_int("B", self.enemy_color_vars[2].get()),
        ]
        if any(not 0 <= channel <= 255 for channel in color):
            raise ValueError("Color channels must be between 0 and 255.")

        movement = self.enemy_fields["movement"].get().strip() or "fall"
        if movement not in {"fall", "weave", "boss"}:
            raise ValueError("Movement must be fall, weave, or boss.")

        clusterable_text = self.enemy_fields["clusterable"].get().strip().lower()
        clusterable = clusterable_text in {"true", "yes", "1", "on"}

        data = {
            "id": enemy_id,
            "name": self.enemy_fields["name"].get().strip() or enemy_id,
            "size": parse_int("Size", self.enemy_fields["size"].get()),
            "health": parse_int("Health", self.enemy_fields["health"].get()),
            "speed": parse_float("Speed", self.enemy_fields["speed"].get()),
            "color": color,
            "movement": movement,
            "unlock_level": parse_int("Unlock Level", self.enemy_fields["unlock_level"].get()),
            "spawn_priority": parse_int("Spawn Priority", self.enemy_fields["spawn_priority"].get()),
            "clusterable": clusterable,
            "segments": parse_int("Segments", self.enemy_fields["segments"].get()),
            "sway_distance": parse_int("Sway Distance", self.enemy_fields["sway_distance"].get()),
            "segment_phase_offset": parse_float("Phase Offset", self.enemy_fields["segment_phase_offset"].get()),
            "wave_speed": parse_float("Wave Speed", self.enemy_fields["wave_speed"].get()),
            "spawn": {
                "chance": parse_float("Spawn Chance", self.enemy_spawn_vars["chance"].get()),
                "chance_per_level": parse_float("Chance / Level", self.enemy_spawn_vars["chance_per_level"].get()),
                "max_chance": parse_float("Max Chance", self.enemy_spawn_vars["max_chance"].get()),
            },
            "attack": {
                "speed": parse_float("Attack Speed", self.enemy_attack_vars["speed"].get()),
                "interval": parse_int("Attack Interval", self.enemy_attack_vars["interval"].get()),
                "size": parse_int("Attack Size", self.enemy_attack_vars["size"].get()),
            },
        }
        return data

    def delete_enemy(self):
        selection = self.enemy_listbox.curselection()
        if not selection:
            return
        enemy_name = self.enemy_listbox.get(selection[0])
        path = ENEMY_DIR / f"{enemy_name}.enemy"
        path.unlink(missing_ok=True)
        self.reload_definitions()

    def clear_level_form(self):
        self.populate_level_form(make_default_level_data())

    def populate_level_form(self, data: dict):
        self.level_fields["level"].set(str(data.get("level", 1)))
        self.level_fields["name"].set(str(data.get("name", "New Level")))
        self.level_fields["target_score"].set(str(data.get("target_score", 10)))
        self.level_fields["spawn_interval_ms"].set(str(data.get("spawn_interval_ms", 850)))
        self.level_fields["boss"].set(str(bool(data.get("boss", False))))

        for row in self.level_weights_rows:
            for widget in (row[0], row[1], row[2]):
                widget.destroy()
        self.level_weights_rows.clear()

        weights = data.get("enemy_weights", {"enemy": 1})
        for enemy_id, weight in weights.items():
            self.add_level_weight_row(enemy_id, weight)

        self.update_level_preview(data)

    def add_level_weight_row(self, enemy_id: str | None = None, weight: float | int | str | None = None):
        row = ttk.Frame(self.level_weights_frame)
        row.pack(fill="x", padx=8, pady=4)

        enemy_var = tk.StringVar(value=enemy_id or "enemy")
        weight_var = tk.StringVar(value=str(weight if weight is not None else 1))
        remove_btn = ttk.Button(row, text="Remove", command=lambda: self.remove_level_weight_row(row, enemy_var, weight_var))
        ttk.Entry(row, textvariable=enemy_var, width=20).pack(side="left")
        ttk.Entry(row, textvariable=weight_var, width=12).pack(side="left", padx=(6, 0))
        remove_btn.pack(side="left", padx=(8, 0))
        self.level_weights_rows.append((enemy_var, weight_var, remove_btn))

    def remove_level_weight_row(self, row_widget: ttk.Frame, enemy_var: tk.StringVar, weight_var: tk.StringVar):
        row_widget.destroy()
        self.level_weights_rows = [entry for entry in self.level_weights_rows if entry[0] is not enemy_var and entry[1] is not weight_var]

    def on_level_select(self, event=None):
        selection = self.level_listbox.curselection()
        if not selection:
            return
        level_name = self.level_listbox.get(selection[0])
        path = LEVEL_DIR / f"{level_name}.lvl"
        try:
            data = load_json_file(path)
        except Exception as exc:
            tk.messagebox.showerror("Load Error", str(exc))
            return
        self.current_level_id = level_name
        self.populate_level_form(data)

    def new_level(self):
        self.current_level_id = None
        self.clear_level_form()

    def save_level(self):
        try:
            data = self.collect_level_data()
        except ValueError as exc:
            tk.messagebox.showerror("Validation Error", str(exc))
            return

        filename = f"level_{data['level']}.lvl"
        target = LEVEL_DIR / filename
        with target.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")

        self.reload_definitions()
        try:
            selection_index = self.level_list.index(str(data["level"]))
            self.level_listbox.select_clear(0, tk.END)
            self.level_listbox.select_set(selection_index)
        except ValueError:
            pass

    def collect_level_data(self) -> dict:
        def parse_int(name: str, value: str):
            try:
                return int(value)
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer.") from exc

        level_number = parse_int("Level", self.level_fields["level"].get())
        if level_number < 1:
            raise ValueError("Level must be at least 1.")

        boss_value = self.level_fields["boss"].get().strip().lower()
        boss = boss_value in {"true", "yes", "1", "on"}

        weights: dict[str, float] = {}
        for enemy_var, weight_var, _ in self.level_weights_rows:
            enemy_id = enemy_var.get().strip()
            weight_text = weight_var.get().strip()
            if not enemy_id:
                continue
            try:
                weight = float(weight_text)
            except ValueError as exc:
                raise ValueError(f"Enemy weight for '{enemy_id}' must be numeric.") from exc
            if weight <= 0:
                raise ValueError(f"Enemy weight for '{enemy_id}' must be positive.")
            weights[enemy_id] = weight
        if not weights:
            raise ValueError("At least one enemy weight is required.")

        return {
            "level": level_number,
            "name": self.level_fields["name"].get().strip() or f"Level {level_number}",
            "target_score": parse_int("Target Score", self.level_fields["target_score"].get()),
            "spawn_interval_ms": parse_int("Spawn Interval", self.level_fields["spawn_interval_ms"].get()),
            "enemy_weights": weights,
            "boss": boss,
        }

    def delete_level(self):
        selection = self.level_listbox.curselection()
        if not selection:
            return
        level_name = self.level_listbox.get(selection[0])
        path = LEVEL_DIR / f"{level_name}.lvl"
        path.unlink(missing_ok=True)
        self.reload_definitions()

    def update_level_preview(self, data: dict):
        self.level_canvas.delete("all")
        weights = data.get("enemy_weights", {"enemy": 1})
        if not weights:
            return

        total = sum(float(v) for v in weights.values())
        y = 10
        max_width = 260
        for enemy_id, weight in weights.items():
            percentage = (float(weight) / total) * 100 if total else 0
            bar_width = int(max_width * percentage / 100)
            self.level_canvas.create_rectangle(30, y, 30 + bar_width, y + 18, fill="#3eea77", outline="white")
            self.level_canvas.create_text(30, y + 9, text=f"{enemy_id}", anchor="w", fill="white", font=("TkDefaultFont", 9, "bold"))
            self.level_canvas.create_text(300, y + 9, text=f"{weight}", fill="white", font=("TkDefaultFont", 9))
            y += 30

        self.level_canvas.create_text(180, 200, text=data.get("name", "Level"), fill="white", font=("TkDefaultFont", 11, "bold"))


if __name__ == "__main__":
    ENEMY_DIR.mkdir(parents=True, exist_ok=True)
    LEVEL_DIR.mkdir(parents=True, exist_ok=True)
    app = ModEditorApp()
    app.mainloop()
