from __future__ import annotations
import importlib.util
from .common import *
from . import common as common_mod

from pathlib import Path
import pprint
import contextlib
import io

CONTENT_DIR = Path(__file__).resolve().parent / "content"
BAKUGAN_FILE_PATH = CONTENT_DIR / "bakugan_templates.py"
ABILITIES_FILE_PATH = CONTENT_DIR / "ability_cards.py"
GATES_FILE_PATH = CONTENT_DIR / "gate_cards.py"
BAKUGAN_MODULE_NAME = "bakugan_modular_full.content.bakugan_templates"
ABILITIES_MODULE_NAME = "bakugan_modular_full.content.ability_cards"
GATES_MODULE_NAME = "bakugan_modular_full.content.gate_cards"



import json

def custom_effect_to_json(effect: dict, timing: str) -> str:
    eff = normalise_custom_effect(effect, timing)
    return json.dumps(eff, indent=2, sort_keys=False)

def ensure_cardlab_item_defaults(item: dict, kind: str) -> dict:
    kind = (kind or "").upper()
    default_timing = "PASSIVE_GATE" if kind == "GATE" else str(item.get("timing", "DURING_BATTLE") or "DURING_BATTLE")
    item.setdefault("effect_mode", "builtin")
    item.setdefault("effect_id", "")
    item["custom_effect"] = normalise_custom_effect(item.get("custom_effect"), default_timing)
    eff = item["custom_effect"]
    item.setdefault("restrictions", eff.get("restrictions", ""))
    item.setdefault("duration", eff.get("duration", ""))
    if kind == "ABILITY":
        item.setdefault("timing", default_timing)
        item.setdefault("color", item.get("color", "RED") or "RED")
    else:
        item.setdefault("gate_type", item.get("gate_type", "GOLD") or "GOLD")
        item.setdefault("bonuses", item.get("bonuses", {}) or {})
    item.setdefault("price", 100)
    item.setdefault("description", "")
    item.setdefault("name", "")
    return item

FIELD_TOOLTIPS = {
    "Type": "What this condition or action does.\nExample: self_attribute_is, add_g, random_g, doom_loser.",
    "Target": "Who the effect applies to.\nExample: self, opponent, or both.",
    "Value": "Main text/value field for the rule. Often used for attributes, gate side, names, or phase-specific text.\nExamples: PYRUS, own_gate, DRAGONOID, RED.",
    "Amount": "Flat number applied by the action or threshold used by the condition.\nExamples: 120 for a G boost, 2 for a minimum count.",
    "Scale": "Named scaling source used by some effects.\nExamples: gates_won, used_abilities, standing_attributes.",
    "Min": "Minimum random or bounded value.\nExample: 0 for a 0-400 random bonus.",
    "Max": "Maximum random or bounded value.\nExample: 400 for a 0-400 random bonus.",
    "Multiplier": "Multiplier applied to another value, usually gate bonus or effect strength.\nExamples: 2 for double gate bonus, 1.5 for a 50% increase.",
    "Color": "Ability colour referenced by the rule.\nExamples: RED, BLUE, GREEN.",
    "Attr map JSON": "JSON mapping attributes to numbers for attribute-based scaling.\nExample: {\"PYRUS\": 100, \"AQUOS\": 50, \"DARKUS\": 120}.",
    "Restrictions": "Optional metadata / reminder field for limits or notes. It does not replace conditions.\nExample: once_per_battle or self_only.\nFor real multiple criteria, use the rule builder / Advanced JSON conditions list, for example:\n{\"conditions\":[{\"type\":\"opponent_attribute_is\",\"value\":\"AQUOS\"},{\"type\":\"opponent_attribute_is\",\"value\":\"DARKUS\"}],\"condition_logic\":\"OR\"}\nor\n{\"conditions\":[{\"type\":\"loadout_has_attributes\",\"value\":[\"HAOS\",\"DARKUS\",\"VENTUS\"]}],\"condition_logic\":\"AND\"}",
    "Duration": "How long the effect should last, as metadata for the rule.\nExamples: battle, until_end_of_battle, match, next_roll.\nUse this to describe persistence, not the trigger phase. Trigger phase is set in Timing / phase.",
}

class HoverTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
    def _schedule(self, _event=None):
        self._cancel()
        self._after_id = self.widget.after(450, self._show)
    def _cancel(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
    def _show(self):
        self._cancel()
        if self.tipwindow is not None or not self.text:
            return
        try:
            x, y, cx, cy = self.widget.bbox("insert")
        except Exception:
            x = y = cx = cy = 0
        x = x + self.widget.winfo_rootx() + 18
        y = y + self.widget.winfo_rooty() + 22
        tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            relief="solid",
            borderwidth=1,
            background="#fffde8",
            foreground="#111111",
            padx=6,
            pady=4,
            wraplength=320,
        )
        label.pack()
        self.tipwindow = tw
    def _hide(self, _event=None):
        self._cancel()
        tw = self.tipwindow
        self.tipwindow = None
        if tw is not None:
            try:
                tw.destroy()
            except Exception:
                pass

def attach_field_tip(label_widget, input_widget, field_name: str):
    text = FIELD_TOOLTIPS.get(field_name, "")
    if not text:
        return
    HoverTip(label_widget, text)
    HoverTip(input_widget, text)


class StoryModeApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Bakugan Story Mode")
        self.db = NPCDatabase()
        self.rng = random.Random()
        self.player: Optional[PlayerProfile] = None
        self.current_save_stem = "session_unsaved"
        set_current_output_dir(self.current_save_stem)
        self.debug_var = tk.BooleanVar(value=False)
        self.npc_market_debug_var = tk.BooleanVar(value=False)

        self.templates = make_bakugan_templates()
        self.abilities = make_ability_cards()
        self.gates = make_gate_cards()

        self.world_tournament_no = self.db.get_world_int("world_tournament_no", 0)
        self.world_season = self.db.get_world_int("world_season", 1)
        self.world_total_tournaments = self.db.get_world_int("world_total_tournaments", max(0, (self.world_season - 1) * 10 + self.world_tournament_no))
        self.world_seed = self.db.get_world_int("world_seed", 0)
        if self.world_seed == 0:
            self.world_seed = self.rng.randint(1, 2_000_000_000)
            self.db.set_world_int("world_seed", self.world_seed)
        self.world_cup_interval = max(1, self.db.get_world_int("world_cup_interval", WORLD_CUP_INTERVAL_DEFAULT))
        self.current_world_champion = self.db.get_world_json("current_world_champion", None)
        self.world_champion_history = self.db.get_world_json("world_champion_history", []) or []
        self.world_cup_new_npcs = int(self.db.get_world_int("world_cup_new_npcs", WORLD_CUP_NEW_NPCS_DEFAULT) or WORLD_CUP_NEW_NPCS_DEFAULT)
        self.season_ban_settings = self.db.get_world_json("season_ban_settings", dict(SEASON_BAN_DEFAULTS)) or dict(SEASON_BAN_DEFAULTS)
        self.current_season_bans = self.db.get_world_json("current_season_bans", empty_season_ban_state(self.world_season)) or empty_season_ban_state(self.world_season)
        self.season_ban_history = self.db.get_world_json("season_ban_history", []) or []
        self.age_progression_enabled = bool(self.db.get_world_int("age_progression_enabled", 0))
        self.season_new_npcs = int(self.db.get_world_int("season_new_npcs", SEASON_NEW_NPCS_DEFAULT) or SEASON_NEW_NPCS_DEFAULT)
        self.autosave_interval_seasons = max(1, int(self.db.get_world_int("autosave_interval_seasons", 5) or 5))
        self.npc_target_population = 192
        self.ensure_npc_universe()
        self.get_season_shop_stock()

        self.text_to_ide_var = tk.BooleanVar(value=bool(self.db.get_world_int("text_to_ide_enabled", 1)))
        self.txt_exports_var = tk.BooleanVar(value=bool(self.db.get_world_int("txt_exports_enabled", 1)))
        self.debug_console_var = tk.BooleanVar(value=bool(self.db.get_world_int("debug_console_enabled", 1)))
        set_text_output_to_ide_enabled(bool(self.text_to_ide_var.get()))
        set_text_file_exports_enabled(bool(self.txt_exports_var.get()))
        set_debug_console_text_enabled(bool(self.debug_console_var.get()))
        self.status_var = tk.StringVar(value="Create a character to begin.")
        self.build_ui()

    def build_ui(self) -> None:
        frm = ttk.Frame(self.root, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Bakugan Story Mode", font=("Arial", 16, "bold")).pack(anchor="w")
        top_row = ttk.Frame(frm)
        top_row.pack(anchor="w", pady=(4, 10), fill="x")
        ttk.Button(top_row, text="Settings", command=self.open_settings).pack(side="left")

        ttk.Label(frm, textvariable=self.status_var, wraplength=700).pack(anchor="w", pady=(0, 10))

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=4)
        for col in range(5):
            btns.columnconfigure(col, weight=1)

        button_specs = [
            ("new_character_button", "New Character", self.new_character),
            ("view_loadout_button", "View Loadout", self.view_loadout),
            ("customise_loadout_button", "Customise Loadout", self.customise_loadout),
            ("shop_button", "Shop", self.open_shop),
            ("binder_button", "Binder", self.open_binder),
            ("start_tournament_button", "Start Tournament", self.start_tournament),
            (None, "NPC Rankings", self.view_npc_rankings),
            (None, "Search Profile", self.search_profile_loadout),
            (None, "Tournament History", self.view_tournament_history),
            ("season_rules_button", "Season Rules", self.view_season_rules),
            (None, "Season Summary", self.view_season_summary),
            ("retire_button", "Retire Character", self.retire_character),
            (None, "Save Game", self.save_character_json),
            (None, "Load Game", self.load_character_json),
            (None, "Card Reference", self.view_card_reference),
            ("auto_season_button", "Auto Rest of Season", self.auto_rest_of_season),
            ("auto_seasons_x_button", "Auto Rest x Seasons", self.auto_rest_x_seasons),
        ]
        for idx, (attr_name, label, command) in enumerate(button_specs):
            row = idx // 5
            column = idx % 5
            btn = ttk.Button(btns, text=label, command=command)
            btn.grid(row=row, column=column, padx=4, pady=4, sticky="ew")
            if attr_name:
                setattr(self, attr_name, btn)

        self.text = tk.Text(frm, width=110, height=30)
        self.text.pack(fill="both", expand=True)
        self.debug_var.trace_add('write', lambda *_: self.update_debug_controls())
        self.update_debug_controls()
        self.update_player_button_visibility()

    def league_band_for_rating(self, rating: float) -> Tuple[str, float, Optional[float]]:
        if rating < 1200:
            return ("Amateur", 800.0, 1200.0)
        if rating < 1600:
            return ("Semi-Pro", 1200.0, 1600.0)
        if rating < 2000:
            return ("Pro", 1600.0, 2000.0)
        return ("Elite", 2000.0, None)

    def league_band_label_for_rating(self, rating: float) -> str:
        name, lo, hi = self.league_band_for_rating(rating)
        if hi is None:
            return f"{name} ({int(lo)}+)"
        return f"{name} ({int(lo)}-{int(hi)})"

    def profile_league_band(self, profile: PlayerProfile) -> str:
        return self.league_band_for_rating(profile.glicko.rating)[0]

    def update_player_button_visibility(self) -> None:
        has_player = self.player is not None
        for btn in (
            getattr(self, "view_loadout_button", None),
            getattr(self, "customise_loadout_button", None),
            getattr(self, "shop_button", None),
            getattr(self, "binder_button", None),
            getattr(self, "retire_button", None),
        ):
            if btn is None:
                continue
            if has_player:
                btn.grid()
            else:
                btn.grid_remove()

    def retire_character(self) -> None:
        if self.player is None:
            messagebox.showerror("No character", "There is no active character to retire.", parent=self.root)
            return
        name = self.player.name
        if not messagebox.askyesno("Retire Character", f"Retire {name} and continue the world without a player character?", parent=self.root):
            return
        self.player = None
        self.update_player_button_visibility()
        self.refresh_status()
        self.append_text(f"Retired player character {name}. The world will continue with NPC-only tournaments.")

    def _load_raw_content_data(self) -> Tuple[List[dict], List[dict], List[dict]]:
        def _load_module(module_name: str, file_path: Path):
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)
            return module

        mod_b = _load_module(BAKUGAN_MODULE_NAME, BAKUGAN_FILE_PATH)
        mod_a = _load_module(ABILITIES_MODULE_NAME, ABILITIES_FILE_PATH)
        mod_g = _load_module(GATES_MODULE_NAME, GATES_FILE_PATH)
        return (
            [dict(x) for x in mod_b.RAW_BAKUGAN_TEMPLATES],
            [dict(x) for x in mod_a.RAW_ABILITY_CARDS],
            [dict(x) for x in mod_g.RAW_GATE_CARDS],
        )

    def _save_raw_content_data(self, raw_bakugan: List[dict], raw_abilities: List[dict], raw_gates: List[dict]) -> None:
        bakugan_header = '"""Bakugan template data."""\n\n'
        abilities_header = '"""Ability card data."""\n\n'
        gates_header = '"""Gate card data."""\n\n'
        BAKUGAN_FILE_PATH.write_text(
            bakugan_header + "RAW_BAKUGAN_TEMPLATES = " + pprint.pformat(raw_bakugan, width=120, sort_dicts=False) + "\n",
            encoding="utf-8",
        )
        ABILITIES_FILE_PATH.write_text(
            abilities_header + "RAW_ABILITY_CARDS = " + pprint.pformat(raw_abilities, width=120, sort_dicts=False) + "\n",
            encoding="utf-8",
        )
        GATES_FILE_PATH.write_text(
            gates_header + "RAW_GATE_CARDS = " + pprint.pformat(raw_gates, width=120, sort_dicts=False) + "\n",
            encoding="utf-8",
        )

    def _refresh_content_from_file(self) -> None:
        import importlib
        import sys
        importlib.invalidate_caches()

        raw_b, raw_a, raw_g = self._load_raw_content_data()

        # Update the actual common-module globals used by make_* helpers.
        common_mod.RAW_BAKUGAN_TEMPLATES = raw_b
        common_mod.RAW_ABILITY_CARDS = raw_a
        common_mod.RAW_GATE_CARDS = raw_g

        # Also refresh locally imported names for any app-side direct reads.
        global RAW_BAKUGAN_TEMPLATES, RAW_ABILITY_CARDS, RAW_GATE_CARDS
        RAW_BAKUGAN_TEMPLATES = raw_b
        RAW_ABILITY_CARDS = raw_a
        RAW_GATE_CARDS = raw_g

        self.templates = common_mod.make_bakugan_templates()
        self.abilities = common_mod.make_ability_cards()
        self.gates = common_mod.make_gate_cards()

        gate_by_name = {g.name: g for g in self.gates}
        gate_by_name_type = {(g.name, g.gate_type): g for g in self.gates}

        ability_by_name = {a.name: a for a in self.abilities}
        ability_by_name_effect = {(a.name, getattr(a, "effect_id", "")): a for a in self.abilities}
        ability_by_effect = {getattr(a, "effect_id", ""): a for a in self.abilities if getattr(a, "effect_id", "")}

        def refresh_profile_cards(profile: PlayerProfile) -> None:
            new_gates = []
            for g in profile.collection_gates:
                fresh = gate_by_name_type.get((g.name, g.gate_type)) or gate_by_name.get(g.name)
                new_gates.append(clone_gate(fresh if fresh is not None else g))
            profile.collection_gates = new_gates

            new_abilities = []
            for a in profile.collection_abilities:
                fresh = (
                    ability_by_name_effect.get((a.name, getattr(a, "effect_id", "")))
                    or ability_by_name.get(a.name)
                    or ability_by_effect.get(getattr(a, "effect_id", ""))
                )
                new_abilities.append(clone_ability(fresh if fresh is not None else a))
            profile.collection_abilities = new_abilities

            try:
                profile.ensure_valid_loadout()
            except Exception:
                pass

        if self.player:
            refresh_profile_cards(self.player)
        npcs = self.all_npcs()
        if npcs:
            for npc in npcs:
                refresh_profile_cards(npc)
            self.save_npcs(npcs)

        try:
            self.refresh_status()
        except Exception:
            pass

    def open_card_lab(self) -> None:
        if not bool(self.debug_var.get()):
            return
        win = tk.Toplevel(self.root)
        win.title("Card Lab")
        win.geometry("1500x900")

        raw_b, raw_a, raw_g = self._load_raw_content_data()
        for item in raw_a:
            ensure_cardlab_item_defaults(item, "ABILITY")
        for item in raw_g:
            ensure_cardlab_item_defaults(item, "GATE")

        search_var = tk.StringVar(value="")
        type_var = tk.StringVar(value="ABILITY")
        subtype_var = tk.StringVar(value="ALL")
        selected = {"kind": None, "index": None}
        current_effect = {"data": normalise_custom_effect(None, "DURING_BATTLE")}

        top = ttk.Frame(win, padding=8)
        top.pack(fill="both", expand=True)

        filter_row = ttk.Frame(top)
        filter_row.pack(fill="x", pady=(0, 8))
        ttk.Label(filter_row, text="Search").pack(side="left")
        ttk.Entry(filter_row, textvariable=search_var, width=34).pack(side="left", padx=(6, 12))
        ttk.Label(filter_row, text="Type").pack(side="left")
        type_box = ttk.Combobox(filter_row, state="readonly", values=["ABILITY", "GATE"], textvariable=type_var, width=10)
        type_box.pack(side="left", padx=(6, 12))
        ttk.Label(filter_row, text="Filter").pack(side="left")
        subtype_box = ttk.Combobox(filter_row, state="readonly", textvariable=subtype_var, width=18)
        subtype_box.pack(side="left", padx=(6, 12))

        body = ttk.Panedwindow(top, orient="horizontal")
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=2)

        tree = ttk.Treeview(left, columns=("type", "subtype", "name", "mode", "effect"), show="headings", height=28)
        for col, w in (("type", 70), ("subtype", 90), ("name", 220), ("mode", 80), ("effect", 220)):
            tree.heading(col, text=col.title())
            tree.column(col, width=w, anchor="w")
        tree.pack(fill="both", expand=True)

        left_btns = ttk.Frame(left)
        left_btns.pack(fill="x", pady=(6, 0))

        form = ttk.Frame(right)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        kind_label = ttk.Label(form, text="No card selected")
        kind_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        name_var = tk.StringVar()
        desc_var = tk.StringVar()
        effect_var = tk.StringVar()
        effect_mode_var = tk.StringVar(value="builtin")
        timing_var = tk.StringVar(value="DURING_BATTLE")
        price_var = tk.StringVar(value="100")
        color_var = tk.StringVar(value="RED")
        gate_type_var = tk.StringVar(value="GOLD")
        preset_var = tk.StringVar(value="")
        restriction_var = tk.StringVar(value="")
        duration_var = tk.StringVar(value="")
        status_var = tk.StringVar(value="")

        attr_vars = {a.name: tk.StringVar(value="0") for a in Attribute}

        ttk.Label(form, text="Name").grid(row=1, column=0, sticky="w")
        ttk.Entry(form, textvariable=name_var, width=36).grid(row=1, column=1, sticky="ew")
        ttk.Label(form, text="Description").grid(row=2, column=0, sticky="nw", pady=(6, 0))
        desc_text = tk.Text(form, width=70, height=5)
        desc_text.grid(row=2, column=1, sticky="ew", pady=(6, 0))

        meta = ttk.Frame(form)
        meta.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for i in range(8):
            meta.columnconfigure(i, weight=0)
        ttk.Label(meta, text="Price").grid(row=0, column=0, sticky="w")
        ttk.Entry(meta, textvariable=price_var, width=8).grid(row=0, column=1, sticky="w", padx=(4, 10))
        ttk.Label(meta, text="Effect mode").grid(row=0, column=2, sticky="w")
        ttk.Combobox(meta, state="readonly", textvariable=effect_mode_var, values=["builtin", "custom"], width=10).grid(row=0, column=3, sticky="w", padx=(4, 10))
        ttk.Label(meta, text="Timing / phase").grid(row=0, column=4, sticky="w")
        timing_box = ttk.Combobox(meta, state="readonly", textvariable=timing_var, values=["ON_ROLL","AFTER_SUCCESSFUL_STAND","ON_BATTLE_START","DURING_ROLL","DURING_BATTLE","AFTER_BATTLE","ON_GATE_CAPTURE","ON_DEFEAT","FLEXIBLE","PASSIVE_GATE"], width=22)
        timing_box.grid(row=0, column=5, sticky="w", padx=(4, 10))
        ttk.Label(meta, text="Effect id").grid(row=1, column=0, sticky="w", pady=(6,0))
        effect_box = ttk.Combobox(meta, textvariable=effect_var, width=28)
        effect_box.grid(row=1, column=1, columnspan=2, sticky="w", padx=(4,10), pady=(6,0))
        ttk.Label(meta, text="Ability color").grid(row=1, column=3, sticky="w", pady=(6,0))
        color_box = ttk.Combobox(meta, state="readonly", textvariable=color_var, values=[c.name for c in AbilityColor], width=10)
        color_box.grid(row=1, column=4, sticky="w", padx=(4,10), pady=(6,0))
        ttk.Label(meta, text="Gate type").grid(row=1, column=5, sticky="w", pady=(6,0))
        gate_type_box = ttk.Combobox(meta, state="readonly", textvariable=gate_type_var, values=[g.name for g in GateType], width=10)
        gate_type_box.grid(row=1, column=6, sticky="w", padx=(4,10), pady=(6,0))

        extra = ttk.Frame(form)
        extra.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        restrictions_label = ttk.Label(extra, text="Restrictions")
        restrictions_label.grid(row=0, column=0, sticky="w")
        restrictions_entry = ttk.Entry(extra, textvariable=restriction_var, width=32)
        restrictions_entry.grid(row=0, column=1, sticky="w", padx=(4,10))
        attach_field_tip(restrictions_label, restrictions_entry, "Restrictions")
        duration_label = ttk.Label(extra, text="Duration")
        duration_label.grid(row=0, column=2, sticky="w")
        duration_entry = ttk.Entry(extra, textvariable=duration_var, width=20)
        duration_entry.grid(row=0, column=3, sticky="w", padx=(4,10))
        attach_field_tip(duration_label, duration_entry, "Duration")
        ttk.Label(extra, text="Preset").grid(row=0, column=4, sticky="w")
        preset_box = ttk.Combobox(extra, state="readonly", textvariable=preset_var, values=[""] + sorted(CARD_LAB_PRESETS.keys()), width=24)
        preset_box.grid(row=0, column=5, sticky="w", padx=(4,10))

        bonus_frame = ttk.LabelFrame(form, text="Attribute bonuses")
        bonus_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        bonus_widgets = []
        for i, attr in enumerate(Attribute):
            ttk.Label(bonus_frame, text=attr.value).grid(row=i, column=0, sticky="w", padx=(6, 6), pady=2)
            e = ttk.Entry(bonus_frame, textvariable=attr_vars[attr.name], width=10)
            e.grid(row=i, column=1, sticky="w", padx=(0, 6), pady=2)
            bonus_widgets.append(e)

        notebook = ttk.Notebook(form)
        notebook.grid(row=6, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        form.rowconfigure(6, weight=1)

        simple_tab = ttk.Frame(notebook)
        advanced_tab = ttk.Frame(notebook)
        preview_tab = ttk.Frame(notebook)
        notebook.add(simple_tab, text="Simple Builder")
        notebook.add(advanced_tab, text="Advanced JSON")
        notebook.add(preview_tab, text="Preview / Validation")

        simple_pane = ttk.Panedwindow(simple_tab, orient="horizontal")
        simple_pane.pack(fill="both", expand=True)
        cond_frame = ttk.LabelFrame(simple_pane, text="Conditions")
        act_frame = ttk.LabelFrame(simple_pane, text="Actions")
        else_frame = ttk.LabelFrame(simple_pane, text="Fallback actions")
        simple_pane.add(cond_frame, weight=1)
        simple_pane.add(act_frame, weight=1)
        simple_pane.add(else_frame, weight=1)

        def make_list_editor(parent, title, kind="condition"):
            parent.columnconfigure(0, weight=1)
            lb = tk.Listbox(parent, height=12)
            lb.grid(row=0, column=0, columnspan=5, sticky="nsew", padx=4, pady=4)
            parent.rowconfigure(0, weight=1)
            lbl_type = ttk.Label(parent, text="Type")
            lbl_type.grid(row=1, column=0, sticky="w")
            type_values = list(CARD_LAB_CONDITION_DEFS.keys()) if kind == "condition" else list(CARD_LAB_ACTION_DEFS.keys())
            type_var_local = tk.StringVar(value=type_values[0])
            cmb_type = ttk.Combobox(parent, state="readonly", values=type_values, textvariable=type_var_local, width=26)
            cmb_type.grid(row=1, column=1, sticky="ew", padx=4)
            attach_field_tip(lbl_type, cmb_type, "Type")

            lbl_target = ttk.Label(parent, text="Target")
            lbl_target.grid(row=2, column=0, sticky="w")
            target_var = tk.StringVar(value="self")
            cmb_target = ttk.Combobox(parent, state="readonly", values=["self","opponent","both"], textvariable=target_var, width=12)
            cmb_target.grid(row=2, column=1, sticky="w", padx=4)
            attach_field_tip(lbl_target, cmb_target, "Target")

            lbl_value = ttk.Label(parent, text="Value")
            lbl_value.grid(row=3, column=0, sticky="w")
            value_var = tk.StringVar(value="")
            ent_value = ttk.Entry(parent, textvariable=value_var, width=20)
            ent_value.grid(row=3, column=1, sticky="ew", padx=4)
            attach_field_tip(lbl_value, ent_value, "Value")

            lbl_amount = ttk.Label(parent, text="Amount")
            lbl_amount.grid(row=4, column=0, sticky="w")
            amount_var = tk.StringVar(value="")
            ent_amount = ttk.Entry(parent, textvariable=amount_var, width=12)
            ent_amount.grid(row=4, column=1, sticky="w", padx=4)
            attach_field_tip(lbl_amount, ent_amount, "Amount")

            lbl_scale = ttk.Label(parent, text="Scale")
            lbl_scale.grid(row=5, column=0, sticky="w")
            scale_var = tk.StringVar(value="")
            ent_scale = ttk.Entry(parent, textvariable=scale_var, width=12)
            ent_scale.grid(row=5, column=1, sticky="w", padx=4)
            attach_field_tip(lbl_scale, ent_scale, "Scale")

            lbl_min = ttk.Label(parent, text="Min")
            lbl_min.grid(row=6, column=0, sticky="w")
            min_var = tk.StringVar(value="")
            ent_min = ttk.Entry(parent, textvariable=min_var, width=12)
            ent_min.grid(row=6, column=1, sticky="w", padx=4)
            attach_field_tip(lbl_min, ent_min, "Min")

            lbl_max = ttk.Label(parent, text="Max")
            lbl_max.grid(row=7, column=0, sticky="w")
            max_var = tk.StringVar(value="")
            ent_max = ttk.Entry(parent, textvariable=max_var, width=12)
            ent_max.grid(row=7, column=1, sticky="w", padx=4)
            attach_field_tip(lbl_max, ent_max, "Max")

            lbl_mult = ttk.Label(parent, text="Multiplier")
            lbl_mult.grid(row=8, column=0, sticky="w")
            mult_var = tk.StringVar(value="")
            ent_mult = ttk.Entry(parent, textvariable=mult_var, width=12)
            ent_mult.grid(row=8, column=1, sticky="w", padx=4)
            attach_field_tip(lbl_mult, ent_mult, "Multiplier")

            lbl_color = ttk.Label(parent, text="Color")
            lbl_color.grid(row=9, column=0, sticky="w")
            color_local = tk.StringVar(value="")
            cmb_color = ttk.Combobox(parent, values=["", "RED", "BLUE", "GREEN"], textvariable=color_local, width=12)
            cmb_color.grid(row=9, column=1, sticky="w", padx=4)
            attach_field_tip(lbl_color, cmb_color, "Color")

            lbl_attrmap = ttk.Label(parent, text="Attr map JSON")
            lbl_attrmap.grid(row=10, column=0, sticky="w")
            attrmap_var = tk.StringVar(value="")
            ent_attrmap = ttk.Entry(parent, textvariable=attrmap_var, width=24)
            ent_attrmap.grid(row=10, column=1, sticky="ew", padx=4)
            attach_field_tip(lbl_attrmap, ent_attrmap, "Attr map JSON")
            btnrow = ttk.Frame(parent)
            btnrow.grid(row=11, column=0, columnspan=5, sticky="w", pady=6)
            return {"listbox": lb, "type_var": type_var_local, "target_var": target_var, "value_var": value_var, "amount_var": amount_var, "scale_var": scale_var, "min_var": min_var, "max_var": max_var, "mult_var": mult_var, "color_var": color_local, "attrmap_var": attrmap_var, "btnrow": btnrow}

        cond_ed = make_list_editor(cond_frame, "Conditions", "condition")
        act_ed = make_list_editor(act_frame, "Actions", "action")
        else_ed = make_list_editor(else_frame, "Fallback", "action")

        adv_text = tk.Text(advanced_tab, width=80, height=28)
        adv_text.pack(fill="both", expand=True, padx=6, pady=6)

        preview_text = tk.Text(preview_tab, width=80, height=28, wrap="word")
        preview_text.pack(fill="both", expand=True, padx=6, pady=6)

        def update_subtype_values(*_):
            if type_var.get() == "ABILITY":
                subtype_box.configure(values=["ALL"] + [c.name for c in AbilityColor])
                if subtype_var.get() not in ["ALL"] + [c.name for c in AbilityColor]:
                    subtype_var.set("ALL")
            else:
                subtype_box.configure(values=["ALL"] + [g.name for g in GateType])
                if subtype_var.get() not in ["ALL"] + [g.name for g in GateType]:
                    subtype_var.set("ALL")

        def rows():
            out = []
            if type_var.get() == "ABILITY":
                for i, item in enumerate(raw_a):
                    subtype = item.get("color", "")
                    out.append(("ABILITY", i, subtype, item))
            else:
                for i, item in enumerate(raw_g):
                    subtype = item.get("gate_type", "")
                    out.append(("GATE", i, subtype, item))
            q = search_var.get().strip().lower()
            sf = subtype_var.get()
            if sf and sf != "ALL":
                out = [r for r in out if str(r[2]).upper() == sf.upper()]
            if q:
                out = [r for r in out if q in f"{r[3].get('name','')} {r[3].get('description','')} {r[3].get('effect_id','')} {r[3].get('effect_mode','')}".lower()]
            return out

        def refresh_tree(*_):
            for iid in tree.get_children():
                tree.delete(iid)
            for kind, idx, subtype, item in rows():
                tree.insert("", "end", iid=f"{kind}:{idx}", values=(kind, subtype, item.get("name", ""), item.get("effect_mode", "builtin"), item.get("effect_id", "")))

        def set_bonus_visibility(is_gate: bool):
            state = "normal" if is_gate else "disabled"
            for w in bonus_widgets:
                w.configure(state=state)
            gate_type_box.configure(state=("readonly" if is_gate else "disabled"))
            color_box.configure(state=("readonly" if not is_gate else "disabled"))
            if is_gate:
                timing_var.set("PASSIVE_GATE")
                timing_box.configure(state="disabled")
            else:
                timing_box.configure(state="readonly")

        def render_item_dict_for_ui(item, kind):
            eff = ensure_cardlab_item_defaults(dict(item), kind)["custom_effect"]
            current_effect["data"] = eff
            adv_text.delete("1.0", "end")
            adv_text.insert("1.0", custom_effect_to_json(eff, eff.get("timing", "PASSIVE_GATE" if kind=="GATE" else "DURING_BATTLE")))
            restriction_var.set(str(eff.get("restrictions", "")))
            duration_var.set(str(eff.get("duration", "")))
            refresh_simple_lists()
            refresh_preview(kind)

        def refresh_simple_lists():
            for editor, key in ((cond_ed, "conditions"), (act_ed, "actions"), (else_ed, "else_actions")):
                lb = editor["listbox"]
                lb.delete(0, "end")
                for row in current_effect["data"].get(key, []):
                    lb.insert("end", json.dumps(row, ensure_ascii=False))

        def read_effect_from_advanced():
            try:
                data = json.loads(adv_text.get("1.0", "end").strip() or "{}")
            except Exception as exc:
                messagebox.showerror("Invalid JSON", str(exc), parent=win)
                return False
            current_effect["data"] = normalise_custom_effect(data, timing_var.get())
            current_effect["data"]["timing"] = timing_var.get()
            if restriction_var.get().strip():
                current_effect["data"]["restrictions"] = restriction_var.get().strip()
            else:
                current_effect["data"].pop("restrictions", None)
            if duration_var.get().strip():
                current_effect["data"]["duration"] = duration_var.get().strip()
            else:
                current_effect["data"].pop("duration", None)
            refresh_simple_lists()
            refresh_preview(selected.get("kind") or type_var.get())
            return True

        def sync_advanced():
            adv_text.delete("1.0", "end")
            adv_text.insert("1.0", custom_effect_to_json(current_effect["data"], timing_var.get()))
            refresh_preview(selected.get("kind") or type_var.get())

        def refresh_preview(kind):
            actual_kind = 'gate' if kind == 'GATE' else 'ability'
            eff = normalise_custom_effect(current_effect["data"], timing_var.get())
            issues = validate_custom_effect(eff, actual_kind)
            lines = [custom_effect_preview(eff, desc_text.get("1.0", "end").strip()), "", "Structured JSON:", custom_effect_to_json(eff, timing_var.get()), "", "Validation:"]
            if issues:
                lines += [f"- {x}" for x in issues]
            else:
                lines.append("- No validation issues detected.")
            preview_text.delete("1.0", "end")
            preview_text.insert("1.0", "\n".join(lines))

        def row_from_editor(editor, kind='condition'):
            row = {"type": editor["type_var"].get()}
            if editor["target_var"].get() and kind == 'action':
                row["target"] = editor["target_var"].get()
            for key, var in (("value", editor["value_var"]), ("amount", editor["amount_var"]), ("scale", editor["scale_var"]), ("min", editor["min_var"]), ("max", editor["max_var"]), ("multiplier", editor["mult_var"])):
                val = var.get().strip()
                if val != "":
                    try:
                        if '.' in val: row[key] = float(val)
                        else: row[key] = int(val)
                    except Exception:
                        row[key] = val
            c = editor["color_var"].get().strip()
            if c:
                row["color"] = c
            amap = editor["attrmap_var"].get().strip()
            if amap:
                try:
                    row["attribute_map"] = json.loads(amap)
                except Exception:
                    row["attribute_map"] = amap
            return row

        def load_editor_from_row(editor, row):
            editor["type_var"].set(row.get("type", "none"))
            editor["target_var"].set(row.get("target", "self"))
            editor["value_var"].set(str(row.get("value", "")))
            editor["amount_var"].set(str(row.get("amount", "")))
            editor["scale_var"].set(str(row.get("scale", "")))
            editor["min_var"].set(str(row.get("min", "")))
            editor["max_var"].set(str(row.get("max", "")))
            editor["mult_var"].set(str(row.get("multiplier", "")))
            editor["color_var"].set(str(row.get("color", "")))
            amap = row.get("attribute_map", "")
            editor["attrmap_var"].set(json.dumps(amap) if isinstance(amap, (dict, list)) else str(amap))

        def make_row_ops(editor, key, kind='condition'):
            lb = editor["listbox"]
            def sel_index():
                cur = lb.curselection()
                return cur[0] if cur else None
            def add_row():
                current_effect["data"].setdefault(key, []).append(row_from_editor(editor, kind))
                refresh_simple_lists(); sync_advanced()
            def upd_row():
                i = sel_index()
                if i is None: return
                current_effect["data"].setdefault(key, [])[i] = row_from_editor(editor, kind)
                refresh_simple_lists(); lb.selection_set(i); sync_advanced()
            def del_row():
                i = sel_index()
                if i is None: return
                del current_effect["data"].setdefault(key, [])[i]
                refresh_simple_lists(); sync_advanced()
            def up_row():
                i = sel_index()
                if i is None or i <= 0: return
                arr = current_effect["data"].setdefault(key, [])
                arr[i-1], arr[i] = arr[i], arr[i-1]
                refresh_simple_lists(); lb.selection_set(i-1); sync_advanced()
            def down_row():
                i = sel_index()
                arr = current_effect["data"].setdefault(key, [])
                if i is None or i >= len(arr)-1: return
                arr[i+1], arr[i] = arr[i], arr[i+1]
                refresh_simple_lists(); lb.selection_set(i+1); sync_advanced()
            def on_pick(_=None):
                i = sel_index()
                if i is None: return
                load_editor_from_row(editor, current_effect["data"].setdefault(key, [])[i])
            lb.bind('<<ListboxSelect>>', on_pick)
            for txt, fn in (("Add", add_row),("Update", upd_row),("Remove", del_row),("Up", up_row),("Down", down_row)):
                ttk.Button(editor["btnrow"], text=txt, command=fn).pack(side='left', padx=2)

        make_row_ops(cond_ed, 'conditions', 'condition')
        make_row_ops(act_ed, 'actions', 'action')
        make_row_ops(else_ed, 'else_actions', 'action')

        def apply_preset(*_):
            name = preset_var.get().strip()
            if not name:
                return
            current_effect["data"] = normalise_custom_effect(CARD_LAB_PRESETS.get(name), timing_var.get())
            if type_var.get() == 'GATE':
                current_effect["data"]["timing"] = 'PASSIVE_GATE'
                timing_var.set('PASSIVE_GATE')
            refresh_simple_lists(); sync_advanced()

        def on_select(*_):
            sel = tree.selection()
            if not sel:
                return
            kind, idx = sel[0].split(":")
            idx = int(idx)
            selected["kind"] = kind
            selected["index"] = idx
            item = raw_a[idx] if kind == 'ABILITY' else raw_g[idx]
            ensure_cardlab_item_defaults(item, kind)
            kind_label.configure(text=f"{kind}: {item.get('name', '')}")
            name_var.set(item.get('name',''))
            price_var.set(str(item.get('price', 100)))
            desc_text.delete('1.0','end'); desc_text.insert('1.0', item.get('description',''))
            effect_var.set(item.get('effect_id',''))
            effect_mode_var.set(item.get('effect_mode','builtin'))
            if kind == 'ABILITY':
                color_var.set(item.get('color','RED'))
                effect_box.configure(values=sorted({str(x.get('effect_id','')) for x in raw_a} | {'CUSTOM'}))
                timing_var.set(item.get('timing','DURING_BATTLE'))
                for attr in Attribute: attr_vars[attr.name].set('0')
            else:
                gate_type_var.set(item.get('gate_type','GOLD'))
                effect_box.configure(values=sorted({str(x.get('effect_id','')) for x in raw_g} | {'CUSTOM'}))
                timing_var.set('PASSIVE_GATE')
                bonuses = item.get('bonuses', {})
                for attr in Attribute: attr_vars[attr.name].set(str(bonuses.get(attr.name, bonuses.get(attr.value, 0))))
            set_bonus_visibility(kind == 'GATE')
            render_item_dict_for_ui(item, kind)

        def build_new_card():
            kind = type_var.get()
            if kind == 'ABILITY':
                item = {'name': 'New Ability', 'color': color_var.get() or 'RED', 'timing': 'DURING_BATTLE', 'description': '', 'effect_id': 'CUSTOM', 'price': 100, 'effect_mode': 'custom', 'custom_effect': normalise_custom_effect({'timing':'DURING_BATTLE','conditions':[],'actions':[{'type':'add_g','target':'self','amount':100}],'else_actions':[]}, 'DURING_BATTLE')}
                raw_a.append(item)
                selected_iid = f'ABILITY:{len(raw_a)-1}'
                type_var.set('ABILITY')
            else:
                item = {'name': 'New Gate', 'gate_type': gate_type_var.get() or 'GOLD', 'bonuses': {a.name:0 for a in Attribute}, 'description': '', 'effect_id': 'CUSTOM', 'price': 110, 'effect_mode': 'custom', 'custom_effect': normalise_custom_effect({'timing':'PASSIVE_GATE','conditions':[],'actions':[{'type':'double_gate_bonus','target':'self'}],'else_actions':[]}, 'PASSIVE_GATE')}
                raw_g.append(item)
                selected_iid = f'GATE:{len(raw_g)-1}'
                type_var.set('GATE')
            refresh_tree(); tree.selection_set(selected_iid); tree.focus(selected_iid); on_select()

        def duplicate_card():
            kind = selected['kind']; idx = selected['index']
            if kind is None: return
            source = dict(raw_a[idx] if kind == 'ABILITY' else raw_g[idx])
            source['name'] = f"{source.get('name','Card')} Copy"
            source['custom_effect'] = deep_copy_effect(source.get('custom_effect'))
            if kind == 'ABILITY':
                raw_a.append(source); iid=f'ABILITY:{len(raw_a)-1}'
            else:
                raw_g.append(source); iid=f'GATE:{len(raw_g)-1}'
            refresh_tree(); tree.selection_set(iid); tree.focus(iid); on_select()

        def delete_card():
            kind = selected['kind']; idx = selected['index']
            if kind is None: return
            item = raw_a[idx] if kind == 'ABILITY' else raw_g[idx]
            if not messagebox.askyesno('Delete card', f"Delete {item.get('name','this card')}?", parent=win):
                return
            if kind == 'ABILITY': del raw_a[idx]
            else: del raw_g[idx]
            selected['kind']=None; selected['index']=None
            refresh_tree()
            status_var.set('Card deleted. Save to content file to persist changes.')

        def validate_card():
            kind = selected['kind']
            if kind is None:
                messagebox.showerror('No card selected', 'Select a card to validate.', parent=win)
                return
            if not read_effect_from_advanced():
                return
            actual_kind = 'gate' if kind == 'GATE' else 'ability'
            eff = normalise_custom_effect(current_effect['data'], timing_var.get())
            issues = validate_custom_effect(eff, actual_kind)
            lines = [custom_effect_preview(eff, desc_text.get('1.0', 'end').strip()), '', 'Structured JSON:', custom_effect_to_json(eff, timing_var.get()), '', 'Validation:']
            if issues:
                lines += [f'- {x}' for x in issues]
                status_var.set(f'Validation found {len(issues)} issue(s).')
            else:
                lines.append('- No validation issues detected.')
                status_var.set('Validation passed.')
            preview_text.delete('1.0', 'end')
            preview_text.insert('1.0', '\n'.join(lines))
            notebook.select(preview_tab)

        def update_card():
            kind = selected['kind']; idx = selected['index']
            if kind is None:
                messagebox.showerror('No card selected', 'Select a card to update.', parent=win)
                return
            if not read_effect_from_advanced():
                return
            item = raw_a[idx] if kind == 'ABILITY' else raw_g[idx]
            item['name'] = name_var.get().strip() or item.get('name','')
            item['description'] = desc_text.get('1.0','end').strip()
            try:
                item['price'] = int(price_var.get() or '0')
            except Exception:
                item['price'] = 0
            item['effect_id'] = effect_var.get().strip() or ('CUSTOM' if effect_mode_var.get().strip() == 'custom' else item.get('effect_id',''))
            item['effect_mode'] = effect_mode_var.get().strip() or ('custom' if item.get('effect_id') == 'CUSTOM' else 'builtin')
            item['custom_effect'] = deep_copy_effect(current_effect['data'])
            if kind == 'ABILITY':
                item['color'] = color_var.get().strip() or 'RED'
                item['timing'] = timing_var.get().strip() or 'DURING_BATTLE'
                item['custom_effect']['timing'] = item['timing']
            else:
                item['gate_type'] = gate_type_var.get().strip() or 'GOLD'
                item['bonuses'] = {attr.name: int(attr_vars[attr.name].get() or '0') for attr in Attribute}
                item['custom_effect']['timing'] = 'PASSIVE_GATE'
            refresh_tree()
            iid = f"{kind}:{idx}"
            if tree.exists(iid):
                tree.selection_set(iid)
                tree.focus(iid)
            status_var.set(f"Updated {kind} '{item.get('name', '')}' in editor. Save selected or Save all to persist.")
            refresh_preview(kind)
            notebook.select(preview_tab)

        def save_card():
            kind = selected['kind']; idx = selected['index']
            if kind is None:
                return
            if not read_effect_from_advanced():
                return
            item = raw_a[idx] if kind == 'ABILITY' else raw_g[idx]
            item['name'] = name_var.get().strip() or item.get('name','')
            item['description'] = desc_text.get('1.0','end').strip()
            item['price'] = int(price_var.get() or '0')
            item['effect_id'] = effect_var.get().strip() or 'CUSTOM'
            item['effect_mode'] = effect_mode_var.get().strip() or ('custom' if item['effect_id']=='CUSTOM' else 'builtin')
            item['custom_effect'] = deep_copy_effect(current_effect['data'])
            if kind == 'ABILITY':
                item['color'] = color_var.get().strip() or 'RED'
                item['timing'] = timing_var.get().strip() or 'DURING_BATTLE'
                item['custom_effect']['timing'] = item['timing']
            else:
                item['gate_type'] = gate_type_var.get().strip() or 'GOLD'
                item['bonuses'] = {attr.name: int(attr_vars[attr.name].get() or '0') for attr in Attribute}
                item['custom_effect']['timing'] = 'PASSIVE_GATE'
            self._save_raw_content_data(raw_b, raw_a, raw_g)
            self._refresh_content_from_file()
            raw_b[:], raw_a[:], raw_g[:] = self._load_raw_content_data()
            status_var.set(f"Saved {kind} '{item.get('name', '')}'")
            refresh_tree()
            iid = f"{kind}:{idx}"
            if tree.exists(iid):
                tree.selection_set(iid)
                tree.focus(iid)
                try:
                    tree.event_generate("<<TreeviewSelect>>")
                except Exception:
                    pass

        def save_all_changes():
            self._save_raw_content_data(raw_b, raw_a, raw_g)
            self._refresh_content_from_file()
            status_var.set('Saved content files.')

        ttk.Button(left_btns, text='New', command=build_new_card).pack(side='left', padx=2)
        ttk.Button(left_btns, text='Duplicate', command=duplicate_card).pack(side='left', padx=2)
        ttk.Button(left_btns, text='Delete', command=delete_card).pack(side='left', padx=2)
        ttk.Button(left_btns, text='Update card', command=update_card).pack(side='left', padx=(8,2))
        ttk.Button(left_btns, text='Validate card', command=validate_card).pack(side='left', padx=2)
        ttk.Button(left_btns, text='Save selected', command=save_card).pack(side='left', padx=(8,2))
        ttk.Button(left_btns, text='Save all', command=save_all_changes).pack(side='left', padx=2)

        ttk.Label(form, textvariable=status_var).grid(row=7, column=0, columnspan=2, sticky='w', pady=(8,0))

        def on_mode_change(*_):
            if effect_mode_var.get() == 'builtin':
                notebook.tab(0, state='hidden'); notebook.tab(1, state='hidden'); notebook.tab(2, state='hidden')
            else:
                notebook.tab(0, state='normal'); notebook.tab(1, state='normal'); notebook.tab(2, state='normal')
            refresh_preview(selected.get('kind') or type_var.get())

        def on_effect_id_change(*_):
            if effect_var.get().strip().upper() == 'CUSTOM' and effect_mode_var.get() != 'custom':
                effect_mode_var.set('custom')

        def on_timing_change(*_):
            current_effect['data']['timing'] = timing_var.get()
            sync_advanced()

        search_var.trace_add('write', refresh_tree)
        type_var.trace_add('write', lambda *_: (update_subtype_values(), refresh_tree()))
        subtype_var.trace_add('write', refresh_tree)
        preset_var.trace_add('write', apply_preset)
        effect_mode_var.trace_add('write', on_mode_change)
        effect_var.trace_add('write', on_effect_id_change)
        timing_var.trace_add('write', on_timing_change)
        tree.bind('<<TreeviewSelect>>', on_select)
        update_subtype_values()
        refresh_tree()
        on_mode_change()

    def open_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.geometry("520x420")
        outer = ttk.Frame(win, padding=10)
        outer.pack(fill="both", expand=True)

        toggles = ttk.LabelFrame(outer, text="General")
        toggles.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(toggles, text="Debug Mode", variable=self.debug_var).pack(anchor="w", padx=8, pady=(8, 4))
        ttk.Checkbutton(toggles, text="Text to IDE", variable=self.text_to_ide_var, command=self.on_output_toggle_changed).pack(anchor="w", padx=8, pady=4)
        ttk.Checkbutton(toggles, text="Create TXTs", variable=self.txt_exports_var, command=self.on_output_toggle_changed).pack(anchor="w", padx=8, pady=4)
        ttk.Checkbutton(toggles, text="Debug Text", variable=self.debug_console_var, command=self.on_output_toggle_changed).pack(anchor="w", padx=8, pady=4)
        ttk.Checkbutton(toggles, text="NPC market debug", variable=self.npc_market_debug_var).pack(anchor="w", padx=8, pady=(4, 8))

        actions = ttk.LabelFrame(outer, text="Tools")
        actions.pack(fill="both", expand=True)

        def add_button(row: int, col: int, label: str, command, enabled: bool = True):
            btn = ttk.Button(actions, text=label, command=command)
            btn.grid(row=row, column=col, padx=6, pady=6, sticky="ew")
            if not enabled:
                btn.configure(state="disabled")
            return btn

        for col in range(2):
            actions.columnconfigure(col, weight=1)

        debug_on = bool(self.debug_var.get())
        add_button(0, 0, "Changelog", self.view_changelog, True)
        add_button(0, 1, "Card Lab", self.open_card_lab, debug_on)
        add_button(1, 0, "Ban Settings", self.configure_season_bans, debug_on)
        add_button(1, 1, "World Cup Settings", self.configure_world_cup, debug_on)
        add_button(2, 0, "Export NPC Loadouts", self.export_npc_loadouts, True)
        add_button(2, 1, "Autosave Settings", self.configure_autosave_settings, True)
        add_button(3, 0, "Test Battle", self.open_debug_test_battle, debug_on)

        note = "Card Lab, Ban Settings, World Cup Settings, and Test Battle require Debug Mode." if not debug_on else ""
        if note:
            ttk.Label(outer, text=note, wraplength=480).pack(anchor="w", pady=(8, 0))

    def configure_autosave_settings(self) -> None:
        current = int(getattr(self, "autosave_interval_seasons", 5) or 5)
        value = simpledialog.askinteger(
            "Autosave Settings",
            "Force autosave every how many seasons?",
            parent=self.root,
            initialvalue=current,
            minvalue=1,
            maxvalue=999,
        )
        if value is None:
            return
        self.autosave_interval_seasons = max(1, int(value))
        self.db.set_world_int("autosave_interval_seasons", self.autosave_interval_seasons)
        self.append_text(f"Forced autosave interval set to every {self.autosave_interval_seasons} seasons.")

    def _debug_battle_profiles(self) -> List[PlayerProfile]:
        profiles = list(self.all_npcs())
        if self.player is not None:
            profiles = [p for p in profiles if p.name != self.player.name] + [self.player]
        return sorted(profiles, key=lambda p: (-p.glicko.rating, p.name.lower()))

    def open_debug_test_battle(self) -> None:
        if not bool(self.debug_var.get()):
            return
        profiles = self._debug_battle_profiles()
        if len(profiles) < 2:
            messagebox.showinfo("Test Battle", "Need at least two profiles to run a test battle.", parent=self.root)
            return

        by_name = {p.name: p for p in profiles}
        win = tk.Toplevel(self.root)
        win.title("Debug Test Battle")
        win.geometry("560x360")
        outer = ttk.Frame(win, padding=10)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)

        names = [p.name for p in profiles]
        p1_var = tk.StringVar(value=names[0])
        p2_var = tk.StringVar(value=names[1] if len(names) > 1 else names[0])
        seed_var = tk.StringVar(value=str(self.world_seed or self.rng.randint(1, 2_000_000_000)))
        log_var = tk.BooleanVar(value=True)

        ttk.Label(outer, text="Player 1").grid(row=0, column=0, sticky="w", pady=4)
        p1_box = ttk.Combobox(outer, textvariable=p1_var, values=names)
        p1_box.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(outer, text="Player 2").grid(row=1, column=0, sticky="w", pady=4)
        p2_box = ttk.Combobox(outer, textvariable=p2_var, values=names)
        p2_box.grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(outer, text="Seed").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=seed_var).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Checkbutton(outer, text="Write play-by-play file", variable=log_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 10))

        info = tk.Text(outer, width=60, height=10)
        info.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(4, 8))
        outer.rowconfigure(4, weight=1)

        def _filter_names(combo: ttk.Combobox, variable: tk.StringVar) -> None:
            query = variable.get().strip().lower()
            filtered = [name for name in names if query in name.lower()]
            combo["values"] = filtered or names

        def _resolve_profile(name: str) -> Optional[PlayerProfile]:
            exact = by_name.get(name)
            if exact is not None:
                return exact
            query = name.strip().lower()
            if not query:
                return None
            matches = [p for p in profiles if query in p.name.lower()]
            if len(matches) == 1:
                return matches[0]
            return None

        def refresh_preview(*_):
            p1 = _resolve_profile(p1_var.get())
            p2 = _resolve_profile(p2_var.get())
            lines = []
            for prof in (p1, p2):
                if prof is None:
                    continue
                prof.ensure_valid_loadout()
                bak = ", ".join(f"{b.name} ({b.attribute.value}, {b.base_g}G)" for b in prof.active_bakugan()) or "None"
                gates = ", ".join(f"{g.name} [{g.gate_type.value}]" for g in prof.active_gates()) or "None"
                abilities = ", ".join(f"{a.name} [{a.color.value}]" for a in prof.active_abilities()) or "None"
                lines.append(f"{prof.name} | Rating {prof.glicko.rating:.0f}")
                lines.append(f"Bakugan: {bak}")
                lines.append(f"Gates: {gates}")
                lines.append(f"Abilities: {abilities}")
                lines.append("")
            info.configure(state="normal")
            info.delete("1.0", "end")
            info.insert("1.0", "\n".join(lines).strip())

            info.configure(state="disabled")

        def _on_name_change(*_):
            _filter_names(p1_box, p1_var)
            _filter_names(p2_box, p2_var)
            refresh_preview()

        p1_var.trace_add("write", _on_name_change)
        p2_var.trace_add("write", _on_name_change)
        refresh_preview()

        def run_test_battle() -> None:
            p1 = _resolve_profile(p1_var.get().strip())
            p2 = _resolve_profile(p2_var.get().strip())
            if p1 is None or p2 is None or p1.name == p2.name:
                messagebox.showerror("Test Battle", "Choose two different valid players. You can type to narrow the list.", parent=win)
                return
            try:
                seed = int(seed_var.get().strip())
            except Exception:
                messagebox.showerror("Test Battle", "Seed must be a whole number.", parent=win)
                return
            forced_log = bool(log_var.get())
            previous_txt_setting = is_text_file_exports_enabled()
            try:
                if forced_log and not previous_txt_setting:
                    set_text_file_exports_enabled(True)
                winner, perf, _match, path = run_single_match(p1, p2, seed=seed, verbose=True, log_to_file=forced_log)
            finally:
                if forced_log and not previous_txt_setting:
                    set_text_file_exports_enabled(previous_txt_setting)
            lines = [
                f"Test battle: {p1.name} vs {p2.name}",
                f"Winner: {winner.name}",
                f"{p1.name}: perf {perf[p1.name]:.1f}",
                f"{p2.name}: perf {perf[p2.name]:.1f}",
            ]
            if forced_log:
                if path is not None:
                    lines.append(f"Saved play-by-play to {path}")
                else:
                    lines.append("Play-by-play file was requested but was not saved.")
            self.append_text("\n".join(lines))

            messagebox.showinfo("Test Battle", "\n".join(lines), parent=win)


        btns = ttk.Frame(outer)
        btns.grid(row=5, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="Run Test Battle", command=run_test_battle).pack(side="left", padx=4)
        ttk.Button(btns, text="Close", command=win.destroy).pack(side="left", padx=4)

    def _export_db_state(self) -> Dict[str, object]:
        profiles = [serialize_profile(p) for p in self.db.load_all_profiles()]
        world_rows = self.db.conn.execute("SELECT key, value FROM world_state").fetchall()
        archives = self.db.load_tournament_archives()
        return {
            "profiles": profiles,
            "world_state": {str(k): str(v) for k, v in world_rows},
            "tournament_archives": archives,
        }

    def _import_db_state(self, snapshot: Dict[str, object]) -> None:
        snap = snapshot if isinstance(snapshot, dict) else {}
        self.db.reset_world()
        profiles = snap.get("profiles", []) or []
        restored_profiles = []
        for item in profiles:
            try:
                restored_profiles.append(deserialize_profile(item))
            except Exception:
                continue
        if restored_profiles:
            self.db.save_profiles(restored_profiles)
        world_state = snap.get("world_state", {}) or {}
        if isinstance(world_state, dict):
            for key, value in world_state.items():
                self.db.conn.execute(
                    "REPLACE INTO world_state (key, value) VALUES (?, ?)",
                    (str(key), str(value)),
                )
        archives = snap.get("tournament_archives", []) or []
        for archive in archives:
            try:
                self.db.save_tournament_archive(archive)
            except Exception:
                pass
        self.db.conn.commit()

    def _build_save_payload(self) -> Dict:
        db_state = self._export_db_state()
        if self.player is None:
            payload = serialize_world_savegame(
                self.world_season,
                self.world_tournament_no,
                self.world_total_tournaments,
                self.world_seed,
            )
        else:
            payload = serialize_savegame(
                self.player,
                self.world_season,
                self.world_tournament_no,
                self.world_total_tournaments,
                self.world_seed,
            )
        payload["db_state"] = db_state
        return payload

    def view_changelog(self) -> None:
        win = tk.Toplevel(self.root)
        win.title(f"Changelog {CHANGELOG_VERSION}")
        win.geometry("900x700")
        top = ttk.Frame(win, padding=8)
        top.pack(fill="both", expand=True)
        ttk.Label(top, text=f"Bakugan Story Mode Changelog | Latest {CHANGELOG_VERSION} ({CHANGELOG_DATE})").pack(anchor="w", pady=(0, 8))
        text_widget = tk.Text(top, width=100, height=40, wrap="word")
        text_widget.pack(fill="both", expand=True)
        lines: List[str] = []
        for version, date_text, items in CHANGELOG_ENTRIES:
            lines.append(f"{version} | {date_text}")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")
        text_widget.insert("1.0", "\n".join(lines).strip())
        text_widget.configure(state="disabled")

    def update_debug_controls(self) -> None:
        debug_on = bool(self.debug_var.get())
        try:
            self.auto_season_button.configure(state="normal")
        except Exception:
            pass
        try:
            self.auto_seasons_x_button.configure(state="normal")
        except Exception:
            pass
        if not debug_on:
            self.npc_market_debug_var.set(False)

    def auto_rest_of_season(self) -> None:
        if self.player is not None:
            if not profile_active_loadout_is_legal_exact(self.player):
                messagebox.showerror("Illegal loadout", "Your active loadout is not legal. Change your loadout before using Auto Rest of Season.", parent=self.root)
                return
            if profile_uses_banned_active(self.player, self.current_season_bans):
                messagebox.showerror("Banned loadout", "Your active loadout contains season-banned items. Change your loadout before using Auto Rest of Season.", parent=self.root)
                return
        debug_on = bool(self.debug_var.get())
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        output_ctx = contextlib.nullcontext() if debug_on or not is_text_output_to_ide_enabled() else contextlib.ExitStack()
        if (not debug_on) and is_text_output_to_ide_enabled():
            output_ctx.enter_context(contextlib.redirect_stdout(stdout_buffer))
            output_ctx.enter_context(contextlib.redirect_stderr(stderr_buffer))
        with output_ctx:
            start_season = self.world_season
            while self.world_season == start_season:
                before_total = self.world_total_tournaments
                before_event = self.world_tournament_no
                before_season = self.world_season
                self.start_tournament(force_manual=False)
                self.root.update_idletasks()
                if self.world_total_tournaments == before_total and self.world_tournament_no == before_event and self.world_season == before_season:
                    break

    def auto_rest_x_seasons(self) -> None:
        count = simpledialog.askinteger("Auto Rest x Seasons", "How many seasons should be simulated?", parent=self.root, minvalue=1, maxvalue=250)
        if not count:
            return
        target_season = self.world_season + int(count)
        while self.world_season < target_season:
            before = (self.world_season, self.world_tournament_no, self.world_total_tournaments)
            self.auto_rest_of_season()
            after = (self.world_season, self.world_tournament_no, self.world_total_tournaments)
            if after == before:
                break

    def append_text(self, text: str) -> None:
        if not is_text_output_to_ide_enabled():
            return
        self.text.insert("end", text + "\n")
        self.text.see("end")

    def debug_append(self, text: str) -> None:
        if bool(self.debug_var.get()) and bool(self.npc_market_debug_var.get()):
            self.append_text(text)

    def on_output_toggle_changed(self) -> None:
        enabled_ide = bool(self.text_to_ide_var.get())
        enabled_txt = bool(self.txt_exports_var.get())
        enabled_console = bool(self.debug_console_var.get())
        set_text_output_to_ide_enabled(enabled_ide)
        set_text_file_exports_enabled(enabled_txt)
        set_debug_console_text_enabled(enabled_console)
        try:
            self.db.set_world_int("text_to_ide_enabled", 1 if enabled_ide else 0)
            self.db.set_world_int("txt_exports_enabled", 1 if enabled_txt else 0)
            self.db.set_world_int("debug_console_enabled", 1 if enabled_console else 0)
        except Exception:
            pass

    def require_player(self) -> bool:
        if self.player is None:
            messagebox.showerror("No character", "Create a character first.", parent=self.root)
            return False
        return True


    def refresh_status(self) -> None:
        try:
            self.update_player_button_visibility()
        except Exception:
            pass
        champion_name = "None"
        if isinstance(self.current_world_champion, dict):
            champion_name = str(self.current_world_champion.get("name") or "None")
        if not self.player:
            bans_label = self.current_ban_summary()
            self.status_var.set(
                f"No active player character | World season {self.world_season}, event {self.world_tournament_no}, total events {self.world_total_tournaments}, NPCs {len(self.db.load_all_profiles())} | World Cup every {self.world_cup_interval} seasons | World Champion {champion_name} | {bans_label}"
            )
            return
        self.player.update_career_stage()
        champ_tag = " | World Champion" if self.is_world_champion(self.player) else ""
        age_tag = f" | Age {profile_age(self.player)}" if getattr(self, "age_progression_enabled", False) else ""
        league_name = self.league_band_label_for_rating(self.player.glicko.rating)
        self.status_var.set(
            f"{self.player.name}{champ_tag}{age_tag} | {self.player.chosen_attribute.value} | £{self.player.money} | "
            f"Rating {self.player.glicko.rating:.0f} | League {league_name} | Stage {self.display_title(self.player)} | "
            f"Titles {self.player.tournament_titles} | Podiums {self.player.podiums} | "
            f"Entered {self.player.tournaments_entered} | Season {self.world_season} Event {self.world_tournament_no} | Total Events {self.world_total_tournaments} | "
            f"World Cup every {self.world_cup_interval} seasons | World Champion {champion_name} | {self.current_ban_summary()}"
        )

    def _binder_state(self) -> Dict[str, List[Dict[str, object]]]:
        if self.player is None:
            return {"bakugan": [], "gates": [], "abilities": []}
        flags = self.player.story_flags if isinstance(self.player.story_flags, dict) else {}
        if not isinstance(flags, dict):
            flags = {}
            self.player.story_flags = flags
        binder = flags.get("binder")
        if not isinstance(binder, dict):
            binder = {}
            flags["binder"] = binder
        for key in ("bakugan", "gates", "abilities"):
            value = binder.get(key)
            if not isinstance(value, list):
                binder[key] = []
        return binder

    def _binder_key_bakugan(self, bakugan: Bakugan) -> str:
        return f"{bakugan.name}::{bakugan.attribute.value}"

    def _binder_key_gate(self, gate: GateCard) -> str:
        return f"{gate.name}::{gate.gate_type.value}"

    def _binder_key_ability(self, ability: AbilityCard) -> str:
        return f"{ability.name}::{ability.color.value}::{ability.timing.name}"

    def _binder_entry_key(self, kind: str, entry: Dict[str, object]) -> str:
        kind = kind.lower()
        if kind == "bakugan":
            return f"{entry.get('name', '')}::{entry.get('attribute', '')}"
        if kind == "gates":
            return f"{entry.get('name', '')}::{entry.get('gate_type', '')}"
        return f"{entry.get('name', '')}::{entry.get('color', '')}::{entry.get('timing', '')}"

    def _binder_total_keys(self) -> Dict[str, Set[str]]:
        bakugan_keys: Set[str] = set()
        for template in self.templates:
            for attr in template.allowed_attributes:
                bakugan_keys.add(f"{template.name}::{attr.value}")
        gate_keys = {f"{g.name}::{g.gate_type.value}" for g in self.gates}
        ability_keys = {f"{a.name}::{a.color.value}::{a.timing.name}" for a in self.abilities}
        return {"bakugan": bakugan_keys, "gates": gate_keys, "abilities": ability_keys}

    def _binder_progress(self) -> Dict[str, Tuple[int, int]]:
        binder = self._binder_state()
        totals = self._binder_total_keys()
        progress: Dict[str, Tuple[int, int]] = {}
        for kind in ("bakugan", "gates", "abilities"):
            owned = {self._binder_entry_key(kind, entry) for entry in binder.get(kind, []) if isinstance(entry, dict)}
            total = len(totals[kind])
            progress[kind] = (len(owned & totals[kind]), total)
        return progress

    def _binder_summary_lines(self) -> List[str]:
        progress = self._binder_progress()
        baku_have, baku_total = progress["bakugan"]
        gate_have, gate_total = progress["gates"]
        ability_have, ability_total = progress["abilities"]
        card_have = gate_have + ability_have
        card_total = gate_total + ability_total
        overall_have = baku_have + card_have
        overall_total = baku_total + card_total
        return [
            f"Bakugan: {baku_have}/{baku_total} added | {max(0, baku_total - baku_have)} left",
            f"Cards: {card_have}/{card_total} added | {max(0, card_total - card_have)} left",
            f"  Gate Cards: {gate_have}/{gate_total}",
            f"  Ability Cards: {ability_have}/{ability_total}",
            f"Overall: {overall_have}/{overall_total} added | {max(0, overall_total - overall_have)} left",
        ]

    def _can_remove_collection_item(self, kind: str) -> Tuple[bool, str]:
        if self.player is None:
            return False, "No player loaded."
        if kind == "bakugan" and len(self.player.collection_bakugan) <= 3:
            return False, "You need at least 3 Bakugan in your collection to keep a legal loadout."
        if kind == "gates" and len(self.player.collection_gates) <= 3:
            return False, "You need at least 3 Gate Cards in your collection to keep a legal loadout."
        if kind == "abilities" and len(self.player.collection_abilities) <= 3:
            return False, "You need at least 3 Ability Cards in your collection to keep a legal loadout."
        return True, ""

    def _remove_collection_index(self, kind: str, idx: int) -> None:
        if self.player is None:
            return
        if kind == "bakugan":
            self.player.collection_bakugan.pop(idx)
            self.player.active_bakugan_idx = [i - 1 if i > idx else i for i in self.player.active_bakugan_idx if i != idx]
        elif kind == "gates":
            self.player.collection_gates.pop(idx)
            self.player.active_gate_idx = [i - 1 if i > idx else i for i in self.player.active_gate_idx if i != idx]
        else:
            self.player.collection_abilities.pop(idx)
            self.player.active_ability_idx = [i - 1 if i > idx else i for i in self.player.active_ability_idx if i != idx]
        self.player.ensure_valid_loadout()

    def _sell_value(self, item) -> int:
        base = max(0, int(getattr(item, "price", 0) or 0))
        if base <= 0:
            return 5
        return max(5, int(round((base * 0.2) / 5.0) * 5))

    def open_binder(self) -> None:
        if not self.require_player():
            return

        win = tk.Toplevel(self.root)
        win.title("Binder")
        win.geometry("1280x760")
        win.transient(self.root)

        summary_var = tk.StringVar(value="")
        ttk.Label(win, textvariable=summary_var, justify="left").pack(anchor="w", padx=10, pady=(10, 6))

        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        tabs = {
            "bakugan": ttk.Frame(notebook),
            "gates": ttk.Frame(notebook),
            "abilities": ttk.Frame(notebook),
        }
        notebook.add(tabs["bakugan"], text="Bakugan")
        notebook.add(tabs["gates"], text="Gate Cards")
        notebook.add(tabs["abilities"], text="Ability Cards")

        ui_state: Dict[str, Dict[str, object]] = {}

        def collection_rows(kind: str) -> List[Tuple[int, str]]:
            rows: List[Tuple[int, str]] = []
            if kind == "bakugan":
                for idx, b in enumerate(self.player.collection_bakugan):
                    rows.append((idx, f"[{idx}] {b.name} | {b.attribute.value} | {b.base_g} G | Sell £{self._sell_value(b)}"))
            elif kind == "gates":
                for idx, g in enumerate(self.player.collection_gates):
                    rows.append((idx, f"[{idx}] {g.name} | {g.gate_type.value} | Sell £{self._sell_value(g)}"))
            else:
                for idx, a in enumerate(self.player.collection_abilities):
                    rows.append((idx, f"[{idx}] {a.name} | {a.color.value} | {a.timing.name} | Sell £{self._sell_value(a)}"))
            return rows

        def binder_rows(kind: str) -> List[str]:
            binder = self._binder_state()
            lines: List[str] = []
            entries = sorted((x for x in binder.get(kind, []) if isinstance(x, dict)), key=lambda d: (str(d.get("name", "")), str(d.get("attribute", d.get("gate_type", d.get("color", ""))))))
            for entry in entries:
                if kind == "bakugan":
                    lines.append(f"{entry.get('name', '')} | {entry.get('attribute', '')} | {entry.get('base_g', 0)} G")
                elif kind == "gates":
                    lines.append(f"{entry.get('name', '')} | {entry.get('gate_type', '')}")
                else:
                    lines.append(f"{entry.get('name', '')} | {entry.get('color', '')} | {entry.get('timing', '')}")
            return lines

        def selected_collection(kind: str):
            lb = ui_state[kind]["collection_listbox"]
            rows = ui_state[kind]["collection_rows"]
            selection = lb.curselection()
            if not selection:
                return None, None
            pos = int(selection[0])
            if pos < 0 or pos >= len(rows):
                return None, None
            return rows[pos]

        def refresh_all() -> None:
            summary_var.set("\n".join(self._binder_summary_lines()))
            for kind in ("bakugan", "gates", "abilities"):
                rows = collection_rows(kind)
                ui_state[kind]["collection_rows"] = rows
                lb = ui_state[kind]["collection_listbox"]
                lb.delete(0, "end")
                for _, label in rows:
                    lb.insert("end", label)
                bb = ui_state[kind]["binder_listbox"]
                bb.delete(0, "end")
                binder_items = binder_rows(kind)
                if binder_items:
                    for line in binder_items:
                        bb.insert("end", line)
                else:
                    bb.insert("end", "Nothing added yet.")
                count_label = ui_state[kind]["count_var"]
                count_label.set(f"Collection {len(rows)} | Binder {max(0, len(binder_items))}")

        def donate_selected(kind: str) -> None:
            can_remove, msg = self._can_remove_collection_item(kind)
            if not can_remove:
                messagebox.showerror("Cannot send to binder", msg, parent=win)
                return
            idx, _label = selected_collection(kind)
            if idx is None:
                messagebox.showerror("No selection", "Select an item from your collection first.", parent=win)
                return
            binder = self._binder_state()
            if kind == "bakugan":
                item = self.player.collection_bakugan[idx]
                key = self._binder_key_bakugan(item)
                existing = {self._binder_entry_key(kind, entry) for entry in binder[kind] if isinstance(entry, dict)}
                if key in existing:
                    messagebox.showerror("Already in binder", "That Bakugan attribute variant is already in the Binder.", parent=win)
                    return
                confirm_msg = f"Send {item.name} {item.attribute.value} to the Binder?\n\nThis is permanent and you will not be able to take it back out."
                if not messagebox.askyesno("Send to Binder", confirm_msg, parent=win):
                    return
                binder[kind].append({"name": item.name, "attribute": item.attribute.value, "base_g": item.base_g, "price": item.price})
                self._remove_collection_index(kind, idx)
                self.append_text(f"Sent Bakugan to Binder: {item.name} {item.attribute.value} {item.base_g} G")
            elif kind == "gates":
                item = self.player.collection_gates[idx]
                key = self._binder_key_gate(item)
                existing = {self._binder_entry_key(kind, entry) for entry in binder[kind] if isinstance(entry, dict)}
                if key in existing:
                    messagebox.showerror("Already in binder", "That Gate Card is already in the Binder.", parent=win)
                    return
                confirm_msg = f"Send Gate Card '{item.name}' ({item.gate_type.value}) to the Binder?\n\nThis is permanent and you will not be able to take it back out."
                if not messagebox.askyesno("Send to Binder", confirm_msg, parent=win):
                    return
                binder[kind].append({"name": item.name, "gate_type": item.gate_type.value, "description": item.description, "price": item.price})
                self._remove_collection_index(kind, idx)
                self.append_text(f"Sent Gate Card to Binder: {item.name} {item.gate_type.value}")
            else:
                item = self.player.collection_abilities[idx]
                key = self._binder_key_ability(item)
                existing = {self._binder_entry_key(kind, entry) for entry in binder[kind] if isinstance(entry, dict)}
                if key in existing:
                    messagebox.showerror("Already in binder", "That Ability Card is already in the Binder.", parent=win)
                    return
                confirm_msg = f"Send Ability Card '{item.name}' ({item.color.value}, {item.timing.name}) to the Binder?\n\nThis is permanent and you will not be able to take it back out."
                if not messagebox.askyesno("Send to Binder", confirm_msg, parent=win):
                    return
                binder[kind].append({"name": item.name, "color": item.color.value, "timing": item.timing.name, "description": item.description, "price": item.price})
                self._remove_collection_index(kind, idx)
                self.append_text(f"Sent Ability Card to Binder: {item.name} {item.color.value}")
            self.refresh_status()
            self.autosave_current_game()
            refresh_all()

        def sell_selected(kind: str) -> None:
            can_remove, msg = self._can_remove_collection_item(kind)
            if not can_remove:
                messagebox.showerror("Cannot sell", msg, parent=win)
                return
            idx, _label = selected_collection(kind)
            if idx is None:
                messagebox.showerror("No selection", "Select an item from your collection first.", parent=win)
                return
            if kind == "bakugan":
                item = self.player.collection_bakugan[idx]
                value = self._sell_value(item)
                desc = f"{item.name} {item.attribute.value} {item.base_g} G"
            elif kind == "gates":
                item = self.player.collection_gates[idx]
                value = self._sell_value(item)
                desc = f"{item.name} {item.gate_type.value}"
            else:
                item = self.player.collection_abilities[idx]
                value = self._sell_value(item)
                desc = f"{item.name} {item.color.value}"
            if not messagebox.askyesno("Sell item", f"Sell {desc} for £{value}?\nThis cannot be undone.", parent=win):
                return
            self._remove_collection_index(kind, idx)
            self.player.money += value
            self.append_text(f"Sold {desc} for £{value}")
            self.refresh_status()
            self.autosave_current_game()
            refresh_all()

        for kind, frame in tabs.items():
            frame.columnconfigure(0, weight=1)
            frame.columnconfigure(1, weight=0)
            frame.columnconfigure(2, weight=1)
            frame.rowconfigure(1, weight=1)
            title = "Bakugan" if kind == "bakugan" else "Gate Cards" if kind == "gates" else "Ability Cards"
            ttk.Label(frame, text=f"Collection {title}").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
            ttk.Label(frame, text=f"Binder {title}").grid(row=0, column=2, sticky="w", padx=8, pady=(8, 4))
            count_var = tk.StringVar(value="")
            ttk.Label(frame, textvariable=count_var).grid(row=0, column=1, sticky="n", padx=8, pady=(8, 4))
            collection_listbox = tk.Listbox(frame, exportselection=False)
            collection_listbox.grid(row=1, column=0, sticky="nsew", padx=(8, 6), pady=(0, 8))
            binder_listbox = tk.Listbox(frame, exportselection=False)
            binder_listbox.grid(row=1, column=2, sticky="nsew", padx=(6, 8), pady=(0, 8))
            btns = ttk.Frame(frame)
            btns.grid(row=1, column=1, sticky="ns", padx=6, pady=8)
            ttk.Button(btns, text="Send to Binder", command=lambda k=kind: donate_selected(k)).pack(fill="x", pady=(0, 8))
            ttk.Button(btns, text="Sell Cheap", command=lambda k=kind: sell_selected(k)).pack(fill="x")
            ttk.Label(btns, text="Binder items are permanent\nand cannot be taken back.", justify="center").pack(pady=(12, 0))
            ui_state[kind] = {
                "collection_listbox": collection_listbox,
                "binder_listbox": binder_listbox,
                "collection_rows": [],
                "count_var": count_var,
            }

        refresh_all()

    def current_ban_summary(self) -> str:
        bans = self.current_season_bans if isinstance(getattr(self, "current_season_bans", None), dict) else empty_season_ban_state(self.world_season)
        if not bool(getattr(self, "season_ban_settings", {}).get("enabled")):
            return "Season bans Off"
        b = len(bans.get("bakugan", []))
        g = len(bans.get("gates", []))
        a = len(bans.get("abilities", []))
        return f"Season bans On ({b} Bakugan, {g} Gate, {a} Ability)"

    def view_season_rules(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Season Rules")
        win.geometry("560x420")
        text_widget = tk.Text(win, width=72, height=24, wrap="word")
        text_widget.pack(fill="both", expand=True)
        settings = self.season_ban_settings if isinstance(self.season_ban_settings, dict) else dict(SEASON_BAN_DEFAULTS)
        bans = self.current_season_bans if isinstance(self.current_season_bans, dict) else empty_season_ban_state(self.world_season)
        lines = ["========== SEASON RULES =========="]
        lines.append(f"Season {self.world_season}")
        if settings.get("enabled"):
            lines.append("Seasonal bans: On")
            source = bans.get("source_season", max(0, self.world_season - 1))
            lines.append(f"Based on usage from Season {source}")
            lines.append("")
            lines.append("Banned Bakugan:")
            for name in (bans.get("bakugan", []) or ["None"]):
                lines.append(f"  - {name}")
            lines.append("")
            lines.append("Banned Gate:")
            for name in (bans.get("gates", []) or ["None"]):
                lines.append(f"  - {name}")
            lines.append("")
            lines.append("Banned Ability:")
            for name in (bans.get("abilities", []) or ["None"]):
                lines.append(f"  - {name}")
            lines.append("")
            lines.append("World Cup ignores seasonal bans.")
        else:
            lines.append("Seasonal bans: Off")
        text_widget.insert("1.0", "\n".join(lines))
        text_widget.configure(state="disabled")

    def configure_season_bans(self) -> None:
        current = self.season_ban_settings if isinstance(self.season_ban_settings, dict) else dict(SEASON_BAN_DEFAULTS)
        win = tk.Toplevel(self.root)
        win.title("Ban Settings")
        win.transient(self.root)
        win.grab_set()
        enabled_var = tk.BooleanVar(value=bool(current.get('enabled')))
        baku_var = tk.StringVar(value=str(int(current.get('bakugan_count', 2))))
        gate_var = tk.StringVar(value=str(int(current.get('gate_count', 1))))
        ability_var = tk.StringVar(value=str(int(current.get('ability_count', 1))))
        ttk.Checkbutton(win, text='Enable seasonal ban list', variable=enabled_var).grid(row=0, column=0, columnspan=2, padx=8, pady=8, sticky='w')
        ttk.Label(win, text='Bakugan banned each season').grid(row=1, column=0, padx=8, pady=4, sticky='w')
        ttk.Entry(win, textvariable=baku_var, width=10).grid(row=1, column=1, padx=8, pady=4, sticky='w')
        ttk.Label(win, text='Gate cards banned each season').grid(row=2, column=0, padx=8, pady=4, sticky='w')
        ttk.Entry(win, textvariable=gate_var, width=10).grid(row=2, column=1, padx=8, pady=4, sticky='w')
        ttk.Label(win, text='Ability cards banned each season').grid(row=3, column=0, padx=8, pady=4, sticky='w')
        ttk.Entry(win, textvariable=ability_var, width=10).grid(row=3, column=1, padx=8, pady=4, sticky='w')
        def save_settings() -> None:
            try:
                settings = {
                    'enabled': bool(enabled_var.get()),
                    'bakugan_count': max(0, int(baku_var.get().strip() or '0')),
                    'gate_count': max(0, int(gate_var.get().strip() or '0')),
                    'ability_count': max(0, int(ability_var.get().strip() or '0')),
                }
            except Exception:
                messagebox.showerror('Invalid values', 'Enter whole numbers for ban counts.', parent=win)
                return
            self.season_ban_settings = settings
            self.db.set_world_json('season_ban_settings', settings)
            if not settings.get('enabled'):
                self.current_season_bans = empty_season_ban_state(self.world_season)
                self.db.set_world_json('current_season_bans', self.current_season_bans)
            self.update_debug_controls()
            self.refresh_status()
            self.append_text(f"Seasonal bans {'enabled' if settings.get('enabled') else 'disabled'}. Counts: {settings['bakugan_count']} Bakugan, {settings['gate_count']} Gate, {settings['ability_count']} Ability.")
            win.destroy()
        def regenerate() -> None:
            self.generate_season_bans(self.world_season, max(0, self.world_season - 1))
            self.apply_season_bans_worldwide()
            self.refresh_status()
            self.append_text(f"Regenerated Season {self.world_season} bans.")
        ttk.Button(win, text='Save', command=save_settings).grid(row=4, column=0, padx=8, pady=8, sticky='w')
        ttk.Button(win, text='Regenerate Current Season', command=regenerate).grid(row=4, column=1, padx=8, pady=8, sticky='e')


    def _weighted_ban_pick(self, usage: Dict[str, float], universe: List[str], count: int, rng: random.Random) -> List[str]:
        count = max(0, min(int(count), len(set(universe))))
        if count <= 0:
            return []
        selected: List[str] = []
        remaining = list(dict.fromkeys(universe))
        while remaining and len(selected) < count:
            weights = []
            for name in remaining:
                use = float(usage.get(name, 0.0))
                weights.append(max(0.1, 1.0 + use * use * 6.0 + use * 12.0))
            total = sum(weights)
            pick = rng.random() * total
            run = 0.0
            chosen = remaining[-1]
            for name, w in zip(remaining, weights):
                run += w
                if run >= pick:
                    chosen = name
                    break
            selected.append(chosen)
            remaining.remove(chosen)
        return selected


    def collect_season_usage_rates(self, source_season: int) -> Dict[str, Dict[str, float]]:
        archives = [arc for arc in self.db.load_tournament_archives() if int(arc.get('season', 0)) == int(source_season) and int(arc.get('event_no', 0)) != 0]
        baku_counts: Dict[str, int] = defaultdict(int)
        gate_counts: Dict[str, int] = defaultdict(int)
        ability_counts: Dict[str, int] = defaultdict(int)
        deck_count = 0
        for arc in archives:
            for entrant in arc.get('entrants', []):
                cb = entrant.get('collection_bakugan', [])
                cg = entrant.get('collection_gates', [])
                ca = entrant.get('collection_abilities', [])
                for idx in entrant.get('active_bakugan_idx', [])[:3]:
                    if 0 <= idx < len(cb):
                        baku_counts[season_bakugan_key(cb[idx].get('name', ''))] += 1
                for idx in entrant.get('active_gate_idx', [])[:3]:
                    if 0 <= idx < len(cg):
                        gate_counts[season_card_key(cg[idx].get('name', ''))] += 1
                for idx in entrant.get('active_ability_idx', [])[:3]:
                    if 0 <= idx < len(ca):
                        ability_counts[season_card_key(ca[idx].get('name', ''))] += 1
                deck_count += 1
        if deck_count <= 0:
            deck_count = 1
        return {
            'bakugan': {k: v / deck_count for k, v in baku_counts.items()},
            'gates': {k: v / deck_count for k, v in gate_counts.items()},
            'abilities': {k: v / deck_count for k, v in ability_counts.items()},
        }


    def generate_season_bans(self, season_no: int, source_season: int) -> Dict[str, object]:
        settings = self.season_ban_settings if isinstance(self.season_ban_settings, dict) else dict(SEASON_BAN_DEFAULTS)
        if not settings.get('enabled'):
            self.current_season_bans = empty_season_ban_state(season_no)
            self.db.set_world_json('current_season_bans', self.current_season_bans)
            return self.current_season_bans
        usage = self.collect_season_usage_rates(source_season) if source_season > 0 else {'bakugan': {}, 'gates': {}, 'abilities': {}}
        baku_name_map = {}
        for t in self.templates:
            baku_name_map.setdefault(season_bakugan_key(t.name), t.name)
        gate_name_map = {}
        for g in self.gates:
            gate_name_map.setdefault(season_card_key(g.name), g.name)
        ability_name_map = {}
        for a in self.abilities:
            ability_name_map.setdefault(season_card_key(a.name), a.name)
        rng = random.Random(self.world_seed + season_no * 92821 + source_season * 131)
        banned_b_keys = self._weighted_ban_pick(usage.get('bakugan', {}), list(baku_name_map.keys()), int(settings.get('bakugan_count', 2)), rng)
        banned_g_keys = self._weighted_ban_pick(usage.get('gates', {}), list(gate_name_map.keys()), int(settings.get('gate_count', 1)), rng)
        banned_a_keys = self._weighted_ban_pick(usage.get('abilities', {}), list(ability_name_map.keys()), int(settings.get('ability_count', 1)), rng)
        bans = {
            'season': int(season_no),
            'enabled': True,
            'source_season': int(source_season),
            'bakugan': [baku_name_map[k] for k in banned_b_keys],
            'gates': [gate_name_map[k] for k in banned_g_keys],
            'abilities': [ability_name_map[k] for k in banned_a_keys],
        }
        self.current_season_bans = bans
        hist = self.season_ban_history if isinstance(self.season_ban_history, list) else []
        hist = [x for x in hist if int(x.get('season', -1)) != int(season_no)]
        hist.append(dict(bans))
        hist.sort(key=lambda x: int(x.get('season', 0)))
        self.season_ban_history = hist
        self.db.set_world_json('current_season_bans', bans)
        self.db.set_world_json('season_ban_history', hist)
        return bans


    def apply_season_bans_worldwide(self) -> None:
        npcs = self.all_npcs()
        for npc in npcs:
            optimise_profile_loadout_with_bans(npc, self.current_season_bans)
            npc.ensure_valid_loadout()
        self.save_npcs(npcs)


    def configure_world_cup(self) -> None:
        current = max(1, int(getattr(self, "world_cup_interval", WORLD_CUP_INTERVAL_DEFAULT)))
        value = simpledialog.askinteger(
            "World Cup Settings",
            "Run a World Cup every how many seasons?",
            parent=self.root,
            minvalue=1,
            initialvalue=current,
        )
        if value is None:
            return
        self.world_cup_interval = max(1, int(value))
        self.db.set_world_int("world_cup_interval", self.world_cup_interval)
        self.db.set_world_int("world_cup_new_npcs", self.world_cup_new_npcs)
        self.append_text(f"World Cup interval set to every {self.world_cup_interval} seasons.")
        self.refresh_status()
        self.update_debug_controls()


    def display_title(self, profile: Optional[PlayerProfile]) -> str:
        if profile is None:
            return "N/A"
        return "World Champion" if self.is_world_champion(profile) else profile.career_stage


    def is_world_champion(self, profile: Optional[PlayerProfile]) -> bool:
        if profile is None:
            return False
        flags = profile.story_flags if isinstance(profile.story_flags, dict) else {}
        return bool(flags.get("world_champion", 0))


    def get_ranked_profiles(self) -> List[PlayerProfile]:
        entrants = [p for p in self.all_npcs() if not profile_is_retired(p)]
        if self.player is not None:
            entrants = [p for p in entrants if p.name != self.player.name]
            entrants.append(self.player)
        return sorted(entrants, key=lambda p: (p.glicko.rating, p.tournament_titles, p.fame), reverse=True)


    def get_world_champion_history_for_profile(self, profile: Optional[PlayerProfile]) -> List[int]:
        if profile is None or not isinstance(profile.story_flags, dict):
            return []
        raw = profile.story_flags.get("world_champion_history", [])
        if not isinstance(raw, list):
            return []
        out: List[int] = []
        for item in raw:
            try:
                out.append(int(item))
            except Exception:
                pass
        return sorted(set(out))


    def _record_world_champion_history(self, winner: Optional[PlayerProfile], winner_name: str, season_no: int, previous_champion: Optional[str]) -> None:
        if winner is not None:
            if not isinstance(winner.story_flags, dict):
                winner.story_flags = {}
            hist = winner.story_flags.get("world_champion_history", [])
            if not isinstance(hist, list):
                hist = []
            if int(season_no) not in [int(x) for x in hist if isinstance(x, (int, float, str))]:
                hist.append(int(season_no))
            winner.story_flags["world_champion_history"] = sorted({int(x) for x in hist if str(x).strip()})
        history = self.world_champion_history if isinstance(self.world_champion_history, list) else []
        history.append({
            "season": int(season_no),
            "winner": winner_name,
            "previous_champion": previous_champion,
            "retained": bool(previous_champion and previous_champion == winner_name),
        })
        self.world_champion_history = history
        self.db.set_world_json("world_champion_history", self.world_champion_history)


    def _clear_world_champion_flags(self, profiles: List[PlayerProfile]) -> None:
        for prof in profiles:
            if not isinstance(prof.story_flags, dict):
                prof.story_flags = {}
            prof.story_flags["world_champion"] = 0


    def apply_world_champion_season_bonus(self, season_no: int) -> None:
        champion_name = None
        if isinstance(self.current_world_champion, dict):
            champion_name = self.current_world_champion.get("name")
        if not champion_name:
            return
        champion = None
        if self.player is not None and self.player.name == champion_name:
            champion = self.player
        if champion is None:
            for npc in self.all_npcs():
                if npc.name == champion_name:
                    champion = npc
                    break
        if champion is None:
            return
        if not isinstance(champion.story_flags, dict):
            champion.story_flags = {}
        last_bonus_season = int(champion.story_flags.get("world_champion_bonus_season", 0))
        if last_bonus_season >= int(season_no):
            return
        champion.training_points += WORLD_CUP_CHAMPION_SEASONAL_TRAINING
        champion.story_flags["world_champion_bonus_season"] = int(season_no)
        self.append_text(f"World Champion bonus: {champion.name} gains +{WORLD_CUP_CHAMPION_SEASONAL_TRAINING} training point for Season {season_no}.")
        if champion is self.player:
            self.save_player()
        else:
            npc_map = {p.name: p for p in self.all_npcs()}
            npc_map[champion.name] = champion
            self.save_npcs(list(npc_map.values()))


    def _world_cup_head_to_head_points(self, tied_names: set[str], records: List[Dict[str, object]]) -> Dict[str, int]:
        values = {name: 0 for name in tied_names}
        for rec in records:
            p1 = str(rec.get("player1", ""))
            p2 = str(rec.get("player2", ""))
            winner = str(rec.get("winner", ""))
            if p1 not in tied_names or p2 not in tied_names:
                continue
            if winner in values:
                values[winner] += WORLD_CUP_WIN_POINTS
        return values


    def _build_world_cup_standings(self, entrants: List[PlayerProfile], table: Dict[str, Dict[str, float]], records: List[Dict[str, object]]) -> List[PlayerProfile]:
        groups: Dict[int, List[PlayerProfile]] = {}
        for prof in entrants:
            pts = int(table[prof.name].get("points", 0))
            groups.setdefault(pts, []).append(prof)

        ordered: List[PlayerProfile] = []
        for pts in sorted(groups.keys(), reverse=True):
            tied_group = groups[pts]
            if len(tied_group) == 1:
                ordered.extend(tied_group)
                continue
            tied_names = {p.name for p in tied_group}
            h2h_points = self._world_cup_head_to_head_points(tied_names, records)
            ordered.extend(sorted(
                tied_group,
                key=lambda p: (
                    h2h_points.get(p.name, 0),
                    table[p.name]["gate_diff"],
                    (table[p.name]["perf_total"] / max(1.0, table[p.name]["matches"])),
                    p.glicko.rating,
                    p.name.lower(),
                ),
                reverse=True,
            ))
        return ordered


    def _apply_world_champion_title(self, winner_name: str, season_no: int, previous_champion: Optional[str] = None) -> None:
        all_npcs = self.all_npcs()
        npc_map = {p.name: p for p in all_npcs}
        everyone = all_npcs[:] + ([self.player] if self.player is not None else [])
        self._clear_world_champion_flags(everyone)
        winner = npc_map.get(winner_name)
        if self.player is not None and self.player.name == winner_name:
            winner = self.player
        if winner is not None:
            if not isinstance(winner.story_flags, dict):
                winner.story_flags = {}
            winner.story_flags["world_champion"] = 1
            winner.story_flags["world_champion_season"] = int(season_no)
            winner.story_flags["world_champion_bonus_season"] = int(season_no)
            winner.fame += WORLD_CUP_CHAMPION_FAME
            winner.sponsorship += WORLD_CUP_CHAMPION_SPONSORSHIP
            winner.money += WORLD_CUP_CHAMPION_CASH
            winner.career_earnings += WORLD_CUP_CHAMPION_CASH
        self._record_world_champion_history(winner, winner_name, season_no, previous_champion)
        self.current_world_champion = {"name": winner_name, "season": int(season_no)}
        self.db.set_world_json("current_world_champion", self.current_world_champion)
        if self.player is not None and self.player.name == winner_name:
            self.save_player()
        self.save_npcs(list(npc_map.values()))


    def _append_world_cup_report_to_text(self, season_no: int, entrants: List[PlayerProfile], standings: List[Tuple[PlayerProfile, Dict[str, float]]], records: List[Dict[str, object]], holder_text: str) -> None:
        lines: List[str] = []
        lines.append("")
        lines.append(f"========== {WORLD_CUP_TOURNAMENT_LABEL.upper()} REPORT ==========")
        lines.append(f"Season {season_no} | Participants {len(entrants)} | Format Double Round Robin")
        lines.append(f"Points system: {WORLD_CUP_WIN_POINTS} points per win, 0 per loss")
        lines.append("Tiebreakers: points, head-to-head points among tied players, gate difference, average performance, rating")
        lines.append("")
        lines.append("Qualified Players and Active Loadouts")
        ranked_names = {prof.name: idx for idx, prof in enumerate(self.get_ranked_profiles(), start=1)}
        for prof in entrants:
            rank_no = ranked_names.get(prof.name, 0)
            champ_tag = " | World Champion" if self.is_world_champion(prof) else ""
            lines.append("")
            lines.append(f"#{rank_no} {prof.name}{champ_tag}")
            lines.extend(player_loadout_lines(prof, "  "))
        lines.append("")
        lines.append("Round Results")
        round_map: Dict[int, List[Dict[str, object]]] = defaultdict(list)
        for rec in records:
            try:
                round_map[int(rec.get("round_no", 0))].append(rec)
            except Exception:
                continue
        for round_no in sorted(round_map):
            lines.append("")
            lines.append(f"Round {round_no}")
            for rec in sorted(round_map[round_no], key=lambda r: int(r.get("leg", 0))):
                p1 = str(rec.get("player1", ""))
                p2 = str(rec.get("player2", ""))
                leg = int(rec.get("leg", 0))
                winner = str(rec.get("winner", ""))
                g1 = int(rec.get("gates1", 0))
                g2 = int(rec.get("gates2", 0))
                lines.append(f"  Leg {leg}: {p1} vs {p2} -> {winner} won ({g1}-{g2} gates)")
        lines.append("")
        lines.append("Final Standings")
        for pos, (prof, stats) in enumerate(standings, start=1):
            avg_perf = stats.get("perf_total", 0.0) / max(1.0, stats.get("matches", 0.0))
            lines.append(
                f"{pos}. {prof.name} | Pts {int(stats.get('points', 0))} | Wins {int(stats.get('wins', 0))} | "
                f"Losses {int(stats.get('losses', 0))} | GateDiff {int(stats.get('gate_diff', 0))} | "
                f"AvgPerf {avg_perf:.1f} | Rating {prof.glicko.rating:.1f}"
            )
        lines.append("")
        lines.append(holder_text)
        block = "\n".join(lines)
        chunk_size = 12000
        for start in range(0, len(block), chunk_size):
            self.append_text(block[start:start + chunk_size])


    def _world_cup_manual_state_text(self, season_no: int, entrants: List[PlayerProfile], table: Dict[str, Dict[str, float]], records: List[Dict[str, object]], viewer_name: Optional[str] = None) -> str:
        standings = self._build_world_cup_standings(entrants, table, records)
        lines = [
            f"{WORLD_CUP_TOURNAMENT_LABEL} Tournament standings",
            f"Season: {season_no}",
            f"Format: Double Round Robin",
            f"Matches completed: {len(records)} / {len(entrants) * (len(entrants) - 1)}",
        ]
        if viewer_name:
            viewer = next((p for p in standings if p.name == viewer_name), None)
            if viewer is not None:
                viewer_stats = table.get(viewer.name, {})
                matches_played = max(1.0, float(viewer_stats.get("matches", 0.0) or 0.0))
                avg_perf = float(viewer_stats.get("perf_total", 0.0) or 0.0) / matches_played if viewer_stats.get("matches", 0.0) else 0.0
                place = next((idx for idx, p in enumerate(standings, start=1) if p.name == viewer_name), None)
                lines.extend([
                    "",
                    "You are participating in the World Cup Tournament.",
                    f"Current position: {place}",
                    f"Points: {int(viewer_stats.get('points', 0))}",
                    f"Wins/Losses: {int(viewer_stats.get('wins', 0))}/{int(viewer_stats.get('losses', 0))}",
                    f"Gate diff: {int(viewer_stats.get('gate_diff', 0))}",
                    f"Average performance: {avg_perf:.1f}",
                    f"Rating: {viewer.glicko.rating:.1f}",
                ])
        lines.append("")
        lines.append("Top standings")
        for idx, prof in enumerate(standings, start=1):
            stats = table.get(prof.name, {})
            matches_played = float(stats.get("matches", 0.0) or 0.0)
            avg_perf = float(stats.get("perf_total", 0.0) or 0.0) / matches_played if matches_played else 0.0
            lines.append(
                f"{idx}. {prof.name} | Pts {int(stats.get('points', 0))} | W-L {int(stats.get('wins', 0))}-{int(stats.get('losses', 0))} | H2H {int(stats.get('head_to_head_points', 0))} | GateDiff {int(stats.get('gate_diff', 0))} | AvgPerf {avg_perf:.1f} | Rating {prof.glicko.rating:.1f}"
            )
        return "\n".join(lines)

    def _export_world_cup_files(self, season_no: int, entrants: List[PlayerProfile], standings: List[Tuple[PlayerProfile, Dict[str, float]]], records: List[Dict[str, object]], play_logs: List[str]) -> Tuple[Path, Path]:
        suffix_rng = random.Random(self.world_seed + season_no * 7919 + len(records))
        summary_path = get_current_output_dir() / build_output_filename("world_cup", len(entrants), len(records), random_suffix(suffix_rng))
        lines = [f"========== {WORLD_CUP_TOURNAMENT_LABEL.upper()} SUMMARY =========="]
        lines.append(f"Season {season_no} | Participants {len(entrants)} | Format Double Round Robin")
        lines.append(f"Points system: {WORLD_CUP_WIN_POINTS} points per win, 0 per loss")
        lines.append("Tiebreakers: points, head-to-head points among tied players, gate difference, average performance, rating")
        lines.append("")
        lines.append(f"{'Pos':<4}{'Name':<22}{'Pts':<6}{'Wins':<6}{'Losses':<8}{'H2H':<6}{'GateDiff':<10}{'AvgPerf':<10}{'Rating':<10}")
        for pos, (prof, stats) in enumerate(standings, start=1):
            avg_perf = stats["perf_total"] / stats["matches"] if stats["matches"] else 0.0
            lines.append(f"{pos:<4}{prof.name:<22}{int(stats['points']):<6}{int(stats['wins']):<6}{int(stats['losses']):<8}{int(stats.get('head_to_head_points', 0)):<6}{int(stats['gate_diff']):<10}{avg_perf:<10.1f}{prof.glicko.rating:<10.1f}")
        lines.append("")
        lines.append(f"World Champion reward: +1 title, +{WORLD_CUP_CHAMPION_FAME} fame, +{WORLD_CUP_CHAMPION_SPONSORSHIP} sponsorship, £{WORLD_CUP_CHAMPION_CASH}, +{WORLD_CUP_CHAMPION_SEASONAL_TRAINING} training point each new season until dethroned")
        lines.append("")
        lines.append("========== LOADOUTS ==========")
        for pos, (prof, _stats) in enumerate(standings, start=1):
            lines.append("")
            lines.append(f"{pos}. {prof.name}")
            lines.extend(player_loadout_lines(prof, "   "))
        summary_path = maybe_write_text(summary_path, "\n".join(lines), encoding="utf-8") or summary_path

        play_path = get_current_output_dir() / build_output_filename("world_cup_playbyplay", len(entrants), len(records), random_suffix(random.Random(self.world_seed + season_no * 12347)))
        text_lines = [f"========== {WORLD_CUP_TOURNAMENT_LABEL.upper()} PLAY BY PLAY =========="]
        text_lines.extend(play_logs)
        play_path = maybe_write_text(play_path, "\n".join(text_lines), encoding="utf-8") or play_path
        return summary_path, play_path


    def run_world_cup(self, season_no: int) -> None:
        ranked = self.get_ranked_profiles()
        entrants = ranked[:8]
        if len(entrants) < 8:
            return

        player_qualified = self.player is not None and any(p.name == self.player.name for p in entrants)
        if self.player is not None and not player_qualified:
            player_rank = next((idx for idx, prof in enumerate(ranked, start=1) if prof.name == self.player.name), None)
            if player_rank is not None:
                self.append_text(
                    f"{WORLD_CUP_TOURNAMENT_LABEL}: you did not qualify this season. Your world ranking was #{player_rank}. Top 8 qualify."
                )

        # World Cup ignores seasonal bans. Re-optimise entrants without ban restrictions.
        # Keep the user player's chosen loadout intact and let them adjust it before the event.
        unrestricted_snapshots = {}
        for prof in entrants:
            unrestricted_snapshots[prof.name] = {
                "bakugan": list(prof.active_bakugan_idx),
                "gates": list(prof.active_gate_idx),
                "abilities": list(prof.active_ability_idx),
            }
            if self.player is not None and prof.name == self.player.name:
                prof.ensure_valid_loadout()
                continue
            optimise_profile_loadout(prof, rng=self.rng)

        manual = False
        handler = None
        if player_qualified:
            self.append_text(f"You qualified for and are participating in the {WORLD_CUP_TOURNAMENT_LABEL} Tournament.")
            change_loadout = messagebox.askyesno(
                f"{WORLD_CUP_TOURNAMENT_LABEL} Tournament",
                "You qualified for the World Cup Tournament. Do you want to review or change your active loadout before your first World Cup match?",
                parent=self.root,
            )
            if change_loadout:
                self.customise_loadout()
                if self.player is not None:
                    self.player.ensure_valid_loadout()
                self.refresh_status()
                self.append_text(f"Using your chosen active loadout for the {WORLD_CUP_TOURNAMENT_LABEL} Tournament.")
            else:
                self.append_text(f"Keeping your current active loadout for the {WORLD_CUP_TOURNAMENT_LABEL} Tournament.")
            manual = messagebox.askyesno(
                f"{WORLD_CUP_TOURNAMENT_LABEL} Tournament",
                "You qualified for the World Cup Tournament. Play your World Cup matches in manual mode?\n\nDuring manual prompts, type AUTO to simulate the rest of the tournament automatically.",
                parent=self.root,
            )
            handler = TkManualChoiceHandler(self.root) if manual else None

        debug = bool(self.debug_var.get())
        logger = Logger(enabled=debug, prefix="world_cup")
        self.append_text(f"{WORLD_CUP_TOURNAMENT_LABEL}: Season {season_no} special event starting. Top 8 by ranking qualify.")
        self.append_text("Qualified: " + ", ".join(f"#{i} {p.name}" for i, p in enumerate(entrants, start=1)))

        table: Dict[str, Dict[str, float]] = {
            p.name: {"points": 0.0, "wins": 0.0, "losses": 0.0, "head_to_head_points": 0.0, "gate_diff": 0.0, "perf_total": 0.0, "matches": 0.0} for p in entrants
        }
        matchup_results: List[Tuple[str, str, bool]] = []
        records: List[Dict[str, object]] = []
        play_logs: List[str] = []

        if handler is not None and hasattr(handler, "set_tournament_state_provider"):
            handler.set_tournament_state_provider(lambda viewer_name=None: self._world_cup_manual_state_text(season_no, entrants, table, records, viewer_name))

        round_no = 1
        for p1, p2 in combinations(entrants, 2):
            for leg in (1, 2):
                match_logger = Logger(enabled=debug, prefix="match")
                manual_player_name = None
                match_handler = None
                if handler is not None and not getattr(handler, "auto_rest", False):
                    if p1.name == self.player.name:
                        manual_player_name = p1.name
                        match_handler = handler
                    elif p2.name == self.player.name:
                        manual_player_name = p2.name
                        match_handler = handler
                match = Match(
                    p1,
                    p2,
                    seed=self.rng.randint(1, 10_000_000),
                    verbose=debug,
                    logger=match_logger,
                    manual_handler=match_handler,
                    manual_player_name=manual_player_name,
                )
                winner, perf, lines = match.play()
                for match_player in match.players:
                    original = p1 if match_player.name == p1.name else p2
                    original.glicko = match_player.glicko
                p1_won = winner.name == p1.name
                matchup_results.append((p1.name, p2.name, p1_won))

                gates1 = len(match.captured[p1.name])
                gates2 = len(match.captured[p2.name])
                table[p1.name]["matches"] += 1
                table[p2.name]["matches"] += 1
                table[p1.name]["perf_total"] += perf[p1.name]
                table[p2.name]["perf_total"] += perf[p2.name]
                table[p1.name]["gate_diff"] += gates1 - gates2
                table[p2.name]["gate_diff"] += gates2 - gates1
                if p1_won:
                    table[p1.name]["wins"] += 1
                    table[p1.name]["points"] += WORLD_CUP_WIN_POINTS
                    table[p1.name]["head_to_head_points"] += WORLD_CUP_WIN_POINTS
                    table[p2.name]["losses"] += 1
                else:
                    table[p2.name]["wins"] += 1
                    table[p2.name]["points"] += WORLD_CUP_WIN_POINTS
                    table[p2.name]["head_to_head_points"] += WORLD_CUP_WIN_POINTS
                    table[p1.name]["losses"] += 1

                records.append({
                    "round_no": round_no,
                    "leg": leg,
                    "player1": p1.name,
                    "player2": p2.name,
                    "winner": winner.name,
                    "perf1": perf[p1.name],
                    "perf2": perf[p2.name],
                    "gates1": gates1,
                    "gates2": gates2,
                })
                play_logs.append("")
                play_logs.append(f"========== ROUND ROBIN SET {round_no} | LEG {leg} | {p1.name} vs {p2.name} ==========")
                play_logs.extend(lines)
            round_no += 1

        if handler is not None and hasattr(handler, "set_tournament_state_provider"):
            handler.set_tournament_state_provider(None)

        standings = self._build_world_cup_standings(entrants, table, records)
        tied_name_group = {p.name for p in entrants}
        h2h_points = self._world_cup_head_to_head_points(tied_name_group, records)
        for prof in entrants:
            table[prof.name]["head_to_head_points"] = h2h_points.get(prof.name, 0)
        finish_map = {p.name: pos for pos, p in enumerate(standings, start=1)}
        standings_with_stats = [(p, table[p.name]) for p in standings]
        winner_name = standings[0].name if standings else ""
        summary_path, play_path = self._export_world_cup_files(season_no, entrants, standings_with_stats, records, play_logs)
        apply_matchup_results(matchup_results, {p.name: p for p in entrants})

        for prof in entrants:
            if not isinstance(prof.story_flags, dict):
                prof.story_flags = {}
            prof.story_flags["_last_used_loadout"] = make_active_loadout_snapshot(prof)
            prof.story_flags["_last_used_season"] = season_no
            prof.story_flags["_last_used_event"] = 0

        for prof in entrants:
            finish = finish_map.get(prof.name, len(entrants))
            payout = tournament_payout_table(finish, len(entrants), TournamentType.SWISS)
            apply_tournament_career_update(prof, finish, len(entrants), TournamentType.SWISS, self.rng, payout)
            if not prof.is_human:
                prof.training_points += 1
                apply_training(prof, self.rng, 1.15 if finish <= 4 else 0.85)
                prof.update_career_stage()
                prof.update_rivals()
                prof.update_signature()

        previous_champion = None
        if isinstance(self.current_world_champion, dict):
            previous_champion = self.current_world_champion.get("name")
        self._apply_world_champion_title(winner_name, season_no, previous_champion)
        holder_text = f"{winner_name} is the new World Champion and earns +1 title, +{WORLD_CUP_CHAMPION_FAME} fame, +{WORLD_CUP_CHAMPION_SPONSORSHIP} sponsorship, £{WORLD_CUP_CHAMPION_CASH}, and +{WORLD_CUP_CHAMPION_SEASONAL_TRAINING} training point each new season until dethroned."
        if previous_champion and previous_champion != winner_name:
            holder_text = f"{previous_champion} loses the World Champion title. {winner_name} is the new World Champion and earns +1 title, +{WORLD_CUP_CHAMPION_FAME} fame, +{WORLD_CUP_CHAMPION_SPONSORSHIP} sponsorship, £{WORLD_CUP_CHAMPION_CASH}, and +{WORLD_CUP_CHAMPION_SEASONAL_TRAINING} training point each new season until dethroned."
        elif previous_champion == winner_name:
            holder_text = f"{winner_name} retains the World Champion title and refreshes the World Champion rewards."

        self._append_world_cup_report_to_text(season_no, entrants, standings_with_stats, records, holder_text)

        archive = make_tournament_archive(season_no, 0, TournamentType.SWISS, len(entrants), entrants, finish_map, winner_name, summary_path, play_path)
        archive["tournament_type"] = WORLD_CUP_TOURNAMENT_LABEL
        archive["format"] = "Double Round Robin"
        archive["special_event"] = True
        archive["does_not_count_toward_season_event"] = True
        archive["world_champion_awarded"] = winner_name
        archive["previous_world_champion"] = previous_champion
        archive["world_champion_retained"] = bool(previous_champion and previous_champion == winner_name)
        archive["world_cup_points_system"] = {"win": WORLD_CUP_WIN_POINTS, "loss": 0}
        archive["world_cup_tiebreakers"] = ["points", "head_to_head_points_among_tied_players", "gate_difference", "average_performance", "rating"]
        archive["round_robin_records"] = records
        archive["standings"] = [
            {
                "position": pos,
                "name": prof.name,
                "points": int(stats.get("points", 0)),
                "wins": int(stats.get("wins", 0)),
                "losses": int(stats.get("losses", 0)),
                "head_to_head_points": int(stats.get("head_to_head_points", 0)),
                "gate_diff": int(stats.get("gate_diff", 0)),
                "avg_perf": round((stats.get("perf_total", 0.0) / max(1.0, stats.get("matches", 0.0))), 2),
                "rating": round(prof.glicko.rating, 1),
            }
            for pos, (prof, stats) in enumerate(standings_with_stats, start=1)
        ]
        self.db.save_tournament_archive(archive)

        npc_map = {p.name: p for p in self.all_npcs()}
        for prof in entrants:
            if not prof.is_human:
                npc_map[prof.name] = prof
        self.save_npcs(list(npc_map.values()))

        # Re-apply seasonal bans after the World Cup so normal tournaments remain restricted.
        if isinstance(getattr(self, "current_season_bans", None), dict) and self.current_season_bans.get("enabled"):
            self.apply_season_bans_worldwide()

        new_npcs = self.add_new_npcs_after_world_cup()
        self.append_text(f"{WORLD_CUP_TOURNAMENT_LABEL} complete. Winner: {winner_name}.")
        self.append_text(holder_text)
        if new_npcs:
            self.append_text(f"New NPCs added after the World Cup: {', '.join(n.name for n in new_npcs)}")
        prodigy_lines = self._future_prodigies_lines()
        if prodigy_lines:
            self.append_text("\n".join(prodigy_lines))
        if is_text_file_exports_enabled():
            self.append_text(f"Saved World Cup summary to {summary_path}")
            self.append_text(f"Saved World Cup play by play to {play_path}")


    def add_new_npcs_after_world_cup(self, count: Optional[int] = None) -> List[PlayerProfile]:
        add_count = max(0, int(self.world_cup_new_npcs if count is None else count))
        if add_count <= 0:
            return []
        existing = list(self.all_npcs())
        target_count = len(existing) + add_count
        pool = generate_npc_pool(target_count, existing, self.rng)
        new_npcs = pool[len(existing):]
        for npc in new_npcs:
            npc.ensure_valid_loadout()
            npc.update_career_stage()
            npc.update_rivals()
            npc.update_signature()
            if isinstance(getattr(self, "current_season_bans", None), dict) and self.current_season_bans.get("enabled"):
                optimise_profile_loadout_with_bans(npc, self.current_season_bans)
        self.save_npcs(pool)
        return new_npcs


    def process_new_season_age_progression(self, new_season: int) -> None:
        if not self.age_progression_enabled:
            return
        retired_names = []
        if self.player is not None:
            age_profile_one_season(self.player, self.rng)
            self.player.update_career_stage()
            self.player.update_signature()
        all_npcs = [p for p in self.db.load_all_profiles() if not p.is_human]
        for npc in all_npcs:
            if age_profile_one_season(npc, self.rng):
                retired_names.append(npc.name)
            npc.update_career_stage()
            npc.update_signature()
        self.save_npcs(all_npcs)
        active_count = sum(1 for p in all_npcs if not profile_is_retired(p))
        self.npc_target_population = max(active_count + max(0, int(self.season_new_npcs)), self.npc_target_population)
        self.db.set_world_int('npc_target_population', self.npc_target_population)
        self.ensure_npc_universe()
        if self.player is not None:
            age_flags = self.player.story_flags if isinstance(self.player.story_flags, dict) else {}
            self.append_text(
                f"Season {new_season}: {self.player.name} is now age {profile_age(self.player)} | "
                f"Peak age {int(age_flags.get('peak_age', profile_age(self.player)))} | "
                f"Retirement age {int(age_flags.get('retirement_age', profile_age(self.player) + 10))}"
            )
        if retired_names:
            self.append_text(f"Season {new_season}: retired players: {', '.join(retired_names[:12])}" + (" ..." if len(retired_names) > 12 else ""))

    def _future_prodigies_lines(self) -> List[str]:
        if not self.age_progression_enabled:
            return []
        prospects = shortlist_future_prodigies([p for p in self.db.load_all_profiles() if not p.is_human], limit=8)
        if not prospects:
            return []
        lines = ["Future Prodigies to watch:"]
        for p in prospects:
            lines.append(f"  - {p.name} | Age {profile_age(p)} | Rating {p.glicko.rating:.0f} | Titles {p.tournament_titles} | Podiums {p.podiums} | Fame {p.fame}")
        return lines


    def maybe_run_world_cup(self, completed_season: int) -> None:
        interval = max(1, int(getattr(self, "world_cup_interval", WORLD_CUP_INTERVAL_DEFAULT)))
        if completed_season <= 0 or completed_season % interval != 0:
            return
        self.run_world_cup(completed_season)


    def ensure_npc_universe(self) -> None:
        all_profiles = [p for p in self.db.load_all_profiles() if not p.is_human]
        retired = [p for p in all_profiles if profile_is_retired(p)]
        active = [p for p in all_profiles if not profile_is_retired(p)]
        pool = generate_npc_pool(self.npc_target_population, active, self.rng, new_player_min_age=bool(active))
        for npc in pool:
            npc.ensure_valid_loadout()
            npc.update_career_stage()
            npc.update_rivals()
            npc.update_signature()
        self.db.save_profiles(retired + pool)


    def _build_seasonal_shop_stock(self, season_no: Optional[int] = None) -> Dict[str, object]:
        season_no = max(1, int(season_no if season_no is not None else self.world_season))

        def bakugan_rarity(template: BakuganTemplate) -> str:
            max_g = max(template.g_powers)
            name = template.name.lower()
            evolved_keywords = ["delta", "neo", "ultimate", "cross", "helix", "blade", "hammer", "master", "knight", "minx", "alpha", "dual", "viper", "cyborg", "rex", "mega", "saint", "magma", "cosmic", "midnight", "titanium", "lumino", "infinity", "blitz"]
            evolved = any(k in name for k in evolved_keywords)
            if max_g >= 560 or template.price >= 500:
                return "Legendary"
            if max_g >= 500 or template.price >= 380 or evolved:
                return "Epic"
            if max_g >= 440 or template.price >= 240:
                return "Rare"
            return "Common"

        def card_rarity(card) -> str:
            price = getattr(card, 'price', 100)
            if price >= 160:
                return "Legendary"
            if price >= 130:
                return "Epic"
            if price >= 105:
                return "Rare"
            return "Common"

        def seasonal_stock(full_items, season_seed: int, count: int, key_fn):
            if len(full_items) <= count:
                return list(full_items)
            local_rng = random.Random(season_seed)
            decorated = []
            for idx, item in enumerate(full_items):
                decorated.append((local_rng.random(), key_fn(item), idx, item))
            decorated.sort(key=lambda x: (x[0], x[1], x[2]))
            picked = [item for _, _, _, item in decorated[:count]]
            picked.sort(key=key_fn)
            return picked

        base = int(self.world_seed or 1)
        bakugan_stock = seasonal_stock(self.templates, base + 10000 + season_no, 18, lambda t: (t.price, max(t.g_powers), t.name))
        gate_stock = seasonal_stock(self.gates, base + 20000 + season_no, 12, lambda g: (g.price, g.gate_type.value, g.name))
        ability_stock = seasonal_stock(self.abilities, base + 30000 + season_no, 12, lambda a: (a.price, a.color.value, a.name))

        stock_rng = random.Random(base + 40000 + season_no)

        def random_stock_amount(rarity: str, category: str) -> int:
            if category == "bakugan":
                ranges = {
                    "Common": (16, 28),
                    "Rare": (10, 18),
                    "Epic": (6, 12),
                    "Legendary": (3, 8),
                }
            else:
                ranges = {
                    "Common": (18, 32),
                    "Rare": (12, 22),
                    "Epic": (6, 14),
                    "Legendary": (3, 8),
                }
            low, high = ranges.get(rarity, (1, 2))
            return stock_rng.randint(low, high)

        loot_boxes = [
            {"code": "L0", "name": "Starter Loot Box", "stock": stock_rng.randint(20, 36), "price": 150, "tier_weights": {"Common": 82, "Rare": 16, "Epic": 2, "Legendary": 0}, "card_weights": {"Common": 78, "Rare": 18, "Epic": 4, "Legendary": 0}, "text": "Cheap box. Mostly base forms and lower-tier cards."},
            {"code": "L1", "name": "Lucky Loot Box", "stock": stock_rng.randint(12, 22), "price": 220, "tier_weights": {"Common": 45, "Rare": 38, "Epic": 15, "Legendary": 2}, "card_weights": {"Common": 40, "Rare": 38, "Epic": 18, "Legendary": 4}, "text": "Balanced odds. Better chance at evolved and stronger pulls."},
            {"code": "L2", "name": "Elite Loot Box", "stock": stock_rng.randint(6, 12), "price": 320, "tier_weights": {"Common": 18, "Rare": 35, "Epic": 32, "Legendary": 15}, "card_weights": {"Common": 15, "Rare": 30, "Epic": 35, "Legendary": 20}, "text": "Best odds for evolved anime Bakugan and premium cards."},
        ]
        # Player-facing shop uses the seasonal selection only, with effectively unlimited stock.
        bakugan_player = {template_stock_key(t): 999999 for t in bakugan_stock}
        gate_player = {gate_stock_key(g): 999999 for g in gate_stock}
        ability_player = {ability_stock_key(a): 999999 for a in ability_stock}
        loot_player = {b["code"]: 999999 for b in loot_boxes}

        # NPC market uses its own separate finite seasonal stock pool.
        npc_rng = random.Random(base + 50000 + season_no)
        bakugan_npc = {template_stock_key(t): npc_rng.randint(10, 20) for t in bakugan_stock}
        gate_npc = {gate_stock_key(g): npc_rng.randint(12, 24) for g in gate_stock}
        ability_npc = {ability_stock_key(a): npc_rng.randint(12, 24) for a in ability_stock}
        loot_npc = {"L0": npc_rng.randint(12, 24), "L1": npc_rng.randint(10, 18), "L2": npc_rng.randint(8, 14)}
        return {
            "season": season_no,
            "bakugan_selection": [template_stock_key(t) for t in bakugan_stock],
            "gate_selection": [gate_stock_key(g) for g in gate_stock],
            "ability_selection": [ability_stock_key(a) for a in ability_stock],
            "loot_selection": [b["code"] for b in loot_boxes],
            "bakugan": bakugan_player,
            "gates": gate_player,
            "abilities": ability_player,
            "loot_boxes": loot_player,
            "bakugan_npc": bakugan_npc,
            "gates_npc": gate_npc,
            "abilities_npc": ability_npc,
            "loot_boxes_npc": loot_npc,
        }


    def get_season_shop_stock(self) -> Dict[str, object]:
        key = "season_shop_stock_v7"
        stock = self.db.get_world_json(key, None)
        if not isinstance(stock, dict) or int(stock.get("season", 0)) != int(self.world_season):
            stock = self._build_seasonal_shop_stock(self.world_season)
            self.db.set_world_json(key, stock)
        return stock


    def save_season_shop_stock(self, stock: Dict[str, object]) -> None:
        self.db.set_world_json("season_shop_stock_v7", stock)


    def consume_shop_stock(self, stock: Dict[str, object], category: str, code: str, qty: int = 1) -> bool:
        bucket = stock.setdefault(category, {})
        if bucket.get(code, 0) < qty:
            return False
        bucket[code] -= qty
        self.save_season_shop_stock(stock)
        return True



    def all_npcs(self) -> List[PlayerProfile]:
        self.ensure_npc_universe()
        return [p for p in self.db.load_all_profiles() if not p.is_human]


    def save_npcs(self, npcs: List[PlayerProfile]) -> None:
        self.db.save_profiles(npcs)


    def view_npc_rankings(self) -> None:
        entrants = list(self.all_npcs())
        if self.player is not None:
            entrants = [p for p in entrants if p.name != self.player.name]
            entrants.append(self.player)
        ranked = sorted(entrants, key=lambda p: (p.glicko.rating, p.tournament_titles, p.fame), reverse=True)
        npc_count = sum(1 for p in ranked if not p.is_human)
        lines = [f"World rankings | NPC universe: {npc_count}"]
        player_rank = None
        for i, prof in enumerate(ranked, start=1):
            if self.player is not None and prof.name == self.player.name:
                player_rank = i
                break
        top_slice = ranked[:20]
        for i, prof in enumerate(top_slice, start=1):
            player_tag = " | You" if self.player is not None and prof.name == self.player.name else ""
            champ_hist = self.get_world_champion_history_for_profile(prof)
            champ_hist_text = f" | WC Seasons {', '.join(str(s) for s in champ_hist)}" if champ_hist else ""
            age_text = f" | Age {profile_age(prof)}" if getattr(self, "age_progression_enabled", False) else ""
            lines.append(
                f"{i:>2}. {prof.name}{age_text} | {self.display_title(prof)} | Rating {prof.glicko.rating:.0f} | "
                f"Titles {prof.tournament_titles} | Podiums {prof.podiums} | Fame {prof.fame}{champ_hist_text} | "
                f"Sig {prof.signature_bakugan}{player_tag}"
            )
        if self.player is not None and player_rank is not None:
            prof = ranked[player_rank - 1]
            lines.append("")
            lines.append(f"Your rank: {player_rank}/{len(ranked)}")
            if player_rank > 20:
                champ_tag = " | World Champion" if self.is_world_champion(prof) else ""
                lines.append(
                    f"{player_rank:>2}. {prof.name}{champ_tag} | {self.display_title(prof)} | Rating {prof.glicko.rating:.0f} | "
                    f"Titles {prof.tournament_titles} | Podiums {prof.podiums} | Fame {prof.fame} | "
                    f"Sig {prof.signature_bakugan} | You"
                )
        self.append_text("\n".join(lines))


    def export_npc_loadouts(self) -> None:
        npcs = sorted(self.all_npcs(), key=lambda p: (-p.glicko.rating, p.name))
        if not npcs:
            messagebox.showinfo("Export NPC Loadouts", "No NPC profiles found to export.")
            return

        default_path = get_current_output_dir() / f"npc_loadouts_season_{self.world_season}_event_{self.world_tournament_no}.csv"
        path_str = filedialog.asksaveasfilename(
            title="Export NPC Loadouts",
            defaultextension=".csv",
            initialdir=str(default_path.parent),
            initialfile=default_path.name,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path_str:
            return

        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)

        headers = [
            "world_rank", "name", "chosen_attribute", "style", "development_focus", "archetype",
            "career_stage", "rating", "peak_rating", "titles", "finals", "podiums", "top8s",
            "tournaments_entered", "wins", "losses", "win_rate", "money", "career_earnings",
            "fame", "sponsorship", "training_points", "rolling_skill", "intelligence",
            "aggression", "risk", "signature_bakugan",
            "bakugan_1", "bakugan_2", "bakugan_3",
            "gate_gold", "gate_silver", "gate_bronze",
            "ability_red", "ability_blue", "ability_green",
        ]

        def bakugan_text(profile: PlayerProfile, idx: int) -> str:
            if 0 <= idx < len(profile.collection_bakugan):
                b = profile.collection_bakugan[idx]
                return f"{b.name} | {b.attribute.value} | {b.base_g}G"
            return ""

        def gate_text(profile: PlayerProfile, idx: int) -> str:
            if 0 <= idx < len(profile.collection_gates):
                g = profile.collection_gates[idx]
                bonus_blob = ", ".join(f"{attr}:{bonus}" for attr, bonus in sorted(g.bonuses.items(), key=lambda item: item[0].value))
                effect_blob = getattr(g, "description", "") or getattr(g, "effect_id", "")
                effect_blob = str(effect_blob).replace("\n", " ").strip()
                return f"{g.name} | {g.gate_type.value} | {bonus_blob} | {effect_blob}"
            return ""

        def ability_text(profile: PlayerProfile, idx: int) -> str:
            if 0 <= idx < len(profile.collection_abilities):
                a = profile.collection_abilities[idx]
                effect_blob = getattr(a, "description", "") or getattr(a, "effect_id", "")
                effect_blob = str(effect_blob).replace("\n", " ").strip()
                return f"{a.name} | {a.color.value} | {effect_blob}"
            return ""

        rows = []
        for world_rank, prof in enumerate(npcs, start=1):
            prof.update_career_stage()
            total_games = prof.wins + prof.losses
            win_rate = (prof.wins / total_games * 100.0) if total_games else 0.0
            active_bak = list(prof.active_bakugan_idx[:3])
            while len(active_bak) < 3:
                active_bak.append(-1)
            active_gate = list(prof.active_gate_idx[:3])
            while len(active_gate) < 3:
                active_gate.append(-1)
            active_ability = list(prof.active_ability_idx[:3])
            while len(active_ability) < 3:
                active_ability.append(-1)

            rows.append([
                world_rank,
                prof.name,
                prof.chosen_attribute.value,
                prof.style.value,
                prof.development_focus,
                prof.archetype.value,
                self.display_title(prof),
                round(prof.glicko.rating, 2),
                round(prof.peak_rating, 2),
                prof.tournament_titles,
                prof.finals,
                prof.podiums,
                prof.top8s,
                prof.tournaments_entered,
                prof.wins,
                prof.losses,
                round(win_rate, 2),
                prof.money,
                prof.career_earnings,
                prof.fame,
                prof.sponsorship,
                prof.training_points,
                round(prof.rolling_skill, 3),
                round(prof.intelligence, 3),
                round(prof.aggression, 3),
                round(prof.risk, 3),
                prof.signature_bakugan,
                bakugan_text(prof, active_bak[0]),
                bakugan_text(prof, active_bak[1]),
                bakugan_text(prof, active_bak[2]),
                gate_text(prof, active_gate[0]),
                gate_text(prof, active_gate[1]),
                gate_text(prof, active_gate[2]),
                ability_text(prof, active_ability[0]),
                ability_text(prof, active_ability[1]),
                ability_text(prof, active_ability[2]),
            ])

        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            writer.writerows(rows)

        try:
            rel = path.relative_to(APP_DIR)
            shown = str(rel)
        except ValueError:
            shown = str(path)
        messagebox.showinfo("Export NPC Loadouts", f"Exported {len(rows)} NPC loadouts to\n{shown}")


    def search_profile_loadout(self) -> None:
        profiles = list(self.db.load_all_profiles())
        if self.player is not None:
            replaced = False
            merged = []
            for p in profiles:
                if p.name == self.player.name and bool(getattr(p, "is_human", False)):
                    if not replaced:
                        merged.append(self.player)
                        replaced = True
                else:
                    merged.append(p)
            if not replaced:
                merged.append(self.player)
            profiles = merged

        public_sort_options = [
            "world ranking", "rating", "peak rating", "titles", "finals", "podiums", "top8s", "fame",
            "wins", "losses", "win rate", "tournaments", "career earnings", "money", "sponsorship", "age",
        ]
        hidden_sort_options = ["training points", "roll", "int", "aggression", "risk"]
        sort_options = public_sort_options + hidden_sort_options if bool(self.debug_var.get()) else public_sort_options[:]

        def safe_win_rate(profile: PlayerProfile) -> float:
            total = profile.wins + profile.losses
            return profile.wins / total if total > 0 else 0.0

        def stat_tuple(profile: PlayerProfile, primary: float) -> Tuple:
            return (primary, profile.glicko.rating, profile.tournament_titles, profile.fame, -profile.losses, profile.name.lower())

        def ranked_profiles(sort_mode: str) -> List[PlayerProfile]:
            if sort_mode == "world ranking":
                live_profiles = [p for p in profiles if not profile_is_retired(p)]
                return sorted(live_profiles, key=lambda p: stat_tuple(p, p.glicko.rating), reverse=True)
            if sort_mode == "rating":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.glicko.rating), reverse=True)
            if sort_mode == "peak rating":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.peak_rating), reverse=True)
            if sort_mode == "titles":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.tournament_titles), reverse=True)
            if sort_mode == "finals":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.finals), reverse=True)
            if sort_mode == "podiums":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.podiums), reverse=True)
            if sort_mode == "top8s":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.top8s), reverse=True)
            if sort_mode == "fame":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.fame), reverse=True)
            if sort_mode == "wins":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.wins), reverse=True)
            if sort_mode == "losses":
                return sorted(profiles, key=lambda p: (p.losses, -p.wins, -p.glicko.rating, p.name.lower()), reverse=True)
            if sort_mode == "win rate":
                return sorted(profiles, key=lambda p: stat_tuple(p, safe_win_rate(p)), reverse=True)
            if sort_mode == "tournaments":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.tournaments_entered), reverse=True)
            if sort_mode == "career earnings":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.career_earnings), reverse=True)
            if sort_mode == "money":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.money), reverse=True)
            if sort_mode == "training points":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.training_points), reverse=True)
            if sort_mode == "sponsorship":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.sponsorship), reverse=True)
            if sort_mode == "age":
                return sorted(profiles, key=lambda p: stat_tuple(p, profile_age(p)), reverse=True)
            if sort_mode == "roll":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.rolling_skill), reverse=True)
            if sort_mode == "int":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.intelligence), reverse=True)
            if sort_mode == "aggression":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.aggression), reverse=True)
            if sort_mode == "risk":
                return sorted(profiles, key=lambda p: stat_tuple(p, p.risk), reverse=True)
            return sorted(profiles, key=lambda p: stat_tuple(p, p.glicko.rating), reverse=True)

        def list_label(profile: PlayerProfile, sort_mode: str, latest_ranked: List[PlayerProfile]) -> str:
            player_tag = " | You" if self.player is not None and profile.name == self.player.name else ""
            retired_tag = " | Retired" if profile_is_retired(profile) else ""
            if sort_mode == "world ranking":
                rank_no = latest_ranked.index(profile) + 1
                return f"#{rank_no} {profile.name}{retired_tag}{player_tag}"
            if sort_mode == "rating":
                return f"{profile.name} | Rating {profile.glicko.rating:.0f}{retired_tag}{player_tag}"
            if sort_mode == "peak rating":
                return f"{profile.name} | Peak {profile.peak_rating:.0f}{retired_tag}{player_tag}"
            if sort_mode == "titles":
                return f"{profile.name} | Titles {profile.tournament_titles}{retired_tag}{player_tag}"
            if sort_mode == "finals":
                return f"{profile.name} | Finals {profile.finals}{retired_tag}{player_tag}"
            if sort_mode == "podiums":
                return f"{profile.name} | Podiums {profile.podiums}{retired_tag}{player_tag}"
            if sort_mode == "top8s":
                return f"{profile.name} | Top8s {profile.top8s}{retired_tag}{player_tag}"
            if sort_mode == "fame":
                return f"{profile.name} | Fame {profile.fame}{retired_tag}{player_tag}"
            if sort_mode == "wins":
                return f"{profile.name} | Wins {profile.wins}{retired_tag}{player_tag}"
            if sort_mode == "losses":
                return f"{profile.name} | Losses {profile.losses}{retired_tag}{player_tag}"
            if sort_mode == "win rate":
                return f"{profile.name} | Win Rate {safe_win_rate(profile) * 100:.1f}%{retired_tag}{player_tag}"
            if sort_mode == "tournaments":
                return f"{profile.name} | Tournaments {profile.tournaments_entered}{retired_tag}{player_tag}"
            if sort_mode == "career earnings":
                return f"{profile.name} | Earnings {profile.career_earnings}{retired_tag}{player_tag}"
            if sort_mode == "money":
                return f"{profile.name} | Money {profile.money}{retired_tag}{player_tag}"
            if sort_mode == "training points":
                return f"{profile.name} | Training {profile.training_points}{retired_tag}{player_tag}"
            if sort_mode == "sponsorship":
                return f"{profile.name} | Sponsorship {profile.sponsorship}{retired_tag}{player_tag}"
            if sort_mode == "age":
                return f"{profile.name} | Age {profile_age(profile)}{retired_tag}{player_tag}"
            if sort_mode == "roll":
                return f"{profile.name} | Roll {profile.rolling_skill:.2f}{retired_tag}{player_tag}"
            if sort_mode == "int":
                return f"{profile.name} | Int {profile.intelligence:.2f}{retired_tag}{player_tag}"
            if sort_mode == "aggression":
                return f"{profile.name} | Agg {profile.aggression:.2f}{retired_tag}{player_tag}"
            if sort_mode == "risk":
                return f"{profile.name} | Risk {profile.risk:.2f}{retired_tag}{player_tag}"
            return f"{profile.name}{retired_tag}{player_tag}"

        win = tk.Toplevel(self.root)
        win.title("Search Profile Loadout")
        win.geometry("1080x720")

        top = ttk.Frame(win, padding=8)
        top.pack(fill="both", expand=True)

        left = ttk.Frame(top)
        left.pack(side="left", fill="y")
        right = ttk.Frame(top)
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Search NPC or player").pack(anchor="w")
        query_var = tk.StringVar()
        entry = ttk.Entry(left, textvariable=query_var, width=32)
        entry.pack(fill="x", pady=(0, 8))

        controls = ttk.Frame(left)
        controls.pack(fill="x", pady=(0, 8))
        ttk.Label(controls, text="Sort by").pack(side="left")
        sort_var = tk.StringVar(value="world ranking")
        sort_box = ttk.Combobox(
            controls,
            textvariable=sort_var,
            values=sort_options,
            state="readonly",
            width=18,
        )

        def refresh_sort_options(*_args):
            try:
                if not sort_box.winfo_exists():
                    return
            except tk.TclError:
                return
            values = public_sort_options + hidden_sort_options if bool(self.debug_var.get()) else public_sort_options[:]
            sort_box.configure(values=values)
            if sort_var.get() not in values:
                sort_var.set("world ranking")
        sort_box.pack(side="left", padx=(6, 0))
        ttk.Label(controls, text="Min Age").pack(side="left", padx=(10, 0))
        min_age_var = tk.StringVar(value="")
        ttk.Entry(controls, textvariable=min_age_var, width=6).pack(side="left", padx=(4, 0))
        ttk.Label(controls, text="Max Age").pack(side="left", padx=(10, 0))
        max_age_var = tk.StringVar(value="")
        ttk.Entry(controls, textvariable=max_age_var, width=6).pack(side="left", padx=(4, 0))
        hide_retired_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Hide Retired", variable=hide_retired_var, command=lambda: refresh_list()).pack(side="left", padx=(10, 0))

        def show_rank_titles() -> None:
            win2 = tk.Toplevel(win)
            win2.title("Career Title Ladder")
            win2.geometry("420x420")
            text = tk.Text(win2, width=48, height=22, wrap="word")
            text.pack(fill="both", expand=True, padx=8, pady=8)
            lines = [
                "Career title ladder",
                "",
                "1. Grand Brawler",
                "2. Master Brawler",
                "3. International Brawler",
                "4. National Brawler",
                "5. Senior Champion",
                "6. Champion",
                "7. Expert",
                "8. Candidate Expert",
                "9. Senior Contender",
                "10. Contender",
                "11. Class A Brawler",
                "12. Class B Brawler",
                "13. Class C Brawler",
                "14. Class D Brawler",
                "15. Rookie",
            ]
            text.insert("1.0", "\n".join(lines))
            text.configure(state="disabled")

        ttk.Button(left, text="View Title Ladder", command=show_rank_titles).pack(anchor="w", pady=(0, 8))

        listbox = tk.Listbox(left, width=42, height=32)
        listbox.pack(fill="y", expand=True)

        text_widget = tk.Text(right, width=88, height=40)
        text_widget.pack(fill="both", expand=True)

        filtered = []
        latest_ranked = []

        def refresh_list(*_args):
            nonlocal filtered, latest_ranked
            q = query_var.get().strip().lower()
            latest_ranked = ranked_profiles(sort_var.get())
            min_age = int(min_age_var.get()) if min_age_var.get().strip().isdigit() else None
            max_age = int(max_age_var.get()) if max_age_var.get().strip().isdigit() else None
            if q:
                filtered = [p for p in latest_ranked if q in p.name.lower()]
            else:
                filtered = latest_ranked[:]
            if bool(hide_retired_var.get()):
                filtered = [
                    p for p in filtered
                    if (not profile_is_retired(p)) or (bool(getattr(p, "is_human", False)) and q and q in p.name.lower())
                ]
            if min_age is not None:
                filtered = [p for p in filtered if profile_age(p) >= min_age]
            if max_age is not None:
                filtered = [p for p in filtered if profile_age(p) <= max_age]
            listbox.delete(0, 'end')
            for p in filtered:
                listbox.insert('end', list_label(p, sort_var.get(), latest_ranked))
            if filtered:
                listbox.selection_set(0)
                show_selected()
            else:
                text_widget.delete('1.0', 'end')
                text_widget.insert('1.0', 'No matching profiles.')

        def show_selected(event=None):
            sel = listbox.curselection()
            if not sel or not filtered:
                return
            prof = filtered[sel[0]]
            rank_sorted = ranked_profiles("world ranking")
            world_rank = next((i for i, p in enumerate(rank_sorted, start=1) if p.name == prof.name), None)

            snap = prof.story_flags.get('_last_used_loadout') if isinstance(prof.story_flags, dict) else None
            season = prof.story_flags.get('_last_used_season') if isinstance(prof.story_flags, dict) else None
            event_no = prof.story_flags.get('_last_used_event') if isinstance(prof.story_flags, dict) else None
            if not isinstance(snap, dict):
                snap = make_active_loadout_snapshot(prof)
            total_matches = prof.wins + prof.losses
            win_rate = safe_win_rate(prof) * 100.0
            debug_mode = bool(self.debug_var.get())
            lines = [
                f"{prof.name}{' | You' if self.player is not None and prof.name == self.player.name else ''}{' | Retired' if profile_is_retired(prof) else ''}",
                f"World Rank #{world_rank if world_rank is not None else 'N/A'}",
                f"Age {profile_age(prof)}" if getattr(self, "age_progression_enabled", False) else "",
                f"Attribute {prof.chosen_attribute.value} | Style {prof.style.value} | Archetype {prof.archetype.value}",
                f"Rating {prof.glicko.rating:.0f} | Peak {prof.peak_rating:.0f} | Titles {prof.tournament_titles} | Finals {prof.finals} | Podiums {prof.podiums} | Top8s {prof.top8s}",
                f"Wins {prof.wins} | Losses {prof.losses} | Win Rate {win_rate:.1f}% | Tournaments {prof.tournaments_entered} | Fame {prof.fame}",
                f"Money {prof.money} | Earnings {prof.career_earnings} | Sponsorship {prof.sponsorship}",
                f"Development {prof.development_focus} | Career Stage {self.display_title(prof)} | Signature {prof.signature_bakugan or 'N/A'}",
            ]
            if self.is_world_champion(prof):
                lines.append("World Champion Status: Active holder")
            champ_history = self.get_world_champion_history_for_profile(prof)
            if self.is_world_champion(prof):
                champ_season = prof.story_flags.get("world_champion_season") if isinstance(prof.story_flags, dict) else None
                if champ_season:
                    lines.append(f"Current Title: World Champion | Won in Season {champ_season}")
                else:
                    lines.append("Current Title: World Champion")
            if champ_history:
                seasons_text = ", ".join(str(s) for s in champ_history)
                if self.is_world_champion(prof):
                    lines.append(f"World Champion History: {seasons_text}")
                else:
                    lines.append(f"Past World Champion Seasons: {seasons_text}")
            if debug_mode:
                age_flags = prof.story_flags if isinstance(prof.story_flags, dict) else {}
                peak_age = age_flags.get('peak_age')
                retirement_age = age_flags.get('retirement_age')
                age_debug_bits = []
                if peak_age is not None:
                    age_debug_bits.append(f"Peak Age {int(peak_age)}")
                if retirement_age is not None:
                    age_debug_bits.append(f"Retirement Age {int(retirement_age)}")
                if age_debug_bits:
                    lines.append(" | ".join(age_debug_bits))
                lines.append(f"Training {prof.training_points}")
                lines.append(f"Stats: Roll {prof.rolling_skill:.2f} | Int {prof.intelligence:.2f} | Agg {prof.aggression:.2f} | Risk {prof.risk:.2f}")
            if total_matches == 0:
                lines.append("Record note: no completed matches recorded yet.")
            if prof.rivals:
                lines.append(f"Rivals: {', '.join(prof.rivals[:3])}")
                for rival_name in prof.rivals[:3]:
                    rec = prof.head_to_head.get(rival_name, {})
                    rw = int(rec.get('wins', 0))
                    rl = int(rec.get('losses', 0))
                    lines.append(f"  vs {rival_name}: {rw}-{rl}")
            if season is not None and event_no is not None:
                lines.append(f"Last used tournament loadout: Season {season} Event {event_no}")
            else:
                lines.append("Last used tournament loadout: no tournament snapshot yet, showing current active loadout")
            lines.append("")
            lines.extend(format_loadout_snapshot_lines(snap))
            text_widget.delete('1.0', 'end')
            text_widget.insert('1.0', '\n'.join(lines))

        query_var.trace_add('write', refresh_list)
        sort_var.trace_add('write', refresh_list)
        min_age_var.trace_add('write', refresh_list)
        max_age_var.trace_add('write', refresh_list)
        debug_sort_trace_id = self.debug_var.trace_add('write', refresh_sort_options)
        debug_list_trace_id = self.debug_var.trace_add('write', lambda *_: refresh_list())

        def _cleanup_search_profile_traces(_event=None):
            try:
                self.debug_var.trace_remove('write', debug_sort_trace_id)
            except Exception:
                pass
            try:
                self.debug_var.trace_remove('write', debug_list_trace_id)
            except Exception:
                pass

        win.bind('<Destroy>', _cleanup_search_profile_traces, add='+')
        listbox.bind('<<ListboxSelect>>', show_selected)
        refresh_sort_options()
        refresh_list()
        entry.focus_set()


    def view_tournament_history(self) -> None:
        archives = self.db.load_tournament_archives()
        if not archives:
            messagebox.showinfo("Tournament History", "No archived tournaments yet.", parent=self.root)
            return

        win = tk.Toplevel(self.root)
        win.title("Tournament History")
        win.geometry("1100x700")

        top = ttk.Frame(win, padding=8)
        top.pack(fill="both", expand=True)

        left = ttk.Frame(top)
        left.pack(side="left", fill="y")
        right = ttk.Frame(top)
        right.pack(side="left", fill="both", expand=True)

        season_counts: Dict[int, int] = defaultdict(int)
        for arc in archives:
            season_counts[int(arc.get('season', 0))] += 1

        ttk.Label(left, text=f"Archived tournaments: {len(archives)}").pack(anchor="w")
        ttk.Label(left, text=f"Seasons played: {len(season_counts)}").pack(anchor="w")
        ttk.Button(left, text="World Championship History", command=self.view_world_championship_history).pack(anchor="w", pady=(4, 8))

        listbox = tk.Listbox(left, width=44, height=34)
        listbox.pack(fill="y", expand=True)
        text_widget = tk.Text(right, width=90, height=40)
        text_widget.pack(fill="both", expand=True)

        display_items = []
        for arc in archives:
            event_label = "WC" if int(arc.get('event_no', 0)) == 0 and arc.get('tournament_type') == WORLD_CUP_TOURNAMENT_LABEL else f"E{int(arc['event_no']):03d}"
            league_part = f" | {arc.get('league')}" if arc.get('league') else ""
            label = f"S{int(arc['season']):02d} {event_label}{league_part} | {arc['tournament_type']} | {arc['participant_count']} players | Winner {arc.get('winner','?')}"
            display_items.append((label, arc['archive_id']))
            listbox.insert('end', label)

        def on_select(event=None):
            sel = listbox.curselection()
            if not sel:
                return
            _, archive_id = display_items[sel[0]]
            arc = self.db.load_archive_by_id(archive_id)
            if not arc:
                return
            lines = summarize_archive_lines(arc)
            text_widget.delete('1.0', 'end')
            text_widget.insert('end', '\n'.join(lines))

        listbox.bind('<<ListboxSelect>>', on_select)
        if display_items:
            listbox.selection_set(0)
            on_select()


    def view_world_championship_history(self) -> None:
        history = self.world_champion_history if isinstance(self.world_champion_history, list) else []
        archives = [arc for arc in self.db.load_tournament_archives() if arc.get("tournament_type") == WORLD_CUP_TOURNAMENT_LABEL or (int(arc.get("event_no", 0)) == 0 and arc.get("special_event"))]
        win = tk.Toplevel(self.root)
        win.title("World Championship History")
        win.geometry("900x700")
        text_widget = tk.Text(win, width=100, height=40, wrap="word")
        text_widget.pack(fill="both", expand=True)
        lines: List[str] = ["========== WORLD CHAMPIONSHIP HISTORY =========="]
        if not history:
            lines.append("No World Championships recorded yet.")
        else:
            current_name = self.current_world_champion.get("name") if isinstance(self.current_world_champion, dict) else None
            for idx, item in enumerate(history, start=1):
                season = int(item.get("season", 0)) if isinstance(item, dict) else 0
                winner = item.get("winner", "?") if isinstance(item, dict) else "?"
                previous = item.get("previous_champion") if isinstance(item, dict) else None
                retained = bool(item.get("retained")) if isinstance(item, dict) else False
                status = "Current holder" if current_name == winner and isinstance(self.current_world_champion, dict) and int(self.current_world_champion.get("season", 0)) == season else ("Retained" if retained else "New champion")
                lines.append(f"{idx}. Season {season}: {winner} | {status}")
                if previous and previous != winner:
                    lines.append(f"   Dethroned: {previous}")
        wc_archives = sorted(archives, key=lambda a: int(a.get("season", 0)))
        if wc_archives:
            lines.append("")
            lines.append("========== WORLD CUP EVENTS ==========")
            for arc in wc_archives:
                season = int(arc.get("season", 0))
                winner = arc.get("winner", "?")
                participants = int(arc.get("participant_count", 0))
                lines.append(f"Season {season}: Winner {winner} | Participants {participants} | Archive {arc.get('archive_id', '?')}")
        text_widget.insert("1.0", "\n".join(lines))
        text_widget.configure(state="disabled")


    def view_season_summary(self) -> None:
        archives = self.db.load_tournament_archives()
        if not archives:
            messagebox.showinfo("Season Summary", "No archived tournaments yet.", parent=self.root)
            return

        grouped = group_archives_by_season(archives)
        seasons = sorted(grouped.keys(), reverse=True)

        win = tk.Toplevel(self.root)
        win.title("Season Summary")
        win.geometry("1100x700")

        top = ttk.Frame(win, padding=8)
        top.pack(fill="both", expand=True)

        left = ttk.Frame(top)
        left.pack(side="left", fill="y")
        right = ttk.Frame(top)
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text=f"Seasons available: {len(seasons)}").pack(anchor="w", pady=(0, 8))
        listbox = tk.Listbox(left, width=24, height=34)
        listbox.pack(fill="y", expand=True)
        text_widget = tk.Text(right, width=90, height=40)
        text_widget.pack(fill="both", expand=True)

        for season in seasons:
            listbox.insert("end", f"Season {season}")

        def on_select(event=None):
            sel = listbox.curselection()
            if not sel:
                return
            season = seasons[sel[0]]
            lines = build_season_summary_lines(archives, season, self.player.name if self.player else None)
            text_widget.delete("1.0", "end")
            text_widget.insert("end", "\n".join(lines))

        listbox.bind("<<ListboxSelect>>", on_select)
        if seasons:
            listbox.selection_set(0)
            on_select()


    def new_character(self) -> None:
        name = simpledialog.askstring("Name", "Enter your character name:", parent=self.root)
        if not name:
            return
        attr = simpledialog.askstring("Attribute", "Choose attribute: Pyrus, Aquos, Subterra, Haos, Darkus, Ventus", parent=self.root)
        if not attr:
            return
        try:
            chosen_attribute = Attribute(attr.capitalize())
        except Exception:
            messagebox.showerror("Invalid attribute", "Please enter a valid attribute.", parent=self.root)
            return

        win = tk.Toplevel(self.root)
        win.title("Stat Priorities")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="Choose your stat priority from highest to lowest.").grid(row=0, column=0, columnspan=2, padx=8, pady=(8, 4), sticky="w")
        options = ["agg", "roll", "int", "risk"]
        labels = ["1st priority", "2nd priority", "3rd priority", "4th priority"]
        vars_ = []
        defaults = ["roll", "int", "agg", "risk"]
        for i, lab in enumerate(labels, start=1):
            ttk.Label(win, text=lab).grid(row=i, column=0, padx=8, pady=4, sticky="w")
            var = tk.StringVar(value=defaults[i-1])
            cb = ttk.Combobox(win, textvariable=var, values=options, state="readonly", width=12)
            cb.grid(row=i, column=1, padx=8, pady=4, sticky="w")
            vars_.append(var)

        ttk.Label(win, text="World Cup interval (seasons)").grid(row=5, column=0, padx=8, pady=4, sticky="w")
        world_cup_var = tk.StringVar(value=str(max(1, int(getattr(self, 'world_cup_interval', WORLD_CUP_INTERVAL_DEFAULT)))))
        ttk.Entry(win, textvariable=world_cup_var, width=12).grid(row=5, column=1, padx=8, pady=4, sticky='w')
        season_bans_var = tk.BooleanVar(value=bool(getattr(self, 'season_ban_settings', {}).get('enabled', False)))
        ttk.Checkbutton(win, text='Enable seasonal ban list', variable=season_bans_var).grid(row=6, column=0, columnspan=2, padx=8, pady=4, sticky='w')
        age_enabled_var = tk.BooleanVar(value=bool(getattr(self, 'age_progression_enabled', False)))
        ttk.Checkbutton(win, text='Enable ages / retirement system', variable=age_enabled_var).grid(row=7, column=0, columnspan=2, padx=8, pady=4, sticky='w')
        ttk.Label(win, text="Starting age").grid(row=8, column=0, padx=8, pady=4, sticky="w")
        player_age_var = tk.StringVar(value=str(PLAYER_DEFAULT_AGE))
        ttk.Entry(win, textvariable=player_age_var, width=12).grid(row=8, column=1, padx=8, pady=4, sticky='w')

        result = {"ok": False, "priority": None, "world_cup_interval": WORLD_CUP_INTERVAL_DEFAULT, "season_bans_enabled": False, "age_enabled": False, "player_age": PLAYER_DEFAULT_AGE}

        def confirm() -> None:
            chosen = [v.get() for v in vars_]
            if sorted(chosen) != sorted(options):
                messagebox.showerror("Invalid priorities", "Choose each stat exactly once.", parent=win)
                return
            try:
                interval = max(1, int(world_cup_var.get().strip()))
            except Exception:
                messagebox.showerror("Invalid World Cup interval", "Enter a whole number of seasons.", parent=win)
                return
            try:
                player_age = max(PLAYER_MIN_AGE, int(player_age_var.get().strip() or str(PLAYER_DEFAULT_AGE)))
            except Exception:
                messagebox.showerror("Invalid age", f"Enter a whole number age of at least {PLAYER_MIN_AGE}.", parent=win)
                return
            result["ok"] = True
            result["priority"] = chosen
            result["world_cup_interval"] = interval
            result["season_bans_enabled"] = bool(season_bans_var.get())
            result["age_enabled"] = bool(age_enabled_var.get())
            result["player_age"] = player_age
            win.destroy()

        ttk.Button(win, text="Create Character", command=confirm).grid(row=9, column=0, padx=8, pady=8, sticky="w")
        ttk.Button(win, text="Cancel", command=win.destroy).grid(row=9, column=1, padx=8, pady=8, sticky="e")

        self.root.wait_window(win)
        if not result["ok"]:
            return

        # Fresh world for a brand new character
        self.db.reset_world()
        self.world_season = 1
        self.world_tournament_no = 0
        self.world_total_tournaments = 0
        self.world_seed = self.rng.randint(1, 2_000_000_000)
        self.db.set_world_int("world_season", self.world_season)
        self.db.set_world_int("world_tournament_no", self.world_tournament_no)
        self.db.set_world_int("world_total_tournaments", self.world_total_tournaments)
        self.db.set_world_int("world_seed", self.world_seed)
        self.world_cup_interval = max(1, int(result.get("world_cup_interval", WORLD_CUP_INTERVAL_DEFAULT)))
        self.world_cup_new_npcs = max(0, int(result.get("world_cup_new_npcs", WORLD_CUP_NEW_NPCS_DEFAULT)))
        self.age_progression_enabled = bool(result.get("age_enabled", False))
        self.season_new_npcs = SEASON_NEW_NPCS_DEFAULT
        self.current_world_champion = None
        self.world_champion_history = []
        self.world_cup_new_npcs = WORLD_CUP_NEW_NPCS_DEFAULT
        self.season_ban_settings = dict(SEASON_BAN_DEFAULTS)
        self.season_ban_settings["enabled"] = bool(result.get("season_bans_enabled", False))
        self.current_season_bans = empty_season_ban_state(self.world_season)
        self.season_ban_history = []
        self.db.set_world_int("world_cup_interval", self.world_cup_interval)
        self.db.set_world_json("current_world_champion", None)
        self.db.set_world_json("world_champion_history", [])
        self.db.set_world_int("world_cup_new_npcs", self.world_cup_new_npcs)
        self.db.set_world_json("season_ban_settings", self.season_ban_settings)
        self.db.set_world_json("current_season_bans", self.current_season_bans)
        self.db.set_world_json("season_ban_history", [])
        self.db.set_world_int("age_progression_enabled", int(self.age_progression_enabled))
        self.db.set_world_int("season_new_npcs", self.season_new_npcs)
        self.db.set_world_int("npc_target_population", self.npc_target_population)
        self.player = draft_starting_profile(name, chosen_attribute, self.rng, True, stat_priority=result["priority"], starting_age=int(result.get("player_age", PLAYER_DEFAULT_AGE)))
        self.player.development_focus = "Balanced"
        self.player.update_signature()
        self.ensure_npc_universe()
        self.get_season_shop_stock()
        self.refresh_status()
        pr = result["priority"]
        self.current_save_stem = f"session_{self.player.name}"
        set_current_output_dir(self.current_save_stem)
        self.append_text(
            f"Created character {self.player.name} with attribute {self.player.chosen_attribute.value}. "
            f"Priority order: {pr[0]} > {pr[1]} > {pr[2]} > {pr[3]}. "
            f"World Cup every {self.world_cup_interval} seasons, +{self.world_cup_new_npcs} NPCs after each World Cup, +{self.season_new_npcs} NPCs each season. Ages {'enabled' if self.age_progression_enabled else 'disabled'}. Seasonal bans {'enabled' if self.season_ban_settings.get('enabled') else 'disabled'}. "
            f"Stats: Roll {self.player.rolling_skill:.2f}, Int {self.player.intelligence:.2f}, Agg {self.player.aggression:.2f}, Risk {self.player.risk:.2f}"
        )
        self.update_debug_controls()


    def view_card_reference(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Card Reference")
        win.geometry("1080x760")

        top = ttk.Frame(win, padding=8)
        top.pack(fill="both", expand=True)
        controls = ttk.Frame(top)
        controls.pack(fill="x")

        mode_var = tk.StringVar(value="Gate Cards")
        search_var = tk.StringVar(value="")
        count_var = tk.StringVar(value="")

        ttk.Radiobutton(controls, text="Gate Cards", variable=mode_var, value="Gate Cards").pack(side="left", padx=4)
        ttk.Radiobutton(controls, text="Ability Cards", variable=mode_var, value="Ability Cards").pack(side="left", padx=4)
        ttk.Label(controls, text="Search:").pack(side="left", padx=(16,4))
        search_entry = ttk.Entry(controls, textvariable=search_var, width=36)
        search_entry.pack(side="left", padx=4, fill="x", expand=True)
        ttk.Label(controls, textvariable=count_var).pack(side="right", padx=4)

        text_widget = tk.Text(top, width=120, height=40, wrap="word")
        text_widget.pack(fill="both", expand=True)

        def gate_lines(query: str) -> list[str]:
            lines = ["GATE CARDS"]
            count = 0
            q = query.lower().strip()
            for g in sorted(self.gates, key=lambda x: (x.gate_type.value, x.name)):
                bonus_text = ", ".join(f"{attr.value} {g.bonuses.get(attr, 0)}" for attr in [Attribute.PYRUS, Attribute.AQUOS, Attribute.SUBTERRA, Attribute.HAOS, Attribute.DARKUS, Attribute.VENTUS])
                hay = f"{g.name} {g.gate_type.value} {bonus_text} {g.description}".lower()
                if q and q not in hay:
                    continue
                count += 1
                lines.append(f"{g.name} | {g.gate_type.value}")
                lines.append(f"  Bonuses: {bonus_text}")
                lines.append(f"  Effect: {g.description}")
                lines.append("")
            count_var.set(f"{count} shown")
            if count == 0:
                lines.append("No matching gate cards.")
            return lines

        def ability_lines(query: str) -> list[str]:
            lines = ["ABILITY CARDS"]
            count = 0
            q = query.lower().strip()
            for a in sorted(self.abilities, key=lambda x: (x.color.value, x.name)):
                hay = f"{a.name} {a.color.value} {a.description}".lower()
                if q and q not in hay:
                    continue
                count += 1
                lines.append(f"{a.name} | {a.color.value}")
                lines.append(f"  Effect: {a.description}")
                lines.append("")
            count_var.set(f"{count} shown")
            if count == 0:
                lines.append("No matching ability cards.")
            return lines

        def refresh(*_args) -> None:
            text_widget.config(state="normal")
            text_widget.delete("1.0", "end")
            q = search_var.get()
            lines = gate_lines(q) if mode_var.get() == "Gate Cards" else ability_lines(q)
            text_widget.insert("1.0", "\n".join(lines))
            text_widget.config(state="disabled")

        mode_var.trace_add("write", refresh)
        search_var.trace_add("write", refresh)
        refresh()
        search_entry.focus_set()


    def view_loadout(self) -> None:
        if not self.require_player():
            return
        lines = player_loadout_lines(self.player)
        self.append_text("\n".join(lines))


    def customise_loadout(self) -> None:
        if not self.require_player():
            return

        win = tk.Toplevel(self.root)
        win.title("Customise Loadout")
        win.transient(self.root)
        win.grab_set()

        pad = {"padx": 6, "pady": 4}

        def bakugan_label(idx: int) -> str:
            b = self.player.collection_bakugan[idx]
            return f"[{idx}] {b.name} | {b.attribute.value} | {b.base_g} G"

        def gate_label(idx: int) -> str:
            g = self.player.collection_gates[idx]
            return f"[{idx}] {g.name} | {g.gate_type.value}"

        def ability_label(idx: int) -> str:
            a = self.player.collection_abilities[idx]
            return f"[{idx}] {a.name} | {a.color.value}"

        ttk.Label(
            win,
            text="Pick your active loadout using the drop-downs below.",
        ).grid(row=0, column=0, columnspan=2, sticky="w", **pad)

        body = ttk.Frame(win)
        body.grid(row=1, column=0, columnspan=2, sticky="nsew", **pad)
        win.columnconfigure(0, weight=1)
        win.rowconfigure(1, weight=1)
        body.columnconfigure(1, weight=1)

        ttk.Label(body, text="Bakugan 1").grid(row=0, column=0, sticky="w", **pad)
        ttk.Label(body, text="Bakugan 2").grid(row=1, column=0, sticky="w", **pad)
        ttk.Label(body, text="Bakugan 3").grid(row=2, column=0, sticky="w", **pad)
        bak_values = [bakugan_label(i) for i in range(len(self.player.collection_bakugan))]
        bak_vars = []
        current_bak = list(self.player.active_bakugan_idx[:3])
        while len(current_bak) < 3 and self.player.collection_bakugan:
            current_bak.append(0)
        for row in range(3):
            initial = bakugan_label(current_bak[row]) if self.player.collection_bakugan else ""
            var = tk.StringVar(value=initial)
            bak_vars.append(var)
            cb = ttk.Combobox(body, textvariable=var, values=bak_values, state="readonly", width=44)
            cb.grid(row=row, column=1, sticky="ew", **pad)

        gate_options = {
            GateType.GOLD: [i for i, g in enumerate(self.player.collection_gates) if g.gate_type == GateType.GOLD],
            GateType.SILVER: [i for i, g in enumerate(self.player.collection_gates) if g.gate_type == GateType.SILVER],
            GateType.BRONZE: [i for i, g in enumerate(self.player.collection_gates) if g.gate_type == GateType.BRONZE],
        }
        gate_vars = {}
        row_no = 3
        for gt in [GateType.GOLD, GateType.SILVER, GateType.BRONZE]:
            ttk.Label(body, text=f"{gt.value} Gate").grid(row=row_no, column=0, sticky="w", **pad)
            values = [gate_label(i) for i in gate_options[gt]]
            current_idx = next(
                (i for i in self.player.active_gate_idx if 0 <= i < len(self.player.collection_gates) and self.player.collection_gates[i].gate_type == gt),
                gate_options[gt][0] if gate_options[gt] else None,
            )
            initial = gate_label(current_idx) if current_idx is not None else ""
            var = tk.StringVar(value=initial)
            gate_vars[gt] = var
            cb = ttk.Combobox(body, textvariable=var, values=values, state="readonly", width=44)
            cb.grid(row=row_no, column=1, sticky="ew", **pad)
            row_no += 1

        ability_options = {
            AbilityColor.RED: [i for i, a in enumerate(self.player.collection_abilities) if a.color == AbilityColor.RED],
            AbilityColor.BLUE: [i for i, a in enumerate(self.player.collection_abilities) if a.color == AbilityColor.BLUE],
            AbilityColor.GREEN: [i for i, a in enumerate(self.player.collection_abilities) if a.color == AbilityColor.GREEN],
        }
        ability_vars = {}
        for color in [AbilityColor.RED, AbilityColor.BLUE, AbilityColor.GREEN]:
            ttk.Label(body, text=f"{color.value} Ability").grid(row=row_no, column=0, sticky="w", **pad)
            values = [ability_label(i) for i in ability_options[color]]
            current_idx = next(
                (i for i in self.player.active_ability_idx if 0 <= i < len(self.player.collection_abilities) and self.player.collection_abilities[i].color == color),
                ability_options[color][0] if ability_options[color] else None,
            )
            initial = ability_label(current_idx) if current_idx is not None else ""
            var = tk.StringVar(value=initial)
            ability_vars[color] = var
            cb = ttk.Combobox(body, textvariable=var, values=values, state="readonly", width=44)
            cb.grid(row=row_no, column=1, sticky="ew", **pad)
            row_no += 1

        preview = tk.Text(win, width=72, height=10)
        preview.grid(row=2, column=0, columnspan=2, sticky="nsew", **pad)
        win.rowconfigure(2, weight=1)

        def parse_index(label: str) -> Optional[int]:
            if not label.startswith("["):
                return None
            try:
                return int(label[1:].split("]", 1)[0])
            except Exception:
                return None

        def refresh_preview(*_args) -> None:
            lines = ["Selected loadout:"]
            for idx, var in enumerate(bak_vars, start=1):
                lines.append(f"Bakugan {idx}: {var.get()}")
            for gt in [GateType.GOLD, GateType.SILVER, GateType.BRONZE]:
                lines.append(f"{gt.value} Gate: {gate_vars[gt].get()}")
            for color in [AbilityColor.RED, AbilityColor.BLUE, AbilityColor.GREEN]:
                lines.append(f"{color.value} Ability: {ability_vars[color].get()}")
            bak = [parse_index(v.get()) for v in bak_vars]
            gates = [parse_index(gate_vars[gt].get()) for gt in [GateType.GOLD, GateType.SILVER, GateType.BRONZE]]
            abilities = [parse_index(ability_vars[c].get()) for c in [AbilityColor.RED, AbilityColor.BLUE, AbilityColor.GREEN]]
            if all(x is not None for x in bak + gates + abilities) and len(set(bak)) == 3:
                old_bak = list(self.player.active_bakugan_idx)
                old_gate = list(self.player.active_gate_idx)
                old_ability = list(self.player.active_ability_idx)
                try:
                    self.player.active_bakugan_idx = bak
                    self.player.active_gate_idx = gates
                    self.player.active_ability_idx = abilities
                    score = score_active_loadout(self.player)
                    lines.append("")
                    lines.append(f"Loadout rating: {score['rating']}/100")
                    lines.append(f"Synergy: {score['synergy']}/30")
                    lines.append(f"Power: {score['power']}/50")
                    lines.append(f"Flexibility: {score['flexibility']}/20")
                finally:
                    self.player.active_bakugan_idx = old_bak
                    self.player.active_gate_idx = old_gate
                    self.player.active_ability_idx = old_ability
            preview.configure(state="normal")
            preview.delete("1.0", "end")
            preview.insert("1.0", "\n".join(lines))
            preview.configure(state="disabled")

        for var in bak_vars + list(gate_vars.values()) + list(ability_vars.values()):
            var.trace_add("write", refresh_preview)
        refresh_preview()

        def save_changes() -> None:
            bak = [parse_index(v.get()) for v in bak_vars]
            gates = [parse_index(gate_vars[gt].get()) for gt in [GateType.GOLD, GateType.SILVER, GateType.BRONZE]]
            abilities = [parse_index(ability_vars[c].get()) for c in [AbilityColor.RED, AbilityColor.BLUE, AbilityColor.GREEN]]

            if any(x is None for x in bak + gates + abilities):
                messagebox.showerror("Invalid selection", "Please select one item for every slot.", parent=win)
                return
            if len(set(bak)) != 3:
                messagebox.showerror("Invalid Bakugan", "Please choose 3 different Bakugan.", parent=win)
                return

            old_bak = list(self.player.active_bakugan_idx)
            old_gate = list(self.player.active_gate_idx)
            old_ability = list(self.player.active_ability_idx)

            self.player.active_bakugan_idx = bak
            self.player.active_gate_idx = gates
            self.player.active_ability_idx = abilities
            self.player.ensure_valid_loadout()
            ok1, msg1 = validate_bakugan_selection(self.player.active_bakugan_idx, self.player.collection_bakugan)
            ok2, msg2 = validate_gate_selection(self.player.active_gate_idx, self.player.collection_gates)
            ok3, msg3 = validate_ability_selection(self.player.active_ability_idx, self.player.collection_abilities)
            if not (ok1 and ok2 and ok3):
                self.player.active_bakugan_idx = old_bak
                self.player.active_gate_idx = old_gate
                self.player.active_ability_idx = old_ability
                messagebox.showerror("Invalid loadout", msg1 if not ok1 else msg2 if not ok2 else msg3, parent=win)
                return

            self.append_text("Updated active loadout.")
            self.refresh_status()
            win.destroy()

        btns = ttk.Frame(win)
        btns.grid(row=3, column=0, columnspan=2, pady=8)
        ttk.Button(btns, text="Save Loadout", command=save_changes).grid(row=0, column=0, padx=6)
        ttk.Button(btns, text="Cancel", command=win.destroy).grid(row=0, column=1, padx=6)


    def open_shop(self) -> None:
        if not self.require_player():
            return
        shop = tk.Toplevel(self.root)
        shop.title("Shop")
        stock = self.get_season_shop_stock()

        def bakugan_rarity(template: BakuganTemplate) -> str:
            max_g = max(template.g_powers)
            name = template.name.lower()
            evolved_keywords = [
                "delta", "neo", "ultimate", "cross", "helix", "blade", "hammer", "master",
                "knight", "minx", "alpha", "dual", "viper", "cyborg", "rex", "mega",
                "saint", "magma", "cosmic", "midnight", "titanium", "lumino", "infinity", "blitz"
            ]
            evolved = any(k in name for k in evolved_keywords)
            if max_g >= 560 or template.price >= 500:
                return "Legendary"
            if max_g >= 500 or template.price >= 380 or evolved:
                return "Epic"
            if max_g >= 440 or template.price >= 240:
                return "Rare"
            return "Common"

        def card_rarity(card) -> str:
            price = getattr(card, 'price', 100)
            if price >= 160:
                return "Legendary"
            if price >= 130:
                return "Epic"
            if price >= 105:
                return "Rare"
            return "Common"

        def bakugan_shop_price(template: BakuganTemplate) -> int:
            mult = {"Common": 1.00, "Rare": 1.15, "Epic": 1.35, "Legendary": 1.60}[bakugan_rarity(template)]
            return int(round(template.price * mult / 5.0) * 5)

        def card_shop_price(card) -> int:
            mult = {"Common": 1.00, "Rare": 1.10, "Epic": 1.25, "Legendary": 1.40}[card_rarity(card)]
            base = getattr(card, 'price', 100)
            return int(round(base * mult / 5.0) * 5)

        def seasonal_stock(full_items, season_seed: int, count: int, key_fn):
            if len(full_items) <= count:
                return list(full_items)
            local_rng = random.Random(season_seed)
            decorated = []
            for idx, item in enumerate(full_items):
                decorated.append((local_rng.random(), key_fn(item), idx, item))
            decorated.sort(key=lambda x: (x[0], x[1], x[2]))
            picked = [item for _, _, _, item in decorated[:count]]
            picked.sort(key=key_fn)
            return picked

        baku_map = {template_stock_key(t): t for t in self.templates}
        gate_map = {gate_stock_key(g): g for g in self.gates}
        ability_map = {ability_stock_key(a): a for a in self.abilities}
        bakugan_stock = [baku_map[k] for k in stock.get("bakugan_selection", []) if k in baku_map]
        gate_stock = [gate_map[k] for k in stock.get("gate_selection", []) if k in gate_map]
        ability_stock = [ability_map[k] for k in stock.get("ability_selection", []) if k in ability_map]

        loot_boxes = [
            {
                "code": "L0",
                "name": "Starter Loot Box",
                "price": 150,
                "tier_weights": {"Common": 82, "Rare": 16, "Epic": 2, "Legendary": 0},
                "card_weights": {"Common": 78, "Rare": 18, "Epic": 4, "Legendary": 0},
                "text": "Cheap box. Mostly base forms and lower-tier cards.",
            },
            {
                "code": "L1",
                "name": "Lucky Loot Box",
                "price": 220,
                "tier_weights": {"Common": 45, "Rare": 38, "Epic": 15, "Legendary": 2},
                "card_weights": {"Common": 40, "Rare": 38, "Epic": 18, "Legendary": 4},
                "text": "Balanced odds. Better chance at evolved and stronger pulls.",
            },
            {
                "code": "L2",
                "name": "Elite Loot Box",
                "price": 320,
                "tier_weights": {"Common": 18, "Rare": 35, "Epic": 32, "Legendary": 15},
                "card_weights": {"Common": 15, "Rare": 30, "Epic": 35, "Legendary": 20},
                "text": "Best odds for evolved anime Bakugan and premium cards.",
            },
        ]

        text_widget = tk.Text(shop, width=120, height=34)
        text_widget.pack(fill="both", expand=True)

        text_widget.insert("end", f"Money: £{self.player.money}\n")
        text_widget.insert("end", f"Season {self.world_season} rotating selection (player stock is unlimited)\n\n")
        text_widget.insert("end", "Bakugan:\n")
        for i, t in enumerate(bakugan_stock):
            attrs = ", ".join(a.value for a in t.allowed_attributes)
            text_widget.insert("end", f"B{i}: {t.name} | {bakugan_rarity(t)} | attrs {attrs} | G {t.g_powers[0]}-{t.g_powers[-1]} | £{bakugan_shop_price(t)} | Stock ∞\n")
        text_widget.insert("end", "\nGate Cards:\n")
        for i, g in enumerate(gate_stock):
            text_widget.insert("end", f"G{i}: {g.name} | {g.gate_type.value} | {card_rarity(g)} | £{card_shop_price(g)} | Stock ∞\n")
        text_widget.insert("end", "\nAbility Cards:\n")
        for i, a in enumerate(ability_stock):
            text_widget.insert("end", f"A{i}: {a.name} | {a.color.value} | {card_rarity(a)} | £{card_shop_price(a)} | Stock ∞\n")
        text_widget.insert("end", "\nLoot Boxes:\n")
        for box in loot_boxes:
            tw = box['tier_weights']
            text_widget.insert("end", f"{box['code']}: {box['name']} | £{box['price']} | Stock ∞ | {box['text']} | Bakugan odds C/R/E/L: {tw['Common']}/{tw['Rare']}/{tw['Epic']}/{tw['Legendary']}\n")

        controls = ttk.Frame(shop)
        controls.pack(fill="x")

        def weighted_choice(items, weight_fn):
            weighted = []
            for item in items:
                w = max(0.0, float(weight_fn(item)))
                if w > 0:
                    weighted.append((w, item))
            if not weighted:
                return self.rng.choice(items)
            total = sum(w for w, _ in weighted)
            roll = self.rng.random() * total
            running = 0.0
            for weight, item in weighted:
                running += weight
                if running >= roll:
                    return item
            return weighted[-1][1]

        def weighted_loot_template(box: Dict) -> BakuganTemplate:
            tier_weights = box['tier_weights']
            def w(template: BakuganTemplate):
                rarity = bakugan_rarity(template)
                strength_bias = max(template.g_powers) / 100.0
                return tier_weights.get(rarity, 0) * (0.8 + strength_bias * 0.05)
            return weighted_choice(self.templates, w)

        def weighted_loot_card(box: Dict):
            card_pool = self.gates + self.abilities
            tier_weights = box['card_weights']
            def w(card):
                rarity = card_rarity(card)
                return tier_weights.get(rarity, 0)
            base_card = weighted_choice(card_pool, w)
            if isinstance(base_card, GateCard):
                return clone_gate(base_card), f"Gate Card {base_card.name}"
            return clone_ability(base_card), f"Ability Card {base_card.name}"

        def open_loot_box(box: Dict) -> None:
            if self.player.money < box["price"]:
                raise ValueError("Not enough money")
            chosen_template = weighted_loot_template(box)
            forced_attr = self.player.chosen_attribute if self.player.chosen_attribute in chosen_template.allowed_attributes and self.rng.random() < 0.55 else None
            bakugan_item = chosen_template.roll_instance(self.player.name, self.rng, forced_attr)
            if box["code"] == "L0":
                lower_half = chosen_template.g_powers[: max(1, len(chosen_template.g_powers)//2)]
                bakugan_item.base_g = self.rng.choice(lower_half)
            elif box["code"] == "L2":
                upper_half = chosen_template.g_powers[max(0, len(chosen_template.g_powers)//2):]
                bakugan_item.base_g = self.rng.choice(upper_half)

            card, card_desc = weighted_loot_card(box)
            self.player.collection_bakugan.append(bakugan_item)
            if isinstance(card, GateCard):
                self.player.collection_gates.append(card)
            else:
                self.player.collection_abilities.append(card)
            self.player.money -= box["price"]
            self.append_text(
                f"Opened {box['name']}: {bakugan_item.name} {bakugan_item.attribute.value} {bakugan_item.base_g} G "
                f"[{bakugan_rarity(chosen_template)}] and {card_desc} [{card_rarity(card)}] for £{box['price']}"
            )

        def buy():
            code = simpledialog.askstring("Buy", "Enter item code, for example B0, G1, A2, L0", parent=shop)
            if not code:
                return
            code = code.strip().upper()
            try:
                if code.startswith("B"):
                    idx = int(code[1:])
                    if idx < 0 or idx >= len(bakugan_stock):
                        raise ValueError("Invalid Bakugan code for this season's stock")
                    t = bakugan_stock[idx]
                    price = bakugan_shop_price(t)
                    if self.player.money < price:
                        raise ValueError("Not enough money")
                    forced_attr = self.player.chosen_attribute if self.player.chosen_attribute in t.allowed_attributes and self.rng.random() < 0.5 else None
                    item = t.roll_instance(self.player.name, self.rng, forced_attr)
                    self.player.collection_bakugan.append(item)
                    self.player.money -= price
                    self.append_text(f"Bought Bakugan: {item.name} {item.attribute.value} {item.base_g} G [{bakugan_rarity(t)}] for £{price}")
                elif code.startswith("G"):
                    idx = int(code[1:])
                    if idx < 0 or idx >= len(gate_stock):
                        raise ValueError("Invalid Gate Card code for this season's stock")
                    g = clone_gate(gate_stock[idx])
                    price = card_shop_price(g)
                    if self.player.money < price:
                        raise ValueError("Not enough money")
                    self.player.collection_gates.append(g)
                    self.player.money -= price
                    self.append_text(f"Bought Gate Card: {g.name} [{card_rarity(g)}] for £{price}")
                elif code.startswith("A"):
                    idx = int(code[1:])
                    if idx < 0 or idx >= len(ability_stock):
                        raise ValueError("Invalid Ability Card code for this season's stock")
                    a = clone_ability(ability_stock[idx])
                    price = card_shop_price(a)
                    if self.player.money < price:
                        raise ValueError("Not enough money")
                    self.player.collection_abilities.append(a)
                    self.player.money -= price
                    self.append_text(f"Bought Ability Card: {a.name} [{card_rarity(a)}] for £{price}")
                elif code.startswith("L"):
                    idx = int(code[1:])
                    if idx < 0 or idx >= len(loot_boxes):
                        raise ValueError("Invalid loot box code")
                    open_loot_box(loot_boxes[idx])
                else:
                    raise ValueError("Invalid code")
                self.player.ensure_valid_loadout()
                self.refresh_status()
                self.autosave_current_game()
                shop.destroy()
                self.open_shop()
            except Exception as e:
                messagebox.showerror("Purchase failed", str(e), parent=shop)

        ttk.Button(controls, text="Buy Item", command=buy).pack(side="left", padx=4, pady=4)


    def autosave_current_game(self, completed_season: Optional[int] = None) -> Optional[Path]:
        payload = self._build_save_payload()
        path = SAVE_DIR / "autosave_latest.json.gz"
        write_save_payload(path, payload)
        checkpoint_season = int(completed_season or 0)
        if checkpoint_season > 0 and checkpoint_season % max(1, int(getattr(self, "autosave_interval_seasons", 5) or 5)) == 0:
            checkpoint_name = f"autosave_season_{checkpoint_season}.json.gz"
            write_save_payload(SAVE_DIR / checkpoint_name, payload)
        return path


    def save_character_json(self) -> None:
        if self.player is not None:
            default_name = build_save_filename(self.player.name, random_suffix(self.rng))
        else:
            default_name = f"save_world_season_{self.world_season}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random_suffix(self.rng)}.json.gz"
        file_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save Game",
            initialdir=str(SAVE_DIR),
            initialfile=default_name,
            defaultextension=".json.gz",
            filetypes=[("Compressed save", "*.json.gz"), ("JSON save", "*.json")],
        )
        if not file_path:
            return
        path = Path(file_path)
        payload = self._build_save_payload()
        write_save_payload(path, payload)
        self.current_save_stem = path.stem
        set_current_output_dir(self.current_save_stem)
        self.autosave_current_game()
        self.append_text(f"Saved game to {path}")
        self.append_text(f"Tournament exports for this save go to {get_current_output_dir()}")


    def load_character_json(self) -> None:
        initial = SAVE_DIR / "autosave_latest.json.gz"
        if not initial.exists():
            initial = SAVE_DIR / "autosave_latest.json"
        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Load Save",
            initialdir=str(SAVE_DIR),
            initialfile=(initial.name if initial.exists() else ""),
            filetypes=[("Compressed save", "*.json.gz"), ("JSON save", "*.json")],
        )
        if not file_path:
            return
        try:
            payload = read_save_payload(Path(file_path))
            if isinstance(payload, dict) and "db_state" in payload:
                self._import_db_state(payload.get("db_state") or {})
            player, world_season, world_tournament_no, world_total_tournaments, world_seed = deserialize_savegame(payload)
            if player is not None:
                player.ensure_valid_loadout()
                player.update_career_stage()
                player.update_signature()
            self.player = player
            self.current_save_stem = Path(file_path).stem
            set_current_output_dir(self.current_save_stem)
            self.world_season = world_season
            self.world_tournament_no = world_tournament_no
            self.world_total_tournaments = world_total_tournaments
            self.world_seed = world_seed or self.rng.randint(1, 2_000_000_000)
            self.db.set_world_int("world_season", self.world_season)
            self.db.set_world_int("world_tournament_no", self.world_tournament_no)
            self.db.set_world_int("world_total_tournaments", self.world_total_tournaments)
            self.db.set_world_int("world_seed", self.world_seed)
            self.world_cup_interval = max(1, self.db.get_world_int("world_cup_interval", WORLD_CUP_INTERVAL_DEFAULT))
            self.current_world_champion = self.db.get_world_json("current_world_champion", None)
            self.world_champion_history = self.db.get_world_json("world_champion_history", []) or []
            self.world_cup_new_npcs = int(self.db.get_world_int("world_cup_new_npcs", WORLD_CUP_NEW_NPCS_DEFAULT) or WORLD_CUP_NEW_NPCS_DEFAULT)
            self.season_ban_settings = self.db.get_world_json("season_ban_settings", dict(SEASON_BAN_DEFAULTS)) or dict(SEASON_BAN_DEFAULTS)
            self.current_season_bans = self.db.get_world_json("current_season_bans", empty_season_ban_state(self.world_season)) or empty_season_ban_state(self.world_season)
            self.season_ban_history = self.db.get_world_json("season_ban_history", []) or []
            self.age_progression_enabled = bool(self.db.get_world_int("age_progression_enabled", 0))
            self.season_new_npcs = int(self.db.get_world_int("season_new_npcs", SEASON_NEW_NPCS_DEFAULT) or SEASON_NEW_NPCS_DEFAULT)
            self.autosave_interval_seasons = max(1, int(self.db.get_world_int("autosave_interval_seasons", 5) or 5))
            self.refresh_status()
            self.update_player_button_visibility()
            if self.player is None:
                self.append_text(f"Loaded world-only autosave from {file_path}")
            else:
                self.append_text(f"Loaded save from {file_path}")
            self.append_text(f"Tournament exports for this save go to {get_current_output_dir()}")
        except Exception as e:
            messagebox.showerror("Load failed", str(e), parent=self.root)


    def build_tournament_field(self, participant_count: int, league_name: Optional[str] = None) -> List[PlayerProfile]:
        npcs = self.all_npcs()
        excluded = {self.player.name} if self.player else set()

        target_league = league_name
        if self.player is not None:
            if (not profile_active_loadout_is_legal_exact(self.player)) or profile_uses_banned_active(self.player, self.current_season_bans):
                raise ValueError(
                    f"Player {self.player.name} does not have a legal active tournament loadout for this season. "
                    "Change the loadout manually before entering."
                )
            target_league = self.profile_league_band(self.player)

        def eligible_candidates_for_window(primary_league: Optional[str]) -> List[PlayerProfile]:
            ordered_leagues = ["Amateur", "Semi-Pro", "Pro", "Elite"]
            allowed = set(ordered_leagues)
            if primary_league in ordered_leagues:
                idx = ordered_leagues.index(primary_league)
                allowed = {primary_league}
                if idx > 0:
                    allowed.add(ordered_leagues[idx - 1])
                if idx < len(ordered_leagues) - 1:
                    allowed.add(ordered_leagues[idx + 1])
            pool: List[PlayerProfile] = []
            for p in npcs:
                if p.name in excluded or profile_is_retired(p):
                    continue
                if primary_league and self.profile_league_band(p) not in allowed:
                    continue
                if enforce_minimum_tournament_eligibility(
                    p,
                    self.rng,
                    self.templates,
                    self.gates,
                    self.abilities,
                    season_bans=self.current_season_bans,
                ):
                    pool.append(p)
            return pool

        candidates = eligible_candidates_for_window(target_league)
        rival_names = set(self.player.rivals) if self.player and self.player.rivals else set()

        def weight_fn(npc: PlayerProfile) -> float:
            weight = 1.0
            band_name = self.profile_league_band(npc)
            if target_league:
                target_mid = league_band_midpoint(target_league)
                dist = abs(float(npc.glicko.rating) - target_mid)
                weight += max(0.0, 1.8 - dist / 260.0)
                if band_name == target_league:
                    weight += 1.5
                else:
                    weight += 0.45
            else:
                weight += max(0.0, npc.glicko.rating - 1450) / 180.0
            weight += npc.fame * 0.02
            weight += npc.tournament_titles * 0.35
            if npc.name in rival_names:
                weight += 2.5
            if self.player is not None and npc.chosen_attribute == self.player.chosen_attribute:
                weight += 0.4
            current_total_event = max(1, int(self.world_total_tournaments or ((self.world_season - 1) * 10 + self.world_tournament_no)))
            last_seen = int(npc.story_flags.get("last_seen_main_event_total", -9999))
            missed = max(0, current_total_event - last_seen - 1)
            weight += min(6.0, missed * 0.55)
            if 1450 <= npc.glicko.rating <= 1650:
                weight += 1.25
            return max(0.1, weight)

        minimum_field = 4
        player_slots = 1 if self.player is not None else 0

        if len(candidates) < minimum_field - player_slots:
            raise ValueError(
                f"Not enough eligible NPCs to build a tournament field for league {target_league or 'Open'}. "
                f"Eligible NPCs: {len(candidates)}"
            )

        legal_sizes = [64, 32, 16, 8, 4]
        max_total_size = len(candidates) + player_slots
        participant_count = max(size for size in legal_sizes if size <= max_total_size)
        needed_npcs = participant_count - player_slots

        picked = weighted_sample_without_replacement(candidates, needed_npcs, self.rng, weight_fn)
        if len(picked) < needed_npcs:
            picked_names = {p.name for p in picked}
            current_total_event = max(1, int(self.world_total_tournaments or ((self.world_season - 1) * 10 + self.world_tournament_no)))
            backfill_pool = [p for p in candidates if p.name not in picked_names]
            def backfill_key(p: PlayerProfile):
                missed = current_total_event - int(p.story_flags.get("last_seen_main_event_total", -9999))
                band_score = -abs(float(p.glicko.rating) - league_band_midpoint(target_league)) if target_league else float(p.glicko.rating)
                return (missed, band_score, p.name.lower())
            backfill_pool.sort(key=backfill_key, reverse=True)
            picked.extend(backfill_pool[: max(0, needed_npcs - len(picked))])

        final_picked: List[PlayerProfile] = []
        current_total_event = max(1, int(self.world_total_tournaments or ((self.world_season - 1) * 10 + self.world_tournament_no)))
        for npc in picked:
            npc.story_flags["last_seen_main_event"] = self.world_tournament_no
            npc.story_flags["last_seen_main_event_total"] = current_total_event
            optimise_profile_loadout_with_bans(npc, self.current_season_bans)
            npc.ensure_valid_loadout()
            if profile_has_minimum_legal_loadout(npc) and not profile_uses_banned_active(npc, self.current_season_bans):
                final_picked.append(npc)

        if len(final_picked) < minimum_field - player_slots:
            raise ValueError(
                f"Not enough eligible NPCs to build a legal tournament field for league {target_league or 'Open'}. "
                f"Eligible NPCs: {len(final_picked)}"
            )

        participant_count = max(size for size in legal_sizes if size <= (len(final_picked) + player_slots))
        needed_npcs = participant_count - player_slots
        return ([self.player] if self.player is not None else []) + final_picked[:needed_npcs]

    def payout_for_finish(self, finish: int, participant_count: int, tournament_type: TournamentType) -> int:
        return tournament_payout_table(finish, participant_count, tournament_type)

    def find_finish_swiss(self, tournament: SwissTournament, player_name: str) -> int:
        for i, p in enumerate(tournament.standings(), start=1):
            if p.name == player_name:
                return i
        return len(tournament.players)

    def apply_post_tournament_progression(self, entrants: List[PlayerProfile], finish_map: Dict[str, int], tournament_type: TournamentType, participant_count: int) -> None:
        entrant_map = {p.name: p for p in entrants}
        all_npcs = self.all_npcs()
        all_map = {p.name: p for p in all_npcs}

        meta_snapshot = build_meta_snapshot(list(all_map.values()) + ([self.player] if self.player else []))

        if self.player:
            self.player.peak_rating = max(self.player.peak_rating, self.player.glicko.rating)
            self.player.development_focus = choose_career_focus(self.player, self.rng, meta_snapshot)
            self.player.update_career_stage()
            self.player.update_rivals()
            self.player.update_signature()

        shared_stock = self.get_season_shop_stock()

        for prof in entrants:
            if not isinstance(prof.story_flags, dict):
                prof.story_flags = {}
            prof.story_flags["_last_used_loadout"] = make_active_loadout_snapshot(prof)
            prof.story_flags["_last_used_season"] = self.world_season
            prof.story_flags["_last_used_event"] = self.world_tournament_no

        for name, finish in finish_map.items():
            if self.player is not None and name == self.player.name:
                payout = self.payout_for_finish(finish, participant_count, tournament_type)
                apply_tournament_career_update(self.player, finish, participant_count, tournament_type, self.rng, payout)
                continue
            npc = entrant_map.get(name) or all_map.get(name)
            if npc is None:
                continue
            payout = tournament_payout_table(finish, participant_count, tournament_type)
            apply_tournament_career_update(npc, finish, participant_count, tournament_type, self.rng, payout)
            npc.training_points += 1
            npc.development_focus = choose_career_focus(npc, self.rng, meta_snapshot)
            apply_training(npc, self.rng, 1.3 if finish <= 4 else 0.9)
            npc_market_progression(npc, self.rng, self.templates, self.gates, self.abilities, meta=meta_snapshot, stock_context=shared_stock, debug_cb=self.debug_append)
            npc.story_flags["last_circuit_finish"] = finish
            npc.story_flags["last_active_tournament"] = self.world_tournament_no
            npc.update_career_stage()
            npc.update_rivals()
            npc.update_signature()
            all_map[npc.name] = npc

        self.save_npcs(list(all_map.values()))
        self.save_season_shop_stock(shared_stock)

    def simulate_parallel_league_tournaments(self, excluded_names: Set[str]) -> List[Dict[str, object]]:
        results: List[Dict[str, object]] = []
        all_npcs = self.all_npcs()
        leftovers: List[PlayerProfile] = []
        for league_name in ["Amateur", "Semi-Pro", "Pro", "Elite"]:
            pool = [
                p for p in all_npcs
                if p.name not in excluded_names
                and not profile_is_retired(p)
                and self.profile_league_band(p) == league_name
            ]
            legal_pool: List[PlayerProfile] = []
            for npc in pool:
                if enforce_minimum_tournament_eligibility(npc, self.rng, self.templates, self.gates, self.abilities, season_bans=self.current_season_bans):
                    optimise_profile_loadout_with_bans(npc, self.current_season_bans)
                    if profile_has_minimum_legal_loadout(npc) and not profile_uses_banned_active(npc, self.current_season_bans):
                        legal_pool.append(npc)
            remaining = legal_pool[:]
            event_counter = 0
            while len(remaining) >= 4:
                event_counter += 1
                if len(remaining) >= 32:
                    participant_count = 32
                elif len(remaining) >= 16:
                    participant_count = 16
                elif len(remaining) >= 8:
                    participant_count = 8
                else:
                    participant_count = 4
                entrants = weighted_sample_without_replacement(
                    remaining,
                    participant_count,
                    self.rng,
                    lambda p: 1.0 + max(0.0, p.glicko.rating - 1000.0) / 250.0 + p.tournament_titles * 0.15,
                )
                used_names = {p.name for p in entrants}
                remaining = [p for p in remaining if p.name not in used_names]
                tournament_type = self.rng.choice(list(TournamentType))
                rounds = max(4, min(11, int(round(log2(participant_count)) + 2))) if tournament_type == TournamentType.SWISS else None
                logger = Logger(enabled=False, prefix=f"parallel_{league_name.lower()}_{event_counter}")
                finish_map: Dict[str, int] = {}
                winner_name = ""
                matchup_results: List[Tuple[str, str, bool]] = []
                if tournament_type == TournamentType.SWISS:
                    tournament = SwissTournament(entrants, rounds=rounds, seed=self.rng.randint(1, 10_000_000), verbose_matches=False, logger=logger, manual_handler=None, manual_player_name=None)
                    tournament.run()
                    matchup_results = [(rec.player1, rec.player2, rec.winner == rec.player1) for rec in tournament.records]
                    standings_players = tournament.standings()
                    for pos, p in enumerate(standings_players, start=1):
                        finish_map[p.name] = pos
                    winner_name = standings_players[0].name if standings_players else ""
                else:
                    knockout = KnockoutTournament(entrants, seed=self.rng.randint(1, 10_000_000), verbose_matches=False, logger=logger, manual_handler=None, manual_player_name=None)
                    result = knockout.run()
                    for round_records in result.rounds:
                        for p1n, p2n, winner_n in round_records:
                            matchup_results.append((p1n, p2n, winner_n == p1n))
                    finish_map.update(result.placements)
                    winner_name = result.champion.name if result.champion else ""
                profile_map = {p.name: p for p in entrants}
                apply_matchup_results(matchup_results, profile_map)
                for prof in entrants:
                    finish = finish_map.get(prof.name, participant_count)
                    payout = tournament_payout_table(finish, participant_count, tournament_type)
                    apply_tournament_career_update(prof, finish, participant_count, tournament_type, self.rng, payout)
                    prof.training_points += 1
                    apply_training(prof, self.rng, 1.2 if finish <= 4 else 0.8)
                    prof.update_career_stage()
                    prof.update_rivals()
                    prof.update_signature()
                standings = []
                for prof in entrants:
                    tourney = getattr(prof, "tourney", None)
                    standings.append({
                        "finish": int(finish_map.get(prof.name, participant_count)),
                        "name": prof.name,
                        "rating": float(prof.glicko.rating),
                        "wins": int(getattr(tourney, "wins", 0)),
                        "losses": int(getattr(tourney, "losses", 0)),
                    })
                standings.sort(key=lambda x: (x["finish"], -x["rating"], x["name"]))
                results.append({
                    "league": league_name,
                    "tournament_no": event_counter,
                    "winner": winner_name,
                    "participant_count": participant_count,
                    "tournament_type": tournament_type.value if hasattr(tournament_type, "value") else str(tournament_type),
                    "top5": standings[:5],
                })
            leftovers.extend(remaining)
        development_counter = 0
        remaining = leftovers[:]
        while len(remaining) >= 4:
            development_counter += 1
            if len(remaining) >= 16:
                participant_count = 16
            elif len(remaining) >= 8:
                participant_count = 8
            else:
                participant_count = 4
            entrants = weighted_sample_without_replacement(
                remaining,
                participant_count,
                self.rng,
                lambda p: 1.0 + max(0.0, p.glicko.rating - 900.0) / 300.0 + p.tournaments_entered * 0.05,
            )
            used_names = {p.name for p in entrants}
            remaining = [p for p in remaining if p.name not in used_names]
            tournament_type = TournamentType.SWISS if participant_count >= 8 else self.rng.choice(list(TournamentType))
            rounds = max(4, min(11, int(round(log2(participant_count)) + 2))) if tournament_type == TournamentType.SWISS else None
            logger = Logger(enabled=False, prefix=f"parallel_development_{development_counter}")
            finish_map: Dict[str, int] = {}
            winner_name = ""
            matchup_results: List[Tuple[str, str, bool]] = []
            if tournament_type == TournamentType.SWISS:
                tournament = SwissTournament(entrants, rounds=rounds, seed=self.rng.randint(1, 10_000_000), verbose_matches=False, logger=logger, manual_handler=None, manual_player_name=None)
                tournament.run()
                matchup_results = [(rec.player1, rec.player2, rec.winner == rec.player1) for rec in tournament.records]
                standings_players = tournament.standings()
                for pos, p in enumerate(standings_players, start=1):
                    finish_map[p.name] = pos
                winner_name = standings_players[0].name if standings_players else ""
            else:
                knockout = KnockoutTournament(entrants, seed=self.rng.randint(1, 10_000_000), verbose_matches=False, logger=logger, manual_handler=None, manual_player_name=None)
                result = knockout.run()
                for round_records in result.rounds:
                    for p1n, p2n, winner_n in round_records:
                        matchup_results.append((p1n, p2n, winner_n == p1n))
                finish_map.update(result.placements)
                winner_name = result.champion.name if result.champion else ""
            profile_map = {p.name: p for p in entrants}
            apply_matchup_results(matchup_results, profile_map)
            for prof in entrants:
                finish = finish_map.get(prof.name, participant_count)
                payout = tournament_payout_table(finish, participant_count, tournament_type)
                apply_tournament_career_update(prof, finish, participant_count, tournament_type, self.rng, payout)
                prof.training_points += 1
                apply_training(prof, self.rng, 1.0 if finish <= 4 else 0.75)
                prof.update_career_stage()
                prof.update_rivals()
                prof.update_signature()
            standings = []
            for prof in entrants:
                tourney = getattr(prof, "tourney", None)
                standings.append({
                    "finish": int(finish_map.get(prof.name, participant_count)),
                    "name": prof.name,
                    "rating": float(prof.glicko.rating),
                    "wins": int(getattr(tourney, "wins", 0)),
                    "losses": int(getattr(tourney, "losses", 0)),
                })
            standings.sort(key=lambda x: (x["finish"], -x["rating"], x["name"]))
            results.append({
                "league": "Development",
                "tournament_no": development_counter,
                "winner": winner_name,
                "participant_count": participant_count,
                "tournament_type": tournament_type.value if hasattr(tournament_type, "value") else str(tournament_type),
                "top5": standings[:5],
            })
        if results:
            self.save_npcs(self.all_npcs())
        return results

    def start_tournament(self, force_manual: Optional[bool] = None) -> None:
        if self.player is not None:
            if not profile_active_loadout_is_legal_exact(self.player):
                messagebox.showerror(
                    "Illegal loadout",
                    "Your active loadout is not legal. Change your loadout before entering this tournament.",
                    parent=self.root,
                )
                return
            if profile_uses_banned_active(self.player, self.current_season_bans):
                messagebox.showerror(
                    "Banned loadout",
                    "Your active loadout contains season-banned items. Change your loadout before entering this tournament.",
                    parent=self.root,
                )
                return

        current_season = self.world_season
        current_event = self.world_tournament_no
        participant_count = self.rng.choice([16, 16, 32, 32, 64])
        tournament_type = self.rng.choice(list(TournamentType))

        def eligible_count_for_league(league_name: str) -> int:
            total = 0
            for p in self.all_npcs():
                if profile_is_retired(p):
                    continue
                if self.profile_league_band(p) != league_name:
                    continue
                if enforce_minimum_tournament_eligibility(
                    p,
                    self.rng,
                    self.templates,
                    self.gates,
                    self.abilities,
                    season_bans=self.current_season_bans,
                ):
                    total += 1
            return total

        if self.player is not None:
            featured_league = self.profile_league_band(self.player)
        else:
            featured_league = None
            for name in ["Elite", "Pro", "Semi-Pro", "Amateur"]:
                if eligible_count_for_league(name) >= 4:
                    featured_league = name
                    break
            if featured_league is None:
                messagebox.showerror(
                    "No tournament available",
                    "There are not enough eligible NPCs in any league to run a main tournament right now.",
                    parent=self.root,
                )
                return

        if force_manual is None and self.player is not None:
            manual = messagebox.askyesno(
                "Mode",
                "Play this tournament in manual mode?\n\nDuring manual prompts, type AUTO to simulate the rest of the tournament automatically.",
                parent=self.root,
            )
        else:
            manual = bool(force_manual) if self.player is not None else False

        debug = bool(self.debug_var.get())
        handler = TkManualChoiceHandler(self.root) if manual else None
        entrants = self.build_tournament_field(participant_count, league_name=featured_league)
        participant_count = len(entrants)
        rounds = max(4, min(11, int(round(log2(participant_count)) + 2))) if tournament_type == TournamentType.SWISS else None

        self.append_text(
            f"Starting {featured_league} league {tournament_type.value} tournament with "
            f"{participant_count} participants in season {current_season}, event {current_event}"
        )
        self.append_text(f"Starting {featured_league} league {tournament_type.value} tournament with {participant_count} participants in season {current_season}, event {current_event}")
        logger = Logger(enabled=debug, prefix="story")

        finish_map: Dict[str, int] = {}
        winner_name = ""
        matchup_results: List[Tuple[str, str, bool]] = []
        if tournament_type == TournamentType.SWISS:
            tournament = SwissTournament(entrants, rounds=rounds, seed=self.rng.randint(1, 10_000_000), verbose_matches=debug, logger=logger, manual_handler=handler, manual_player_name=self.player.name if manual and self.player is not None else None)
            tournament.run()
            matchup_results = [(rec.player1, rec.player2, rec.winner == rec.player1) for rec in tournament.records]
            summary_path, play_path = tournament.export_files(seed=self.rng.randint(1, 10_000_000), save_play_by_play=True)
            standings = tournament.standings()
            for pos, p in enumerate(standings, start=1):
                finish_map[p.name] = pos
            winner_name = standings[0].name if standings else ""
            if self.player is not None:
                finish = finish_map.get(self.player.name, participant_count)
                payout = self.payout_for_finish(finish, participant_count, tournament_type)
                self.append_text(f"Finished {finish} in Swiss. Earned £{payout}.")
            if is_text_file_exports_enabled():
                self.append_text(f"Saved summary to {summary_path}")
                if play_path:
                    self.append_text(f"Saved play by play to {play_path}")
        else:
            knockout = KnockoutTournament(entrants, seed=self.rng.randint(1, 10_000_000), verbose_matches=debug, logger=logger, manual_handler=handler, manual_player_name=self.player.name if manual and self.player is not None else None)
            result = knockout.run()
            for round_records in result.rounds:
                for p1n, p2n, winner_n in round_records:
                    matchup_results.append((p1n, p2n, winner_n == p1n))
            summary_path, play_path = knockout.export_files(seed=self.rng.randint(1, 10_000_000), save_play_by_play=True)
            finish_map.update(result.placements)
            winner_name = result.champion.name if result.champion else ""
            if self.player is not None:
                finish = result.placements.get(self.player.name, participant_count)
                payout = self.payout_for_finish(finish, participant_count, tournament_type)
                self.append_text(f"Finished {finish} in Knockout. Earned £{payout}.")
            if is_text_file_exports_enabled():
                self.append_text(f"Saved summary to {summary_path}")
                if play_path:
                    self.append_text(f"Saved play by play to {play_path}")

        profile_map = {p.name: p for p in entrants}
        if self.player is not None:
            profile_map[self.player.name] = self.player
        apply_matchup_results(matchup_results, profile_map)
        archive = make_tournament_archive(current_season, current_event, tournament_type, participant_count, entrants, finish_map, winner_name, summary_path, play_path)
        archive["league"] = featured_league
        archive["parallel_leagues"] = self.simulate_parallel_league_tournaments({p.name for p in entrants})
        self.db.save_tournament_archive(archive)
        self.apply_post_tournament_progression(entrants, finish_map, tournament_type, participant_count)

        previous_season = current_season
        self.world_total_tournaments += 1
        self.world_season = 1 + (self.world_total_tournaments // 10)
        self.world_tournament_no = 1 + (self.world_total_tournaments % 10)
        self.db.set_world_int("world_total_tournaments", self.world_total_tournaments)
        self.db.set_world_int("world_tournament_no", self.world_tournament_no)
        self.db.set_world_int("world_season", self.world_season)
        if self.world_season != previous_season:
            self.apply_world_champion_season_bonus(self.world_season)
            self.save_season_shop_stock(self._build_seasonal_shop_stock(self.world_season))
            self.generate_season_bans(self.world_season, previous_season)
            self.apply_season_bans_worldwide()
            if self.season_ban_settings.get("enabled"):
                bans = self.current_season_bans
                self.append_text(f"Season {self.world_season} ban list generated from Season {previous_season} usage. Bakugan: {', '.join(bans.get('bakugan', [])) or 'None'} | Gate: {', '.join(bans.get('gates', [])) or 'None'} | Ability: {', '.join(bans.get('abilities', [])) or 'None'}")
            self.process_new_season_age_progression(self.world_season)
            self.maybe_run_world_cup(previous_season)
            self.autosave_current_game(completed_season=previous_season)

        self.append_text(f"Archived tournament history for Season {current_season} Event {current_event}. Simulated parallel league tournaments for the rest of the playerbase.")
        if self.player is not None:
            player_finish = finish_map.get(self.player.name, participant_count)
            self.append_text(f"Career updated: finish {player_finish}, money £{self.player.money}, rating {self.player.glicko.rating:.0f}, peak {self.player.peak_rating:.0f}, titles {self.player.tournament_titles}, podiums {self.player.podiums}, top8s {self.player.top8s}, stage {self.display_title(self.player)}")
        self.autosave_current_game()
        self.refresh_status()

        if debug:
            debug_name = build_output_filename("story_debug", participant_count, rounds if rounds is not None else None, random_suffix(self.rng))
            path = logger.save(debug_name)
            if path is not None:
                self.append_text(f"Saved debug log to {path}")

# ============================================================
# STANDALONE RUNNERS
# ============================================================
# STANDALONE RUNNERS
# ============================================================

def generate_profiles(count: int, seed: int = 42) -> List[PlayerProfile]:
    rng = random.Random(seed)
    used = set()
    out = []
    for _ in range(count):
        name = random_name(rng, used)
        attr = rng.choice(all_attributes())
        out.append(draft_starting_profile(name, attr, rng, False))
    return out


def run_single_match(player1: PlayerProfile, player2: PlayerProfile, seed: int = 42, verbose: bool = True, log_to_file: bool = True) -> Tuple[PlayerProfile, Dict[str, float], Match, Optional[Path]]:
    logger = Logger(enabled=verbose)
    match = Match(player1, player2, seed=seed, verbose=verbose, logger=logger)
    winner, perf, lines = match.play()

    print("\n========== SINGLE MATCH RESULT ==========")
    print(f"Winner: {winner.name}")
    print(f"{player1.name}: perf={perf[player1.name]:.1f}, gates={len(match.captured[player1.name])}, rating={match.players[0].glicko.rating:.0f}")
    print(f"{player2.name}: perf={perf[player2.name]:.1f}, gates={len(match.captured[player2.name])}, rating={match.players[1].glicko.rating:.0f}")

    output_path = None
    if log_to_file:
        filename = build_output_filename("single_match", 2, 1, random_suffix(random.Random(seed)))
        output_path = get_current_output_dir() / filename
        text_lines = ["========== SINGLE MATCH PLAY BY PLAY =========="]
        text_lines.extend(lines)
        text_lines.append("")
        text_lines.append("========== LOADOUTS ==========")
        text_lines.extend(player_loadout_lines(player1))
        text_lines.append("")
        text_lines.extend(player_loadout_lines(player2))
        written_path = maybe_write_text(output_path, "\n".join(text_lines), encoding="utf-8")
        if written_path is not None:
            output_path = written_path
            print(f"Saved log to: {output_path}")
    return winner, perf, match, output_path
