
from __future__ import annotations

import csv
import json
import random
import sqlite3
import string
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
from math import exp, floor, log, log2, pi, sqrt
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Set
from collections import defaultdict
from itertools import combinations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

import sys
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from .content import RAW_BAKUGAN_TEMPLATES, RAW_ABILITY_CARDS, RAW_GATE_CARDS
import re


# ============================================================
# PATHS AND FILE HELPERS
# ============================================================

def get_documents_folder() -> Path:
    home = Path.home()
    docs = home / "Documents"
    return docs if docs.exists() else home


APP_DIR = get_documents_folder() / "bakugan outputs"
APP_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_DIR = APP_DIR / "debug_logs"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
SAVE_DIR = APP_DIR / "saves"
SAVE_DIR.mkdir(parents=True, exist_ok=True)
SAVE_OUTPUTS_DIR = APP_DIR / "save_outputs"
SAVE_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
CURRENT_OUTPUT_DIR = SAVE_OUTPUTS_DIR / "session_unsaved"
CURRENT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "bakugan_story.db"
WORLD_CUP_INTERVAL_DEFAULT = 10
WORLD_CUP_NEW_NPCS_DEFAULT = 2
WORLD_CUP_TOURNAMENT_LABEL = "World Cup"
WORLD_CUP_WIN_POINTS = 3
WORLD_CUP_CHAMPION_FAME = 25
WORLD_CUP_CHAMPION_SPONSORSHIP = 3
WORLD_CUP_CHAMPION_CASH = 4000
WORLD_CUP_CHAMPION_SEASONAL_TRAINING = 1

PLAYER_MIN_AGE = 8
PLAYER_DEFAULT_AGE = 16
PLAYER_INITIAL_MAX_AGE = 25
SEASON_NEW_NPCS_DEFAULT = 2

SEASON_BAN_DEFAULTS = {
    "enabled": False,
    "bakugan_count": 2,
    "gate_count": 1,
    "ability_count": 1,
}

CHANGELOG_VERSION = "v1.2.0"
CHANGELOG_DATE = "2026-03-23"
CHANGELOG_ENTRIES: List[Tuple[str, str, List[str]]] = [
    ("v0.10", "2026-03-23", [
        "Added changelog viewer button near Debug mode.",
        "Added persistent World Champion season history on player and NPC profiles.",
        "Added World Championship History viewer from Tournament History.",
        "Added named gold-gate valuation bonus in the loadout optimiser.",
        "Added Debug-only Auto Rest of Season control and proper control-state handling.",
    ]),
    ("v0.09", "2026-03-23", [
        "Fixed named gold gates so the correct Bakugan receives the double bonus during battle resolution.",
        "Added naming normalisation for Delta Dragonoid II, Preyas II, Angelo, Diablo, and Fourtress.",
        "Set Debug mode to off by default.",
        "Added World Cup interval choice during character creation and Debug World Cup settings.",
    ]),
    ("v0.08", "2026-03-23", [
        "Updated main and content files with price adjustments for top Bakugan.",
        "Battle Ax Vladitor price increased to £450.",
        "Dual Hydranoid price increased to £325.",
        "Delta Dragonoid price increased to £340.",
    ]),
    ("v0.07", "2026-03-23", [
        "Improved ability loadout AI with live-rate and ceiling scoring.",
        "Ability trios are scored as a package rather than isolated per-colour picks.",
        "Added gate synergy into ability scoring.",
        "Added a post-selection sanity pass to replace dead abilities with live same-colour alternatives.",
    ]),
    ("v0.06", "2026-03-23", [
        "Added Export NPC Loadouts CSV utility.",
        "Fixed exporter field mismatches and card text fallbacks.",
        "Improved NPC battle ability usage, conservation, and support selection.",
        "Added player-search sorting by broader profile and career stats, then gated hidden stat visibility behind Debug mode.",
    ]),
    ("v0.05", "2026-03-23", [
        "Added World Cup special event system with configurable interval.",
        "World Cup runs as a double round robin for the top 8 ranked players.",
        "Added points table and tiebreakers for World Cup standings.",
        "Added World Champion rewards, current champion tracking, and seasonal champion training bonus.",
        "Added player double-stand choice to claim the gate or move to another gate.",
    ]),
    ("v0.04", "2026-03-23", [
        "Expanded player search and profile display.",
        "Added sort options for roll, intelligence, aggression, risk, rating peaks, titles, finals, podiums, top 8s, fame, earnings, money, training, sponsorship, and match record.",
        "Restored missing StoryModeApp UI methods after regression fixes.",
    ]),
    ("v0.03", "2026-03-23", [
        "Added archetype-aware shop and auto-loadout AI.",
        "Introduced Power Rush, Gate Control, Combo Setup, Counter, and Balanced Tempo archetypes.",
        "Added card tagging and archetype-aware value scoring for Bakugan, gates, and abilities.",
        "Improved loadout optimisation to score legal triplets with better synergy.",
    ]),
    ("v0.02", "2026-03-23", [
        "Improved INT-tier personality rules and board-state awareness.",
        "AI now adapts gate choice, Bakugan choice, targeting, ability timing, and double-stand decisions based on score pressure and remaining resources.",
        "Improved gate choice, battle commitment, and shop/loadout decision logic to use more forward planning and conservation.",
    ]),
    ("v0.01", "2026-03-23", [
        "Expanded NPC first-name and surname pools for much larger variety.",
        "Adjusted starter Bakugan and gate-card auditing work in the base project state.",
    ]),
]


CONTENT_MODULE_NAME = "bakugan_content_custombuilder"
CONTENT_FILE_PATH = Path(__file__).with_name(f"{CONTENT_MODULE_NAME}.py")


CARD_LAB_CONDITION_DEFS = {
    "none": "No condition",
    "self_attribute_is": "Self attribute is",
    "opponent_attribute_is": "Opponent attribute is",
    "either_attribute_is": "Either battler attribute is",
    "self_original_g_lower": "Self original G is lower",
    "self_original_g_higher": "Self original G is higher",
    "battle_on_own_gate": "Battle is on own gate",
    "battle_on_opponent_gate": "Battle is on opponent gate",
    "opponent_used_more_abilities": "Opponent used more abilities",
    "self_gates_won_at_least": "Self gates won at least",
    "self_used_abilities_at_least": "Self used abilities at least",
    "dragonoid_family_battling": "Dragonoid-family Bakugan is battling",
    "another_friendly_standing": "Another friendly Bakugan is standing",
    "gate_type_is": "Gate type is",
    "named_bakugan_matches_gate": "Named Bakugan matches gate",
    "random_chance_succeeds": "Random chance succeeds",
    "used_colors_include": "Used colors include",
    "self_name_contains": "Self name contains text",
}

CARD_LAB_ACTION_DEFS = {
    "none": "No action",
    "add_g": "Add G",
    "subtract_g": "Subtract G",
    "add_random_g": "Add random G",
    "double_gate_bonus": "Double gate bonus",
    "multiply_gate_bonus": "Multiply gate bonus",
    "swap_original_g": "Swap original G",
    "swap_attributes": "Swap attributes",
    "block_color": "Block card color",
    "block_attribute_effects": "Block attribute effects",
    "return_one_used_ability": "Return one used ability",
    "return_all_used_abilities": "Return all used abilities",
    "move_support_bakugan_into_battle": "Move support Bakugan into battle",
    "summon_support_bakugan": "Summon support Bakugan",
    "replace_with_unused_bakugan": "Replace with unused Bakugan",
    "doom_loser": "Remove loser from match",
    "reset_both_to_original_g": "Reset both to original G",
    "add_g_by_attribute_map": "Add G by attribute map",
    "add_g_by_gates_won": "Scale by gates won",
    "add_g_by_used_abilities": "Scale by used abilities",
    "add_g_by_standing_attributes": "Scale by standing attributes",
    "enable_combo_battle": "Enable combo battle",
    "improve_roll": "Improve roll",
    "add_g_on_battle_start": "Add G on battle start",
    "pending_do_over": "Set do-over",
    "pending_high_original_loses_g": "Higher original G loses G",
    "double_ability_boosts": "Double ability boosts",
    "prevent_abilities": "Prevent abilities",
    "add_g_to_lower_current": "Add G to lower current side",
    "add_g_if_attribute": "Add G if attribute matches",
}

CARD_LAB_PRESETS = {
    "Flat Boost": {"timing": "DURING_BATTLE", "conditions": [], "actions": [{"type": "add_g", "target": "self", "amount": 100}], "else_actions": []},
    "Conditional Boost": {"timing": "DURING_BATTLE", "conditions": [{"type": "self_attribute_is", "value": "DARKUS"}], "actions": [{"type": "add_g", "target": "self", "amount": 120}], "else_actions": []},
    "Comeback Boost": {"timing": "DURING_BATTLE", "conditions": [{"type": "self_original_g_lower", "value": True}], "actions": [{"type": "add_g", "target": "self", "amount": 120}], "else_actions": []},
    "Gate-Scaling Boost": {"timing": "DURING_BATTLE", "conditions": [], "actions": [{"type": "add_g_by_gates_won", "target": "self", "scale": 50}], "else_actions": []},
    "Used-Abilities Scaling": {"timing": "DURING_BATTLE", "conditions": [], "actions": [{"type": "add_g_by_used_abilities", "target": "self", "scale": 40}], "else_actions": []},
    "Color Shutdown": {"timing": "FLEXIBLE", "conditions": [], "actions": [{"type": "block_color", "target": "opponent", "color": "RED"}], "else_actions": []},
    "Attribute Shutdown": {"timing": "DURING_BATTLE", "conditions": [], "actions": [{"type": "block_attribute_effects", "target": "both"}], "else_actions": []},
    "Gate Bonus Doubler": {"timing": "DURING_BATTLE", "conditions": [], "actions": [{"type": "double_gate_bonus", "target": "self"}], "else_actions": []},
    "Bakugan Replacement": {"timing": "FLEXIBLE", "conditions": [], "actions": [{"type": "replace_with_unused_bakugan", "target": "self"}], "else_actions": []},
    "Support Summon": {"timing": "FLEXIBLE", "conditions": [{"type": "another_friendly_standing", "value": True}], "actions": [{"type": "move_support_bakugan_into_battle", "target": "self"}], "else_actions": []},
    "Loser Removed": {"timing": "FLEXIBLE", "conditions": [], "actions": [{"type": "doom_loser", "target": "opponent"}], "else_actions": []},
    "Random Bonus": {"timing": "DURING_BATTLE", "conditions": [], "actions": [{"type": "add_random_g", "target": "self", "min": 0, "max": 200}], "else_actions": []},
    "Reset Battle State": {"timing": "DURING_BATTLE", "conditions": [], "actions": [{"type": "reset_both_to_original_g", "target": "both"}], "else_actions": []},
    "Named Gold Gate": {"timing": "PASSIVE_GATE", "conditions": [{"type": "named_bakugan_matches_gate", "value": True}], "actions": [{"type": "double_gate_bonus", "target": "self"}], "else_actions": []},
}

def deep_copy_effect(effect: Optional[Dict]) -> Dict:
    return json.loads(json.dumps(effect or {"timing": "DURING_BATTLE", "conditions": [], "actions": []}))

def normalise_custom_effect(effect: Optional[Dict], timing: str = "DURING_BATTLE") -> Dict:
    base = {"timing": timing, "conditions": [], "actions": [], "else_actions": []}
    if isinstance(effect, dict):
        base.update({k: deep_copy_effect(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v for k, v in effect.items()})
    if not isinstance(base.get("conditions"), list):
        base["conditions"] = []
    if not isinstance(base.get("actions"), list):
        base["actions"] = []
    if not isinstance(base.get("else_actions"), list):
        base["else_actions"] = []
    return base

def _attribute_from_value(value: str) -> Optional[Attribute]:
    if not value:
        return None
    value = str(value).upper()
    return Attribute.__members__.get(value)


def custom_effect_preview(effect: Optional[Dict], fallback_desc: str = "") -> str:
    eff = normalise_custom_effect(effect)
    timing = eff.get('timing', 'DURING_BATTLE')
    def cond_to_text(cond: Dict) -> str:
        ctype = cond.get('type', 'none'); val = cond.get('value', '')
        mapping = {
            'self_attribute_is': f"self attribute is {val}",
            'opponent_attribute_is': f"opponent attribute is {val}",
            'either_attribute_is': f"either battler attribute is {val}",
            'self_original_g_lower': 'self original G is lower',
            'self_original_g_higher': 'self original G is higher',
            'battle_on_own_gate': 'battle is on own gate',
            'battle_on_opponent_gate': 'battle is on opponent gate',
            'opponent_used_more_abilities': 'opponent used more abilities',
            'self_gates_won_at_least': f"self has at least {val} gates won",
            'self_used_abilities_at_least': f"self has used at least {val} abilities",
            'dragonoid_family_battling': 'a Dragonoid-family Bakugan is battling',
            'another_friendly_standing': 'another friendly Bakugan is standing',
            'gate_type_is': f"gate type is {val}",
            'named_bakugan_matches_gate': 'named Bakugan matches gate',
            'random_chance_succeeds': f"random chance {val}% succeeds",
            'self_name_contains': f"self name contains '{val}'",
        }
        if ctype == 'used_colors_include':
            return f"used colors include {', '.join(val) if isinstance(val, list) else val}"
        return mapping.get(ctype, ctype)
    def action_to_text(action: Dict) -> str:
        atype = action.get('type', 'none'); target = action.get('target', 'self'); amt = action.get('amount', action.get('scale', ''))
        mapping = {
            'add_g': f"add {amt} G to {target}",
            'subtract_g': f"subtract {amt} G from {target}",
            'add_random_g': f"add random G {action.get('min',0)} to {action.get('max',0)} to {target}",
            'double_gate_bonus': f"double gate bonus for {target}",
            'multiply_gate_bonus': f"multiply gate bonus for {target} by {action.get('multiplier', action.get('amount', 2))}",
            'swap_original_g': 'swap original G',
            'swap_attributes': 'swap attributes',
            'block_color': f"block {action.get('color','')} cards for {target}",
            'block_attribute_effects': 'block attribute-based effects',
            'return_one_used_ability': f"return one used ability for {target}",
            'return_all_used_abilities': 'return all used abilities',
            'move_support_bakugan_into_battle': f"move support Bakugan into battle for {target}",
            'summon_support_bakugan': f"move support Bakugan into battle for {target}",
            'replace_with_unused_bakugan': f"replace {target} with unused Bakugan",
            'doom_loser': 'remove the loser from the match',
            'reset_both_to_original_g': 'reset battling G to original',
            'add_g_by_attribute_map': 'add G using attribute map',
            'add_g_by_gates_won': f"add {action.get('scale',0)} G per gate won",
            'add_g_by_used_abilities': f"add {action.get('scale',0)} G per used ability",
            'add_g_by_standing_attributes': f"add {action.get('scale',0)} G per standing attribute",
            'enable_combo_battle': 'enable combo battle',
            'improve_roll': f"improve roll by {amt}",
            'add_g_on_battle_start': f"add {amt} G on battle start",
            'pending_do_over': 'restart the battle',
            'pending_high_original_loses_g': f"higher original G loses {amt}",
            'double_ability_boosts': 'double ability boosts',
            'prevent_abilities': 'prevent abilities',
            'add_g_to_lower_current': f"lower current side gains {amt} G",
            'add_g_if_attribute': f"add {amt} G if attribute is {action.get('attribute','')}",
        }
        return mapping.get(atype, atype)
    cond_text = ' and '.join(cond_to_text(c) for c in eff.get('conditions', []))
    act_text = '; '.join(action_to_text(a) for a in eff.get('actions', []))
    else_text = '; '.join(action_to_text(a) for a in eff.get('else_actions', []))
    parts = [f"Timing: {timing}"]
    if cond_text:
        parts.append(f"If {cond_text}, then {act_text or 'no action'}.")
    elif act_text:
        parts.append(act_text.capitalize() + '.')
    if else_text:
        parts.append(f"Else: {else_text}.")
    return '\n'.join(parts) if len(parts) > 1 else (fallback_desc or 'No effect.')


def validate_custom_effect(effect: Optional[Dict], kind: str = 'ability') -> List[str]:
    eff = normalise_custom_effect(effect)
    issues = []
    timing = eff.get('timing')
    valid_timings = {'ON_ROLL','AFTER_SUCCESSFUL_STAND','ON_BATTLE_START','DURING_ROLL','DURING_BATTLE','AFTER_BATTLE','ON_GATE_CAPTURE','ON_DEFEAT','FLEXIBLE','PASSIVE_GATE'}
    if kind == 'ability' and timing not in valid_timings - {'PASSIVE_GATE'}:
        issues.append('Ability timing is not supported.')
    if kind == 'gate' and timing != 'PASSIVE_GATE':
        issues.append('Gate timing must be PASSIVE_GATE.')
    if not eff.get('actions') and not eff.get('else_actions'):
        issues.append('At least one action or fallback action is required.')
    for cond in eff.get('conditions', []):
        if cond.get('type') not in CARD_LAB_CONDITION_DEFS:
            issues.append(f"Unsupported condition: {cond.get('type')}")
    for branch in ('actions','else_actions'):
        for action in eff.get(branch, []):
            if action.get('type') not in CARD_LAB_ACTION_DEFS:
                issues.append(f"Unsupported action: {action.get('type')}")
    action_types = [a.get('type') for a in eff.get('actions', [])]
    if 'replace_with_unused_bakugan' in action_types and ('move_support_bakugan_into_battle' in action_types or 'summon_support_bakugan' in action_types):
        issues.append('Replace Bakugan plus support movement may have execution-order issues.')
    if action_types.count('double_gate_bonus') + action_types.count('multiply_gate_bonus') > 1:
        issues.append('Multiple gate bonus multipliers may stack heavily.')
    for action in eff.get('actions', []) + eff.get('else_actions', []):
        if action.get('type') == 'block_color' and str(action.get('color','')).upper() == 'BLUE':
            issues.append('Blue-color blocking is only partially supported by the current engine.')
    return issues


def _context_condition_match(match_obj, context: Dict, cond: Dict) -> bool:
    ctype = cond.get('type', 'none')
    if ctype in {'none', ''}:
        return True
    active = context.get('active_baku'); other = context.get('other_baku'); player = context.get('player'); field_gate = context.get('field_gate')
    if ctype == 'self_attribute_is':
        attr = _attribute_from_value(cond.get('value')); return bool(active and attr and match_obj._has_attribute(active, attr))
    if ctype == 'opponent_attribute_is':
        attr = _attribute_from_value(cond.get('value')); return bool(other and attr and match_obj._has_attribute(other, attr))
    if ctype == 'either_attribute_is':
        attr = _attribute_from_value(cond.get('value')); return bool(attr and ((active and match_obj._has_attribute(active, attr)) or (other and match_obj._has_attribute(other, attr))))
    if ctype == 'self_original_g_lower': return bool(active and other and active.base_g < other.base_g)
    if ctype == 'self_original_g_higher': return bool(active and other and active.base_g > other.base_g)
    if ctype == 'battle_on_own_gate': return bool(field_gate and player and field_gate.set_by_player_name == player.name)
    if ctype == 'battle_on_opponent_gate': return bool(field_gate and player and field_gate.set_by_player_name != player.name)
    if ctype == 'opponent_used_more_abilities':
        opponent = context.get('opponent'); return bool(player and opponent and len(match_obj.used_ability_idx.get(opponent.name, [])) > len(match_obj.used_ability_idx.get(player.name, [])))
    if ctype == 'self_gates_won_at_least':
        n = int(cond.get('value', 0) or 0); return bool(player and match_obj.match_stats[player.name].gates_captured >= n)
    if ctype == 'self_used_abilities_at_least':
        n = int(cond.get('value', 0) or 0); return bool(player and match_obj._used_ability_count(player) >= n)
    if ctype == 'dragonoid_family_battling': return bool(active and 'dragonoid' in active.name.lower())
    if ctype == 'another_friendly_standing':
        if not (field_gate and player and active): return False
        return any(b.owner_name == player.name and b is not active for b in field_gate.bakugan_on_card)
    if ctype == 'gate_type_is': return bool(field_gate and field_gate.gate_card.gate_type.name.upper() == str(cond.get('value','')).upper())
    if ctype == 'named_bakugan_matches_gate': return bool(field_gate and active and _gate_targets_bakugan_name(field_gate.gate_card, active))
    if ctype == 'random_chance_succeeds':
        chance = float(cond.get('value', 100) or 100); return match_obj.random.random() * 100.0 < chance
    if ctype == 'used_colors_include':
        if not player: return False
        needed = set(cond.get('value', [])); used = match_obj._used_ability_colors(player); return needed.issubset(used)
    if ctype == 'self_name_contains':
        value = str(cond.get('value','')).lower(); return bool(active and value in active.name.lower())
    return False


def _context_action_apply(match_obj, action: Dict, context: Dict, state: Optional[BattleState] = None, roll_phase: bool = False) -> Optional[Bakugan]:
    active = context.get('active_baku'); other = context.get('other_baku'); player = context.get('player'); opponent = context.get('opponent'); field_gate = context.get('field_gate'); attacker_slot = bool(context.get('attacker_slot', True))
    if state is not None:
        self_g_attr = 'attacker_g' if attacker_slot else 'defender_g'
        opp_g_attr = 'defender_g' if attacker_slot else 'attacker_g'
        self_log = state.attacker_mod_log if attacker_slot else state.defender_mod_log
        opp_log = state.defender_mod_log if attacker_slot else state.attacker_mod_log
    atype = action.get('type','none'); target = action.get('target','self')
    if atype == 'improve_roll':
        amt = float(action.get('amount',0)); match_obj.temp_roll_modifiers[player.name] += amt; match_obj.log(f"{player.name} gains roll bonus {amt:.2f}")
    elif atype == 'enable_combo_battle': match_obj.pending_combo_battle = player.name
    elif atype == 'pending_do_over': match_obj.pending_do_over = player.name
    elif atype == 'pending_high_original_loses_g': match_obj.pending_level_down = player.name
    elif atype == 'add_g_on_battle_start': match_obj.pending_roll_battle_bonus[player.name] = match_obj.pending_roll_battle_bonus.get(player.name,0) + int(action.get('amount',0))
    elif state is not None and atype in {'add_g','subtract_g'}:
        amt = int(action.get('amount',0)) * (1 if atype == 'add_g' else -1)
        if target == 'self': setattr(state, self_g_attr, getattr(state, self_g_attr) + amt); self_log.append(f"Custom effect: {'+' if amt>=0 else ''}{amt} G")
        elif target == 'opponent': setattr(state, opp_g_attr, getattr(state, opp_g_attr) + amt); opp_log.append(f"Custom effect: {'+' if amt>=0 else ''}{amt} G")
        else:
            setattr(state, self_g_attr, getattr(state, self_g_attr) + amt); setattr(state, opp_g_attr, getattr(state, opp_g_attr) + amt)
            self_log.append(f"Custom effect: {'+' if amt>=0 else ''}{amt} G"); opp_log.append(f"Custom effect: {'+' if amt>=0 else ''}{amt} G")
    elif state is not None and atype == 'add_random_g':
        amt = match_obj.random.randint(int(action.get('min',0)), int(action.get('max',0)))
        if target == 'opponent': setattr(state, opp_g_attr, getattr(state, opp_g_attr) + amt); opp_log.append(f"Custom effect: random +{amt} G")
        else: setattr(state, self_g_attr, getattr(state, self_g_attr) + amt); self_log.append(f"Custom effect: random +{amt} G")
    elif state is not None and atype in {'double_gate_bonus','multiply_gate_bonus'}:
        mult = float(action.get('multiplier', action.get('amount', 2 if atype=='double_gate_bonus' else 1)))
        if mult == 1: mult = 2.0
        if target == 'opponent':
            if attacker_slot: state.defender_bonus_multiplier *= mult
            else: state.attacker_bonus_multiplier *= mult
            opp_log.append(f'Custom effect: gate bonus x{mult:g}')
        elif target == 'both':
            state.attacker_bonus_multiplier *= mult; state.defender_bonus_multiplier *= mult
            self_log.append(f'Custom effect: gate bonus x{mult:g}'); opp_log.append(f'Custom effect: gate bonus x{mult:g}')
        else:
            if attacker_slot: state.attacker_bonus_multiplier *= mult
            else: state.defender_bonus_multiplier *= mult
            self_log.append(f'Custom effect: gate bonus x{mult:g}')
    elif state is not None and atype == 'block_color':
        color = str(action.get('color','RED')).upper()
        if color == 'RED':
            if target == 'opponent':
                if attacker_slot: state.defender_block_red = True
                else: state.attacker_block_red = True
                opp_log.append('Custom effect: Red cards blocked')
            elif target == 'both':
                state.attacker_block_red = True; state.defender_block_red = True
                self_log.append('Custom effect: Red cards blocked'); opp_log.append('Custom effect: Red cards blocked')
        else:
            if target == 'opponent':
                if attacker_slot: state.defender_prevent_abilities = True
                else: state.attacker_prevent_abilities = True
                opp_log.append(f'Custom effect: {color} cards blocked (general prevention)')
            elif target == 'both':
                state.attacker_prevent_abilities = True; state.defender_prevent_abilities = True
                self_log.append(f'Custom effect: {color} cards blocked (general prevention)'); opp_log.append(f'Custom effect: {color} cards blocked (general prevention)')
    elif state is not None and atype == 'block_attribute_effects':
        state.attacker_prevent_abilities = True; state.defender_prevent_abilities = True
        self_log.append('Custom effect: attribute effects canceled'); opp_log.append('Custom effect: attribute effects canceled')
    elif state is not None and atype == 'swap_original_g':
        state.attacker_g, state.defender_g = other.base_g, active.base_g
        self_log.append('Custom effect: original G swapped'); opp_log.append('Custom effect: original G swapped')
    elif state is not None and atype == 'swap_attributes':
        state.attacker_attribute_override = other.attribute; state.defender_attribute_override = active.attribute
        self_log.append('Custom effect: attributes swapped'); opp_log.append('Custom effect: attributes swapped')
    elif state is not None and atype == 'doom_loser':
        if target == 'self':
            if attacker_slot: state.doom_attacker = True
            else: state.doom_defender = True
            self_log.append('Custom effect: self doomed on loss')
        else:
            if attacker_slot: state.doom_defender = True
            else: state.doom_attacker = True
            self_log.append('Custom effect: loser doomed')
    elif atype == 'return_one_used_ability':
        target_player = opponent if target == 'opponent' else player
        used = match_obj.used_ability_idx.get(target_player.name, [])
        if used: used.pop()
    elif atype == 'return_all_used_abilities':
        for p in match_obj.players: match_obj.used_ability_idx[p.name].clear()
    elif atype == 'replace_with_unused_bakugan' and state is not None:
        replacement = match_obj._choose_support_bakugan(player, active, field_gate)
        if replacement is not None:
            self_log.append(f"Custom effect: replaced with {replacement.name}")
            return replacement
    elif atype in {'summon_support_bakugan','move_support_bakugan_into_battle'} and state is not None:
        match_obj._apply_attractor(player, active, field_gate, state, attacker_slot)
    elif state is not None and atype == 'reset_both_to_original_g':
        state.attacker_g = context['active_baku'].base_g if attacker_slot else context['other_baku'].base_g
        state.defender_g = context['other_baku'].base_g if attacker_slot else context['active_baku'].base_g
        self_log.append('Custom effect: reset to original G'); opp_log.append('Custom effect: reset to original G')
    elif state is not None and atype == 'add_g_by_attribute_map':
        amap = action.get('map', {})
        if target == 'opponent': amt = int(amap.get(other.attribute.name, 0)); setattr(state, opp_g_attr, getattr(state, opp_g_attr) + amt); opp_log.append(f"Custom effect: +{amt} G")
        else: amt = int(amap.get(active.attribute.name, 0)); setattr(state, self_g_attr, getattr(state, self_g_attr) + amt); self_log.append(f"Custom effect: +{amt} G")
    elif state is not None and atype == 'add_g_by_gates_won':
        target_player = opponent if target == 'opponent' else player; amt = int(action.get('scale',0)) * match_obj.match_stats[target_player.name].gates_captured
        if target == 'opponent': setattr(state, opp_g_attr, getattr(state, opp_g_attr) + amt); opp_log.append(f"Custom effect: +{amt} from won gates")
        else: setattr(state, self_g_attr, getattr(state, self_g_attr) + amt); self_log.append(f"Custom effect: +{amt} from won gates")
    elif state is not None and atype == 'add_g_by_used_abilities':
        target_player = opponent if target == 'opponent' else player; amt = int(action.get('scale',0)) * match_obj._used_ability_count(target_player)
        if target == 'opponent': setattr(state, opp_g_attr, getattr(state, opp_g_attr) + amt); opp_log.append(f"Custom effect: +{amt} from used abilities")
        else: setattr(state, self_g_attr, getattr(state, self_g_attr) + amt); self_log.append(f"Custom effect: +{amt} from used abilities")
    elif state is not None and atype == 'add_g_by_standing_attributes':
        amt = int(action.get('scale',0)) * max(1, len(match_obj._standing_attributes()))
        if target == 'opponent': setattr(state, opp_g_attr, getattr(state, opp_g_attr) + amt); opp_log.append(f"Custom effect: +{amt} from standing attributes")
        else: setattr(state, self_g_attr, getattr(state, self_g_attr) + amt); self_log.append(f"Custom effect: +{amt} from standing attributes")
    elif state is not None and atype == 'double_ability_boosts':
        if target == 'opponent':
            if attacker_slot: state.defender_ability_multiplier *= 2.0
            else: state.attacker_ability_multiplier *= 2.0
            opp_log.append('Custom effect: ability boosts doubled')
        elif target == 'both':
            state.attacker_ability_multiplier *= 2.0; state.defender_ability_multiplier *= 2.0
            self_log.append('Custom effect: ability boosts doubled'); opp_log.append('Custom effect: ability boosts doubled')
        else:
            if attacker_slot: state.attacker_ability_multiplier *= 2.0
            else: state.defender_ability_multiplier *= 2.0
            self_log.append('Custom effect: ability boosts doubled')
    elif state is not None and atype == 'prevent_abilities':
        if target == 'opponent':
            if attacker_slot: state.defender_prevent_abilities = True
            else: state.attacker_prevent_abilities = True
            opp_log.append('Custom effect: abilities prevented')
        elif target == 'both':
            state.attacker_prevent_abilities = True; state.defender_prevent_abilities = True
            self_log.append('Custom effect: abilities prevented'); opp_log.append('Custom effect: abilities prevented')
        else:
            if attacker_slot: state.attacker_prevent_abilities = True
            else: state.defender_prevent_abilities = True
            self_log.append('Custom effect: self abilities prevented')
    elif state is not None and atype == 'add_g_to_lower_current':
        amt = int(action.get('amount',0))
        if getattr(state, self_g_attr) < getattr(state, opp_g_attr): setattr(state, self_g_attr, getattr(state, self_g_attr) + amt); self_log.append(f"Custom effect: lower side +{amt} G")
        elif getattr(state, opp_g_attr) < getattr(state, self_g_attr): setattr(state, opp_g_attr, getattr(state, opp_g_attr) + amt); opp_log.append(f"Custom effect: lower side +{amt} G")
    elif state is not None and atype == 'add_g_if_attribute':
        attr = _attribute_from_value(action.get('attribute')); amt = int(action.get('amount',0))
        if active and attr and match_obj._has_attribute(active, attr): setattr(state, self_g_attr, getattr(state, self_g_attr) + amt); self_log.append(f"Custom effect: {attr.value} +{amt} G")
        if other and attr and match_obj._has_attribute(other, attr): setattr(state, opp_g_attr, getattr(state, opp_g_attr) + amt); opp_log.append(f"Custom effect: {attr.value} +{amt} G")
    return None

def _custom_effect_matches(match_obj, effect: Dict, context: Dict) -> bool:
    return all(_context_condition_match(match_obj, context, cond) for cond in effect.get('conditions', []))




def profile_age(profile: PlayerProfile) -> int:
    flags = profile.story_flags if isinstance(profile.story_flags, dict) else {}
    return int(flags.get("age", PLAYER_DEFAULT_AGE) or PLAYER_DEFAULT_AGE)

def profile_is_retired(profile: PlayerProfile) -> bool:
    flags = profile.story_flags if isinstance(profile.story_flags, dict) else {}
    return bool(flags.get("retired", 0))

def _skewed_stat(rng: random.Random, lo: float, hi: float, a: float = 1.35, b: float = 3.4) -> float:
    return round(lo + (hi - lo) * rng.betavariate(a, b), 2)

def ensure_age_metadata(profile: PlayerProfile, rng: random.Random, starting_age: Optional[int] = None) -> None:
    if not isinstance(profile.story_flags, dict):
        profile.story_flags = {}
    flags = profile.story_flags
    if starting_age is None:
        starting_age = int(flags.get("age", PLAYER_DEFAULT_AGE) or PLAYER_DEFAULT_AGE)
    age = max(PLAYER_MIN_AGE, int(starting_age))
    seeded = bool(flags.get("_age_seeded", 0))
    flags.setdefault("age", age)
    flags.setdefault("peak_age", max(age + rng.randint(3, 10), rng.randint(18, 28)))
    flags.setdefault("retirement_age", max(int(flags["peak_age"]) + rng.randint(3, 10), int(flags["peak_age"]) + 1))
    for key in ("growth_roll","growth_int","growth_agg","growth_risk"):
        flags.setdefault(key, round(rng.uniform(0.005, 0.025), 4))
    for key in ("decline_roll","decline_int","decline_agg","decline_risk"):
        flags.setdefault(key, round(rng.uniform(0.003, 0.018), 4))
    flags.setdefault("retired", 0)
    if not seeded:
        years = max(0, age - PLAYER_MIN_AGE)
        for _ in range(years):
            if age <= int(flags["peak_age"]):
                profile.rolling_skill = min(0.99, round(profile.rolling_skill + float(flags["growth_roll"]), 2))
                profile.intelligence = min(0.99, round(profile.intelligence + float(flags["growth_int"]), 2))
                profile.aggression = min(0.99, round(profile.aggression + float(flags["growth_agg"]), 2))
                profile.risk = min(0.99, round(profile.risk + float(flags["growth_risk"]), 2))
        flags["_age_seeded"] = 1

def age_profile_one_season(profile: PlayerProfile, rng: random.Random) -> bool:
    ensure_age_metadata(profile, rng, profile_age(profile))
    flags = profile.story_flags
    new_age = profile_age(profile) + 1
    flags["age"] = new_age
    peak_age = int(flags.get("peak_age", new_age))
    retirement_age = int(flags.get("retirement_age", peak_age + 5))
    if new_age <= peak_age:
        profile.rolling_skill = min(0.99, round(profile.rolling_skill + float(flags.get("growth_roll", 0.01)), 2))
        profile.intelligence = min(0.99, round(profile.intelligence + float(flags.get("growth_int", 0.01)), 2))
        profile.aggression = min(0.99, round(profile.aggression + float(flags.get("growth_agg", 0.01)), 2))
        profile.risk = min(0.99, round(profile.risk + float(flags.get("growth_risk", 0.01)), 2))
    else:
        profile.rolling_skill = max(0.05, round(profile.rolling_skill - float(flags.get("decline_roll", 0.01)), 2))
        profile.intelligence = max(0.05, round(profile.intelligence - float(flags.get("decline_int", 0.01)), 2))
        profile.aggression = max(0.05, round(profile.aggression - float(flags.get("decline_agg", 0.01)), 2))
        profile.risk = max(0.05, round(profile.risk - float(flags.get("decline_risk", 0.01)), 2))
    if not profile.is_human and new_age >= retirement_age:
        flags["retired"] = 1
        return True
    return False

def shortlist_future_prodigies(profiles: List[PlayerProfile], limit: int = 8) -> List[PlayerProfile]:
    eligible = [p for p in profiles if (not profile_is_retired(p)) and profile_age(p) <= 18]
    return sorted(
        eligible,
        key=lambda p: (p.glicko.rating, p.tournament_titles, p.podiums, p.fame, -profile_age(p), p.name.lower()),
        reverse=True,
    )[:limit]

def profile_active_loadout_is_legal_exact(profile: PlayerProfile) -> bool:
    baku_ok, _ = validate_bakugan_selection(list(profile.active_bakugan_idx), profile.collection_bakugan)
    gate_ok, _ = validate_gate_selection(list(profile.active_gate_idx), profile.collection_gates)
    ability_ok, _ = validate_ability_selection(list(profile.active_ability_idx), profile.collection_abilities)
    return baku_ok and gate_ok and ability_ok

def set_current_output_dir(label: str) -> Path:
    global CURRENT_OUTPUT_DIR
    safe = "".join(ch for ch in str(label) if ch.isalnum() or ch in ("_", "-", " ")).strip().replace(" ", "_") or "session_unsaved"
    CURRENT_OUTPUT_DIR = SAVE_OUTPUTS_DIR / safe
    CURRENT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return CURRENT_OUTPUT_DIR


def get_current_output_dir() -> Path:
    CURRENT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return CURRENT_OUTPUT_DIR


def random_suffix(rng: Optional[random.Random] = None, length: int = 6) -> str:
    rng = rng or random.Random()
    chars = string.ascii_lowercase + string.digits
    return "".join(rng.choice(chars) for _ in range(length))


def build_output_filename(
    tournament_type: str,
    participant_count: int,
    rounds: Optional[int] = None,
    suffix: Optional[str] = None,
) -> str:
    suffix = suffix or random_suffix()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if rounds is None:
        return f"{tournament_type}_{participant_count}players_{timestamp}_{suffix}.txt"
    return f"{tournament_type}_{participant_count}players_{rounds}rounds_{timestamp}_{suffix}.txt"


def build_save_filename(player_name: str, suffix: Optional[str] = None) -> str:
    suffix = suffix or random_suffix()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(ch for ch in player_name if ch.isalnum() or ch in ("_", "-", " ")).strip().replace(" ", "_")
    return f"save_{safe_name}_{timestamp}_{suffix}.json"


def serialize_savegame(player: "PlayerProfile", world_season: int, world_tournament_no: int, world_total_tournaments: int = 0, world_seed: int = 0) -> Dict:
    return {
        "save_version": 3,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "world_season": world_season,
        "world_tournament_no": world_tournament_no,
        "world_total_tournaments": int(world_total_tournaments),
        "world_seed": int(world_seed),
        "player": serialize_profile(player),
    }


def deserialize_savegame(payload: Dict) -> Tuple["PlayerProfile", int, int, int, int]:
    player = deserialize_profile(payload["player"])
    world_season = int(payload.get("world_season", 1))
    world_tournament_no = int(payload.get("world_tournament_no", 0))
    world_total_tournaments = int(payload.get("world_total_tournaments", max(0, (world_season - 1) * 10 + world_tournament_no)))
    world_seed = int(payload.get("world_seed", 0))
    return player, world_season, world_tournament_no, world_total_tournaments, world_seed


# ============================================================
# ENUMS
# ============================================================


# ============================================================
# NAMED BAKUGAN / GATE NAME NORMALISATION
# ============================================================

def normalize_named_bakugan_token(name: str) -> str:
    token = (name or "").strip().lower()
    token = token.replace("’", "'")
    token = token.replace("ii", "2")
    token = token.replace("delta dragonoid 2", "delta dragonoid")
    token = token.replace("delta dragonoid ii", "delta dragonoid")
    token = token.replace("preyas 2", "preyas")
    token = token.replace("preyas ii", "preyas")
    token = token.replace("preyas angelo", "preyas")
    token = token.replace("preyas diablo", "preyas")
    token = token.replace("angelo", "preyas")
    token = token.replace("diablo", "preyas")
    token = token.replace("fourtress", "fortress")
    token = token.replace("'s", "")
    token = re.sub(r"[^a-z0-9]+", " ", token).strip()
    return token

def _gate_targets_bakugan_name(gate: object, bakugan: object) -> bool:
    gate_name = normalize_named_bakugan_token(getattr(gate, "name", ""))
    baku_name = normalize_named_bakugan_token(getattr(bakugan, "name", ""))
    if not gate_name or not baku_name:
        return False
    return gate_name == baku_name


def season_bakugan_key(name: str) -> str:
    return normalize_named_bakugan_token(name)


def season_card_key(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def empty_season_ban_state(season_no: int = 0) -> Dict[str, object]:
    return {
        "season": int(season_no),
        "enabled": False,
        "bakugan": [],
        "gates": [],
        "abilities": [],
        "source_season": max(0, int(season_no) - 1),
    }


def profile_uses_banned_active(profile: "PlayerProfile", season_bans: Optional[Dict[str, object]]) -> bool:
    if not season_bans or not season_bans.get("enabled"):
        return False
    banned_b = {season_bakugan_key(x) for x in season_bans.get("bakugan", [])}
    banned_g = {season_card_key(x) for x in season_bans.get("gates", [])}
    banned_a = {season_card_key(x) for x in season_bans.get("abilities", [])}
    for b in profile.active_bakugan():
        if season_bakugan_key(b.name) in banned_b:
            return True
    for g in profile.active_gates():
        if season_card_key(g.name) in banned_g:
            return True
    for a in profile.active_abilities():
        if season_card_key(a.name) in banned_a:
            return True
    return False




def legal_ban_filtered_indices(profile: "PlayerProfile", season_bans: Optional[Dict[str, object]]) -> Tuple[List[int], List[int], List[int]]:
    if not season_bans or not season_bans.get("enabled"):
        return (
            list(range(len(profile.collection_bakugan))),
            list(range(len(profile.collection_gates))),
            list(range(len(profile.collection_abilities))),
        )
    banned_b = {season_bakugan_key(x) for x in season_bans.get("bakugan", [])}
    banned_g = {season_card_key(x) for x in season_bans.get("gates", [])}
    banned_a = {season_card_key(x) for x in season_bans.get("abilities", [])}
    baku_idx = [i for i, b in enumerate(profile.collection_bakugan) if season_bakugan_key(b.name) not in banned_b]
    gate_idx = [i for i, g in enumerate(profile.collection_gates) if season_card_key(g.name) not in banned_g]
    ability_idx = [i for i, a in enumerate(profile.collection_abilities) if season_card_key(a.name) not in banned_a]
    return baku_idx, gate_idx, ability_idx


def apply_ban_safe_fallback_loadout(profile: "PlayerProfile", season_bans: Optional[Dict[str, object]]) -> bool:
    baku_idx, gate_idx, ability_idx = legal_ban_filtered_indices(profile, season_bans)
    chosen_b = pick_unique_bakugan_indices(baku_idx, profile.collection_bakugan)
    chosen_g = pick_unique_gate_indices(gate_idx, profile.collection_gates)
    chosen_a = pick_unique_ability_indices(ability_idx, profile.collection_abilities)
    if len(chosen_b) < 3 or len(chosen_g) < 3 or len(chosen_a) < 3:
        return False
    profile.active_bakugan_idx = chosen_b
    profile.active_gate_idx = chosen_g
    profile.active_ability_idx = chosen_a
    profile.ensure_valid_loadout()
    return profile_has_minimum_legal_loadout(profile) and not profile_uses_banned_active(profile, season_bans)

def _baku_sig(b: "Bakugan") -> Tuple[str, str, int, int]:
    return (season_bakugan_key(b.name), b.attribute.value, int(b.base_g), int(getattr(b, "price", 0)))


def _gate_sig(g: "GateCard") -> Tuple[str, str, str, Tuple[Tuple[str, int], ...], int]:
    return (season_card_key(g.name), g.gate_type.value, g.effect_id, tuple(sorted((k.value, int(v)) for k, v in g.bonuses.items())), int(getattr(g, "price", 0)))


def _ability_sig(a: "AbilityCard") -> Tuple[str, str, str, int]:
    return (season_card_key(a.name), a.color.value, a.effect_id, int(getattr(a, "price", 0)))


def optimise_profile_loadout_with_bans(profile: "PlayerProfile", season_bans: Optional[Dict[str, object]] = None) -> None:
    if not season_bans or not season_bans.get("enabled"):
        optimise_profile_loadout(profile)
        return

    banned_b = {season_bakugan_key(x) for x in season_bans.get("bakugan", [])}
    banned_g = {season_card_key(x) for x in season_bans.get("gates", [])}
    banned_a = {season_card_key(x) for x in season_bans.get("abilities", [])}

    orig_b = list(profile.collection_bakugan)
    orig_g = list(profile.collection_gates)
    orig_a = list(profile.collection_abilities)

    filtered_b = [b for b in orig_b if season_bakugan_key(b.name) not in banned_b]
    filtered_g = [g for g in orig_g if season_card_key(g.name) not in banned_g]
    filtered_a = [a for a in orig_a if season_card_key(a.name) not in banned_a]

    if len({(b.name, b.attribute, b.base_g) for b in filtered_b}) < 3 or len({g.gate_type for g in filtered_g}) < 3 or len({a.color for a in filtered_a}) < 3:
        apply_ban_safe_fallback_loadout(profile, season_bans)
        return

    profile.collection_bakugan = filtered_b
    profile.collection_gates = filtered_g
    profile.collection_abilities = filtered_a
    optimise_profile_loadout(profile)

    chosen_b_sigs = [_baku_sig(profile.collection_bakugan[i]) for i in profile.active_bakugan_idx if 0 <= i < len(profile.collection_bakugan)]
    chosen_g_sigs = [_gate_sig(profile.collection_gates[i]) for i in profile.active_gate_idx if 0 <= i < len(profile.collection_gates)]
    chosen_a_sigs = [_ability_sig(profile.collection_abilities[i]) for i in profile.active_ability_idx if 0 <= i < len(profile.collection_abilities)]

    profile.collection_bakugan = orig_b
    profile.collection_gates = orig_g
    profile.collection_abilities = orig_a

    def remap(sig_list, pool, sig_fn):
        used = set()
        out = []
        for sig in sig_list:
            for idx, item in enumerate(pool):
                if idx in used:
                    continue
                if sig_fn(item) == sig:
                    out.append(idx)
                    used.add(idx)
                    break
        return out

    profile.active_bakugan_idx = remap(chosen_b_sigs, orig_b, _baku_sig)
    profile.active_gate_idx = remap(chosen_g_sigs, orig_g, _gate_sig)
    profile.active_ability_idx = remap(chosen_a_sigs, orig_a, _ability_sig)
    profile.ensure_valid_loadout()
    if profile_uses_banned_active(profile, season_bans) or not profile_has_minimum_legal_loadout(profile):
        apply_ban_safe_fallback_loadout(profile, season_bans)

class Attribute(str, Enum):
    PYRUS = "Pyrus"
    AQUOS = "Aquos"
    SUBTERRA = "Subterra"
    HAOS = "Haos"
    DARKUS = "Darkus"
    VENTUS = "Ventus"


class AbilityColor(str, Enum):
    RED = "Red"
    BLUE = "Blue"
    GREEN = "Green"


class GateType(str, Enum):
    GOLD = "Gold"
    SILVER = "Silver"
    BRONZE = "Bronze"


class Timing(Enum):
    DURING_ROLL = auto()
    DURING_BATTLE = auto()
    FLEXIBLE = auto()


class PlayerStyle(str, Enum):
    BALANCED = "Balanced"
    TACTICAL = "Tactical"
    RECKLESS = "Reckless"
    DEFENSIVE = "Defensive"
    COMBO = "Combo"
    AGGRESSIVE = "Aggressive"
    PATIENT = "Patient"
    ADAPTIVE = "Adaptive"
    OPPORTUNIST = "Opportunist"


class PlayerArchetype(str, Enum):
    POWER_RUSH = "Power Rush"
    GATE_CONTROL = "Gate Control"
    COMBO_SETUP = "Combo Setup"
    COUNTER = "Counter"
    BALANCED_TEMPO = "Balanced Tempo"
    ATTRITION = "Attrition"
    RESOURCE_LOOP = "Resource Loop"
    HIGH_ROLL = "High Roll"
    TEMPO_PIVOT = "Tempo Pivot"


class TournamentType(str, Enum):
    SWISS = "Swiss"
    KNOCKOUT = "Knockout"


# ============================================================
# GLICKO 2
# ============================================================

DEFAULT_START_RATING = 1500.0
DEFAULT_START_RD = 200.0
DEFAULT_START_SIGMA = 0.06
GLICKO2_SCALE = 173.7178
DEFAULT_TAU = 0.5

MAX_COLLECTION_BAKUGAN = 18
MAX_COLLECTION_GATES = 12
MAX_COLLECTION_ABILITIES = 12


@dataclass
class GlickoRating:
    rating: float = DEFAULT_START_RATING
    rd: float = DEFAULT_START_RD
    sigma: float = DEFAULT_START_SIGMA

    def copy(self) -> "GlickoRating":
        return GlickoRating(self.rating, self.rd, self.sigma)


def glicko_g(phi: float) -> float:
    return 1.0 / sqrt(1.0 + 3.0 * phi * phi / (pi * pi))


def glicko_E(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + exp(-glicko_g(phi_j) * (mu - mu_j)))


def glicko2_expected_score(player: GlickoRating, opponent: GlickoRating) -> float:
    mu = (player.rating - 1500.0) / GLICKO2_SCALE
    mu_j = (opponent.rating - 1500.0) / GLICKO2_SCALE
    phi_j = opponent.rd / GLICKO2_SCALE
    return glicko_E(mu, mu_j, phi_j)


def glicko2_update(player: GlickoRating, opponent: GlickoRating, score: float, tau: float = DEFAULT_TAU) -> GlickoRating:
    mu = (player.rating - 1500.0) / GLICKO2_SCALE
    phi = player.rd / GLICKO2_SCALE
    sigma = player.sigma

    mu_j = (opponent.rating - 1500.0) / GLICKO2_SCALE
    phi_j = opponent.rd / GLICKO2_SCALE

    g = glicko_g(phi_j)
    E = glicko_E(mu, mu_j, phi_j)
    v = 1.0 / (g * g * E * (1.0 - E))
    delta = v * g * (score - E)

    a = log(sigma * sigma)

    def f(x: float) -> float:
        ex = exp(x)
        num = ex * (delta * delta - phi * phi - v - ex)
        den = 2.0 * ((phi * phi + v + ex) ** 2)
        return (num / den) - ((x - a) / (tau * tau))

    A = a
    if delta * delta > phi * phi + v:
        B = log(delta * delta - phi * phi - v)
    else:
        k = 1
        while f(a - k * tau) < 0:
            k += 1
        B = a - k * tau

    fA = f(A)
    fB = f(B)
    while abs(B - A) > 1e-6:
        C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB < 0:
            A = B
            fA = fB
        else:
            fA = fA / 2.0
        B = C
        fB = fC

    sigma_prime = exp(A / 2.0)
    phi_star = sqrt(phi * phi + sigma_prime * sigma_prime)
    phi_prime = 1.0 / sqrt((1.0 / (phi_star * phi_star)) + (1.0 / v))
    mu_prime = mu + (phi_prime * phi_prime) * g * (score - E)

    return GlickoRating(
        rating=1500.0 + GLICKO2_SCALE * mu_prime,
        rd=GLICKO2_SCALE * phi_prime,
        sigma=sigma_prime,
    )


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class Bakugan:
    name: str
    attribute: Attribute
    base_g: int
    price: int = 150
    owner_name: str = ""
    used: bool = False


@dataclass
class BakuganTemplate:
    name: str
    allowed_attributes: List[Attribute]
    min_g_power: int
    max_g_power: int
    price: int

    @property
    def g_powers(self) -> List[int]:
        return list(range(self.min_g_power, self.max_g_power + 1, 10))

    def roll_instance(self, owner_name: str, rng: random.Random, forced_attribute: Optional[Attribute] = None) -> Bakugan:
        attr = forced_attribute if forced_attribute in self.allowed_attributes else rng.choice(self.allowed_attributes)
        g = rng.randrange(self.min_g_power, self.max_g_power + 10, 10)
        return Bakugan(self.name, attr, g, self.price, owner_name, False)


@dataclass
class AbilityCard:
    name: str
    color: AbilityColor
    timing: Timing
    description: str
    effect_id: str
    price: int = 100
    used: bool = False
    effect_mode: str = "builtin"
    custom_effect: Optional[Dict] = None
    effect_mode: str = "builtin"
    custom_effect: Optional[Dict] = None


@dataclass
class GateCard:
    name: str
    gate_type: GateType
    bonuses: Dict[Attribute, int]
    description: str
    effect_id: str
    price: int = 110
    used: bool = False
    effect_mode: str = "builtin"
    custom_effect: Optional[Dict] = None


@dataclass
class FieldGate:
    gate_card: GateCard
    set_by_player_name: str
    bakugan_on_card: List[Bakugan] = field(default_factory=list)
    revealed: bool = False

    def is_empty(self) -> bool:
        return len(self.bakugan_on_card) == 0

    def has_friendly_of(self, player_name: str) -> bool:
        return any(b.owner_name == player_name for b in self.bakugan_on_card)

    def has_opponent_of(self, player_name: str) -> bool:
        return any(b.owner_name != player_name for b in self.bakugan_on_card)

    def get_single_friendly_of(self, player_name: str) -> Optional[Bakugan]:
        for b in self.bakugan_on_card:
            if b.owner_name == player_name:
                return b
        return None

    def get_single_opponent_of(self, player_name: str) -> Optional[Bakugan]:
        for b in self.bakugan_on_card:
            if b.owner_name != player_name:
                return b
        return None


@dataclass
class BattleState:
    attacker_g: int
    defender_g: int
    attacker_mod_log: List[str] = field(default_factory=list)
    defender_mod_log: List[str] = field(default_factory=list)
    attacker_prevent_abilities: bool = False
    defender_prevent_abilities: bool = False
    attacker_bonus_multiplier: float = 1.0
    defender_bonus_multiplier: float = 1.0
    attacker_flat_gate_bonus_extra: int = 0
    defender_flat_gate_bonus_extra: int = 0
    attacker_attribute_override: Optional[Attribute] = None
    defender_attribute_override: Optional[Attribute] = None
    doom_attacker: bool = False
    doom_defender: bool = False
    attacker_block_red: bool = False
    defender_block_red: bool = False
    attacker_ability_multiplier: float = 1.0
    defender_ability_multiplier: float = 1.0


@dataclass
class MatchStats:
    rolls_attempted: int = 0
    rolls_landed: int = 0
    battles_fought: int = 0
    battles_won: int = 0
    abilities_used: int = 0
    gates_set: int = 0
    gates_captured: int = 0
    misses: int = 0
    tie_breakers_won: int = 0


@dataclass
class TournamentStats:
    score: float = 0.0
    wins: int = 0
    losses: int = 0
    matches_played: int = 0
    gate_diff: int = 0
    battle_diff: int = 0
    performance_total: float = 0.0
    opponents: List[str] = field(default_factory=list)
    buchholz: float = 0.0


@dataclass
class PlayerProfile:
    name: str
    chosen_attribute: Attribute
    style: PlayerStyle
    rolling_skill: float
    intelligence: float
    aggression: float
    risk: float
    money: int
    glicko: GlickoRating
    collection_bakugan: List[Bakugan]
    collection_gates: List[GateCard]
    collection_abilities: List[AbilityCard]
    active_bakugan_idx: List[int]
    active_gate_idx: List[int]
    active_ability_idx: List[int]
    is_human: bool = False
    wins: int = 0
    losses: int = 0
    tourney: TournamentStats = field(default_factory=TournamentStats)
    tournaments_entered: int = 0
    tournament_titles: int = 0
    finals: int = 0
    podiums: int = 0
    top8s: int = 0
    career_earnings: int = 0
    peak_rating: float = DEFAULT_START_RATING
    fame: int = 0
    training_points: int = 0
    sponsorship: int = 0
    career_stage: str = "Rookie"
    development_focus: str = "Balanced"
    archetype: PlayerArchetype = PlayerArchetype.BALANCED_TEMPO
    signature_bakugan: str = ""
    rivals: List[str] = field(default_factory=list)
    head_to_head: Dict[str, Dict[str, int]] = field(default_factory=dict)
    story_flags: Dict[str, int] = field(default_factory=dict)
    tournament_history: List[Dict[str, object]] = field(default_factory=list)

    def clone_for_match(self) -> "PlayerProfile":
        def clone_baku(b: Bakugan) -> Bakugan:
            return Bakugan(b.name, b.attribute, b.base_g, b.price, b.owner_name, False)

        def clone_gate(g: GateCard) -> GateCard:
            return GateCard(g.name, g.gate_type, dict(g.bonuses), g.description, g.effect_id, g.price, False, getattr(g, "effect_mode", "builtin"), deep_copy_effect(getattr(g, "custom_effect", None)))

        def clone_ability(a: AbilityCard) -> AbilityCard:
            return AbilityCard(a.name, a.color, a.timing, a.description, a.effect_id, a.price, False, getattr(a, "effect_mode", "builtin"), deep_copy_effect(getattr(a, "custom_effect", None)))

        return PlayerProfile(
            name=self.name,
            chosen_attribute=self.chosen_attribute,
            style=self.style,
            rolling_skill=self.rolling_skill,
            intelligence=self.intelligence,
            aggression=self.aggression,
            risk=self.risk,
            money=self.money,
            glicko=self.glicko.copy(),
            collection_bakugan=[clone_baku(b) for b in self.collection_bakugan],
            collection_gates=[clone_gate(g) for g in self.collection_gates],
            collection_abilities=[clone_ability(a) for a in self.collection_abilities],
            active_bakugan_idx=list(self.active_bakugan_idx),
            active_gate_idx=list(self.active_gate_idx),
            active_ability_idx=list(self.active_ability_idx),
            is_human=self.is_human,
            wins=self.wins,
            losses=self.losses,
            tourney=TournamentStats(**asdict(self.tourney)),
            tournaments_entered=self.tournaments_entered,
            tournament_titles=self.tournament_titles,
            finals=self.finals,
            podiums=self.podiums,
            top8s=self.top8s,
            career_earnings=self.career_earnings,
            peak_rating=self.peak_rating,
            fame=self.fame,
            training_points=self.training_points,
            sponsorship=self.sponsorship,
            career_stage=self.career_stage,
            development_focus=self.development_focus,
            archetype=self.archetype,
            signature_bakugan=self.signature_bakugan,
            rivals=list(self.rivals),
            head_to_head={k: dict(v) for k, v in self.head_to_head.items()},
            story_flags=dict(self.story_flags),
            tournament_history=[dict(x) for x in self.tournament_history],
        )

    def active_bakugan(self) -> List[Bakugan]:
        return [self.collection_bakugan[i] for i in self.active_bakugan_idx if 0 <= i < len(self.collection_bakugan)]

    def active_gates(self) -> List[GateCard]:
        return [self.collection_gates[i] for i in self.active_gate_idx if 0 <= i < len(self.collection_gates)]

    def active_abilities(self) -> List[AbilityCard]:
        return [self.collection_abilities[i] for i in self.active_ability_idx if 0 <= i < len(self.collection_abilities)]

    def ensure_valid_loadout(self) -> None:
        self.active_bakugan_idx = pick_unique_bakugan_indices(self.active_bakugan_idx, self.collection_bakugan)
        if len(self.active_bakugan_idx) < min(3, len(self.collection_bakugan)):
            fallback = list(range(len(self.collection_bakugan)))
            self.active_bakugan_idx = pick_unique_bakugan_indices(fallback, self.collection_bakugan)

        self.active_gate_idx = pick_unique_gate_indices(self.active_gate_idx, self.collection_gates)
        self.active_ability_idx = pick_unique_ability_indices(self.active_ability_idx, self.collection_abilities)

        baku_ok, _ = validate_bakugan_selection(self.active_bakugan_idx, self.collection_bakugan) if len(self.collection_bakugan) >= 3 else (True, "")
        if not baku_ok:
            fallback = list(range(len(self.collection_bakugan)))
            self.active_bakugan_idx = pick_unique_bakugan_indices(fallback, self.collection_bakugan)

        gate_ok, _ = validate_gate_selection(self.active_gate_idx, self.collection_gates) if len(self.collection_gates) >= 3 else (True, "")
        if not gate_ok:
            fallback = list(range(len(self.collection_gates)))
            self.active_gate_idx = pick_unique_gate_indices(fallback, self.collection_gates)

        ability_ok, _ = validate_ability_selection(self.active_ability_idx, self.collection_abilities) if len(self.collection_abilities) >= 3 else (True, "")
        if not ability_ok:
            fallback = list(range(len(self.collection_abilities)))
            self.active_ability_idx = pick_unique_ability_indices(fallback, self.collection_abilities)

    def update_career_stage(self) -> None:
        rating = self.glicko.rating
        if self.tournament_titles >= 5 or rating >= 1800:
            self.career_stage = "Champion"
        elif self.tournament_titles >= 2 or rating >= 1680:
            self.career_stage = "Star"
        elif self.finals >= 3 or rating >= 1600:
            self.career_stage = "Contender"
        elif self.tournaments_entered >= 8 or rating >= 1530:
            self.career_stage = "Veteran"
        else:
            self.career_stage = "Rookie"

    def record_matchup(self, other_name: str, did_win: bool) -> None:
        if not other_name or other_name == self.name:
            return
        rec = self.head_to_head.setdefault(other_name, {"wins": 0, "losses": 0})
        if did_win:
            rec["wins"] = int(rec.get("wins", 0)) + 1
        else:
            rec["losses"] = int(rec.get("losses", 0)) + 1
        self.update_rivals()

    def update_rivals(self) -> None:
        candidates = []
        for other_name, rec in self.head_to_head.items():
            wins = int(rec.get("wins", 0))
            losses = int(rec.get("losses", 0))
            total = wins + losses
            if total < 3:
                continue
            close_record = total >= 5 and abs(wins - losses) <= 1
            negative_record = losses > wins
            if not (close_record or negative_record):
                continue
            score = total * 10 + (losses - wins) * 6 - abs(wins - losses)
            candidates.append((score, total, losses - wins, other_name))
        candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3].lower()), reverse=True)
        self.rivals = [name for _, _, _, name in candidates[:3]]

    def record_rival(self, other_name: str) -> None:
        # Backward-compatible fallback; keeps manually flagged rivals but capped.
        if other_name and other_name != self.name and other_name not in self.rivals:
            self.rivals.append(other_name)
            self.rivals = self.rivals[-3:]

    def update_signature(self) -> None:
        if not self.collection_bakugan:
            return
        active_set = set()
        for idx in self.active_bakugan_idx:
            if 0 <= idx < len(self.collection_bakugan):
                active_set.add(id(self.collection_bakugan[idx]))
        best = max(
            self.collection_bakugan,
            key=lambda b: (
                id(b) in active_set,
                b.base_g,
                b.attribute == self.chosen_attribute,
                b.name,
            ),
        )
        self.signature_bakugan = f"{best.name} ({best.attribute.value} {best.base_g}G)"


@dataclass
class MatchRecord:
    round_no: int
    player1: str
    player2: str
    winner: str
    perf1: float
    perf2: float
    rating1_before: float
    rating2_before: float
    rating1_after: float
    rating2_after: float


@dataclass
class KnockoutResult:
    champion: Optional[PlayerProfile] = None
    placements: Dict[str, int] = field(default_factory=dict)
    rounds: List[List[Tuple[str, str, str]]] = field(default_factory=list)


# ============================================================
# LOGGING
# ============================================================

class Logger:
    def __init__(self, enabled: bool = False, prefix: str = "debug"):
        self.enabled = enabled
        self.prefix = prefix
        self.lines: List[str] = []

    def log(self, text: str) -> None:
        self.lines.append(text)
        if self.enabled:
            print(text)

    def save(self, filename: str) -> Path:
        path = DEBUG_DIR / filename
        path.write_text("\n".join(self.lines), encoding="utf-8")
        return path


# ============================================================
# CARD DATABASE
# ============================================================



def template_stock_key(template) -> str:
    return getattr(template, "name", str(template))


def gate_stock_key(gate) -> str:
    return getattr(gate, "name", str(gate))


def ability_stock_key(ability) -> str:
    return getattr(ability, "name", str(ability))

def all_attributes() -> List[Attribute]:
    return [
        Attribute.PYRUS,
        Attribute.AQUOS,
        Attribute.SUBTERRA,
        Attribute.HAOS,
        Attribute.DARKUS,
        Attribute.VENTUS,
    ]


def _attrs_from_names(names: List[str]) -> List[Attribute]:
    valid = []
    valid_names = ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS']
    for raw in names:
        if raw in Attribute.__members__:
            valid.append(Attribute[raw])
            continue
        upper = str(raw).upper()
        found = [Attribute[name] for name in valid_names if name in upper]
        for attr in found:
            if attr not in valid:
                valid.append(attr)
    if not valid:
        raise ValueError(f'No valid attributes parsed from: {names}')
    return valid


def make_bakugan_templates() -> List[BakuganTemplate]:
    templates: List[BakuganTemplate] = []
    for item in RAW_BAKUGAN_TEMPLATES:
        templates.append(
            BakuganTemplate(
                item["name"],
                _attrs_from_names(item["allowed_attributes"]),
                item.get("min_g_power"),
                item.get("max_g_power"),
                item["price"],
            )
        )
    return templates


def make_ability_cards() -> List[AbilityCard]:
    cards: List[AbilityCard] = []
    for item in RAW_ABILITY_CARDS:
        cards.append(
            AbilityCard(
                item["name"],
                AbilityColor[item["color"]],
                Timing[item["timing"]],
                item["description"],
                item["effect_id"],
                item["price"],
                False,
                item.get("effect_mode", "builtin"),
                normalise_custom_effect(item.get("custom_effect"), "PASSIVE_GATE"),
            )
        )
    return cards


def make_gate_cards() -> List[GateCard]:
    cards: List[GateCard] = []
    for item in RAW_GATE_CARDS:
        bonuses = {Attribute[k]: v for k, v in item["bonuses"].items()}
        cards.append(
            GateCard(
                item["name"],
                GateType[item["gate_type"]],
                bonuses,
                item["description"],
                item["effect_id"],
                item["price"],
                False,
                item.get("effect_mode", "builtin"),
                normalise_custom_effect(item.get("custom_effect"), "PASSIVE_GATE"),
            )
        )
    return cards


# ============================================================
# UTILS
# ============================================================

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def clone_bakugan(b: Bakugan) -> Bakugan:
    return Bakugan(b.name, b.attribute, b.base_g, b.price, b.owner_name, False)


def clone_gate(g: GateCard) -> GateCard:
    return GateCard(g.name, g.gate_type, dict(g.bonuses), g.description, g.effect_id, g.price, False, getattr(g, "effect_mode", "builtin"), deep_copy_effect(getattr(g, "custom_effect", None)))


def clone_ability(a: AbilityCard) -> AbilityCard:
    return AbilityCard(a.name, a.color, a.timing, a.description, a.effect_id, a.price, False, getattr(a, "effect_mode", "builtin"), deep_copy_effect(getattr(a, "custom_effect", None)))


def pick_unique_bakugan_indices(indices: List[int], collection: List[Bakugan]) -> List[int]:
    chosen: List[int] = []
    seen_exact: Set[Tuple[str, Attribute]] = set()
    for idx in indices:
        if not (0 <= idx < len(collection)) or idx in chosen:
            continue
        b = collection[idx]
        key = (b.name, b.attribute)
        if key in seen_exact:
            continue
        chosen.append(idx)
        seen_exact.add(key)
        if len(chosen) >= 3:
            return chosen[:3]
    for idx, b in enumerate(collection):
        if idx in chosen:
            continue
        key = (b.name, b.attribute)
        if key in seen_exact:
            continue
        chosen.append(idx)
        seen_exact.add(key)
        if len(chosen) >= 3:
            break
    return chosen[:3]


def validate_bakugan_selection(indices: List[int], collection: List[Bakugan]) -> Tuple[bool, str]:
    if len(indices) != 3 or len(set(indices)) != 3:
        return False, "Choose exactly 3 unique Bakugan."
    if any(not (0 <= i < len(collection)) for i in indices):
        return False, "One or more Bakugan indices are out of range."
    exact = [(collection[i].name, collection[i].attribute) for i in indices]
    if len(set(exact)) != 3:
        return False, "Your active Bakugan loadout cannot contain duplicate exact Bakugan. Example: only one Darkus Percival, but a Pyrus Percival is allowed."
    return True, ""



def pick_unique_gate_indices(indices: List[int], collection: List[GateCard], preferred_order: Optional[List[GateType]] = None) -> List[int]:
    preferred_order = preferred_order or [GateType.GOLD, GateType.SILVER, GateType.BRONZE]
    by_type: Dict[GateType, List[int]] = {gt: [] for gt in preferred_order}
    extras: List[int] = []
    seen: Set[int] = set()
    for idx in indices:
        if idx in seen or not (0 <= idx < len(collection)):
            continue
        seen.add(idx)
        gt = collection[idx].gate_type
        if gt in by_type:
            by_type[gt].append(idx)
        else:
            extras.append(idx)

    chosen: List[int] = []
    for gt in preferred_order:
        if by_type[gt]:
            chosen.append(by_type[gt][0])

    for idx in indices:
        if idx in chosen or not (0 <= idx < len(collection)):
            continue
        chosen.append(idx)
        if len(chosen) >= 3:
            break

    if len(chosen) < 3:
        for idx in range(len(collection)):
            if idx in chosen:
                continue
            chosen.append(idx)
            if len(chosen) >= 3:
                break
    return chosen[:3]


def pick_unique_ability_indices(indices: List[int], collection: List[AbilityCard], preferred_order: Optional[List[AbilityColor]] = None) -> List[int]:
    preferred_order = preferred_order or [AbilityColor.RED, AbilityColor.BLUE, AbilityColor.GREEN]
    by_color: Dict[AbilityColor, List[int]] = {c: [] for c in preferred_order}
    seen: Set[int] = set()
    for idx in indices:
        if idx in seen or not (0 <= idx < len(collection)):
            continue
        seen.add(idx)
        color = collection[idx].color
        if color in by_color:
            by_color[color].append(idx)

    chosen: List[int] = []
    for color in preferred_order:
        if by_color[color]:
            chosen.append(by_color[color][0])

    for idx in indices:
        if idx in chosen or not (0 <= idx < len(collection)):
            continue
        chosen.append(idx)
        if len(chosen) >= 3:
            break

    if len(chosen) < 3:
        for idx in range(len(collection)):
            if idx in chosen:
                continue
            chosen.append(idx)
            if len(chosen) >= 3:
                break
    return chosen[:3]


def validate_gate_selection(indices: List[int], collection: List[GateCard]) -> Tuple[bool, str]:
    if len(indices) != 3 or len(set(indices)) != 3:
        return False, "Choose exactly 3 unique gate cards."
    if any(not (0 <= i < len(collection)) for i in indices):
        return False, "One or more gate indices are out of range."
    types = [collection[i].gate_type for i in indices]
    if len(set(types)) != 3:
        return False, "Your active gate loadout must contain exactly one Gold, one Silver, and one Bronze gate."
    return True, ""


def validate_ability_selection(indices: List[int], collection: List[AbilityCard]) -> Tuple[bool, str]:
    if len(indices) != 3 or len(set(indices)) != 3:
        return False, "Choose exactly 3 unique ability cards."
    if any(not (0 <= i < len(collection)) for i in indices):
        return False, "One or more ability indices are out of range."
    colors = [collection[i].color for i in indices]
    if set(colors) != {AbilityColor.RED, AbilityColor.BLUE, AbilityColor.GREEN}:
        return False, "Your active ability loadout must contain exactly one Red, one Blue, and one Green ability."
    return True, ""



def player_loadout_lines(player: PlayerProfile, prefix: str = "") -> List[str]:
    player.ensure_valid_loadout()
    player.update_career_stage()
    player.update_signature()
    lines = []
    lines.append(f"{prefix}{player.name}")
    lines.append(
        f"{prefix}Style: {player.style.value} | Roll {player.rolling_skill:.2f} | Int {player.intelligence:.2f} | "
        f"Agg {player.aggression:.2f} | Risk {player.risk:.2f}"
    )
    lines.append(
        f"{prefix}Rating {player.glicko.rating:.0f} | RD {player.glicko.rd:.1f} | Sigma {player.glicko.sigma:.4f} | "
        f"Stage {player.career_stage} | Titles {player.tournament_titles} | Podiums {player.podiums} | Fame {player.fame}"
    )
    lines.append(
        f"{prefix}Career: Tournaments {player.tournaments_entered} | Earnings £{player.career_earnings} | Peak {player.peak_rating:.0f} | "
        f"Focus {player.development_focus} | Archetype {player.archetype.value} | Signature {player.signature_bakugan or 'N/A'}"
    )
    if player.rivals:
        lines.append(f"{prefix}Rivals: {', '.join(player.rivals[-5:])}")

    lines.append(f"{prefix}Bakugan:")
    for idx, b in enumerate(player.collection_bakugan):
        marker = "*" if idx in player.active_bakugan_idx else " "
        lines.append(f"{prefix}  {marker} [{idx}] {b.name} | {b.attribute.value} | {b.base_g} G")

    lines.append(f"{prefix}Gate Cards:")
    for idx, g in enumerate(player.collection_gates):
        marker = "*" if idx in player.active_gate_idx else " "
        lines.append(f"{prefix}  {marker} [{idx}] {g.name} | {g.gate_type.value}")

    lines.append(f"{prefix}Ability Cards:")
    for idx, a in enumerate(player.collection_abilities):
        marker = "*" if idx in player.active_ability_idx else " "
        lines.append(f"{prefix}  {marker} [{idx}] {a.name} | {a.color.value}")
    return lines


class ManualChoiceHandler:
    def choose_gate_to_set(self, player: PlayerProfile, remaining_gate_indices: List[int]) -> int:
        raise NotImplementedError

    def choose_bakugan_to_roll(self, player: PlayerProfile, remaining_bakugan_indices: List[int]) -> int:
        raise NotImplementedError

    def choose_target_gate(self, player: PlayerProfile, field_descriptions: List[str]) -> int:
        raise NotImplementedError

    def choose_roll_ability(self, player: PlayerProfile, options: List[int]) -> Optional[int]:
        raise NotImplementedError

    def choose_battle_ability(self, player: PlayerProfile, options: List[int], context: str) -> Optional[int]:
        raise NotImplementedError

    def choose_double_stand_action(self, player: PlayerProfile, current_gate_desc: str, other_gate_desc: str) -> str:
        raise NotImplementedError


class TkManualChoiceHandler(ManualChoiceHandler):
    def __init__(self, root: tk.Tk):
        self.root = root
        self.auto_rest = False

    def _ask_choice(self, title: str, prompt: str, options: List[str], allow_skip: bool = False) -> Optional[int]:
        msg = prompt + "\n\n" + "\n".join(f"{i}: {o}" for i, o in enumerate(options))
        if allow_skip:
            msg += "\n\nEnter blank to skip."
        while True:
            ans = simpledialog.askstring(title, msg, parent=self.root)
            if ans is None:
                return None if allow_skip else 0
            ans = ans.strip()
            if allow_skip and ans == "":
                return None
            if ans.isdigit():
                idx = int(ans)
                if 0 <= idx < len(options):
                    return idx
            messagebox.showerror("Invalid choice", "Please enter a valid index.", parent=self.root)

    def choose_gate_to_set(self, player: PlayerProfile, remaining_gate_indices: List[int]) -> int:
        options = [f"[{i}] {player.collection_gates[i].name} ({player.collection_gates[i].gate_type.value})" for i in remaining_gate_indices]
        choice = self._ask_choice("Choose Gate", f"{player.name}: choose a gate to set", options)
        if choice is None:
            return remaining_gate_indices[0]
        return remaining_gate_indices[choice]

    def choose_bakugan_to_roll(self, player: PlayerProfile, remaining_bakugan_indices: List[int]) -> int:
        options = [f"[{i}] {player.collection_bakugan[i].name} {player.collection_bakugan[i].attribute.value} {player.collection_bakugan[i].base_g} G" for i in remaining_bakugan_indices]
        choice = self._ask_choice("Choose Bakugan", f"{player.name}: choose Bakugan to roll", options)
        if choice is None:
            return remaining_bakugan_indices[0]
        return remaining_bakugan_indices[choice]

    def choose_target_gate(self, player: PlayerProfile, field_descriptions: List[str]) -> int:
        choice = self._ask_choice("Choose Target Gate", f"{player.name}: choose gate to aim at", field_descriptions)
        return 0 if choice is None else choice

    def choose_roll_ability(self, player: PlayerProfile, options: List[int]) -> Optional[int]:
        if not options:
            return None
        labels = [f"[{i}] {player.collection_abilities[i].name}" for i in options]
        choice = self._ask_choice("Roll Ability", f"{player.name}: choose a roll ability", labels, allow_skip=True)
        return None if choice is None else options[choice]

    def choose_battle_ability(self, player: PlayerProfile, options: List[int], context: str) -> Optional[int]:
        if not options:
            return None
        labels = [f"[{i}] {player.collection_abilities[i].name}" for i in options]
        choice = self._ask_choice("Battle Ability", f"{player.name}: choose a battle ability\n{context}", labels, allow_skip=True)
        return None if choice is None else options[choice]

    def choose_double_stand_action(self, player: PlayerProfile, current_gate_desc: str, other_gate_desc: str) -> str:
        options = [
            f"Win current gate now: {current_gate_desc}",
            f"Move newest Bakugan to other gate: {other_gate_desc}",
        ]
        choice = self._ask_choice("Double Stand", f"{player.name}: choose what to do after a double stand", options)
        return "capture" if choice in (None, 0) else "move"


# ============================================================
# MATCH ENGINE
# ============================================================

class Match:
    def __init__(
        self,
        player1: PlayerProfile,
        player2: PlayerProfile,
        seed: Optional[int] = None,
        verbose: bool = False,
        logger: Optional[Logger] = None,
        manual_handler: Optional[ManualChoiceHandler] = None,
        manual_player_name: Optional[str] = None,
    ):
        self.random = random.Random(seed)
        self.players = [player1.clone_for_match(), player2.clone_for_match()]
        self.turn_index = 0
        self.turn_count = 1
        self.max_turns = 200
        self.field: List[FieldGate] = []
        self.logger = logger or Logger(enabled=verbose)
        self.verbose = verbose
        self.manual_handler = manual_handler
        self.manual_player_name = manual_player_name

        self.used_bakugan_idx: Dict[str, List[int]] = {p.name: [] for p in self.players}
        self.used_ability_idx: Dict[str, List[int]] = {p.name: [] for p in self.players}
        self.remaining_gate_idx: Dict[str, List[int]] = {p.name: list(p.active_gate_idx) for p in self.players}
        self.remaining_bakugan_cycle_idx: Dict[str, List[int]] = {p.name: list(p.active_bakugan_idx) for p in self.players}
        self.captured: Dict[str, List[GateCard]] = {p.name: [] for p in self.players}
        self.match_stats: Dict[str, MatchStats] = {p.name: MatchStats() for p in self.players}
        self.temp_roll_modifiers: Dict[str, float] = {p.name: 0.0 for p in self.players}
        self.removed_bakugan_idx: Dict[str, Set[int]] = {p.name: set() for p in self.players}
        self.pending_a_hand_up: Optional[str] = None
        self.pending_combo_battle: Optional[str] = None
        self.pending_lockdown: Optional[str] = None
        self.pending_level_down: Optional[str] = None
        self.pending_do_over: Optional[str] = None
        self.pending_roll_battle_bonus: Dict[str, int] = defaultdict(int)

    def log(self, text: str) -> None:
        self.logger.log(text)

    def current_player(self) -> PlayerProfile:
        return self.players[self.turn_index]

    def other_player(self) -> PlayerProfile:
        return self.players[1 - self.turn_index]

    def player_is_manual(self, player: PlayerProfile) -> bool:
        return (
            self.manual_handler is not None
            and player.name == self.manual_player_name
            and not getattr(self.manual_handler, "auto_rest", False)
        )


    def _strategic_plan(self, player: PlayerProfile) -> Dict[str, float]:
        smartness = clamp(player.intelligence, 0.2, 0.99)
        pressure = self._match_pressure(player)
        own_gates = len(self.captured[player.name])
        opp = self.other_player() if self.current_player().name == player.name else self.current_player()
        opp_gates = len(self.captured[opp.name])
        lead = own_gates - opp_gates
        archetype = getattr(player, "archetype", PlayerArchetype.BALANCED_TEMPO)
        style = getattr(player, "style", PlayerStyle.BALANCED)

        plan = {
            "contest_bias": 0.0,
            "empty_bias": 0.0,
            "resource_conserve": 0.0,
            "setup_bias": 0.0,
            "snowball_bias": 0.0,
            "comeback_bias": 0.0,
            "ace_preserve": 0.0,
            "risk_push": 0.0,
        }

        if lead > 0:
            plan["empty_bias"] += 18 + 16 * smartness
            plan["resource_conserve"] += 10 + 12 * smartness
            plan["ace_preserve"] += 6 + 12 * smartness
        elif lead < 0:
            plan["contest_bias"] += 18 + 20 * smartness
            plan["comeback_bias"] += 10 + 14 * smartness
            plan["risk_push"] += 6 + 10 * smartness

        if pressure["own_match_point"]:
            plan["empty_bias"] += 12
            plan["resource_conserve"] += 10
        if pressure["opp_match_point"]:
            plan["contest_bias"] += 18
            plan["comeback_bias"] += 12

        if archetype == PlayerArchetype.POWER_RUSH:
            plan["contest_bias"] += 16
            plan["snowball_bias"] += 14
            plan["risk_push"] += 8
        elif archetype == PlayerArchetype.GATE_CONTROL:
            plan["empty_bias"] += 14
            plan["resource_conserve"] += 6
        elif archetype == PlayerArchetype.COMBO_SETUP:
            plan["setup_bias"] += 20
            plan["resource_conserve"] += 8
        elif archetype == PlayerArchetype.COUNTER:
            plan["contest_bias"] += 8
            plan["resource_conserve"] += 12
        elif archetype == PlayerArchetype.ATTRITION:
            plan["resource_conserve"] += 18
            plan["empty_bias"] += 8
        elif archetype == PlayerArchetype.RESOURCE_LOOP:
            plan["setup_bias"] += 14
            plan["resource_conserve"] += 18
        elif archetype == PlayerArchetype.HIGH_ROLL:
            plan["risk_push"] += 18
            plan["contest_bias"] += 8
        elif archetype == PlayerArchetype.TEMPO_PIVOT:
            plan["contest_bias"] += 10
            plan["empty_bias"] += 10
            plan["setup_bias"] += 10

        if style == PlayerStyle.TACTICAL:
            plan["resource_conserve"] += 8
            plan["ace_preserve"] += 8
        elif style == PlayerStyle.DEFENSIVE:
            plan["empty_bias"] += 12
            plan["resource_conserve"] += 10
        elif style == PlayerStyle.RECKLESS:
            plan["contest_bias"] += 18
            plan["risk_push"] += 16
        elif style == PlayerStyle.COMBO:
            plan["setup_bias"] += 18
        elif style == PlayerStyle.AGGRESSIVE:
            plan["contest_bias"] += 16
            plan["snowball_bias"] += 12
        elif style == PlayerStyle.PATIENT:
            plan["empty_bias"] += 12
            plan["ace_preserve"] += 14
            plan["resource_conserve"] += 12
        elif style == PlayerStyle.ADAPTIVE:
            plan["contest_bias"] += 6
            plan["empty_bias"] += 6
            plan["setup_bias"] += 6
        elif style == PlayerStyle.OPPORTUNIST:
            plan["contest_bias"] += 10
            plan["comeback_bias"] += 10
            plan["ace_preserve"] += 4

        return plan

    def _remaining_bakugan_for_turn(self, player: PlayerProfile) -> List[int]:
        remaining = [
            i for i in player.active_bakugan_idx
            if i not in self.used_bakugan_idx[player.name] and i not in self.removed_bakugan_idx[player.name]
        ]
        if not remaining:
            self.used_bakugan_idx[player.name].clear()
            remaining = [i for i in player.active_bakugan_idx if i not in self.removed_bakugan_idx[player.name]]
            if remaining:
                self.log(f"{player.name} refreshes Bakugan and can reuse their loadout")
        return remaining

    def _unused_abilities(self, player: PlayerProfile, timings: Optional[List[Timing]] = None) -> List[int]:
        out = []
        for idx in player.active_ability_idx:
            if idx in self.used_ability_idx[player.name]:
                continue
            ability = player.collection_abilities[idx]
            if timings is None or ability.timing in timings:
                out.append(idx)
        return out

    def _bakugan_index(self, player: PlayerProfile, bakugan: Bakugan) -> Optional[int]:
        for idx, candidate in enumerate(player.collection_bakugan):
            if candidate is bakugan:
                return idx
        return None

    def _used_ability_count(self, player: PlayerProfile) -> int:
        return len(self.used_ability_idx[player.name])

    def _used_gate_count(self, player: PlayerProfile) -> int:
        return self.match_stats[player.name].gates_set + len(self.captured[player.name])

    def _standing_attributes(self) -> Set[Attribute]:
        attrs: Set[Attribute] = set()
        for fg in self.field:
            for baku in fg.bakugan_on_card:
                attrs.update(self._attribute_options(baku))
        return attrs

    def _effective_attribute(self, bakugan: Bakugan, state: BattleState, attacker_slot: bool) -> Attribute:
        override = state.attacker_attribute_override if attacker_slot else state.defender_attribute_override
        return override or bakugan.attribute

    def _attribute_options(self, bakugan: Bakugan) -> List[Attribute]:
        if bakugan.name == "Preyas Diablo":
            return [Attribute.PYRUS, Attribute.AQUOS]
        if bakugan.name == "Preyas Angelo":
            return [Attribute.HAOS, Attribute.AQUOS]
        return [bakugan.attribute]

    def _has_attribute(self, bakugan: Bakugan, attribute: Attribute) -> bool:
        return attribute in self._attribute_options(bakugan)

    def _attribute_label(self, bakugan: Bakugan) -> str:
        attrs = self._attribute_options(bakugan)
        if len(attrs) == 1:
            return attrs[0].value
        return "/".join(attr.value for attr in attrs)

    def _is_dragonoid_family(self, bakugan: Bakugan) -> bool:
        return "Dragonoid" in bakugan.name or bakugan.name in {"Delta", "Neo Dragonoid", "Cross Dragonoid", "Helix Dragonoid", "Ultimate Dragonoid"}

    def _best_value_for_bakugan(self, bakugan: Bakugan, value_map: Dict[Attribute, int]) -> int:
        return max(value_map.get(attr, 0) for attr in self._attribute_options(bakugan))

    def _best_gate_bonus_for_bakugan(self, bakugan: Bakugan, gate: GateCard) -> int:
        return max(gate.bonuses.get(attr, 0) for attr in self._attribute_options(bakugan))

    def _normalized_bakugan_name(self, name: str) -> str:
        norm = ''.join(ch.lower() for ch in name if ch.isalnum())
        alias_map = {
            'deltadragonoid': 'deltadragonoidii',
            'deltadragonoidii': 'deltadragonoidii',
            'fortress': 'fourtress',
            'fourtress': 'fourtress',
            'angelodiablopreyas': 'preyasii',
            'diabloangelopreyas': 'preyasii',
            'preyasangelo': 'preyasii',
            'preyasdiablo': 'preyasii',
            'preyasii': 'preyasii',
            'preyas': 'preyas',
        }
        return alias_map.get(norm, norm)

    def _gate_named_target_key(self, gate: GateCard) -> str:
        gate_name_key = self._normalized_bakugan_name(gate.name)
        if gate_name_key in {'preyas', 'preyasii', 'deltadragonoidii', 'fourtress'}:
            return gate_name_key
        desc = (gate.description or '').lower()
        if 'preyas ii' in desc:
            return 'preyasii'
        if 'preyas gets the gate card bonus twice' in desc:
            return 'preyas'
        if 'delta dragonoid ii' in desc:
            return 'deltadragonoidii'
        if 'fourtress' in desc or 'fortress' in desc:
            return 'fourtress'
        return gate_name_key

    def _gate_gets_named_double_bonus(self, gate: GateCard, bakugan: Bakugan) -> bool:
        if gate.effect_id != 'GATE_DOUBLE_BONUS_NAMED':
            return False
        return self._gate_named_target_key(gate) == self._normalized_bakugan_name(bakugan.name)

    def _randomize_special_stand_form(self, bakugan: Bakugan) -> None:
        original_name = bakugan.name
        if original_name == "Preyas":
            new_attr = self.random.choice(all_attributes())
            bakugan.attribute = new_attr
            self.log(f"{original_name} changes attribute on stand to {new_attr.value}")
        elif original_name in {"Diablo/Angelo", "Angelo/Diablo Preyas", "Diablo/Angelo Preyas"}:
            form = self.random.choice(["Diablo", "Angelo"])
            if form == "Diablo":
                bakugan.name = "Preyas Diablo"
                bakugan.attribute = Attribute.PYRUS
            else:
                bakugan.name = "Preyas Angelo"
                bakugan.attribute = Attribute.HAOS
            self.log(f"{original_name} opens as {bakugan.name} with {self._attribute_label(bakugan)} attributes")

    def _bakugan_in_arena(self, player: PlayerProfile, idx: int) -> bool:
        target = player.collection_bakugan[idx]
        for fg in self.field:
            for baku in fg.bakugan_on_card:
                if baku is target:
                    return True
        return False

    def _best_unused_bakugan_idx(self, player: PlayerProfile, field_gate: Optional[FieldGate] = None, exclude_idx: Optional[int] = None) -> Optional[int]:
        candidates = []
        for idx in player.active_bakugan_idx:
            if idx == exclude_idx:
                continue
            if idx in self.removed_bakugan_idx[player.name]:
                continue
            if self._bakugan_in_arena(player, idx):
                continue
            baku = player.collection_bakugan[idx]
            score = baku.base_g
            if field_gate is not None:
                score += self._best_gate_bonus_for_bakugan(baku, field_gate.gate_card)
            candidates.append((score, idx))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        return candidates[0][1]

    def _choose_support_bakugan(self, player: PlayerProfile, active_baku: Bakugan, field_gate: Optional[FieldGate] = None) -> Optional[Bakugan]:
        active_idx = self._bakugan_index(player, active_baku)
        best_idx = self._best_unused_bakugan_idx(player, field_gate, exclude_idx=active_idx)
        if best_idx is None:
            return None
        return player.collection_bakugan[best_idx]

    def _apply_attractor(self, player: PlayerProfile, active_baku: Bakugan, field_gate: Optional[FieldGate], state: BattleState, attacker_slot: bool) -> Optional[Bakugan]:
        support_baku = self._choose_support_bakugan(player, active_baku, field_gate)
        if support_baku is None:
            return None

        support_idx = self._bakugan_index(player, support_baku)
        if support_idx is not None and support_idx in self.removed_bakugan_idx[player.name]:
            return None

        own_g_attr = 'attacker_g' if attacker_slot else 'defender_g'
        own_log = state.attacker_mod_log if attacker_slot else state.defender_mod_log
        setattr(state, own_g_attr, getattr(state, own_g_attr) + support_baku.base_g)

        if support_idx is not None and support_idx not in self.used_bakugan_idx[player.name]:
            self.used_bakugan_idx[player.name].append(support_idx)

        own_log.append(f"Support Bakugan {support_baku.name}: +{support_baku.base_g}")
        self.log(f"{player.name} calls in support from {support_baku.name}")
        return support_baku

    def _move_all_field_bakugan_to_used(self) -> None:
        for fg in self.field:
            for baku in fg.bakugan_on_card:
                owner = next(p for p in self.players if p.name == baku.owner_name)
                idx = self._bakugan_index(owner, baku)
                if idx is not None and idx not in self.used_bakugan_idx[owner.name]:
                    self.used_bakugan_idx[owner.name].append(idx)
            fg.bakugan_on_card.clear()

    def setup_field_if_needed(self) -> None:
        if len(self.field) >= 2:
            return

        for player in self.players:
            if len(self.field) >= 2:
                break
            if not self.remaining_gate_idx[player.name]:
                continue
            gate_idx = self.choose_gate_to_set(player)
            gate = clone_gate(player.collection_gates[gate_idx])
            self.remaining_gate_idx[player.name].remove(gate_idx)
            self.match_stats[player.name].gates_set += 1
            self.field.append(FieldGate(gate_card=gate, set_by_player_name=player.name))
            self.log(f"{player.name} sets {gate.name} to the field")

    def choose_gate_to_set(self, player: PlayerProfile) -> int:
        options = list(self.remaining_gate_idx[player.name])
        if self.player_is_manual(player):
            manual_choice = self.manual_handler.choose_gate_to_set(player, options)
            if not getattr(self.manual_handler, "auto_rest", False):
                return manual_choice

        smartness = clamp(player.intelligence, 0.2, 0.99)
        active_bakus = [player.collection_bakugan[i] for i in player.active_bakugan_idx if 0 <= i < len(player.collection_bakugan)]
        score_map = []
        for idx in options:
            gate = player.collection_gates[idx]
            score = gate_profile_value(player, gate, active_bakus=active_bakus, intelligence_override=smartness)
            if player.style == PlayerStyle.TACTICAL:
                score += 16
            if player.style == PlayerStyle.DEFENSIVE and gate.gate_type == GateType.SILVER:
                score += 14
            if player.style == PlayerStyle.COMBO and gate.gate_type == GateType.GOLD:
                score += 10
            if player.style == PlayerStyle.AGGRESSIVE and gate.gate_type == GateType.GOLD:
                score += 10
            if player.style == PlayerStyle.PATIENT and gate.gate_type == GateType.BRONZE:
                score += 8
            if player.style == PlayerStyle.OPPORTUNIST and gate.gate_type != GateType.GOLD:
                score += 6
            score += self.random.uniform(-38, 38) * (1.0 - smartness)
            score_map.append((score, idx))
        score_map.sort(reverse=True)
        return score_map[0][1]

    def choose_bakugan_to_roll(self, player: PlayerProfile) -> int:
        remaining = self._remaining_bakugan_for_turn(player)
        if self.player_is_manual(player):
            manual_choice = self.manual_handler.choose_bakugan_to_roll(player, remaining)
            if not getattr(self.manual_handler, "auto_rest", False):
                return manual_choice

        smartness = clamp(player.intelligence, 0.2, 0.99)
        plan = self._strategic_plan(player)

        def score_idx(idx: int) -> float:
            b = player.collection_bakugan[idx]
            total = b.base_g * (0.92 + 0.14 * smartness)
            empty_lanes = sum(1 for fg in self.field if fg.is_empty())
            for fg in self.field:
                gate_bonus = self._best_gate_bonus_for_bakugan(b, fg.gate_card)
                total += gate_bonus * (0.42 + 0.72 * smartness)
                total += gate_profile_value(player, fg.gate_card, active_bakus=[b], intelligence_override=smartness) * (0.08 + 0.10 * smartness)
                opp = fg.get_single_opponent_of(player.name)
                if opp:
                    opp_bonus = self._best_gate_bonus_for_bakugan(opp, fg.gate_card)
                    projected = (b.base_g + gate_bonus) - (opp.base_g + opp_bonus)
                    total += projected * (0.34 + 0.54 * smartness)
                    total += 48 * player.aggression
                    if projected < 0:
                        total -= abs(projected) * (0.12 + 0.22 * smartness - 0.10 * player.risk)
                elif empty_lanes > 0:
                    total += 12 + 16 * smartness - 12 * player.aggression
            strongest_idx = max(remaining, key=lambda j: player.collection_bakugan[j].base_g) if remaining else idx
            weakest_idx = min(remaining, key=lambda j: player.collection_bakugan[j].base_g) if remaining else idx
            if len(remaining) >= 3 and idx == strongest_idx:
                total -= (18 * smartness * (1.0 - player.risk)) + plan["ace_preserve"]
            if idx == weakest_idx and plan["empty_bias"] > plan["contest_bias"]:
                total += 8 + 10 * smartness
            if idx == strongest_idx and plan["contest_bias"] > plan["empty_bias"]:
                total += 8 + 8 * smartness
            total += plan["snowball_bias"] * 0.35
            total += plan["comeback_bias"] * 0.20 if 0 < 0 else 0.0
            total += plan["risk_push"] * player.risk * 0.35
            total += self.random.uniform(-52, 52) * (1.0 - smartness)
            return total

        return max(remaining, key=score_idx)

    def choose_target_gate(self, player: PlayerProfile, bakugan_idx: int) -> int:
        bakugan = player.collection_bakugan[bakugan_idx]
        if self.player_is_manual(player):
            descriptions = []
            for fg in self.field:
                desc = f"{fg.gate_card.name} | set by {fg.set_by_player_name}"
                occ = ", ".join(f"{b.owner_name}:{b.name}" for b in fg.bakugan_on_card) or "empty"
                desc += f" | {occ}"
                descriptions.append(desc)
            manual_choice = self.manual_handler.choose_target_gate(player, descriptions)
            if not getattr(self.manual_handler, "auto_rest", False):
                return manual_choice

        smartness = clamp(player.intelligence, 0.2, 0.99)
        plan = self._strategic_plan(player)
        scores = []
        for i, fg in enumerate(self.field):
            gate_bonus = self._best_gate_bonus_for_bakugan(bakugan, fg.gate_card)
            score = gate_bonus * (0.65 + 0.85 * smartness)
            score += gate_profile_value(player, fg.gate_card, active_bakus=[bakugan], intelligence_override=smartness) * (0.10 + 0.08 * smartness)
            if fg.is_empty():
                score += 24 * (1.0 - player.aggression) + 10 * smartness + plan["empty_bias"]
            if fg.has_opponent_of(player.name):
                opp = fg.get_single_opponent_of(player.name)
                if opp:
                    opp_bonus = self._best_gate_bonus_for_bakugan(opp, fg.gate_card)
                    projection = (bakugan.base_g + gate_bonus) - (opp.base_g + opp_bonus)
                    score += projection * (0.38 + 0.70 * smartness)
                    score += 58 * player.aggression + plan["contest_bias"]
                    if projection < 0:
                        score -= abs(projection) * (0.18 + 0.18 * smartness - 0.08 * player.risk)
                    elif projection > 0:
                        score += min(90, projection) * (0.08 + 0.12 * smartness)
            if fg.has_friendly_of(player.name) and not fg.has_opponent_of(player.name):
                score -= 85 * smartness + plan["ace_preserve"] * 0.5
            score += self.random.uniform(-48, 48) * (1.0 - smartness)
            scores.append((score, i))
        scores.sort(reverse=True)
        return scores[0][1]

    def choose_roll_ability(self, player: PlayerProfile, bakugan_idx: int, target_gate_idx: int) -> Optional[int]:
        options = self._unused_abilities(player, [Timing.DURING_ROLL, Timing.FLEXIBLE])
        if not options:
            return None
        if self.player_is_manual(player):
            manual_choice = self.manual_handler.choose_roll_ability(player, options)
            if not getattr(self.manual_handler, "auto_rest", False):
                return manual_choice

        smartness = clamp(player.intelligence, 0.2, 0.99)
        plan = self._strategic_plan(player)
        bakugan = player.collection_bakugan[bakugan_idx]
        target_gate = self.field[target_gate_idx]
        projected_need = 0.0
        if target_gate.has_opponent_of(player.name):
            opp = target_gate.get_single_opponent_of(player.name)
            if opp is not None:
                projected_need = (opp.base_g + self._best_gate_bonus_for_bakugan(opp, target_gate.gate_card)) - (bakugan.base_g + self._best_gate_bonus_for_bakugan(bakugan, target_gate.gate_card))
        scored = []
        for idx in options:
            ability = player.collection_abilities[idx]
            score = -999.0
            if ability.effect_id == "EXACT_A_HAND_UP":
                score = 55 + max(0.0, projected_need) * 0.35 if self._has_attribute(bakugan, Attribute.HAOS) else -999
            elif ability.effect_id == "EXACT_CLEAN_SLATE":
                occupied = sum(len(fg.bakugan_on_card) for fg in self.field)
                score = 48 + occupied * (10 + 8 * smartness) if self._has_attribute(bakugan, Attribute.DARKUS) and occupied else -999
            elif ability.effect_id == "EXACT_COMBO_BATTLE":
                support_count = sum(1 for j in player.active_bakugan_idx if j not in self.used_bakugan_idx[player.name] and j != bakugan_idx)
                score = 42 + support_count * 14 + (16 if target_gate.has_opponent_of(player.name) else 0)
            elif ability.effect_id == "EXACT_LOCKDOWN":
                score = 44 + max(0.0, projected_need) * 0.28
            elif ability.effect_id == "EXACT_LEVEL_DOWN":
                score = 40 + max(0.0, projected_need) * 0.30
            elif ability.effect_id == "EXACT_DO_OVER":
                score = 34 + 12 * smartness
            elif ability.effect_id == "ROLL_PLUS":
                score = 18 + max(0.0, projected_need) * 0.12
            elif ability.effect_id == "ROLL_CHOOSE_BEST":
                score = 20 + max(0.0, projected_need) * 0.10
            elif ability.effect_id == "ROLL_RECOVER":
                score = 16 + (10 if bakugan.base_g < 380 else 0)
            elif ability.effect_id == "ROLL_IGNORE_BAD_MATCH":
                score = 14 + max(0.0, projected_need) * 0.16
            elif ability.effect_id == "ROLL_BATTLE_BONUS":
                score = 16 + self._best_gate_bonus_for_bakugan(bakugan, target_gate.gate_card) * 0.18
            if score > -999:
                tags = ability_tags(ability)
                if "combo" in tags:
                    score += plan["setup_bias"] * 0.65
                if "resource" in tags:
                    score += plan["resource_conserve"] * 0.60
                if "comeback" in tags:
                    score += plan["comeback_bias"] * 0.70
                if "raw_power" in tags:
                    score += plan["risk_push"] * 0.35 + plan["snowball_bias"] * 0.40
                score += self.random.uniform(-10, 10) * (1.0 - smartness)
                scored.append((score, idx))
        if not scored:
            return None
        scored.sort(reverse=True)
        best_score, best_idx = scored[0]
        use_threshold = 28 + 26 * smartness - max(0.0, projected_need) * 0.12
        return best_idx if best_score > use_threshold else None

    def apply_roll_ability(self, player: PlayerProfile, ability_idx: int, bakugan_idx: int) -> None:
        ability = player.collection_abilities[ability_idx]
        bakugan = player.collection_bakugan[bakugan_idx]
        self.used_ability_idx[player.name].append(ability_idx)
        self.match_stats[player.name].abilities_used += 1

        if getattr(ability, "effect_mode", "builtin") == "custom" or ability.effect_id == "CUSTOM":
            context = {"player": player, "active_baku": bakugan}
            eff = normalise_custom_effect(getattr(ability, "custom_effect", None), ability.timing.name)
            if _custom_effect_matches(self, eff, context):
                for action in eff.get("actions", []):
                    _context_action_apply(self, action, context, None, True)
            else:
                for action in eff.get("else_actions", []):
                    _context_action_apply(self, action, context, None, True)
            self.log(f"{player.name} uses custom roll ability {ability.name}: {custom_effect_preview(eff, ability.description)}")
            return

        if ability.effect_id == "EXACT_A_HAND_UP":
            if self._has_attribute(bakugan, Attribute.HAOS):
                self.pending_a_hand_up = player.name
                self.log(f"{player.name} uses {ability.name}. Lowest G in the next battle this turn gets +50")
            else:
                self.log(f"{player.name} cannot use {ability.name} because {bakugan.name} is not Haos")
        elif ability.effect_id == "EXACT_CLEAN_SLATE":
            if self._has_attribute(bakugan, Attribute.DARKUS):
                self._move_all_field_bakugan_to_used()
                self.log(f"{player.name} uses {ability.name}. All standing Bakugan return to used piles")
            else:
                self.log(f"{player.name} cannot use {ability.name} because {bakugan.name} is not Darkus")
        elif ability.effect_id == "EXACT_COMBO_BATTLE":
            self.pending_combo_battle = player.name
            self.log(f"{player.name} uses {ability.name}. If this roll starts a battle, both sides add support Bakugan")
        elif ability.effect_id == "EXACT_LOCKDOWN":
            self.temp_roll_modifiers[player.name] += 0.12
            self.pending_lockdown = player.name
            self.log(f"{player.name} uses {ability.name}. If this roll starts a battle, the opponent cannot play Red Ability Cards")
        elif ability.effect_id == "EXACT_LEVEL_DOWN":
            self.pending_level_down = player.name
            self.log(f"{player.name} uses {ability.name}. If this roll starts a battle, the higher original G opponent loses 100")
        elif ability.effect_id == "EXACT_DO_OVER":
            self.pending_do_over = player.name
            self.log(f"{player.name} uses {ability.name}. If this roll starts a battle, other pending roll effects are canceled")
        elif ability.effect_id == "ROLL_PLUS":
            self.temp_roll_modifiers[player.name] += 0.12
            self.log(f"{player.name} uses roll ability {ability.name}")
        elif ability.effect_id == "ROLL_CHOOSE_BEST":
            self.temp_roll_modifiers[player.name] += 0.09
            self.log(f"{player.name} uses roll ability {ability.name}")
        elif ability.effect_id == "ROLL_RECOVER":
            self.temp_roll_modifiers[player.name] += 0.07
            self.log(f"{player.name} uses roll ability {ability.name}")
        elif ability.effect_id == "ROLL_IGNORE_BAD_MATCH":
            self.temp_roll_modifiers[player.name] += 0.08
            self.log(f"{player.name} uses roll ability {ability.name}")
        elif ability.effect_id == "ROLL_BATTLE_BONUS":
            self.temp_roll_modifiers[player.name] += 0.06
            self.log(f"{player.name} uses roll ability {ability.name}")
        else:
            self.log(f"{player.name} uses {ability.name}")

    def resolve_roll(self, player: PlayerProfile, bakugan_idx: int, target_gate_idx: int) -> Optional[int]:
        self.match_stats[player.name].rolls_attempted += 1
        self.temp_roll_modifiers[player.name] = 0.0

        bakugan = player.collection_bakugan[bakugan_idx]
        self.log(f"{player.name} rolls {bakugan.name} ({bakugan.attribute.value}, {bakugan.base_g} G)")

        roll_ability_idx = self.choose_roll_ability(player, bakugan_idx, target_gate_idx)
        if roll_ability_idx is not None:
            self.apply_roll_ability(player, roll_ability_idx, bakugan_idx)

        target_gate = self.field[target_gate_idx]
        accuracy = 0.35 + player.rolling_skill * 0.35 + player.intelligence * 0.15
        accuracy += self.temp_roll_modifiers[player.name]
        accuracy += min(0.10, self._best_gate_bonus_for_bakugan(bakugan, target_gate.gate_card) / 1200.0)
        if player.style == PlayerStyle.TACTICAL:
            accuracy += 0.04
        elif player.style == PlayerStyle.RECKLESS:
            accuracy -= 0.03
        accuracy = clamp(accuracy, 0.08, 0.95)
        drift = clamp(0.18 - player.rolling_skill * 0.08, 0.03, 0.18)

        roll = self.random.random()
        landed_gate_idx = None
        if roll < accuracy:
            landed_gate_idx = target_gate_idx
            self.log(f"{player.name} lands on intended gate {self.field[landed_gate_idx].gate_card.name}")
        elif len(self.field) > 1 and roll < accuracy + drift:
            landed_gate_idx = 1 - target_gate_idx
            self.log(f"{player.name} drifts onto {self.field[landed_gate_idx].gate_card.name}")
        else:
            self.used_bakugan_idx[player.name].append(bakugan_idx)
            self.match_stats[player.name].misses += 1
            self.log(f"{player.name} misses the field")
            return None

        open_chance = clamp(0.74 + player.rolling_skill * 0.18, 0.2, 0.98)
        if self.random.random() > open_chance:
            self.used_bakugan_idx[player.name].append(bakugan_idx)
            self.match_stats[player.name].misses += 1
            self.log(f"{bakugan.name} fails to open")
            return None

        opened_baku = clone_bakugan(bakugan)
        opened_baku.owner_name = player.name
        self._randomize_special_stand_form(opened_baku)
        self.field[landed_gate_idx].bakugan_on_card.append(opened_baku)
        self.used_bakugan_idx[player.name].append(bakugan_idx)
        self.match_stats[player.name].rolls_landed += 1
        self.log(f"{bakugan.name} opens on {self.field[landed_gate_idx].gate_card.name}")
        return landed_gate_idx

    def maybe_shift_if_own_stack(self, player: PlayerProfile, landed_gate_idx: int) -> int:
        fg = self.field[landed_gate_idx]
        own_count = sum(1 for b in fg.bakugan_on_card if b.owner_name == player.name)
        opp_count = sum(1 for b in fg.bakugan_on_card if b.owner_name != player.name)
        if own_count >= 2 and opp_count == 0 and len(self.field) == 2:
            newest_idx = max((i for i, b in enumerate(fg.bakugan_on_card) if b.owner_name == player.name), default=None)
            if newest_idx is None:
                return landed_gate_idx

            other_idx = 1 - landed_gate_idx
            other_fg = self.field[other_idx]
            moved = fg.bakugan_on_card[newest_idx]

            current_desc = f"{fg.gate_card.name} with {len(fg.bakugan_on_card)} of your Bakugan and no opponent"
            other_opp = sum(1 for b in other_fg.bakugan_on_card if b.owner_name != player.name)
            other_own = sum(1 for b in other_fg.bakugan_on_card if b.owner_name == player.name)
            other_desc = f"{other_fg.gate_card.name} with your {other_own} and opponent {other_opp}"

            if self.player_is_manual(player):
                action = self.manual_handler.choose_double_stand_action(player, current_desc, other_desc)
                if not getattr(self.manual_handler, "auto_rest", False):
                    if action == "capture":
                        self.log(f"{player.name} keeps the double stand on {fg.gate_card.name} to claim the gate")
                        return landed_gate_idx
                    fg.bakugan_on_card.pop(newest_idx)
                    other_fg.bakugan_on_card.append(moved)
                    self.log(f"{player.name} moves {moved.name} to {other_fg.gate_card.name} instead of claiming {fg.gate_card.name}")
                    return other_idx

            smartness = clamp(player.intelligence, 0.2, 0.99)
            stay_value = 95.0 + gate_profile_value(player, fg.gate_card, active_bakus=[b for b in fg.bakugan_on_card if b.owner_name == player.name], intelligence_override=smartness) * 0.12

            moved_team = [b for i, b in enumerate(fg.bakugan_on_card) if b.owner_name == player.name and i != newest_idx]
            move_value = gate_profile_value(player, other_fg.gate_card, active_bakus=[moved], intelligence_override=smartness) * (0.18 + 0.10 * smartness)
            move_value += gate_profile_value(player, fg.gate_card, active_bakus=moved_team, intelligence_override=smartness) * 0.05
            if other_opp > 0:
                projected_margin = moved.base_g - max((b.base_g for b in other_fg.bakugan_on_card if b.owner_name != player.name), default=0)
                move_value += projected_margin * (0.18 + 0.18 * smartness)
                move_value += 18 + 34 * smartness
            elif other_own > 0:
                move_value -= 10 + 18 * smartness
            else:
                move_value += 8 + 14 * smartness

            style_bias = {
                PlayerStyle.RECKLESS: 16.0,
                PlayerStyle.DEFENSIVE: -8.0,
                PlayerStyle.TACTICAL: -4.0,
            }.get(player.style, 0.0)
            move_value += style_bias

            if move_value > stay_value:
                fg.bakugan_on_card.pop(newest_idx)
                other_fg.bakugan_on_card.append(moved)
                self.log(f"{moved.name} shifts to {other_fg.gate_card.name}")
                return other_idx

            self.log(f"{player.name} keeps the double stand on {fg.gate_card.name}")
        return landed_gate_idx

    def _clear_pending_roll_effects(self, player_name: Optional[str] = None) -> None:
        for attr in ('pending_a_hand_up', 'pending_combo_battle', 'pending_lockdown', 'pending_level_down', 'pending_do_over'):
            val = getattr(self, attr, None)
            if player_name is None or val == player_name:
                setattr(self, attr, None)

    def _used_ability_colors(self, player: PlayerProfile):
        return {player.collection_abilities[i].color for i in self.used_ability_idx[player.name] if 0 <= i < len(player.collection_abilities)}

    def _standing_count_for(self, player: PlayerProfile) -> int:
        return sum(1 for fg in self.field for b in fg.bakugan_on_card if b.owner_name == player.name)

    def _captured_count_for(self, player: PlayerProfile) -> int:
        return len(self.captured[player.name])

    def _match_pressure(self, player: PlayerProfile) -> Dict[str, float]:
        opponent = self.other_player() if self.current_player().name == player.name else self.current_player()
        own_captured = self._captured_count_for(player)
        opp_captured = self._captured_count_for(opponent)
        remaining_abilities = len(self._unused_abilities(player))
        remaining_bakugan = len(self._remaining_bakugan_for_turn(player))
        return {
            "score_diff": float(own_captured - opp_captured),
            "trailing": 1.0 if own_captured < opp_captured else 0.0,
            "leading": 1.0 if own_captured > opp_captured else 0.0,
            "own_match_point": 1.0 if own_captured >= 2 else 0.0,
            "opp_match_point": 1.0 if opp_captured >= 2 else 0.0,
            "remaining_abilities": float(remaining_abilities),
            "remaining_bakugan": float(remaining_bakugan),
        }

    def _battle_support_score(self, player: PlayerProfile, baku: Bakugan, field_gate: FieldGate) -> float:
        score = baku.base_g + self._best_gate_bonus_for_bakugan(baku, field_gate.gate_card)
        if baku.attribute == player.chosen_attribute:
            score += 18
        if player.style == PlayerStyle.COMBO:
            score += 8
        if player.style == PlayerStyle.DEFENSIVE and field_gate.set_by_player_name == player.name:
            score += 6
        return score


    def choose_battle_ability(self, player: PlayerProfile, attacker_slot: bool, context: str, active_baku: Bakugan, other_baku: Bakugan, field_gate: FieldGate, state: BattleState) -> Optional[int]:
        options = self._unused_abilities(player, [Timing.DURING_BATTLE, Timing.FLEXIBLE])
        if attacker_slot and state.attacker_block_red:
            options = [i for i in options if player.collection_abilities[i].color != AbilityColor.RED]
        elif (not attacker_slot) and state.defender_block_red:
            options = [i for i in options if player.collection_abilities[i].color != AbilityColor.RED]
        if not options:
            return None
        if self.player_is_manual(player):
            manual_choice = self.manual_handler.choose_battle_ability(player, options, context)
            if not getattr(self.manual_handler, "auto_rest", False):
                return manual_choice

        pressure_info = self._match_pressure(player)
        smartness = clamp(player.intelligence, 0.2, 0.99)
        plan = self._strategic_plan(player)
        reckless = player.intelligence < 0.45
        elite = player.intelligence >= 0.8
        own_g = state.attacker_g if attacker_slot else state.defender_g
        opp_g = state.defender_g if attacker_slot else state.attacker_g
        current_margin = own_g - opp_g
        need = max(0.0, -current_margin)
        cushion = max(0.0, current_margin)

        raw_power_ids = {
            "BATTLE_PLUS_60", "BATTLE_PLUS_80", "BATTLE_PLUS_120", "BATTLE_PYRUS_BOOST", "BATTLE_DARKUS_BOOST",
            "EXACT_AQUOS_ONLY", "EXACT_DARKUS_ONLY", "EXACT_DOUBLE_GATE_BONUS", "EXACT_DRAGONOID_DOUBLE_GATE",
            "EXACT_BOOST_ALL", "EXACT_LOWEST_G_BONUS", "EXACT_STANDING_ATTR_SCALING", "EXACT_GATE_WON_SCALING",
            "EXACT_USED_ABILITY_SCALING", "EXACT_LEGENDS_OF_LIGHT", "EXACT_LEGENDS_OF_WIND", "EXACT_BIG_BRAWL",
            "GREEN_BEST_GATE_MATCH", "EXACT_CAROUSEL_T1", "EXACT_CAROUSEL_T2", "EXACT_CAROUSEL_T3",
        }
        disruption_ids = {
            "EXACT_DOOM_CARD", "EXACT_COLORVOID", "EXACT_LEVEL_DOWN", "GREEN_BLOCK_ENEMY", "EXACT_SWAP_ORIGINAL_G",
            "EXACT_EARTH_SHUTDOWN", "EXACT_BRUSHFIRE", "EXACT_POWER_FROM_DARKNESS", "EXACT_COLOR_SWAP",
        }
        setup_ids = {
            "EXACT_ATTRACTOR", "EXACT_AQUOS_SWAP", "EXACT_RETURN_USED_ABILITY", "EXACT_ALICES_SURPRISE",
            "EXACT_BLUE_GREEN_COMBINE",
        }

        def estimate(idx: int) -> float:
            ability = player.collection_abilities[idx]
            eff_other_attr = self._effective_attribute(other_baku, state, not attacker_slot)
            if ability.effect_id == "EXACT_ALICES_SURPRISE":
                opponent = self.other_player() if self.current_player().name == player.name else self.current_player()
                if self._used_ability_count(opponent) <= self._used_ability_count(player):
                    return -999
                bonus_map = {Attribute.PYRUS:50, Attribute.AQUOS:50, Attribute.SUBTERRA:100, Attribute.HAOS:100, Attribute.DARKUS:120, Attribute.VENTUS:120}
                return self._best_value_for_bakugan(active_baku, bonus_map)
            if ability.effect_id == "EXACT_BIG_BRAWL":
                bonus_map = {Attribute.PYRUS:20, Attribute.AQUOS:40, Attribute.SUBTERRA:10, Attribute.HAOS:30, Attribute.DARKUS:20, Attribute.VENTUS:30}
                return self._best_value_for_bakugan(active_baku, bonus_map) * max(1, len(self._standing_attributes()))
            if ability.effect_id == "EXACT_BRUSHFIRE":
                if field_gate.set_by_player_name == player.name:
                    return -999
                bonus_map = {Attribute.PYRUS:140, Attribute.SUBTERRA:70}
                return self._best_value_for_bakugan(active_baku, bonus_map)
            if ability.effect_id == "EXACT_POWER_FROM_DARKNESS":
                if field_gate.set_by_player_name == player.name:
                    return -999
                bonus_map = {Attribute.HAOS:60, Attribute.DARKUS:140}
                return self._best_value_for_bakugan(active_baku, bonus_map)
            if ability.effect_id == "EXACT_COLORVOID":
                opponent = self.other_player() if self.current_player().name == player.name else self.current_player()
                return 90 if self._used_gate_count(opponent) > self._used_gate_count(player) else -999
            if ability.effect_id == "EXACT_AQUOS_SWAP":
                return 80 if self._has_attribute(active_baku, Attribute.AQUOS) and self._best_unused_bakugan_idx(player, field_gate, self._bakugan_index(player, active_baku)) is not None else -999
            if ability.effect_id == "EXACT_COLOR_SWAP":
                return 75 if active_baku.base_g < other_baku.base_g else -999
            if ability.effect_id == "EXACT_DOOM_CARD":
                return 85
            if ability.effect_id == "EXACT_EARTH_SHUTDOWN":
                if not any(self._has_attribute(active_baku, a) for a in {Attribute.PYRUS, Attribute.AQUOS, Attribute.VENTUS}):
                    return -999
                bonus_map = {Attribute.SUBTERRA:200, Attribute.HAOS:100, Attribute.DARKUS:100}
                return bonus_map.get(eff_other_attr, 0)
            if ability.effect_id == "EXACT_LEVEL_DOWN":
                return 80 if other_baku.base_g > active_baku.base_g else -999
            if ability.effect_id == "EXACT_SWAP_ORIGINAL_G":
                return abs(other_baku.base_g - active_baku.base_g) * 0.6
            if ability.effect_id == "EXACT_RETURN_USED_ABILITY":
                return 70 if self._used_ability_count(player) > 0 else -999
            if ability.effect_id == "EXACT_DOUBLE_GATE_BONUS":
                return self._best_gate_bonus_for_bakugan(active_baku, field_gate.gate_card)
            if ability.effect_id == "EXACT_DRAGONOID_DOUBLE_GATE":
                return self._best_gate_bonus_for_bakugan(active_baku, field_gate.gate_card) if self._is_dragonoid_family(active_baku) else -999
            if ability.effect_id == "EXACT_GATE_WON_SCALING":
                return 50 * max(1, self.match_stats[player.name].gates_captured)
            if ability.effect_id == "EXACT_USED_ABILITY_SCALING":
                return 40 * max(1, self._used_ability_count(player))
            if ability.effect_id == "EXACT_AQUOS_ONLY":
                return 120 if self._has_attribute(active_baku, Attribute.AQUOS) else -999
            if ability.effect_id == "EXACT_DARKUS_ONLY":
                return 120 if self._has_attribute(active_baku, Attribute.DARKUS) else -999
            if ability.effect_id == "EXACT_STANDING_ATTR_SCALING":
                return 20 * max(1, len(self._standing_attributes()))
            if ability.effect_id == "EXACT_LOWEST_G_BONUS":
                return 80 if active_baku.base_g < other_baku.base_g else -999
            if ability.effect_id == "EXACT_ATTRACTOR":
                candidates = [self._battle_support_score(player, player.collection_bakugan[i], field_gate) for i in player.active_bakugan_idx if i not in self.removed_bakugan_idx[player.name] and not self._bakugan_in_arena(player, i) and self._bakugan_index(player, active_baku) != i]
                return max(candidates) if candidates else -999
            if ability.effect_id == "EXACT_LEGENDS_OF_LIGHT":
                bonus_map = {Attribute.HAOS:80, Attribute.SUBTERRA:50, Attribute.DARKUS:50}
                return self._best_value_for_bakugan(active_baku, bonus_map)
            if ability.effect_id == "EXACT_LEGENDS_OF_WIND":
                bonus_map = {Attribute.VENTUS:80, Attribute.PYRUS:50, Attribute.DARKUS:50}
                return self._best_value_for_bakugan(active_baku, bonus_map)
            if ability.effect_id == "EXACT_BLUE_GREEN_COMBINE":
                colors = self._used_ability_colors(player)
                return 100 if ('BLUE' in colors and 'GREEN' in colors) else -999
            if ability.effect_id == "EXACT_BOOST_ALL":
                return 50 * max(1, self._standing_count_for(player))
            if ability.effect_id == "EXACT_CAROUSEL_T1":
                return 50
            if ability.effect_id == "EXACT_CAROUSEL_T2":
                return 125
            if ability.effect_id == "EXACT_CAROUSEL_T3":
                return 200
            return 50

        scored = []
        for idx in options:
            ability = player.collection_abilities[idx]
            val = estimate(idx)
            if val <= -999:
                continue
            if ability.effect_id in raw_power_ids:
                val += need * (0.10 + 0.10 * smartness)
                val -= cushion * (0.03 + 0.05 * smartness)
            if ability.effect_id in disruption_ids:
                val += pressure_info["opp_match_point"] * 45
                val += pressure_info["trailing"] * 24
                val += max(0.0, other_baku.base_g - active_baku.base_g) * 0.08
            if ability.effect_id in setup_ids:
                val += pressure_info["remaining_bakugan"] * 3.5
                val += pressure_info["remaining_abilities"] * (5.0 if elite else 2.0)
                if pressure_info["opp_match_point"] and not pressure_info["own_match_point"]:
                    val -= 18
            if player.style == PlayerStyle.RECKLESS and ability.effect_id in raw_power_ids:
                val += 12
            if player.style == PlayerStyle.DEFENSIVE and ability.effect_id in disruption_ids:
                val += 10
            if player.style == PlayerStyle.COMBO and ability.effect_id in setup_ids:
                val += 10
            if player.style == PlayerStyle.AGGRESSIVE and ability.effect_id in raw_power_ids:
                val += 10
            if player.style == PlayerStyle.PATIENT and ability.effect_id in setup_ids:
                val += 8
            if player.style == PlayerStyle.OPPORTUNIST and (ability.effect_id in disruption_ids or ability.effect_id in setup_ids):
                val += 8
            if player.style == PlayerStyle.ADAPTIVE:
                val += 4
            if ability.effect_id in raw_power_ids:
                val += plan["snowball_bias"] * 0.35 + plan["risk_push"] * 0.25
            if ability.effect_id in disruption_ids:
                val += plan["contest_bias"] * 0.20 + plan["comeback_bias"] * 0.35
            if ability.effect_id in setup_ids:
                val += plan["setup_bias"] * 0.45 + plan["resource_conserve"] * 0.25
            val += need * (0.05 + 0.05 * smartness)
            val += pressure_info["opp_match_point"] * 25
            val += pressure_info["own_match_point"] * 8
            if elite and pressure_info["leading"] and cushion >= 80:
                val -= 16
            if reckless and need > 0:
                val += 12
            val += self.random.uniform(-8, 8) * (1.0 - smartness)
            scored.append((val, idx))
        if not scored:
            return None
        scored.sort(reverse=True)
        conserve_threshold = 28 + 24 * smartness
        conserve_threshold += pressure_info["leading"] * 10
        conserve_threshold -= pressure_info["trailing"] * 10
        conserve_threshold -= pressure_info["opp_match_point"] * 14
        conserve_threshold -= min(18.0, need * 0.08)
        conserve_threshold += max(0.0, cushion - 60) * 0.04
        if reckless:
            conserve_threshold -= 8
        if elite:
            conserve_threshold += 6
        return scored[0][1] if scored[0][0] > conserve_threshold else None

    def apply_gate_effect(self, field_gate: FieldGate, atk_baku: Bakugan, def_baku: Bakugan, state: BattleState) -> None:
        gid = field_gate.gate_card.effect_id
        gate_card = field_gate.gate_card
        if getattr(gate_card, "effect_mode", "builtin") == "custom" or gid == "CUSTOM":
            atk_player = next(p for p in self.players if p.name == atk_baku.owner_name)
            def_player = next(p for p in self.players if p.name == def_baku.owner_name)
            for active_baku, other_baku, player, opponent, attacker_slot in ((atk_baku, def_baku, atk_player, def_player, True), (def_baku, atk_baku, def_player, atk_player, False)):
                context = {"player": player, "opponent": opponent, "active_baku": active_baku, "other_baku": other_baku, "field_gate": field_gate, "attacker_slot": attacker_slot}
                eff = normalise_custom_effect(getattr(gate_card, "custom_effect", None), "PASSIVE_GATE")
                if _custom_effect_matches(self, eff, context):
                    for action in eff.get("actions", []):
                        _context_action_apply(self, action, context, state, False)
                else:
                    for action in eff.get("else_actions", []):
                        _context_action_apply(self, action, context, state, False)
            return
        if gid in {"GATE_NONE", "GATE_EXACT_NONE"}:
            return
        elif gid == "GATE_EXACT_BAIT":
            p1, p2 = self.players
            c1 = self._used_gate_count(p1)
            c2 = self._used_gate_count(p2)
            if c1 < c2:
                self.used_ability_idx[p1.name].clear()
                state.attacker_mod_log.append("Gate effect: used abilities returned to unused pile") if atk_baku.owner_name == p1.name else state.defender_mod_log.append("Gate effect: used abilities returned to unused pile")
            elif c2 < c1:
                self.used_ability_idx[p2.name].clear()
                state.attacker_mod_log.append("Gate effect: used abilities returned to unused pile") if atk_baku.owner_name == p2.name else state.defender_mod_log.append("Gate effect: used abilities returned to unused pile")
            return
        elif gid == "GATE_EXACT_DOUBLE_ABILITY_BOOSTS":
            state.attacker_ability_multiplier *= 2.0
            state.defender_ability_multiplier *= 2.0
            state.attacker_mod_log.append("Gate effect: ability boosts doubled")
            state.defender_mod_log.append("Gate effect: ability boosts doubled")
            return
        elif gid == "GATE_EXACT_SWAP_ORIGINAL_G":
            state.attacker_g = def_baku.base_g
            state.defender_g = atk_baku.base_g
            state.attacker_mod_log.append("Gate effect: original G swapped")
            state.defender_mod_log.append("Gate effect: original G swapped")
            return
        elif gid == "GATE_EXACT_SWAP_ORIGINAL_G_IF_AQUOS":
            if self._has_attribute(atk_baku, Attribute.AQUOS) or self._has_attribute(def_baku, Attribute.AQUOS):
                state.attacker_g = def_baku.base_g
                state.defender_g = atk_baku.base_g
                state.attacker_mod_log.append("Gate effect: Aquos original G swapped")
                state.defender_mod_log.append("Gate effect: Aquos original G swapped")
            return
        elif gid == "GATE_EXACT_GATE_WON_SCALING":
            atk_player = next(p for p in self.players if p.name == atk_baku.owner_name)
            def_player = next(p for p in self.players if p.name == def_baku.owner_name)
            atk_bonus = 100 * self.match_stats[atk_player.name].gates_captured
            def_bonus = 100 * self.match_stats[def_player.name].gates_captured
            state.attacker_g += atk_bonus
            state.defender_g += def_bonus
            state.attacker_mod_log.append(f"Gate effect: +{atk_bonus} from won gates")
            state.defender_mod_log.append(f"Gate effect: +{def_bonus} from won gates")
            return
        elif gid == "GATE_EXACT_ABILITY_USED_SCALING":
            atk_player = next(p for p in self.players if p.name == atk_baku.owner_name)
            def_player = next(p for p in self.players if p.name == def_baku.owner_name)
            atk_bonus = 100 * self._used_ability_count(atk_player)
            def_bonus = 100 * self._used_ability_count(def_player)
            state.attacker_g += atk_bonus
            state.defender_g += def_bonus
            state.attacker_mod_log.append(f"Gate effect: +{atk_bonus} from used abilities")
            state.defender_mod_log.append(f"Gate effect: +{def_bonus} from used abilities")
            return
        elif gid == "GATE_EXACT_NO_ABILITIES":
            state.attacker_prevent_abilities = True
            state.defender_prevent_abilities = True
            state.attacker_mod_log.append("Gate effect: no abilities can be played")
            state.defender_mod_log.append("Gate effect: no abilities can be played")
            return
        elif gid == "GATE_EXACT_RETURN_ALL_USED":
            for p in self.players:
                self.used_ability_idx[p.name].clear()
            state.attacker_mod_log.append("Gate effect: all used abilities returned")
            state.defender_mod_log.append("Gate effect: all used abilities returned")
            return
        elif gid == "GATE_EXACT_DOUBLE_LOWER_ORIGINAL_G":
            if atk_baku.base_g < def_baku.base_g:
                state.attacker_g += atk_baku.base_g
                state.attacker_mod_log.append(f"Gate effect: lower original G doubled (+{atk_baku.base_g})")
            elif def_baku.base_g < atk_baku.base_g:
                state.defender_g += def_baku.base_g
                state.defender_mod_log.append(f"Gate effect: lower original G doubled (+{def_baku.base_g})")
            return
        elif gid == "GATE_LOW_G_ADVANTAGE":
            if state.attacker_g < state.defender_g:
                state.attacker_g += 80
                state.attacker_mod_log.append("Gate effect: lower G +80")
            elif state.defender_g < state.attacker_g:
                state.defender_g += 80
                state.defender_mod_log.append("Gate effect: lower G +80")
        elif gid == "GATE_SWAP_STYLE":
            # handled before battle starts for exact Bakugan Swap; keep fallback for older cards
            return
        elif gid == "GATE_BONUS_INVERT":
            if atk_baku.base_g > def_baku.base_g:
                state.attacker_bonus_multiplier *= 0.5
                state.attacker_mod_log.append("Gate effect: bonus halved")
            elif def_baku.base_g > atk_baku.base_g:
                state.defender_bonus_multiplier *= 0.5
                state.defender_mod_log.append("Gate effect: bonus halved")
        elif gid == "GATE_SUBTERRA_FOCUS":
            if self._has_attribute(atk_baku, Attribute.SUBTERRA):
                state.attacker_g += 50
                state.attacker_mod_log.append("Gate effect: Subterra +50")
            if self._has_attribute(def_baku, Attribute.SUBTERRA):
                state.defender_g += 50
                state.defender_mod_log.append("Gate effect: Subterra +50")
        elif gid == "GATE_DARKUS_FOCUS":
            if self._has_attribute(atk_baku, Attribute.DARKUS):
                state.attacker_g += 50
                state.attacker_mod_log.append("Gate effect: Darkus +50")
            if self._has_attribute(def_baku, Attribute.DARKUS):
                state.defender_g += 50
                state.defender_mod_log.append("Gate effect: Darkus +50")
        elif gid == "GATE_VENTUS_FOCUS":
            if self._has_attribute(atk_baku, Attribute.VENTUS):
                state.attacker_g += 50
                state.attacker_mod_log.append("Gate effect: Ventus +50")
            if self._has_attribute(def_baku, Attribute.VENTUS):
                state.defender_g += 50
                state.defender_mod_log.append("Gate effect: Ventus +50")
        elif gid == "GATE_AQUOS_FOCUS":
            if self._has_attribute(atk_baku, Attribute.AQUOS):
                state.attacker_g += 50
                state.attacker_mod_log.append("Gate effect: Aquos +50")
            if self._has_attribute(def_baku, Attribute.AQUOS):
                state.defender_g += 50
                state.defender_mod_log.append("Gate effect: Aquos +50")
        elif gid == "GATE_HAOS_FOCUS":
            if self._has_attribute(atk_baku, Attribute.HAOS):
                state.attacker_g += 50
                state.attacker_mod_log.append("Gate effect: Haos +50")
            if self._has_attribute(def_baku, Attribute.HAOS):
                state.defender_g += 50
                state.defender_mod_log.append("Gate effect: Haos +50")
        elif gid == "GATE_FAST_ATTRS":
            if any(self._has_attribute(atk_baku, attr) for attr in {Attribute.PYRUS, Attribute.HAOS, Attribute.VENTUS}):
                state.attacker_g += 40
                state.attacker_mod_log.append("Gate effect: fast attr +40")
            if any(self._has_attribute(def_baku, attr) for attr in {Attribute.PYRUS, Attribute.HAOS, Attribute.VENTUS}):
                state.defender_g += 40
                state.defender_mod_log.append("Gate effect: fast attr +40")
        elif gid == "GATE_TOUGH_ATTRS":
            if any(self._has_attribute(atk_baku, attr) for attr in {Attribute.SUBTERRA, Attribute.HAOS}):
                state.attacker_g += 35
                state.attacker_mod_log.append("Gate effect: tough attr +35")
            if any(self._has_attribute(def_baku, attr) for attr in {Attribute.SUBTERRA, Attribute.HAOS}):
                state.defender_g += 35
                state.defender_mod_log.append("Gate effect: tough attr +35")
        elif gid == "GATE_PYRUS_AQUOS_SPIKE":
            if any(self._has_attribute(atk_baku, attr) for attr in {Attribute.PYRUS, Attribute.AQUOS}):
                state.attacker_g += 45
                state.attacker_mod_log.append("Gate effect: fire/water +45")
            if any(self._has_attribute(def_baku, attr) for attr in {Attribute.PYRUS, Attribute.AQUOS}):
                state.defender_g += 45
                state.defender_mod_log.append("Gate effect: fire/water +45")

    def apply_battle_ability(self, player: PlayerProfile, ability_idx: int, active_baku: Bakugan, other_baku: Bakugan, field_gate: FieldGate, state: BattleState, attacker_slot: bool) -> Bakugan:
        ability = player.collection_abilities[ability_idx]

        if attacker_slot:
            own_g = "attacker_g"
            opp_g = "defender_g"
            opp_block = "defender_prevent_abilities"
            own_log = state.attacker_mod_log
            opp_log = state.defender_mod_log
        else:
            own_g = "defender_g"
            opp_g = "attacker_g"
            opp_block = "attacker_prevent_abilities"
            own_log = state.defender_mod_log
            opp_log = state.attacker_mod_log

        own_ability_mult = state.attacker_ability_multiplier if attacker_slot else state.defender_ability_multiplier

        def scaled(amount: int) -> int:
            return int(round(amount * own_ability_mult))

        def commit_use():
            self.used_ability_idx[player.name].append(ability_idx)
            self.match_stats[player.name].abilities_used += 1
            self.log(f"{player.name} uses {ability.name}")

        opp_effective_attr = self._effective_attribute(other_baku, state, not attacker_slot)

        if getattr(ability, "effect_mode", "builtin") == "custom" or ability.effect_id == "CUSTOM":
            context = {"player": player, "opponent": (self.other_player() if self.current_player().name == player.name else self.current_player()), "active_baku": active_baku, "other_baku": other_baku, "field_gate": field_gate, "attacker_slot": attacker_slot}
            eff = normalise_custom_effect(getattr(ability, "custom_effect", None), ability.timing.name)
            commit_use()
            if _custom_effect_matches(self, eff, context):
                for action in eff.get("actions", []):
                    repl_b = _context_action_apply(self, action, context, state, False)
                    if repl_b is not None:
                        active_baku = repl_b
                own_log.append(f"{ability.name}: custom effect")
            else:
                for action in eff.get("else_actions", []):
                    repl_b = _context_action_apply(self, action, context, state, False)
                    if repl_b is not None:
                        active_baku = repl_b
                own_log.append(f"{ability.name}: fallback custom effect")
            return active_baku

        if ability.effect_id == "EXACT_ALICES_SURPRISE":
            opponent = self.other_player() if self.current_player().name == player.name else self.current_player()
            if self._used_ability_count(opponent) <= self._used_ability_count(player):
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            bonus_map = {Attribute.PYRUS:50, Attribute.AQUOS:50, Attribute.SUBTERRA:100, Attribute.HAOS:100, Attribute.DARKUS:120, Attribute.VENTUS:120}
            bonus = self._best_value_for_bakugan(active_baku, bonus_map)
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "EXACT_BIG_BRAWL":
            bonus_map = {Attribute.PYRUS:20, Attribute.AQUOS:40, Attribute.SUBTERRA:10, Attribute.HAOS:30, Attribute.DARKUS:20, Attribute.VENTUS:30}
            per_attr = self._best_value_for_bakugan(active_baku, bonus_map)
            bonus = per_attr * max(1, len(self._standing_attributes()))
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "EXACT_BRUSHFIRE":
            if field_gate.set_by_player_name == player.name:
                self.log(f"{player.name} cannot use {ability.name} on their own gate")
                return active_baku
            bonus_map = {Attribute.PYRUS:140, Attribute.SUBTERRA:70}
            bonus = self._best_value_for_bakugan(active_baku, bonus_map)
            if bonus <= 0:
                self.log(f"{player.name} gains nothing from {ability.name}")
                return active_baku
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "EXACT_POWER_FROM_DARKNESS":
            if field_gate.set_by_player_name == player.name:
                self.log(f"{player.name} cannot use {ability.name} on their own gate")
                return active_baku
            bonus_map = {Attribute.HAOS:60, Attribute.DARKUS:140}
            bonus = self._best_value_for_bakugan(active_baku, bonus_map)
            if bonus <= 0:
                self.log(f"{player.name} gains nothing from {ability.name}")
                return active_baku
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "EXACT_COLORVOID":
            opponent = self.other_player() if self.current_player().name == player.name else self.current_player()
            if self._used_gate_count(opponent) <= self._used_gate_count(player):
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            worst_attr = min(list(Attribute), key=lambda a: field_gate.gate_card.bonuses.get(a, 0))
            commit_use()
            if attacker_slot:
                state.defender_attribute_override = worst_attr
            else:
                state.attacker_attribute_override = worst_attr
            own_log.append(f"{ability.name}: changes opponent to {worst_attr.value}")
            return active_baku
        elif ability.effect_id == "EXACT_AQUOS_SWAP":
            if not self._has_attribute(active_baku, Attribute.AQUOS):
                self.log(f"{player.name} cannot use {ability.name} because {active_baku.name} is not Aquos")
                return active_baku
            active_idx = self._bakugan_index(player, active_baku)
            replacement_idx = self._best_unused_bakugan_idx(player, field_gate, active_idx)
            if replacement_idx is None:
                self.log(f"{player.name} has no unused Bakugan for {ability.name}")
                return active_baku
            replacement = player.collection_bakugan[replacement_idx]
            commit_use()
            for i, baku in enumerate(field_gate.bakugan_on_card):
                if baku is active_baku:
                    field_gate.bakugan_on_card[i] = replacement
                    break
            if replacement_idx not in self.used_bakugan_idx[player.name]:
                self.used_bakugan_idx[player.name].append(replacement_idx)
            own_log.append(f"{ability.name}: replaces {active_baku.name} with {replacement.name}")
            return replacement
        elif ability.effect_id == "EXACT_COLOR_SWAP":
            if active_baku.base_g >= other_baku.base_g:
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            commit_use()
            active_eff = self._effective_attribute(active_baku, state, attacker_slot)
            other_eff = self._effective_attribute(other_baku, state, not attacker_slot)
            if attacker_slot:
                state.attacker_attribute_override = other_eff
                state.defender_attribute_override = active_eff
            else:
                state.defender_attribute_override = other_eff
                state.attacker_attribute_override = active_eff
            own_log.append(f"{ability.name}: swaps battle attributes")
            return active_baku
        elif ability.effect_id == "EXACT_DOOM_CARD":
            commit_use()
            if attacker_slot:
                state.doom_attacker = True
            else:
                state.doom_defender = True
            if self._has_attribute(active_baku, Attribute.DARKUS):
                setattr(state, own_g, getattr(state, own_g) + 30)
                own_log.append(f"{ability.name}: Darkus +30")
            else:
                own_log.append(f"{ability.name}: loser will be removed from the match")
            return active_baku
        elif ability.effect_id == "EXACT_EARTH_SHUTDOWN":
            if not any(self._has_attribute(active_baku, a) for a in {Attribute.PYRUS, Attribute.AQUOS, Attribute.VENTUS}):
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            bonus_map = {Attribute.SUBTERRA:200, Attribute.HAOS:100, Attribute.DARKUS:100}
            bonus = bonus_map.get(opp_effective_attr, 0)
            if bonus <= 0:
                self.log(f"{player.name} gains nothing from {ability.name}")
                return active_baku
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "EXACT_LEVEL_DOWN":
            if other_baku.base_g <= active_baku.base_g:
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            commit_use()
            setattr(state, opp_g, getattr(state, opp_g) - scaled(100))
            own_log.append(f"{ability.name}: highest original G loses 100")
            return active_baku
        elif ability.effect_id == "EXACT_SWAP_ORIGINAL_G":
            commit_use()
            own_current = getattr(state, own_g)
            opp_current = getattr(state, opp_g)
            setattr(state, own_g, other_baku.base_g)
            setattr(state, opp_g, active_baku.base_g)
            own_log.append(f"{ability.name}: original G values swapped for this battle")
            opp_log.append(f"{ability.name}: original G values swapped for this battle")
            return active_baku
        elif ability.effect_id == "EXACT_RETURN_USED_ABILITY":
            if not self.used_ability_idx[player.name]:
                self.log(f"{player.name} has no used abilities for {ability.name}")
                return active_baku
            commit_use()
            returned_idx = self.used_ability_idx[player.name].pop(0)
            own_log.append(f"{ability.name}: returns {player.collection_abilities[returned_idx].name} to unused")
            return active_baku
        elif ability.effect_id == "EXACT_DOUBLE_GATE_BONUS":
            commit_use()
            if attacker_slot:
                state.attacker_bonus_multiplier *= 2.0
            else:
                state.defender_bonus_multiplier *= 2.0
            own_log.append(f"{ability.name}: gate bonus doubled")
            return active_baku
        elif ability.effect_id == "EXACT_DRAGONOID_DOUBLE_GATE":
            if not self._is_dragonoid_family(active_baku):
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            commit_use()
            if attacker_slot:
                state.attacker_bonus_multiplier *= 2.0
            else:
                state.defender_bonus_multiplier *= 2.0
            own_log.append(f"{ability.name}: Dragonoid gate bonus doubled")
            return active_baku
        elif ability.effect_id == "EXACT_GATE_WON_SCALING":
            bonus = 50 * self.match_stats[player.name].gates_captured
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus} from won gates")
            return active_baku
        elif ability.effect_id == "EXACT_USED_ABILITY_SCALING":
            bonus = 40 * self._used_ability_count(player)
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus} from used abilities")
            return active_baku
        elif ability.effect_id == "EXACT_AQUOS_ONLY":
            if not self._has_attribute(active_baku, Attribute.AQUOS):
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(120))
            own_log.append(f"{ability.name}: Aquos +120")
            return active_baku
        elif ability.effect_id == "EXACT_DARKUS_ONLY":
            if not self._has_attribute(active_baku, Attribute.DARKUS):
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(120))
            own_log.append(f"{ability.name}: Darkus +120")
            return active_baku
        elif ability.effect_id == "EXACT_STANDING_ATTR_SCALING":
            bonus = 20 * max(1, len(self._standing_attributes()))
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus} from standing attributes")
            return active_baku
        elif ability.effect_id == "EXACT_LOWEST_G_BONUS":
            if active_baku.base_g >= other_baku.base_g:
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(80))
            own_log.append(f"{ability.name}: lower original G +80")
            return active_baku
        elif ability.effect_id == "EXACT_ATTRACTOR":
            candidates = []
            for idx in player.active_bakugan_idx:
                if idx in self.removed_bakugan_idx[player.name] or self._bakugan_index(player, active_baku) == idx or self._bakugan_in_arena(player, idx):
                    continue
                candidates.append((player.collection_bakugan[idx].base_g, idx))
            if not candidates:
                self.log(f"{player.name} has no legal support for {ability.name}")
                return active_baku
            candidates.sort(reverse=True)
            sup_idx = max(candidates, key=lambda item: self._battle_support_score(player, player.collection_bakugan[item[1]], field_gate))[1]
            sup_baku = player.collection_bakugan[sup_idx]
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + sup_baku.base_g)
            if sup_idx not in self.used_bakugan_idx[player.name]:
                self.used_bakugan_idx[player.name].append(sup_idx)
            own_log.append(f"{ability.name}: support {sup_baku.name} +{sup_baku.base_g}")
            return active_baku
        elif ability.effect_id == "EXACT_LEGENDS_OF_LIGHT":
            bonus_map = {Attribute.HAOS:80, Attribute.SUBTERRA:50, Attribute.DARKUS:50}
            bonus = self._best_value_for_bakugan(active_baku, bonus_map)
            if bonus <= 0:
                self.log(f"{player.name} gains nothing from {ability.name}")
                return active_baku
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "EXACT_LEGENDS_OF_WIND":
            bonus_map = {Attribute.VENTUS:80, Attribute.PYRUS:50, Attribute.DARKUS:50}
            bonus = self._best_value_for_bakugan(active_baku, bonus_map)
            if bonus <= 0:
                self.log(f"{player.name} gains nothing from {ability.name}")
                return active_baku
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "EXACT_BLUE_GREEN_COMBINE":
            colors = self._used_ability_colors(player)
            if 'BLUE' not in colors or 'GREEN' not in colors:
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(100))
            own_log.append(f"{ability.name}: +100")
            return active_baku
        elif ability.effect_id == "EXACT_BOOST_ALL":
            bonus = 50 * max(1, self._standing_count_for(player))
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "EXACT_CAROUSEL_T1":
            bonus = self.random.randrange(0, 101, 10)
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "EXACT_CAROUSEL_T2":
            bonus = self.random.randrange(0, 251, 10)
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "EXACT_CAROUSEL_T3":
            bonus = self.random.randrange(0, 401, 10)
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "GREEN_BLOCK_ENEMY":
            commit_use()
            setattr(state, opp_block, True)
            own_log.append(f"{ability.name}: blocks enemy ability")
            return active_baku
        elif ability.effect_id == "BATTLE_PLUS_80":
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(80))
            own_log.append(f"{ability.name}: +80")
            return active_baku
        elif ability.effect_id == "BATTLE_PLUS_120":
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(120))
            own_log.append(f"{ability.name}: +120")
            return active_baku
        elif ability.effect_id == "BATTLE_PYRUS_BOOST":
            bonus = 120 if self._has_attribute(active_baku, Attribute.PYRUS) else 70
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "BATTLE_PLUS_60":
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(60))
            own_log.append(f"{ability.name}: +60")
            return active_baku
        elif ability.effect_id == "BATTLE_DARKUS_BOOST":
            bonus = 130 if self._has_attribute(active_baku, Attribute.DARKUS) else 65
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(bonus))
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "GREEN_BEST_GATE_MATCH":
            best_bonus = max(field_gate.gate_card.bonuses.values())
            current_bonus = self._best_gate_bonus_for_bakugan(active_baku, field_gate.gate_card)
            extra = max(0, best_bonus - current_bonus)
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + scaled(extra))
            own_log.append(f"{ability.name}: +{extra}")
            return active_baku
        elif ability.effect_id == "GREEN_SABOTAGE_100":
            commit_use()
            setattr(state, opp_g, getattr(state, opp_g) - scaled(100))
            own_log.append(f"{ability.name}: opponent -100")
            return active_baku
        return active_baku

    def standard_gate_bonus(self, gate: GateCard, effective_attribute, mult: float, extra: int, bakugan: Optional[Bakugan] = None) -> int:
        if isinstance(effective_attribute, list):
            raw = max(gate.bonuses.get(attr, 0) for attr in effective_attribute)
        else:
            raw = gate.bonuses.get(effective_attribute, 0)
        if bakugan is not None and self._gate_gets_named_double_bonus(gate, bakugan):
            raw *= 2
        return int(raw * mult) + extra

    def conduct_battle(self, attacker: PlayerProfile, defender: PlayerProfile, gate_idx: int) -> PlayerProfile:
        fg = self.field[gate_idx]
        atk_baku = fg.get_single_friendly_of(attacker.name)
        def_baku = fg.get_single_opponent_of(attacker.name)
        if atk_baku is None or def_baku is None:
            raise ValueError("Battle missing Bakugan")

        self.match_stats[attacker.name].battles_fought += 1
        self.match_stats[defender.name].battles_fought += 1

        self.log(f"Battle starts on {fg.gate_card.name}")
        self.log(f"{attacker.name}: {atk_baku.name} ({self._attribute_label(atk_baku)}, {atk_baku.base_g} G)")
        self.log(f"{defender.name}: {def_baku.name} ({self._attribute_label(def_baku)}, {def_baku.base_g} G)")

        # Exact gate effects that modify which Bakugan are present.
        if fg.gate_card.effect_id == "GATE_EXACT_BAKUGAN_SWAP":
            for player_obj, current_baku in ((attacker, atk_baku), (defender, def_baku)):
                current_idx = self._bakugan_index(player_obj, current_baku)
                replacement_idx = self._best_unused_bakugan_idx(player_obj, fg, current_idx)
                if replacement_idx is not None:
                    replacement = player_obj.collection_bakugan[replacement_idx]
                    for i, baku in enumerate(fg.bakugan_on_card):
                        if baku is current_baku:
                            fg.bakugan_on_card[i] = replacement
                            break
                    if replacement_idx not in self.used_bakugan_idx[player_obj.name]:
                        self.used_bakugan_idx[player_obj.name].append(replacement_idx)
                    self.log(f"{fg.gate_card.name} swaps in {replacement.name} for {player_obj.name}")
            atk_baku = fg.get_single_friendly_of(attacker.name)
            def_baku = fg.get_single_opponent_of(attacker.name)

        state = BattleState(atk_baku.base_g, def_baku.base_g)

        # Exact gate effect: Bait
        self.apply_gate_effect(fg, atk_baku, def_baku, state)

        # Exact pre-battle roll abilities.
        if self.pending_do_over is not None:
            self.log("Do Over activates: other pending roll-based pre-battle effects are canceled")
            self.pending_combo_battle = None
            self.pending_a_hand_up = None
            self.pending_lockdown = None
            self.pending_level_down = None
            self.pending_do_over = None

        if self.pending_lockdown is not None:
            if self.pending_lockdown == attacker.name:
                state.defender_block_red = True
                state.attacker_mod_log.append("Lockdown: opponent Red abilities blocked")
            elif self.pending_lockdown == defender.name:
                state.attacker_block_red = True
                state.defender_mod_log.append("Lockdown: opponent Red abilities blocked")
            self.pending_lockdown = None

        if self.pending_level_down is not None:
            if self.pending_level_down == attacker.name and def_baku.base_g > atk_baku.base_g:
                state.defender_g -= 100
                state.attacker_mod_log.append("Level Down: opponent -100")
            elif self.pending_level_down == defender.name and atk_baku.base_g > def_baku.base_g:
                state.attacker_g -= 100
                state.defender_mod_log.append("Level Down: opponent -100")
            self.pending_level_down = None

        if self.pending_combo_battle is not None:
            support_info = []
            for player_obj, own_g_attr, own_log in ((attacker, 'attacker_g', state.attacker_mod_log), (defender, 'defender_g', state.defender_mod_log)):
                # used or unused, but not currently in arena and not removed.
                candidates = []
                for idx in player_obj.active_bakugan_idx:
                    if idx in self.removed_bakugan_idx[player_obj.name]:
                        continue
                    if self._bakugan_in_arena(player_obj, idx):
                        continue
                    baku = player_obj.collection_bakugan[idx]
                    candidates.append((baku.base_g, idx))
                if candidates:
                    smartness = clamp(player_obj.intelligence, 0.2, 0.99)
                    candidates.sort(reverse=True)
                    if smartness > 0.72:
                        sup_idx = max(candidates, key=lambda item: self._battle_support_score(player_obj, player_obj.collection_bakugan[item[1]], fg))[1]
                    else:
                        sup_idx = max(candidates, key=lambda item: item[0] + self.random.uniform(-20, 20) * (1.0 - smartness))[1]
                    sup_baku = player_obj.collection_bakugan[sup_idx]
                    setattr(state, own_g_attr, getattr(state, own_g_attr) + sup_baku.base_g)
                    if sup_idx not in self.used_bakugan_idx[player_obj.name]:
                        self.used_bakugan_idx[player_obj.name].append(sup_idx)
                    own_log.append(f"Combo Battle support {sup_baku.name}: +{sup_baku.base_g}")
                    support_info.append(f"{player_obj.name} adds {sup_baku.name}")
            if support_info:
                self.log("Combo Battle activates: " + "; ".join(support_info))
            self.pending_combo_battle = None

        if self.pending_a_hand_up is not None:
            if state.attacker_g < state.defender_g:
                state.attacker_g += 50
                state.attacker_mod_log.append("A Hand Up: +50 to lower G")
            elif state.defender_g < state.attacker_g:
                state.defender_g += 50
                state.defender_mod_log.append("A Hand Up: +50 to lower G")
            self.pending_a_hand_up = None

        atk_context = f"{attacker.name} {state.attacker_g} vs {defender.name} {state.defender_g}"
        atk_ability_idx = self.choose_battle_ability(attacker, True, atk_context, atk_baku, def_baku, fg, state)
        if atk_ability_idx is not None:
            atk_baku = self.apply_battle_ability(attacker, atk_ability_idx, atk_baku, def_baku, fg, state, True)

        def_context = f"{defender.name} {state.defender_g} vs {attacker.name} {state.attacker_g}"
        def_ability_idx = self.choose_battle_ability(defender, False, def_context, def_baku, atk_baku, fg, state)
        if def_ability_idx is not None and not state.defender_prevent_abilities:
            def_baku = self.apply_battle_ability(defender, def_ability_idx, def_baku, atk_baku, fg, state, False)

        atk_attr = self._effective_attribute(atk_baku, state, True)
        def_attr = self._effective_attribute(def_baku, state, False)
        atk_bonus_attrs = self._attribute_options(atk_baku) if state.attacker_attribute_override is None else [atk_attr]
        def_bonus_attrs = self._attribute_options(def_baku) if state.defender_attribute_override is None else [def_attr]
        atk_bonus = self.standard_gate_bonus(fg.gate_card, atk_bonus_attrs, state.attacker_bonus_multiplier, state.attacker_flat_gate_bonus_extra, atk_baku)
        def_bonus = self.standard_gate_bonus(fg.gate_card, def_bonus_attrs, state.defender_bonus_multiplier, state.defender_flat_gate_bonus_extra, def_baku)
        state.attacker_g += atk_bonus
        state.defender_g += def_bonus
        state.attacker_mod_log.append(f"Gate bonus +{atk_bonus} ({atk_attr.value})")
        state.defender_mod_log.append(f"Gate bonus +{def_bonus} ({def_attr.value})")
        if self._gate_gets_named_double_bonus(fg.gate_card, atk_baku):
            state.attacker_mod_log.append(f"{fg.gate_card.name}: named Bakugan double gate bonus")
        if self._gate_gets_named_double_bonus(fg.gate_card, def_baku):
            state.defender_mod_log.append(f"{fg.gate_card.name}: named Bakugan double gate bonus")

        self.log(f"{attacker.name} final G: {state.attacker_g}")
        self.log(f"  Mods: {', '.join(state.attacker_mod_log) if state.attacker_mod_log else 'none'}")
        self.log(f"{defender.name} final G: {state.defender_g}")
        self.log(f"  Mods: {', '.join(state.defender_mod_log) if state.defender_mod_log else 'none'}")

        if state.attacker_g > state.defender_g:
            winner = attacker
        elif state.defender_g > state.attacker_g:
            winner = defender
        else:
            self.log("Battle tied, tiebreak roll")
            s1 = attacker.rolling_skill * 0.6 + attacker.intelligence * 0.25 + self.random.random() * 0.15
            s2 = defender.rolling_skill * 0.6 + defender.intelligence * 0.25 + self.random.random() * 0.15
            winner = attacker if s1 >= s2 else defender
            self.match_stats[winner.name].tie_breakers_won += 1
            self.log(f"Tiebreak winner: {winner.name}")

        loser = defender if winner is attacker else attacker
        # Doom Card exact removal.
        if (winner is attacker and state.doom_attacker) or (winner is defender and state.doom_defender):
            losing_baku = def_baku if winner is attacker else atk_baku
            losing_player = loser
            losing_idx = self._bakugan_index(losing_player, losing_baku)
            if losing_idx is not None:
                self.removed_bakugan_idx[losing_player.name].add(losing_idx)
                self.log(f"Doom Card removes {losing_baku.name} from the rest of the match")

        self.match_stats[winner.name].battles_won += 1
        self.match_stats[winner.name].gates_captured += 1
        self.captured[winner.name].append(fg.gate_card)
        winner.tourney.battle_diff += 1
        loser.tourney.battle_diff -= 1

        self.log(f"{winner.name} wins the battle and captures {fg.gate_card.name}")
        self.field.pop(gate_idx)
        return winner

    def resolve_non_battle_capture(self, player: PlayerProfile, gate_idx: int) -> None:
        fg = self.field[gate_idx]
        owners = {b.owner_name for b in fg.bakugan_on_card}
        if len(owners) == 1 and player.name in owners and len(fg.bakugan_on_card) >= 2:
            self.captured[player.name].append(fg.gate_card)
            self.match_stats[player.name].gates_captured += 1
            self.log(f"{player.name} captures {fg.gate_card.name} uncontested")
            self.field.pop(gate_idx)

    def check_winner(self) -> Optional[PlayerProfile]:
        for p in self.players:
            if len(self.captured[p.name]) >= 3:
                self.log(f"{p.name} wins the match with 3 gate cards")
                return p
        return None

    def end_turn(self) -> None:
        self.turn_index = 1 - self.turn_index
        self.turn_count += 1

    def performance_score(self, player: PlayerProfile) -> float:
        s = self.match_stats[player.name]
        roll_acc = s.rolls_landed / s.rolls_attempted if s.rolls_attempted else 0.0
        battle_wr = s.battles_won / s.battles_fought if s.battles_fought else 0.0
        score = 0.0
        score += s.gates_captured * 100
        score += s.battles_won * 35
        score += roll_acc * 40
        score += battle_wr * 50
        score += s.abilities_used * 3
        score += s.tie_breakers_won * 10
        score -= s.misses * 8
        return score

    def performance_mapped_result(self, player: PlayerProfile, opponent: PlayerProfile, winner: PlayerProfile) -> float:
        p_score = self.performance_score(player)
        o_score = self.performance_score(opponent)
        total = max(1.0, abs(p_score) + abs(o_score))
        relative = clamp((p_score - o_score) / total, -0.35, 0.35)
        if player == winner:
            return clamp(0.75 + relative, 0.55, 1.0)
        return clamp(0.25 + relative, 0.0, 0.45)

    def update_ratings(self, p1: PlayerProfile, p2: PlayerProfile, winner: PlayerProfile) -> None:
        old1 = p1.glicko.copy()
        old2 = p2.glicko.copy()
        s1 = self.performance_mapped_result(p1, p2, winner)
        s2 = self.performance_mapped_result(p2, p1, winner)
        p1.glicko = glicko2_update(old1, old2, s1)
        p2.glicko = glicko2_update(old2, old1, s2)
        self.log("Ratings updated")
        self.log(f"{p1.name}: {old1.rating:.0f} -> {p1.glicko.rating:.0f}")
        self.log(f"{p2.name}: {old2.rating:.0f} -> {p2.glicko.rating:.0f}")

    def play(self) -> Tuple[PlayerProfile, Dict[str, float], List[str]]:
        self.log(f"Match start: {self.players[0].name} vs {self.players[1].name}")
        while self.turn_count <= self.max_turns:
            self.log("")
            self.log(f"Turn {self.turn_count}")
            self.setup_field_if_needed()
            if not self.field:
                break

            player = self.current_player()
            self.log(f"Current player: {player.name}")
            self.log(f"Score: {self.players[0].name} {len(self.captured[self.players[0].name])} | {self.players[1].name} {len(self.captured[self.players[1].name])}")

            baku_idx = self.choose_bakugan_to_roll(player)
            target_gate_idx = self.choose_target_gate(player, baku_idx)
            landed_gate_idx = self.resolve_roll(player, baku_idx, target_gate_idx)

            if landed_gate_idx is not None:
                landed_gate_idx = self.maybe_shift_if_own_stack(player, landed_gate_idx)
                fg = self.field[landed_gate_idx]
                if fg.has_opponent_of(player.name):
                    self.conduct_battle(player, self.other_player(), landed_gate_idx)
                else:
                    self.log(f"No battle on {fg.gate_card.name}")
                    self.resolve_non_battle_capture(player, landed_gate_idx)
                    self._clear_pending_roll_effects(player.name)
            else:
                self._clear_pending_roll_effects(player.name)

            winner = self.check_winner()
            if winner is not None:
                break
            self.end_turn()

        if self.check_winner() is None:
            p1, p2 = self.players
            p1_score = self.performance_score(p1)
            p2_score = self.performance_score(p2)
            winner = p1 if p1_score >= p2_score else p2
            self.log(f"Turn cap reached, winner on performance: {winner.name}")
        else:
            winner = self.check_winner()

        p1, p2 = self.players
        self.update_ratings(p1, p2, winner)

        perf = {p.name: self.performance_score(p) for p in self.players}
        self.log(f"Match end: winner {winner.name}")
        return winner, perf, list(self.logger.lines)


# ============================================================
# TOURNAMENTS
# ============================================================

class SwissTournament:
    def __init__(self, players: List[PlayerProfile], rounds: int, seed: int = 42, verbose_matches: bool = False, logger: Optional[Logger] = None, manual_handler: Optional[ManualChoiceHandler] = None, manual_player_name: Optional[str] = None):
        self.players = players
        self.rounds = rounds
        self.random = random.Random(seed)
        self.verbose_matches = verbose_matches
        self.logger = logger or Logger(enabled=verbose_matches)
        self.records: List[MatchRecord] = []
        self.match_logs: List[Tuple[int, str]] = []
        self.manual_handler = manual_handler
        self.manual_player_name = manual_player_name

    def recompute_buchholz(self) -> None:
        score_map = {p.name: p.tourney.score for p in self.players}
        for p in self.players:
            p.tourney.buchholz = sum(score_map.get(opp, 0.0) for opp in p.tourney.opponents)

    def standings(self) -> List[PlayerProfile]:
        self.recompute_buchholz()
        return sorted(
            self.players,
            key=lambda p: (
                p.tourney.score,
                p.tourney.buchholz,
                p.tourney.gate_diff,
                p.tourney.battle_diff,
                (p.tourney.performance_total / p.tourney.matches_played if p.tourney.matches_played else 0.0),
                p.glicko.rating,
            ),
            reverse=True
        )

    def swiss_pairings(self) -> List[Tuple[PlayerProfile, Optional[PlayerProfile]]]:
        standings = self.standings()
        unpaired = standings[:]
        pairings = []
        while unpaired:
            p1 = unpaired.pop(0)
            candidate_index = None
            for i, p2 in enumerate(unpaired):
                if p2.name not in p1.tourney.opponents:
                    candidate_index = i
                    break
            if candidate_index is None:
                if unpaired:
                    candidate_index = 0
                else:
                    pairings.append((p1, None))
                    break
            p2 = unpaired.pop(candidate_index)
            pairings.append((p1, p2))
        return pairings

    def run(self) -> None:
        for round_no in range(1, self.rounds + 1):
            print(f"\n========== ROUND {round_no} ==========")
            for p1, p2 in self.swiss_pairings():
                if p2 is None:
                    print(f"{p1.name} receives a bye")
                    p1.tourney.score += 1.0
                    p1.tourney.wins += 1
                    p1.tourney.matches_played += 1
                    p1.tourney.performance_total += 100.0
                    p1.wins += 1
                    continue

                rating1_before = p1.glicko.rating
                rating2_before = p2.glicko.rating
                expected1 = glicko2_expected_score(p1.glicko, p2.glicko)
                expected2 = glicko2_expected_score(p2.glicko, p1.glicko)
                print(f"{p1.name} vs {p2.name} | expected {expected1:.3f} to {expected2:.3f}")

                match_logger = Logger(enabled=self.verbose_matches, prefix="match")
                match = Match(
                    p1, p2,
                    seed=self.random.randint(1, 10_000_000),
                    verbose=self.verbose_matches,
                    logger=match_logger,
                    manual_handler=self.manual_handler,
                    manual_player_name=self.manual_player_name,
                )
                winner, perf, lines = match.play()
                winner_original = p1 if winner.name == p1.name else p2
                loser_original = p2 if winner.name == p1.name else p1

                for match_player in match.players:
                    original = p1 if match_player.name == p1.name else p2
                    original.glicko = match_player.glicko

                winner_original.tourney.score += 1.0
                winner_original.tourney.wins += 1
                loser_original.tourney.losses += 1
                winner_original.wins += 1
                loser_original.losses += 1
                p1.tourney.matches_played += 1
                p2.tourney.matches_played += 1
                p1.tourney.gate_diff += len(match.captured[p1.name]) - len(match.captured[p2.name])
                p2.tourney.gate_diff += len(match.captured[p2.name]) - len(match.captured[p1.name])
                p1.tourney.performance_total += perf[p1.name]
                p2.tourney.performance_total += perf[p2.name]
                p1.tourney.opponents.append(p2.name)
                p2.tourney.opponents.append(p1.name)

                print(f"Winner: {winner.name} | {p1.name} perf {perf[p1.name]:.1f} | {p2.name} perf {perf[p2.name]:.1f} | Gates {len(match.captured[p1.name])}-{len(match.captured[p2.name])}")

                self.records.append(MatchRecord(round_no, p1.name, p2.name, winner.name, perf[p1.name], perf[p2.name], rating1_before, rating2_before, p1.glicko.rating, p2.glicko.rating))
                self.match_logs.append((round_no, "\n".join(lines)))

            self.recompute_buchholz()
            self.print_round_standings()

    def print_round_standings(self, top_n: int = 10) -> None:
        print("\nCurrent standings")
        for idx, p in enumerate(self.standings()[:top_n], start=1):
            avg_perf = p.tourney.performance_total / p.tourney.matches_played if p.tourney.matches_played else 0.0
            print(f"{idx:>2}. {p.name:<18} Pts {p.tourney.score:<4.1f} Buch {p.tourney.buchholz:<4.1f} GateDiff {p.tourney.gate_diff:<3d} BattleDiff {p.tourney.battle_diff:<3d} AvgPerf {avg_perf:>6.1f} Rating {p.glicko.rating:>7.1f}")

    def export_files(self, seed: int = 42, save_play_by_play: bool = True) -> Tuple[Path, Optional[Path]]:
        filename = build_output_filename("swiss_tournament", len(self.players), self.rounds, random_suffix(random.Random(seed + 1001)))
        summary_path = get_current_output_dir() / filename
        lines = ["========== FINAL LEADERBOARD =========="]
        lines.append(f"{'Pos':<4}{'Name':<20}{'Pts':<6}{'Wins':<6}{'Losses':<8}{'Buch':<8}{'GateDiff':<10}{'BattleDiff':<12}{'AveragePerf':<12}{'Rating':<10}")
        for idx, p in enumerate(self.standings(), start=1):
            avg_perf = p.tourney.performance_total / p.tourney.matches_played if p.tourney.matches_played else 0.0
            lines.append(f"{idx:<4}{p.name:<20}{p.tourney.score:<6.1f}{p.tourney.wins:<6}{p.tourney.losses:<8}{p.tourney.buchholz:<8.1f}{p.tourney.gate_diff:<10d}{p.tourney.battle_diff:<12d}{avg_perf:<10.1f}{p.glicko.rating:<10.1f}")
        lines.append("")
        lines.append("========== MATCH RECORDS ==========")
        for rec in self.records:
            lines.append(f"Round {rec.round_no}: {rec.player1} vs {rec.player2} | Winner {rec.winner} | Perf {rec.perf1:.1f}-{rec.perf2:.1f} | Rating {rec.rating1_before:.1f}->{rec.rating1_after:.1f} / {rec.rating2_before:.1f}->{rec.rating2_after:.1f}")
        lines.append("")
        lines.append("========== FINAL LOADOUTS ==========")
        for idx, p in enumerate(self.standings(), start=1):
            lines.append("")
            lines.append(f"{idx}. {p.name}")
            lines.extend(player_loadout_lines(p, "   "))
        summary_path.write_text("\n".join(lines), encoding="utf-8")

        play_path = None
        if save_play_by_play:
            filename = build_output_filename("swiss_tournament_playbyplay", len(self.players), self.rounds, random_suffix(random.Random(seed + 1002)))
            play_path = get_current_output_dir() / filename
            text_lines = ["========== SWISS TOURNAMENT PLAY BY PLAY =========="]
            for round_no, text in self.match_logs:
                text_lines.append("")
                text_lines.append(f"========== ROUND {round_no} MATCH ==========")
                text_lines.append(text)
            play_path.write_text("\n".join(text_lines), encoding="utf-8")
        return summary_path, play_path


class KnockoutTournament:
    def __init__(self, players: List[PlayerProfile], seed: int = 42, verbose_matches: bool = False, logger: Optional[Logger] = None, manual_handler: Optional[ManualChoiceHandler] = None, manual_player_name: Optional[str] = None):
        self.players = players
        self.random = random.Random(seed)
        self.verbose_matches = verbose_matches
        self.logger = logger or Logger(enabled=verbose_matches)
        self.manual_handler = manual_handler
        self.manual_player_name = manual_player_name
        self.result = KnockoutResult()
        self.play_logs: List[str] = []

    def bracket_seed_order(self, players: List[PlayerProfile]) -> List[PlayerProfile]:
        seeded = sorted(players, key=lambda p: p.glicko.rating, reverse=True)
        ordered = []
        left, right = 0, len(seeded) - 1
        while left <= right:
            if left == right:
                ordered.append(seeded[left])
            else:
                ordered.append(seeded[left])
                ordered.append(seeded[right])
            left += 1
            right -= 1
        return ordered

    def round_finish_range(self, round_size: int) -> Tuple[int, int]:
        if round_size <= 2:
            return (2, 2)
        start = (round_size // 2) + 1
        end = round_size
        return (start, end)

    def run(self) -> KnockoutResult:
        current = self.players[:]
        while len(current) > 1:
            size = len(current)
            if size == 2:
                round_name = "Final"
            elif size == 4:
                round_name = "Semifinal"
            elif size == 8:
                round_name = "Quarterfinal"
            else:
                round_name = f"Round of {size}"

            print(f"\n========== {round_name.upper()} ==========")
            seeded = self.bracket_seed_order(current)
            winners = []
            round_records = []
            eliminated_this_round = []
            for i in range(0, len(seeded), 2):
                p1, p2 = seeded[i], seeded[i + 1]
                expected1 = glicko2_expected_score(p1.glicko, p2.glicko)
                expected2 = glicko2_expected_score(p2.glicko, p1.glicko)
                print(f"{p1.name} vs {p2.name} | expected {expected1:.3f} to {expected2:.3f}")

                match_logger = Logger(enabled=self.verbose_matches, prefix="match")
                match = Match(
                    p1, p2,
                    seed=self.random.randint(1, 10_000_000),
                    verbose=self.verbose_matches,
                    logger=match_logger,
                    manual_handler=self.manual_handler,
                    manual_player_name=self.manual_player_name,
                )
                winner, perf, lines = match.play()
                loser = p2 if winner.name == p1.name else p1

                for match_player in match.players:
                    original = p1 if match_player.name == p1.name else p2
                    original.glicko = match_player.glicko

                winners.append(p1 if winner.name == p1.name else p2)
                eliminated_this_round.append((loser.name, perf[loser.name], loser.glicko.rating))
                round_records.append((p1.name, p2.name, winner.name))
                winner_original = p1 if winner.name == p1.name else p2
                loser_original = p2 if winner.name == p1.name else p1
                winner_original.wins += 1
                loser_original.losses += 1
                winner_original.tourney.wins += 1
                loser_original.tourney.losses += 1
                p1.tourney.matches_played += 1
                p2.tourney.matches_played += 1
                p1.tourney.performance_total += perf[p1.name]
                p2.tourney.performance_total += perf[p2.name]
                print(f"Winner: {winner.name} | {p1.name} perf {perf[p1.name]:.1f} | {p2.name} perf {perf[p2.name]:.1f} | Gates {len(match.captured[p1.name])}-{len(match.captured[p2.name])}")

                self.play_logs.append(f"========== {round_name.upper()} ==========")
                self.play_logs.extend(lines)
                self.play_logs.append("")

            start_finish, _end_finish = self.round_finish_range(len(current))
            ordered_losers = sorted(eliminated_this_round, key=lambda x: (-x[1], -x[2], x[0]))
            for offset, (loser_name, _perf, _rating) in enumerate(ordered_losers):
                self.result.placements[loser_name] = start_finish + offset

            self.result.rounds.append(round_records)
            current = winners

        champion = current[0]
        self.result.champion = champion
        self.result.placements[champion.name] = 1

        print("\n========== KNOCKOUT FINAL PLACINGS ==========")
        ordered = sorted(self.result.placements.items(), key=lambda x: x[1])
        for pos, (name, finish) in enumerate(ordered, start=1):
            player = next(p for p in self.players if p.name == name)
            avg_perf = player.tourney.performance_total / player.tourney.matches_played if player.tourney.matches_played else player.glicko.rating
            print(f"{pos:>2}. {name:<20} Finish {finish:<3d} Rating {player.glicko.rating:>7.1f} Average Performance {avg_perf:>6.1f}")
        return self.result

    def export_files(self, seed: int = 42, save_play_by_play: bool = True) -> Tuple[Path, Optional[Path]]:
        summary_path = get_current_output_dir() / build_output_filename("knockout_tournament", len(self.players), None, random_suffix(random.Random(seed + 2001)))
        lines = ["========== KNOCKOUT FINAL PLACINGS =========="]
        ordered = sorted(self.result.placements.items(), key=lambda x: x[1])
        for pos, (name, finish) in enumerate(ordered, start=1):
            player = next(p for p in self.players if p.name == name)
            avg_perf = player.tourney.performance_total / player.tourney.matches_played if player.tourney.matches_played else player.glicko.rating
            lines.append(f"{pos:>2}. {name:<20} Finish {finish:<3d} Rating {player.glicko.rating:>7.1f} Average Performance {avg_perf:>6.1f}")
        lines.append("")
        lines.append("========== ROUND RESULTS ==========")
        for i, recs in enumerate(self.result.rounds, start=1):
            lines.append(f"Round block {i}")
            for p1, p2, winner in recs:
                lines.append(f"  {p1} vs {p2} | Winner {winner}")
        lines.append("")
        lines.append("========== FINAL LOADOUTS ==========")
        ordered_players = sorted(self.players, key=lambda p: (self.result.placements.get(p.name, 999), -p.glicko.rating))
        for p in ordered_players:
            lines.append("")
            lines.extend(player_loadout_lines(p))
        summary_path.write_text("\n".join(lines), encoding="utf-8")

        play_path = None
        if save_play_by_play:
            play_path = get_current_output_dir() / build_output_filename("knockout_playbyplay", len(self.players), None, random_suffix(random.Random(seed + 2002)))
            play_path.write_text("\n".join(self.play_logs), encoding="utf-8")
        return summary_path, play_path


# ============================================================
# PERSISTENCE
# ============================================================

class NPCDatabase:
    def __init__(self, db_path: Path = DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS npc_profiles (
                name TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS world_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tournament_archives (
                archive_id TEXT PRIMARY KEY,
                season INTEGER NOT NULL,
                event_no INTEGER NOT NULL,
                tournament_type TEXT NOT NULL,
                participant_count INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                data TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def save_profile(self, profile: PlayerProfile) -> None:
        self.conn.execute(
            "REPLACE INTO npc_profiles (name, data) VALUES (?, ?)",
            (profile.name, json.dumps(serialize_profile(profile))),
        )
        self.conn.commit()

    def save_profiles(self, profiles: List[PlayerProfile]) -> None:
        self.conn.executemany(
            "REPLACE INTO npc_profiles (name, data) VALUES (?, ?)",
            [(p.name, json.dumps(serialize_profile(p))) for p in profiles],
        )
        self.conn.commit()

    def load_all_profiles(self) -> List[PlayerProfile]:
        rows = self.conn.execute("SELECT data FROM npc_profiles").fetchall()
        out = []
        for (data,) in rows:
            out.append(deserialize_profile(json.loads(data)))
        return out

    def get_world_int(self, key: str, default: int = 0) -> int:
        row = self.conn.execute("SELECT value FROM world_state WHERE key=?", (key,)).fetchone()
        return int(row[0]) if row else default

    def set_world_int(self, key: str, value: int) -> None:
        self.conn.execute("REPLACE INTO world_state (key, value) VALUES (?, ?)", (key, str(int(value))))
        self.conn.commit()

    def get_world_json(self, key: str, default=None):
        row = self.conn.execute("SELECT value FROM world_state WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row[0])
        except Exception:
            return default

    def set_world_json(self, key: str, value) -> None:
        self.conn.execute("REPLACE INTO world_state (key, value) VALUES (?, ?)", (key, json.dumps(value)))
        self.conn.commit()

    def save_tournament_archive(self, archive: Dict) -> None:
        self.conn.execute(
            "REPLACE INTO tournament_archives (archive_id, season, event_no, tournament_type, participant_count, created_at, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                archive["archive_id"],
                int(archive["season"]),
                int(archive["event_no"]),
                archive["tournament_type"],
                int(archive["participant_count"]),
                archive.get("created_at", datetime.now().isoformat(timespec="seconds")),
                json.dumps(archive),
            ),
        )
        self.conn.commit()

    def load_tournament_archives(self) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT data FROM tournament_archives ORDER BY season DESC, event_no DESC"
        ).fetchall()
        return [json.loads(data) for (data,) in rows]

    def load_archive_by_id(self, archive_id: str) -> Optional[Dict]:
        row = self.conn.execute("SELECT data FROM tournament_archives WHERE archive_id=?", (archive_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def reset_world(self) -> None:
        self.conn.execute("DELETE FROM npc_profiles")
        self.conn.execute("DELETE FROM world_state")
        self.conn.execute("DELETE FROM tournament_archives")
        self.conn.commit()


def serialize_profile(p: PlayerProfile) -> Dict:
    p.ensure_valid_loadout()
    p.update_career_stage()
    p.update_signature()
    return {
        "name": p.name,
        "chosen_attribute": p.chosen_attribute.value,
        "style": p.style.value,
        "rolling_skill": p.rolling_skill,
        "intelligence": p.intelligence,
        "aggression": p.aggression,
        "risk": p.risk,
        "money": p.money,
        "glicko": asdict(p.glicko),
        "collection_bakugan": [
            {"name": b.name, "attribute": b.attribute.value, "base_g": b.base_g, "price": b.price}
            for b in p.collection_bakugan
        ],
        "collection_gates": [
            {"name": g.name, "gate_type": g.gate_type.value, "bonuses": {k.value: v for k, v in g.bonuses.items()}, "description": g.description, "effect_id": g.effect_id, "price": g.price}
            for g in p.collection_gates
        ],
        "collection_abilities": [
            {"name": a.name, "color": a.color.value, "timing": a.timing.name, "description": a.description, "effect_id": a.effect_id, "price": a.price}
            for a in p.collection_abilities
        ],
        "active_bakugan_idx": p.active_bakugan_idx,
        "active_gate_idx": p.active_gate_idx,
        "active_ability_idx": p.active_ability_idx,
        "is_human": p.is_human,
        "wins": p.wins,
        "losses": p.losses,
        "tourney": asdict(p.tourney),
        "tournaments_entered": p.tournaments_entered,
        "tournament_titles": p.tournament_titles,
        "finals": p.finals,
        "podiums": p.podiums,
        "top8s": p.top8s,
        "career_earnings": p.career_earnings,
        "peak_rating": p.peak_rating,
        "fame": p.fame,
        "training_points": p.training_points,
        "sponsorship": p.sponsorship,
        "career_stage": p.career_stage,
        "development_focus": p.development_focus,
        "archetype": p.archetype.value,
        "signature_bakugan": p.signature_bakugan,
        "rivals": list(p.rivals),
        "head_to_head": {k: {"wins": int(v.get("wins", 0)), "losses": int(v.get("losses", 0))} for k, v in p.head_to_head.items()},
        "story_flags": dict(p.story_flags),
        "age": profile_age(p),
        "tournament_history": [dict(x) for x in p.tournament_history[-20:]],
    }


def deserialize_profile(d: Dict) -> PlayerProfile:
    rng = random.Random()
    starting_age = int((d.get("story_flags", {}) or {}).get("age", d.get("age", PLAYER_DEFAULT_AGE)) or PLAYER_DEFAULT_AGE)
    profile = PlayerProfile(
        name=d["name"],
        chosen_attribute=Attribute(d["chosen_attribute"]),
        style=PlayerStyle(d["style"]),
        rolling_skill=d["rolling_skill"],
        intelligence=d["intelligence"],
        aggression=d["aggression"],
        risk=d["risk"],
        money=d["money"],
        glicko=GlickoRating(**d["glicko"]),
        collection_bakugan=[
            Bakugan(x["name"], Attribute(x["attribute"]), x["base_g"], x.get("price", 150))
            for x in d["collection_bakugan"]
        ],
        collection_gates=[
            GateCard(
                x["name"],
                GateType(x["gate_type"]),
                {Attribute(k): v for k, v in x["bonuses"].items()},
                x["description"],
                x["effect_id"],
                x.get("price", 110),
            )
            for x in d["collection_gates"]
        ],
        collection_abilities=[
            AbilityCard(
                x["name"],
                AbilityColor(x["color"]),
                Timing[x["timing"]],
                x["description"],
                x["effect_id"],
                x.get("price", 100),
            )
            for x in d["collection_abilities"]
        ],
        active_bakugan_idx=list(d.get("active_bakugan_idx", [0, 1, 2])),
        active_gate_idx=list(d.get("active_gate_idx", [0, 1, 2])),
        active_ability_idx=list(d.get("active_ability_idx", [0, 1, 2])),
        is_human=d.get("is_human", False),
        wins=d.get("wins", 0),
        losses=d.get("losses", 0),
        tourney=TournamentStats(**d.get("tourney", {})),
        tournaments_entered=d.get("tournaments_entered", 0),
        tournament_titles=d.get("tournament_titles", 0),
        finals=d.get("finals", 0),
        podiums=d.get("podiums", 0),
        top8s=d.get("top8s", 0),
        career_earnings=d.get("career_earnings", 0),
        peak_rating=d.get("peak_rating", d.get("glicko", {}).get("rating", DEFAULT_START_RATING)),
        fame=d.get("fame", 0),
        training_points=d.get("training_points", 0),
        sponsorship=d.get("sponsorship", 0),
        career_stage=d.get("career_stage", "Rookie"),
        development_focus=d.get("development_focus", "Balanced"),
        archetype=PlayerArchetype(d.get("archetype", derive_archetype_name_from_payload(d))),
        signature_bakugan=d.get("signature_bakugan", ""),
        rivals=list(d.get("rivals", [])),
        head_to_head={k: {"wins": int(v.get("wins", 0)), "losses": int(v.get("losses", 0))} for k, v in d.get("head_to_head", {}).items()},
        story_flags=dict(d.get("story_flags", {})),
        tournament_history=[dict(x) for x in d.get("tournament_history", [])],
    )
    ensure_age_metadata(profile, rng, starting_age=starting_age)
    profile.ensure_valid_loadout()
    profile.update_career_stage()
    profile.update_rivals()
    profile.update_signature()
    return profile




def make_active_loadout_snapshot(profile: PlayerProfile) -> Dict[str, object]:
    profile.ensure_valid_loadout()
    return {
        "bakugan": [
            {"name": b.name, "attribute": b.attribute.value, "base_g": b.base_g}
            for b in profile.active_bakugan()
        ],
        "gates": [
            {"name": g.name, "gate_type": g.gate_type.value}
            for g in profile.active_gates()
        ],
        "abilities": [
            {"name": a.name, "color": a.color.value}
            for a in profile.active_abilities()
        ],
    }


def format_loadout_snapshot_lines(snapshot: Dict[str, object], prefix: str = "") -> List[str]:
    lines: List[str] = []
    baku = list(snapshot.get("bakugan", []))
    gates = list(snapshot.get("gates", []))
    abilities = list(snapshot.get("abilities", []))
    lines.append(f"{prefix}Bakugan:")
    if baku:
        for b in baku:
            lines.append(f"{prefix}  - {b.get('name','?')} | {b.get('attribute','?')} | {b.get('base_g','?')} G")
    else:
        lines.append(f"{prefix}  - None")
    lines.append(f"{prefix}Gate Cards:")
    if gates:
        for g in gates:
            lines.append(f"{prefix}  - {g.get('name','?')} | {g.get('gate_type','?')}")
    else:
        lines.append(f"{prefix}  - None")
    lines.append(f"{prefix}Ability Cards:")
    if abilities:
        for a in abilities:
            lines.append(f"{prefix}  - {a.get('name','?')} | {a.get('color','?')}")
    else:
        lines.append(f"{prefix}  - None")
    return lines


def summarize_archive_lines(archive: Dict) -> List[str]:
    lines: List[str] = []
    lines.append(
        f"Season {archive['season']} Event {archive['event_no']} | {archive['tournament_type']} | Participants {archive['participant_count']} | Winner {archive.get('winner', 'Unknown')}"
    )
    standings = archive.get("standings", [])
    if standings:
        lines.append("Standings:")
        for row in standings[: min(16, len(standings))]:
            lines.append(
                f"  {row.get('position', '?'):>2}. {row.get('name', '?')} | Finish {row.get('finish', '?')} | Rating {row.get('rating', 0):.1f} | Titles {row.get('titles', 0)} | Money £{row.get('money', 0)}"
            )
    entrants = archive.get("entrants", [])
    if entrants:
        lines.append("")
        lines.append("Entrant snapshots:")
        for snap in entrants:
            lines.append(
                f"- {snap['name']} | Attr {snap['chosen_attribute']} | Style {snap['style']} | Rating {snap['glicko']['rating']:.1f} | Money £{snap['money']} | Titles {snap.get('tournament_titles', 0)}"
            )
            baku = snap.get('collection_bakugan', [])
            active_b = snap.get('active_bakugan_idx', [])
            if baku and active_b:
                lines.append('    Bakugan:')
                for idx in active_b:
                    if 0 <= idx < len(baku):
                        b = baku[idx]
                        lines.append(f"      {b['name']} | {b['attribute']} | {b['base_g']} G")
            gates = snap.get('collection_gates', [])
            active_g = snap.get('active_gate_idx', [])
            if gates and active_g:
                lines.append('    Gates:')
                for idx in active_g:
                    if 0 <= idx < len(gates):
                        g = gates[idx]
                        lines.append(f"      {g['name']} | {g['gate_type']}")
            abilities = snap.get('collection_abilities', [])
            active_a = snap.get('active_ability_idx', [])
            if abilities and active_a:
                lines.append('    Abilities:')
                for idx in active_a:
                    if 0 <= idx < len(abilities):
                        a = abilities[idx]
                        lines.append(f"      {a['name']} | {a['color']}")
    return lines


def group_archives_by_season(archives: List[Dict]) -> Dict[int, List[Dict]]:
    grouped: Dict[int, List[Dict]] = defaultdict(list)
    for arc in archives:
        grouped[int(arc.get("season", 0))].append(arc)
    for season in grouped:
        grouped[season].sort(key=lambda a: int(a.get("event_no", 0)))
    return grouped


def build_season_summary_lines(archives: List[Dict], season: int, player_name: Optional[str] = None) -> List[str]:
    grouped = group_archives_by_season(archives)
    season_archives = grouped.get(season, [])
    lines: List[str] = []
    if not season_archives:
        return [f"No archives found for Season {season}."]

    player_finishes: List[int] = []
    winners: Dict[str, int] = defaultdict(int)
    podiums: Dict[str, int] = defaultdict(int)
    finals: Dict[str, int] = defaultdict(int)
    champion_ratings: List[Tuple[float, str, int]] = []
    title_holders: Dict[str, int] = defaultdict(int)
    money_leaders: Dict[str, int] = defaultdict(int)

    lines.append(f"Season {season} Summary")
    lines.append(f"Tournaments played: {len(season_archives)}")
    lines.append("")
    lines.append("Event champions:")

    for arc in season_archives:
        event_no = int(arc.get("event_no", 0))
        winner = arc.get("winner", "Unknown")
        winners[winner] += 1
        standings = arc.get("standings", [])
        participant_count = int(arc.get("participant_count", 0))
        winner_rating = 0.0
        for row in standings:
            finish = int(row.get("finish", participant_count))
            name = row.get("name", "?")
            if finish <= 3:
                podiums[name] += 1
            if finish <= 2:
                finals[name] += 1
            if finish == 1:
                title_holders[name] += 1
                winner_rating = float(row.get("rating", 0.0))
            if finish == 1:
                money_leaders[name] = max(money_leaders[name], int(row.get("money", 0)))
            if player_name and name == player_name:
                player_finishes.append(finish)
        champion_ratings.append((winner_rating, winner, event_no))
        event_label = "World Cup" if event_no == 0 and arc.get("tournament_type") == WORLD_CUP_TOURNAMENT_LABEL else f"Event {event_no}"
        lines.append(f"  {event_label}: {winner} | {arc.get('tournament_type', '?')} | {participant_count} players | Winning rating {winner_rating:.0f}")

    lines.append("")
    lines.append("Season leaderboards:")
    top_titles = sorted(title_holders.items(), key=lambda x: (-x[1], x[0]))[:5]
    top_podiums = sorted(podiums.items(), key=lambda x: (-x[1], x[0]))[:5]
    top_finals = sorted(finals.items(), key=lambda x: (-x[1], x[0]))[:5]
    top_rated_champs = sorted(champion_ratings, key=lambda x: (-x[0], x[2]))[:5]

    lines.append("  Most titles this season:")
    for name, count in top_titles:
        lines.append(f"    {name}: {count}")
    lines.append("  Most podiums this season:")
    for name, count in top_podiums:
        lines.append(f"    {name}: {count}")
    lines.append("  Most finals this season:")
    for name, count in top_finals:
        lines.append(f"    {name}: {count}")
    lines.append("  Highest-rated event champions:")
    for rating, name, event_no in top_rated_champs:
        label = "World Cup" if event_no == 0 else f"Event {event_no}"
        lines.append(f"    {label}: {name} at {rating:.0f}")

    if player_name:
        lines.append("")
        lines.append(f"Player season view: {player_name}")
        if player_finishes:
            avg_finish = sum(player_finishes) / len(player_finishes)
            best_finish = min(player_finishes)
            titles = sum(1 for x in player_finishes if x == 1)
            podium_count = sum(1 for x in player_finishes if x <= 3)
            finals_count = sum(1 for x in player_finishes if x <= 2)
            lines.append(f"  Events entered: {len(player_finishes)}")
            lines.append(f"  Best finish: {best_finish}")
            lines.append(f"  Average finish: {avg_finish:.2f}")
            lines.append(f"  Titles: {titles}")
            lines.append(f"  Finals: {finals_count}")
            lines.append(f"  Podiums: {podium_count}")
            lines.append("  Event finishes:")
            for arc in season_archives:
                standings = arc.get("standings", [])
                for row in standings:
                    if row.get("name") == player_name:
                        event_no = int(arc.get('event_no',0))
                        event_label = "World Cup" if event_no == 0 and arc.get("tournament_type") == WORLD_CUP_TOURNAMENT_LABEL else f"Event {event_no}"
                        lines.append(f"    {event_label}: Finish {int(row.get('finish', 0))} | Rating {float(row.get('rating', 0.0)):.1f} | Money £{int(row.get('money', 0))}")
                        break
        else:
            lines.append("  Player did not appear in this season's archived tournaments.")

    return lines


def make_tournament_archive(season: int, event_no: int, tournament_type, participant_count: int, entrants: List[PlayerProfile], finish_map: Dict[str, int], winner_name: str, summary_path: Optional[Path], play_path: Optional[Path]) -> Dict:
    serialized_entrants = [serialize_profile(p) for p in entrants]
    standings = []
    for snap in serialized_entrants:
        standings.append({
            "position": finish_map.get(snap['name'], participant_count),
            "finish": finish_map.get(snap['name'], participant_count),
            "name": snap['name'],
            "rating": snap['glicko']['rating'],
            "money": snap['money'],
            "titles": snap.get('tournament_titles', 0),
        })
    standings.sort(key=lambda x: (x['position'], -x['rating'], x['name']))
    return {
        "archive_id": f"S{season:03d}-E{event_no:04d}-{random_suffix(random.Random(season * 100000 + event_no), 8)}",
        "season": season,
        "event_no": event_no,
        "tournament_type": tournament_type.value if hasattr(tournament_type, "value") else str(tournament_type),
        "participant_count": participant_count,
        "winner": winner_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "summary_path": str(summary_path) if summary_path else "",
        "play_path": str(play_path) if play_path else "",
        "standings": standings,
        "entrants": serialized_entrants,
    }

# ============================================================
# GENERATION
# ============================================================

NAME_PARTS_1 = ['Aaron', 'Abigail', 'Ada', 'Adrian', 'Aiko', 'Aisha', 'Akira', 'Alba', 'Alejandro', 'Alec', 'Alex', 'Alexandra', 'Alina', 'Amara', 'Amir', 'Ana', 'Anaya', 'Andrei', 'Anika', 'Anna', 'Aria', 'Arthur', 'Asher', 'Astrid', 'Aya', 'Beatrice', 'Bella', 'Benjamin', 'Bianca', 'Boris', 'Caleb', 'Camila', 'Carla', 'Carmen', 'Caspian', 'Cecilia', 'Celeste', 'Chiara', 'Chloe', 'Clara', 'Connor', 'Cora', 'Dahlia', 'Damon', 'Daniel', 'Daria', 'David', 'Delia', 'Diana', 'Diego', 'Dominic', 'Eden', 'Edith', 'Elias', 'Elina', 'Elise', 'Eliza', 'Ella', 'Emil', 'Emilia', 'Emma', 'Enzo', 'Erika', 'Ethan', 'Eva', 'Felix', 'Fiona', 'Freya', 'Gabriel', 'Gael', 'Gemma', 'George', 'Gianna', 'Gideon', 'Grace', 'Hana', 'Hannah', 'Harper', 'Hazel', 'Helena', 'Henry', 'Hugo', 'Ibrahim', 'Ida', 'Ilya', 'Ines', 'Iris', 'Isaac', 'Isabel', 'Isla', 'Ivan', 'Jade', 'James', 'Jasper', 'Javier', 'Jonah', 'Jonas', 'Josephine', 'Jude', 'Julia', 'Kai', 'Karina', 'Katarina', 'Keira', 'Kian', 'Laila', 'Lara', 'Layla', 'Leah', 'Leo', 'Leon', 'Lila', 'Lilia', 'Lina', 'Logan', 'Lucia', 'Lucian', 'Lucy', 'Luka', 'Luna', 'Lydia', 'Maja', 'Malik', 'Marco', 'Marcus', 'Mariam', 'Marta', 'Mateo', 'Matilda', 'Maya', 'Mila', 'Milo', 'Mina', 'Mira', 'Miriam', 'Nadia', 'Naomi', 'Natalia', 'Nico', 'Nikolai', 'Nina', 'Noah', 'Nora', 'Nova', 'Olivia', 'Omar', 'Ophelia', 'Oscar', 'Otis', 'Petra', 'Philip', 'Phoebe', 'Piper', 'Quentin', 'Rafael', 'Rhea', 'Rina', 'Roman', 'Rosalie', 'Rowan', 'Sabrina', 'Samuel', 'Sara', 'Sasha', 'Selene', 'Sofia', 'Soren', 'Stella', 'Talia', 'Theo', 'Tobias', 'Valentina', 'Vera', 'Victor', 'Viola', 'Violet', 'Wesley', 'Yara', 'Yasmin', 'Zara']
NAME_PARTS_2 = ['Adams', 'Adler', 'Ahmed', 'Akiyama', 'Alvarez', 'Andersson', 'Antonov', 'Archer', 'Arslan', 'Baba', 'Bae', 'Baker', 'Baran', 'Becker', 'Bennett', 'Bianchi', 'Blackwood', 'Blake', 'Brown', 'Carter', 'Castillo', 'Choi', 'Clarke', 'Costa', 'Cruz', 'Dawson', 'Diaz', 'Dubois', 'Edwards', 'Ellis', 'Eriksen', 'Evans', 'Farrell', 'Fischer', 'Flores', 'Ford', 'Foster', 'Garcia', 'Gardner', 'Gibson', 'Gonzalez', 'Gray', 'Green', 'Griffin', 'Hall', 'Hart', 'Hayes', 'Hoffmann', 'Hughes', 'Ibrahim', 'Ivanov', 'Jackson', 'Jensen', 'Johansson', 'Jones', 'Kaur', 'Kaya', 'Kim', 'Klein', 'Kovacs', 'Kowalski', 'Kumar', 'Larsson', 'Lee', 'Lopez', 'Martin', 'Martinez', 'Mason', 'Meyer', 'Miller', 'Mitchell', 'Morgan', 'Mori', 'Morris', 'Murphy', 'Nakamura', 'Navarro', 'Nguyen', 'Nielsen', 'Novak', 'Novotny', 'Olsen', 'Ortiz', 'Owens', 'Park', 'Patel', 'Pereira', 'Petrov', 'Popov', 'Price', 'Quinn', 'Rahman', 'Ramirez', 'Reed', 'Reyes', 'Riley', 'Rivera', 'Roberts', 'Robinson', 'Rossi', 'Russell', 'Sahin', 'Saito', 'Sato', 'Schmidt', 'Schneider', 'Scott', 'Sharma', 'Silva', 'Singh', 'Smith', 'Sokolov', 'Stewart', 'Stone', 'Sullivan', 'Suzuki', 'Taylor', 'Thomas', 'Torres', 'Turner', 'Usman', 'Valdez', 'Van Dijk', 'Varga', 'Vasquez', 'Volkov', 'Wagner', 'Walker', 'Walsh', 'Ward', 'Watson', 'Weber', 'White', 'Williams', 'Wilson', 'Wright', 'Yamamoto', 'Yang', 'Young', 'Zimmermann']


def random_name(rng: random.Random, used: set[str]) -> str:
    while True:
        name = f"{rng.choice(NAME_PARTS_1)} {rng.choice(NAME_PARTS_2)}"
        if name not in used:
            used.add(name)
            return name


def generate_stats_from_priority(priority_order: List[str], rng: random.Random) -> Dict[str, float]:
    values = [round(v, 2) for v in sorted([rng.uniform(0.45, 0.95) for _ in range(4)], reverse=True)]
    stats = {}
    for stat, value in zip(priority_order, values):
        stats[stat] = value
    return stats


def draft_starting_profile(name: str, chosen_attribute: Attribute, rng: random.Random, is_human: bool = False, stat_priority: Optional[List[str]] = None, starting_age: Optional[int] = None) -> PlayerProfile:
    templates = make_bakugan_templates()
    abilities = make_ability_cards()
    gates = make_gate_cards()

    beginner_names = {"Serpenoid", "Juggernoid", "Robotallion", "Saurus", "Falconeer"}
    beginner_pool = [t for t in templates if t.name in beginner_names]

    if len(beginner_pool) < 3:
        raise ValueError("Starter Bakugan pool is missing required templates")

    matching_templates = [t for t in beginner_pool if chosen_attribute in t.allowed_attributes]
    if not matching_templates:
        raise ValueError("No starter Bakugan can match the chosen attribute")

    guaranteed_template = rng.choice(matching_templates)
    remaining_templates = [t for t in beginner_pool if t.name != guaranteed_template.name]
    other_templates = rng.sample(remaining_templates, 2)

    bakugan = [guaranteed_template.roll_instance(name, rng, chosen_attribute)]
    for t in other_templates:
        forced_attr = chosen_attribute if (chosen_attribute in t.allowed_attributes and rng.random() < 0.35) else None
        bakugan.append(t.roll_instance(name, rng, forced_attr))
    rng.shuffle(bakugan)
    gate_cards = [
        clone_gate(rng.choice([g for g in gates if g.gate_type == GateType.GOLD])),
        clone_gate(rng.choice([g for g in gates if g.gate_type == GateType.SILVER])),
        clone_gate(rng.choice([g for g in gates if g.gate_type == GateType.BRONZE])),
    ]
    ability_cards = [
        clone_ability(rng.choice([a for a in abilities if a.color == AbilityColor.RED])),
        clone_ability(rng.choice([a for a in abilities if a.color == AbilityColor.BLUE])),
        clone_ability(rng.choice([a for a in abilities if a.color == AbilityColor.GREEN])),
    ]

    if stat_priority is None:
        stat_map = {
            "roll": _skewed_stat(rng, 0.30, 0.95),
            "int": _skewed_stat(rng, 0.28, 0.95),
            "agg": _skewed_stat(rng, 0.18, 0.95),
            "risk": _skewed_stat(rng, 0.15, 0.95),
        }
    else:
        stat_map = generate_stats_from_priority(stat_priority, rng)

    style_choice = rng.choice(list(PlayerStyle))
    profile = PlayerProfile(
        name=name,
        chosen_attribute=chosen_attribute,
        style=style_choice,
        rolling_skill=stat_map["roll"],
        intelligence=stat_map["int"],
        aggression=stat_map["agg"],
        risk=stat_map["risk"],
        money=500 if is_human else 0,
        glicko=GlickoRating(),
        collection_bakugan=bakugan,
        collection_gates=gate_cards,
        collection_abilities=ability_cards,
        active_bakugan_idx=[0, 1, 2],
        active_gate_idx=[0, 1, 2],
        active_ability_idx=[0, 1, 2],
        is_human=is_human,
        development_focus=rng.choice(["Balanced", "Power", "Control", "Strategy", "Aggro", "Greed"]),
    )
    profile.archetype = derive_archetype_for_profile(profile, rng)
    ensure_age_metadata(profile, rng, starting_age=starting_age)
    profile.ensure_valid_loadout()
    profile.update_career_stage()
    profile.update_rivals()
    profile.update_signature()
    return profile


def generate_npc_pool(count: int, existing: List[PlayerProfile], rng: random.Random, new_player_min_age: bool = False) -> List[PlayerProfile]:
    used_names = {p.name for p in existing}
    profiles = existing[:]
    initial_generation = len(existing) == 0
    while len(profiles) < count:
        name = random_name(rng, used_names)
        attr = rng.choice(all_attributes())
        npc_age = rng.randint(PLAYER_MIN_AGE, PLAYER_INITIAL_MAX_AGE) if initial_generation else (PLAYER_MIN_AGE if new_player_min_age else rng.randint(PLAYER_MIN_AGE, PLAYER_INITIAL_MAX_AGE))
        npc = draft_starting_profile(name, attr, rng, False, starting_age=npc_age)
        npc.money = rng.randint(150, 1100)
        npc.development_focus = rng.choice(["Balanced", "Power", "Control", "Strategy", "Aggro", "Greed"])
        npc.archetype = derive_archetype_for_profile(npc, rng)
        npc.story_flags["debut_tournament"] = rng.randint(0, 12)
        npc.update_signature()
        profiles.append(npc)
    return profiles[:count]


def weighted_sample_without_replacement(population: List[PlayerProfile], k: int, rng: random.Random, weight_fn: Callable[[PlayerProfile], float]) -> List[PlayerProfile]:
    pool = population[:]
    chosen: List[PlayerProfile] = []
    while pool and len(chosen) < k:
        weights = [max(0.01, weight_fn(p)) for p in pool]
        total = sum(weights)
        roll = rng.random() * total
        running = 0.0
        idx = 0
        for i, w in enumerate(weights):
            running += w
            if running >= roll:
                idx = i
                break
        chosen.append(pool.pop(idx))
    return chosen


def profile_strength_score(profile: PlayerProfile) -> float:
    baku = profile.active_bakugan() or profile.collection_bakugan
    best_baku = max((b.base_g for b in baku), default=350)
    avg_baku = sum(b.base_g for b in baku) / len(baku) if baku else 350
    return (
        profile.glicko.rating
        + profile.rolling_skill * 80
        + profile.intelligence * 90
        + profile.aggression * 35
        + best_baku * 0.35
        + avg_baku * 0.15
        + profile.fame * 1.2
    )


def _normalized_bakugan_name_key(name: str) -> str:
    norm = ''.join(ch.lower() for ch in name if ch.isalnum())
    alias_map = {
        'deltadragonoid': 'deltadragonoidii',
        'deltadragonoidii': 'deltadragonoidii',
        'fortress': 'fourtress',
        'fourtress': 'fourtress',
        'angelodiablopreyas': 'preyasii',
        'diabloangelopreyas': 'preyasii',
        'preyasangelo': 'preyasii',
        'preyasdiablo': 'preyasii',
        'preyasii': 'preyasii',
        'preyas': 'preyas',
    }
    return alias_map.get(norm, norm)


def _gate_named_target_key_for_scoring(gate: GateCard) -> str:
    gate_name_key = _normalized_bakugan_name_key(gate.name)
    if gate_name_key in {'preyas', 'preyasii', 'deltadragonoidii', 'fourtress'}:
        return gate_name_key
    desc = (gate.description or '').lower()
    if 'preyas ii' in desc:
        return 'preyasii'
    if 'preyas gets the gate card bonus twice' in desc:
        return 'preyas'
    if 'delta dragonoid ii' in desc or 'delta dragonoid' in desc:
        return 'deltadragonoidii'
    if 'fourtress' in desc or 'fortress' in desc:
        return 'fourtress'
    return gate_name_key


def _gate_named_double_bonus_count(gate: GateCard, active_bakus: Optional[List[Bakugan]]) -> int:
    if getattr(gate, 'effect_id', '') != 'GATE_DOUBLE_BONUS_NAMED' or not active_bakus:
        return 0
    target = _gate_named_target_key_for_scoring(gate)
    return sum(1 for b in active_bakus if _normalized_bakugan_name_key(b.name) == target)


def gate_profile_value(profile: PlayerProfile, gate: GateCard, active_bakus: Optional[List[Bakugan]] = None, meta: Optional[Dict[str, object]] = None, intelligence_override: Optional[float] = None) -> float:
    smartness = clamp(intelligence_override if intelligence_override is not None else profile.intelligence, 0.2, 0.99)
    bakus = active_bakus if active_bakus is not None else (profile.active_bakugan() or profile.collection_bakugan[:3])
    attrs = {b.attribute for b in bakus}
    total = sum(gate.bonuses.values()) * (0.22 + 0.20 * smartness)
    total += sum(gate.bonuses.get(a, 0) for a in attrs) * (0.55 + 0.35 * smartness)
    total += gate.bonuses.get(profile.chosen_attribute, 0) * (0.65 + 0.55 * smartness)
    effect_id = getattr(gate, 'effect_id', '') or ''
    used_abilities = min(4, len(profile.active_ability_idx))
    named_double_hits = _gate_named_double_bonus_count(gate, bakus)
    if named_double_hits:
        best_named_bonus = max((max(gate.bonuses.get(attr, 0) for attr in [*all_attributes()]) for _ in range(1)), default=0)
        total += named_double_hits * (28 + best_named_bonus * (0.18 + 0.18 * smartness))
        total += named_double_hits * (10 + 18 * smartness)
    if effect_id == 'GATE_EXACT_DOUBLE_ABILITY_BOOSTS':
        total += 26 + used_abilities * (9 + 5 * smartness)
    elif effect_id == 'GATE_EXACT_NO_ABILITIES':
        total -= 14 + used_abilities * (7 + 10 * smartness)
    elif effect_id in {'GATE_EXACT_SWAP_ORIGINAL_G', 'GATE_EXACT_DOUBLE_LOWER_ORIGINAL_G', 'GATE_EXACT_SWAP_ORIGINAL_G_IF_AQUOS'}:
        low_power_count = sum(1 for b in bakus if b.base_g <= 390)
        high_power_count = sum(1 for b in bakus if b.base_g >= 440)
        total += low_power_count * (10 + 12 * smartness)
        total -= high_power_count * (4 + 9 * smartness)
    elif effect_id == 'GATE_EXACT_GATE_WON_SCALING':
        total += profile.tourney.wins * (2 + 6 * smartness)
    elif effect_id == 'GATE_EXACT_ABILITY_USED_SCALING':
        total += used_abilities * (8 + 7 * smartness)
    elif effect_id == 'GATE_EXACT_RETURN_ALL_USED':
        total += 10 + 10 * smartness
    elif effect_id == 'GATE_EXACT_BAKUGAN_SWAP':
        total += 12 + 14 * smartness
    elif effect_id == 'GATE_EXACT_BAIT':
        total += 8 + 10 * smartness
    elif effect_id in {'GATE_NONE', 'GATE_EXACT_NONE'}:
        total -= 6 * smartness
    if meta is not None:
        meta_attr = meta.get('dominant_attr')
        if meta_attr is not None:
            total += gate.bonuses.get(meta_attr, 0) * (0.10 + 0.18 * smartness)
    return total



def _is_dragonoid_family_name(bakugan: Bakugan) -> bool:
    lower_name = bakugan.name.lower()
    return "dragonoid" in lower_name or "dragono" in lower_name



def ability_context_scores(profile: PlayerProfile, ability: AbilityCard, active_bakus: Optional[List[Bakugan]] = None,
                           active_gates: Optional[List[GateCard]] = None, meta: Optional[Dict[str, object]] = None) -> Dict[str, float]:
    bakus = active_bakus if active_bakus is not None else (profile.active_bakugan() or profile.collection_bakugan[:3])
    gates = active_gates if active_gates is not None else (profile.active_gates() or profile.collection_gates[:3])
    tags = ability_tags(ability)
    eid = ability.effect_id or ""
    attrs = [b.attribute for b in bakus]
    attr_counts = {a: attrs.count(a) for a in set(attrs)}
    dominant_attr = max(attr_counts, key=attr_counts.get) if attr_counts else profile.chosen_attribute
    gate_tags_seen: Set[str] = set()
    for gate in gates:
        gate_tags_seen |= gate_tags(gate)

    opening = 0.0
    behind = 0.0
    finisher = 0.0
    reliability = 0.0
    strategy = 0.0

    if ability.color == AbilityColor.RED:
        opening += 18
        finisher += 10
    elif ability.color == AbilityColor.BLUE:
        finisher += 12
        reliability += 8
    else:
        behind += 12
        strategy += 6

    if "raw_power" in tags:
        opening += 10
        finisher += 18
        reliability += 6
    if "combo" in tags:
        strategy += 18
        finisher += 8
    if "disruption" in tags:
        behind += 18
        strategy += 12
    if "comeback" in tags:
        behind += 20
    if "resource" in tags:
        reliability += 12
        strategy += 10

    if eid in {"EXACT_LOCKDOWN", "ROLL_PLUS", "ROLL_CHOOSE_BEST", "ROLL_RECOVER", "ROLL_IGNORE_BAD_MATCH", "ROLL_BATTLE_BONUS"}:
        opening += 22
        reliability += 14
    if eid in {"EXACT_DOOM_CARD", "EXACT_LEVEL_DOWN", "EXACT_COLORVOID", "EXACT_CLEAN_SLATE", "EXACT_DO_OVER"}:
        behind += 18
        strategy += 10
    if eid in {"EXACT_ALICES_SURPRISE", "EXACT_ATTRACTOR", "EXACT_BLUE_GREEN_COMBINE", "EXACT_RETURN_USED_ABILITY"}:
        finisher += 16
        strategy += 18
    if eid in {"EXACT_DARKUS_ONLY", "EXACT_AQUOS_ONLY", "EXACT_POWER_FROM_DARKNESS", "EXACT_BRUSHFIRE"}:
        reliability += 18
        finisher += 12

    if active_bakus:
        live_ratio = ability_live_rate(profile, ability, active_bakus, active_gates)
        reliability += live_ratio * 24
        if live_ratio < 0.34:
            strategy -= (0.34 - live_ratio) * 24

    if active_bakus and dominant_attr:
        if eid == "EXACT_DARKUS_ONLY" and dominant_attr == Attribute.DARKUS:
            strategy += 24
            finisher += 10
        if eid in {"EXACT_AQUOS_ONLY", "EXACT_AQUOS_SWAP"} and dominant_attr == Attribute.AQUOS:
            strategy += 24
            reliability += 8
        if eid == "EXACT_POWER_FROM_DARKNESS" and dominant_attr in {Attribute.DARKUS, Attribute.HAOS}:
            strategy += 20
        if eid == "EXACT_BRUSHFIRE" and dominant_attr in {Attribute.PYRUS, Attribute.SUBTERRA}:
            strategy += 18

    if "combo" in gate_tags_seen and "combo" in tags:
        strategy += 12
    if "resource" in gate_tags_seen and "resource" in tags:
        strategy += 10
    if "swing" in gate_tags_seen and ("comeback" in tags or eid in {"EXACT_ATTRACTOR", "EXACT_COLOR_SWAP"}):
        behind += 8
        strategy += 10

    if profile.archetype == PlayerArchetype.POWER_RUSH:
        opening += 8
        finisher += 10
        strategy += 4 if "raw_power" in tags else -2
    elif profile.archetype == PlayerArchetype.GATE_CONTROL:
        strategy += 10 + (10 if ("combo" in tags or "disruption" in tags) else 0)
        opening -= 2
    elif profile.archetype == PlayerArchetype.COMBO_SETUP:
        strategy += 16 + (10 if "combo" in tags else 0)
        finisher += 6
    elif profile.archetype == PlayerArchetype.COUNTER:
        behind += 10 + (10 if "disruption" in tags else 0)
        reliability += 4
    else:
        reliability += 6

    if profile.style == PlayerStyle.TACTICAL:
        strategy += 12
        reliability += 8
    elif profile.style == PlayerStyle.DEFENSIVE:
        behind += 10
        reliability += 10
    elif profile.style == PlayerStyle.RECKLESS:
        opening += 8
        finisher += 8
        reliability -= 2
    elif profile.style == PlayerStyle.COMBO:
        strategy += 12
    elif profile.style == PlayerStyle.BALANCED:
        reliability += 6

    return {"opening": opening, "behind": behind, "finisher": finisher, "reliability": reliability, "strategy": strategy}


def ability_role_need(profile: PlayerProfile, chosen: List[AbilityCard]) -> Dict[str, float]:
    tags_seen: Set[str] = set()
    by_color = {a.color for a in chosen}
    for a in chosen:
        tags_seen |= ability_tags(a)
    return {
        "opening": 1.0 if AbilityColor.RED not in by_color else 0.35,
        "behind": 1.0 if "comeback" not in tags_seen and "disruption" not in tags_seen else 0.45,
        "finisher": 1.0 if "raw_power" not in tags_seen else 0.5,
        "reliability": 1.0 if "resource" not in tags_seen else 0.55,
        "strategy": 1.0 if "combo" not in tags_seen and "disruption" not in tags_seen else 0.55,
    }


def loadout_upgrade_delta(profile: PlayerProfile, candidate, category: str, meta: Optional[Dict[str, object]] = None) -> float:
    smartness = clamp(profile.intelligence, 0.2, 0.99)
    active_bakus = profile.active_bakugan() or profile.collection_bakugan[:3]
    active_gates = profile.active_gates() or profile.collection_gates[:3]
    if category == "baku":
        current = [profile.collection_bakugan[i] for i in profile.active_bakugan_idx if 0 <= i < len(profile.collection_bakugan)] or active_bakus
        cand_val = bakugan_profile_value(profile, candidate, active_gates=active_gates, meta=meta, intelligence_override=smartness)
        weakest = min((bakugan_profile_value(profile, b, active_gates=active_gates, meta=meta, intelligence_override=smartness) for b in current), default=cand_val)
        name_penalty = sum(1 for b in profile.collection_bakugan if normalize_named_bakugan_token(b.name) == normalize_named_bakugan_token(candidate.name)) * (5 + 8 * smartness)
        return cand_val - weakest - name_penalty
    if category == "gate":
        current = [profile.collection_gates[i] for i in profile.active_gate_idx if 0 <= i < len(profile.collection_gates)] or active_gates
        same_type = [g for g in current if g.gate_type == candidate.gate_type]
        cand_val = gate_profile_value(profile, candidate, active_bakus=active_bakus, meta=meta, intelligence_override=smartness)
        cand_val += gate_profile_archetype_bonus(profile, candidate, active_bakus, meta=meta, intelligence_override=smartness)
        weakest = min((gate_profile_value(profile, g, active_bakus=active_bakus, meta=meta, intelligence_override=smartness) + gate_profile_archetype_bonus(profile, g, active_bakus, meta=meta, intelligence_override=smartness) for g in same_type), default=cand_val - 4)
        return cand_val - weakest
    current = [profile.collection_abilities[i] for i in profile.active_ability_idx if 0 <= i < len(profile.collection_abilities)] or []
    same_color = [a for a in current if a.color == candidate.color]
    cand_val = ability_profile_value(profile, candidate, active_bakus=active_bakus, active_gates=active_gates, meta=meta, intelligence_override=smartness)
    cand_val += ability_profile_archetype_bonus(profile, candidate, active_bakus, active_gates=active_gates, meta=meta, intelligence_override=smartness)
    ctx = ability_context_scores(profile, candidate, active_bakus, active_gates, meta)
    cand_val += 0.25 * sum(ctx.values())
    weakest = min((ability_profile_value(profile, a, active_bakus=active_bakus, active_gates=active_gates, meta=meta, intelligence_override=smartness) + ability_profile_archetype_bonus(profile, a, active_bakus, active_gates=active_gates, meta=meta, intelligence_override=smartness) for a in same_color), default=cand_val - 4)
    unusable_penalty = 0 if ability_is_live_for_team(profile, candidate, active_bakus, active_gates) else (22 + 60 * smartness)
    return cand_val - weakest - unusable_penalty

def ability_live_rate(profile: PlayerProfile, ability: AbilityCard, active_bakus: Optional[List[Bakugan]] = None,
                      active_gates: Optional[List[GateCard]] = None) -> float:
    bakus = active_bakus if active_bakus is not None else (profile.active_bakugan() or profile.collection_bakugan[:3])
    gates = active_gates if active_gates is not None else (profile.active_gates() or profile.collection_gates[:3])
    if not bakus:
        return 0.5
    attrs = [b.attribute for b in bakus]
    attr_set = set(attrs)
    eid = ability.effect_id
    team_n = max(1, len(bakus))
    gate_n = max(1, len(gates))

    if eid in {"EXACT_AQUOS_SWAP", "EXACT_AQUOS_ONLY"}:
        return sum(1 for a in attrs if a == Attribute.AQUOS) / team_n
    if eid == "EXACT_DARKUS_ONLY":
        return sum(1 for a in attrs if a == Attribute.DARKUS) / team_n
    if eid == "EXACT_DRAGONOID_DOUBLE_GATE":
        return sum(1 for b in bakus if _is_dragonoid_family_name(b)) / team_n
    if eid == "EXACT_EARTH_SHUTDOWN":
        return sum(1 for a in attrs if a in {Attribute.PYRUS, Attribute.AQUOS, Attribute.VENTUS}) / team_n
    if eid == "EXACT_POWER_FROM_DARKNESS":
        return sum(1 for a in attrs if a in {Attribute.DARKUS, Attribute.HAOS}) / team_n
    if eid == "EXACT_BRUSHFIRE":
        return sum(1 for a in attrs if a in {Attribute.PYRUS, Attribute.SUBTERRA}) / team_n
    if eid in {"EXACT_LEGENDS_OF_WIND"}:
        return min(1.0, sum(1 for a in attrs if a in {Attribute.VENTUS, Attribute.PYRUS, Attribute.DARKUS}) / team_n)
    if eid in {"EXACT_LEGENDS_OF_LIGHT"}:
        return min(1.0, sum(1 for a in attrs if a in {Attribute.HAOS, Attribute.SUBTERRA, Attribute.DARKUS}) / team_n)
    if eid == "EXACT_DOUBLE_GATE_BONUS":
        best_gate_bonus = max((g.bonuses.get(b.attribute, 0) for g in gates for b in bakus), default=0)
        return clamp(best_gate_bonus / 120.0, 0.15, 1.0)
    if eid in {"EXACT_BLUE_GREEN_COMBINE", "EXACT_RETURN_USED_ABILITY"}:
        return 0.55
    if eid in {"EXACT_ALICES_SURPRISE", "EXACT_COLORVOID"}:
        return 0.7
    if eid == "EXACT_ATTRACTOR":
        return 0.85 if len(bakus) >= 3 else 0.55
    if eid in {"EXACT_LOCKDOWN", "EXACT_DOOM_CARD", "EXACT_DO_OVER", "EXACT_LEVEL_DOWN", "ROLL_PLUS",
               "ROLL_CHOOSE_BEST", "ROLL_RECOVER", "ROLL_IGNORE_BAD_MATCH", "ROLL_BATTLE_BONUS"}:
        return 0.95
    return 0.85


def ability_ceiling_score(profile: PlayerProfile, ability: AbilityCard, active_bakus: Optional[List[Bakugan]] = None,
                          active_gates: Optional[List[GateCard]] = None, meta: Optional[Dict[str, object]] = None) -> float:
    bakus = active_bakus if active_bakus is not None else (profile.active_bakugan() or profile.collection_bakugan[:3])
    gates = active_gates if active_gates is not None else (profile.active_gates() or profile.collection_gates[:3])
    attrs = {b.attribute for b in bakus}
    max_gate_bonus = max((g.bonuses.get(b.attribute, 0) for g in gates for b in bakus), default=0)
    eid = ability.effect_id
    ceiling = 0.0

    if eid in {"EXACT_DARKUS_ONLY", "EXACT_AQUOS_ONLY"}:
        ceiling += 42
    elif eid in {"EXACT_DOUBLE_GATE_BONUS", "EXACT_DRAGONOID_DOUBLE_GATE"}:
        ceiling += 30 + max_gate_bonus * 0.18
    elif eid == "EXACT_POWER_FROM_DARKNESS":
        ceiling += 48 if Attribute.DARKUS in attrs else 26
    elif eid == "EXACT_BRUSHFIRE":
        ceiling += 38 if Attribute.PYRUS in attrs else 20
    elif eid == "EXACT_ATTRACTOR":
        ceiling += 36
    elif eid == "EXACT_ALICES_SURPRISE":
        ceiling += 34
    elif eid == "EXACT_LEVEL_DOWN":
        ceiling += 32
    elif eid == "EXACT_DOOM_CARD":
        ceiling += 30
    elif eid == "EXACT_LOCKDOWN":
        ceiling += 28
    elif eid == "EXACT_COLORVOID":
        ceiling += 26
    elif eid == "EXACT_RETURN_USED_ABILITY":
        ceiling += 20
    elif eid == "EXACT_BLUE_GREEN_COMBINE":
        ceiling += 22
    elif eid in {"EXACT_LEGENDS_OF_LIGHT", "EXACT_LEGENDS_OF_WIND", "EXACT_BIG_BRAWL", "EXACT_STANDING_ATTR_SCALING",
                 "EXACT_GATE_WON_SCALING", "EXACT_USED_ABILITY_SCALING"}:
        ceiling += 24
    else:
        tags = ability_tags(ability)
        if "raw_power" in tags:
            ceiling += 22
        if "combo" in tags:
            ceiling += 18
        if "disruption" in tags:
            ceiling += 18

    if meta is not None and meta.get("dominant_attr") in attrs:
        ceiling += 6
    return ceiling


def ability_gate_synergy_score(profile: PlayerProfile, ability: AbilityCard, active_bakus: Optional[List[Bakugan]] = None,
                               active_gates: Optional[List[GateCard]] = None, meta: Optional[Dict[str, object]] = None) -> float:
    bakus = active_bakus if active_bakus is not None else (profile.active_bakugan() or profile.collection_bakugan[:3])
    gates = active_gates if active_gates is not None else (profile.active_gates() or profile.collection_gates[:3])
    eid = ability.effect_id
    tags = ability_tags(ability)
    gtags = set()
    for gate in gates:
        gtags |= gate_tags(gate)
    max_gate_bonus = max((g.bonuses.get(b.attribute, 0) for g in gates for b in bakus), default=0)
    score = 0.0

    if eid in {"EXACT_DOUBLE_GATE_BONUS", "EXACT_DRAGONOID_DOUBLE_GATE"}:
        score += max_gate_bonus * 0.22
    if eid in {"EXACT_RETURN_USED_ABILITY", "EXACT_BLUE_GREEN_COMBINE"} and ("combo" in gtags or "resource" in gtags):
        score += 18
    if eid in {"EXACT_ATTRACTOR", "EXACT_COLOR_SWAP"} and ("swing" in gtags or "trick" in gtags):
        score += 14
    if eid in {"EXACT_LOCKDOWN", "EXACT_DOOM_CARD", "EXACT_COLORVOID"} and "disruption" in gtags:
        score += 12
    if eid == "EXACT_POWER_FROM_DARKNESS":
        score += sum(g.bonuses.get(Attribute.DARKUS, 0) for g in gates) * 0.08
    if eid == "EXACT_AQUOS_ONLY":
        score += sum(g.bonuses.get(Attribute.AQUOS, 0) for g in gates) * 0.08
    if eid == "EXACT_DARKUS_ONLY":
        score += sum(g.bonuses.get(Attribute.DARKUS, 0) for g in gates) * 0.08
    if "combo" in tags and "combo" in gtags:
        score += 8
    if meta is not None and meta.get("dominant_attr") is not None:
        score += sum(g.bonuses.get(meta["dominant_attr"], 0) for g in gates) * 0.03
    return score


def ability_is_live_for_team(profile: PlayerProfile, ability: AbilityCard, active_bakus: Optional[List[Bakugan]] = None,
                             active_gates: Optional[List[GateCard]] = None) -> bool:
    return ability_live_rate(profile, ability, active_bakus, active_gates) >= 0.20


def ability_profile_value(profile: PlayerProfile, ability: AbilityCard, active_bakus: Optional[List[Bakugan]] = None,
                          active_gates: Optional[List[GateCard]] = None, meta: Optional[Dict[str, object]] = None,
                          intelligence_override: Optional[float] = None) -> float:
    smartness = clamp(intelligence_override if intelligence_override is not None else profile.intelligence, 0.2, 0.99)
    bakus = active_bakus if active_bakus is not None else (profile.active_bakugan() or profile.collection_bakugan[:3])
    gates = active_gates if active_gates is not None else (profile.active_gates() or profile.collection_gates[:3])
    attrs = {b.attribute for b in bakus}
    text_blob = f"{ability.name} {ability.description} {ability.effect_id}".lower()

    base = 12.0
    if ability.color == AbilityColor.GREEN:
        base += 12 + 10 * smartness
    elif ability.color == AbilityColor.BLUE:
        base += 9 + profile.aggression * 7
    else:
        base += max(0.0, 0.72 - profile.rolling_skill) * 30 + 4

    if profile.chosen_attribute.value.lower() in text_blob:
        base += 8 + 7 * smartness
    attr_hits = sum(1 for a in attrs if a.value.lower() in text_blob)
    base += attr_hits * (4 + 2 * smartness)

    if any(k in text_blob for k in ['swap', 'replace', 'doom', 'shutdown', 'block', 'steal', 'double']):
        base += 4 + 5 * smartness
    if any(k in text_blob for k in ['gate', 'ability used', 'used ability', 'standing', 'battle']):
        base += 4 + 4 * smartness

    live_rate = ability_live_rate(profile, ability, bakus, gates)
    ceiling = ability_ceiling_score(profile, ability, bakus, gates, meta)
    gate_synergy = ability_gate_synergy_score(profile, ability, bakus, gates, meta)
    ctx = ability_context_scores(profile, ability, bakus, gates, meta)

    score = base + ceiling * (0.35 + 0.15 * smartness) + gate_synergy
    score += ctx["reliability"] * (0.45 + 0.20 * smartness)
    score += ctx["strategy"] * (0.35 + 0.25 * smartness)
    score += ctx["opening"] * (0.12 + 0.08 * profile.aggression)
    score += ctx["behind"] * (0.16 + 0.14 * smartness)
    score += ctx["finisher"] * (0.18 + 0.10 * profile.aggression)

    if live_rate <= 0.0:
        return -120 - 320 * smartness
    if live_rate < 0.20:
        score -= (0.20 - live_rate) * (90 + 180 * smartness)
    score += live_rate * (24 + 34 * smartness)

    if ability.effect_id == "EXACT_DARKUS_ONLY":
        score += sum(1 for b in bakus if b.attribute == Attribute.DARKUS) * (10 + 7 * smartness)
    if ability.effect_id == "EXACT_AQUOS_ONLY":
        score += sum(1 for b in bakus if b.attribute == Attribute.AQUOS) * (10 + 7 * smartness)

    if meta is not None and meta.get('dominant_attr') is not None and meta.get('dominant_attr').value.lower() in text_blob:
        score += 4 + 5 * smartness
    return score


def build_meta_snapshot(profiles: List[PlayerProfile]) -> Dict[str, object]:
    attr_counts = {a: 0 for a in Attribute}
    style_counts = {s: 0 for s in PlayerStyle}
    strong_names: List[str] = []
    for p in profiles:
        style_counts[p.style] += 1
        for b in p.active_bakugan()[:3]:
            attr_counts[b.attribute] += 1
            if b.base_g >= 430:
                strong_names.append(b.name)
    dominant_attr = max(attr_counts, key=attr_counts.get) if attr_counts else Attribute.PYRUS
    dominant_style = max(style_counts, key=style_counts.get) if style_counts else PlayerStyle.BALANCED
    return {
        "attr_counts": attr_counts,
        "style_counts": style_counts,
        "dominant_attr": dominant_attr,
        "dominant_style": dominant_style,
        "strong_names": strong_names[-40:],
    }


def choose_career_focus(profile: PlayerProfile, rng: random.Random, meta: Optional[Dict[str, object]] = None) -> str:
    weakness_order = sorted([
        (profile.rolling_skill, "Control"),
        (profile.intelligence, "Strategy"),
        (profile.aggression, "Power"),
        (1.0 - profile.risk, "Aggro"),
    ], key=lambda x: x[0])
    smartness = profile.intelligence
    if smartness < 0.45 and rng.random() < 0.55:
        return rng.choice(["Balanced", "Power", "Control", "Strategy", "Aggro", "Greed"])
    focus = weakness_order[0][1]
    if meta is not None and meta.get("dominant_attr") == profile.chosen_attribute and profile.glicko.rating > profile.peak_rating - 20:
        focus = "Control" if profile.rolling_skill < 0.85 else "Strategy"
    if profile.money < 180 and smartness > 0.7:
        focus = "Greed"
    if profile.tournament_titles == 0 and profile.tournaments_entered >= 8 and smartness > 0.6:
        focus = "Power" if profile.aggression < 0.7 else "Strategy"
    return focus


def derive_archetype_name_from_payload(payload: Dict) -> str:
    focus = str(payload.get("development_focus", "Balanced"))
    style = str(payload.get("style", PlayerStyle.BALANCED.value))
    intelligence = float(payload.get("intelligence", 0.6))
    aggression = float(payload.get("aggression", 0.5))
    risk = float(payload.get("risk", 0.5))
    if focus == "Power" or aggression >= 0.78 or style in {PlayerStyle.RECKLESS.value, PlayerStyle.AGGRESSIVE.value}:
        return PlayerArchetype.POWER_RUSH.value
    if focus == "Control" or style in {PlayerStyle.DEFENSIVE.value, PlayerStyle.PATIENT.value}:
        return PlayerArchetype.GATE_CONTROL.value
    if focus == "Strategy" or style == PlayerStyle.COMBO.value or intelligence >= 0.84:
        return PlayerArchetype.COMBO_SETUP.value
    if style == PlayerStyle.TACTICAL.value and intelligence >= 0.68 and risk <= 0.58:
        return PlayerArchetype.COUNTER.value
    if focus == "Greed" or style == PlayerStyle.OPPORTUNIST.value:
        return PlayerArchetype.HIGH_ROLL.value
    if style == PlayerStyle.ADAPTIVE.value and intelligence >= 0.72:
        return PlayerArchetype.TEMPO_PIVOT.value
    if intelligence >= 0.82 and aggression <= 0.48:
        return PlayerArchetype.RESOURCE_LOOP.value
    if intelligence >= 0.76 and risk <= 0.42:
        return PlayerArchetype.ATTRITION.value
    return PlayerArchetype.BALANCED_TEMPO.value


def derive_archetype_for_profile(profile: PlayerProfile, rng: Optional[random.Random] = None) -> PlayerArchetype:
    focus = profile.development_focus
    style = profile.style
    intelligence = profile.intelligence
    aggression = profile.aggression
    risk = profile.risk
    if focus == "Power" or aggression >= 0.78 or style in {PlayerStyle.RECKLESS, PlayerStyle.AGGRESSIVE}:
        return PlayerArchetype.POWER_RUSH
    if focus == "Control" or style in {PlayerStyle.DEFENSIVE, PlayerStyle.PATIENT}:
        return PlayerArchetype.GATE_CONTROL
    if focus == "Strategy" or style == PlayerStyle.COMBO or intelligence >= 0.84:
        return PlayerArchetype.COMBO_SETUP
    if style == PlayerStyle.TACTICAL and intelligence >= 0.68 and risk <= 0.58:
        return PlayerArchetype.COUNTER
    if focus == "Greed" or style == PlayerStyle.OPPORTUNIST:
        return PlayerArchetype.HIGH_ROLL
    if style == PlayerStyle.ADAPTIVE and intelligence >= 0.72:
        return PlayerArchetype.TEMPO_PIVOT
    if intelligence >= 0.82 and aggression <= 0.48:
        return PlayerArchetype.RESOURCE_LOOP
    if intelligence >= 0.76 and risk <= 0.42:
        return PlayerArchetype.ATTRITION
    if focus == "Aggro":
        return PlayerArchetype.POWER_RUSH
    return PlayerArchetype.BALANCED_TEMPO


def profile_archetype_weights(profile: PlayerProfile) -> Dict[str, float]:
    archetype = getattr(profile, "archetype", PlayerArchetype.BALANCED_TEMPO)
    base = {
        "bakugan_power": 1.00,
        "bakugan_attribute_fit": 1.00,
        "gate_bonus_fit": 1.00,
        "gate_effect": 1.00,
        "ability_raw_power": 1.00,
        "ability_combo": 1.00,
        "ability_disruption": 1.00,
        "synergy": 1.00,
        "coverage": 1.00,
        "economy": 1.00,
    }
    if archetype == PlayerArchetype.POWER_RUSH:
        base.update({"bakugan_power": 1.35, "bakugan_attribute_fit": 1.05, "gate_bonus_fit": 1.10, "gate_effect": 0.84, "ability_raw_power": 1.28, "ability_combo": 0.78, "ability_disruption": 0.88, "synergy": 0.92, "coverage": 0.82, "economy": 0.92})
    elif archetype == PlayerArchetype.GATE_CONTROL:
        base.update({"bakugan_power": 0.96, "bakugan_attribute_fit": 1.10, "gate_bonus_fit": 1.32, "gate_effect": 1.34, "ability_raw_power": 0.92, "ability_combo": 1.02, "ability_disruption": 1.05, "synergy": 1.22, "coverage": 1.08, "economy": 1.02})
    elif archetype == PlayerArchetype.COMBO_SETUP:
        base.update({"bakugan_power": 0.96, "bakugan_attribute_fit": 1.12, "gate_bonus_fit": 1.03, "gate_effect": 1.22, "ability_raw_power": 0.90, "ability_combo": 1.42, "ability_disruption": 1.00, "synergy": 1.32, "coverage": 1.00, "economy": 1.02})
    elif archetype == PlayerArchetype.COUNTER:
        base.update({"bakugan_power": 0.92, "bakugan_attribute_fit": 1.00, "gate_bonus_fit": 0.98, "gate_effect": 1.16, "ability_raw_power": 0.86, "ability_combo": 1.02, "ability_disruption": 1.46, "synergy": 1.10, "coverage": 1.00, "economy": 1.08})
    elif archetype == PlayerArchetype.ATTRITION:
        base.update({"bakugan_power": 0.98, "bakugan_attribute_fit": 1.06, "gate_bonus_fit": 1.10, "gate_effect": 1.20, "ability_raw_power": 0.86, "ability_combo": 0.94, "ability_disruption": 1.28, "synergy": 1.18, "coverage": 1.12, "economy": 1.10})
    elif archetype == PlayerArchetype.RESOURCE_LOOP:
        base.update({"bakugan_power": 0.90, "bakugan_attribute_fit": 1.10, "gate_bonus_fit": 1.08, "gate_effect": 1.24, "ability_raw_power": 0.84, "ability_combo": 1.24, "ability_disruption": 1.00, "synergy": 1.34, "coverage": 0.98, "economy": 1.16})
    elif archetype == PlayerArchetype.HIGH_ROLL:
        base.update({"bakugan_power": 1.10, "bakugan_attribute_fit": 0.94, "gate_bonus_fit": 1.02, "gate_effect": 0.92, "ability_raw_power": 1.18, "ability_combo": 0.92, "ability_disruption": 0.90, "synergy": 0.96, "coverage": 0.84, "economy": 0.88})
    elif archetype == PlayerArchetype.TEMPO_PIVOT:
        base.update({"bakugan_power": 1.00, "bakugan_attribute_fit": 1.08, "gate_bonus_fit": 1.14, "gate_effect": 1.10, "ability_raw_power": 0.98, "ability_combo": 1.10, "ability_disruption": 1.10, "synergy": 1.20, "coverage": 1.10, "economy": 1.02})
    return base


def ability_tags(card: AbilityCard) -> Set[str]:
    eid = card.effect_id
    tags: Set[str] = set()
    if eid in {"ROLL_PLUS", "ROLL_CHOOSE_BEST", "ROLL_RECOVER", "ROLL_IGNORE_BAD_MATCH", "ROLL_BATTLE_BONUS", "EXACT_ALICES_SURPRISE", "EXACT_BIG_BRAWL", "EXACT_BRUSHFIRE", "EXACT_POWER_FROM_DARKNESS", "EXACT_DOUBLE_GATE_BONUS", "EXACT_DRAGONOID_DOUBLE_GATE", "EXACT_GATE_WON_SCALING", "EXACT_USED_ABILITY_SCALING", "EXACT_AQUOS_ONLY", "EXACT_DARKUS_ONLY", "EXACT_STANDING_ATTR_SCALING"}:
        tags.add("raw_power")
    if eid in {"EXACT_COMBO_BATTLE", "EXACT_ATTRACTOR", "EXACT_BLUE_GREEN_COMBINE", "EXACT_AQUOS_SWAP", "EXACT_COLOR_SWAP", "EXACT_RETURN_USED_ABILITY"}:
        tags.add("combo")
    if eid in {"EXACT_CLEAN_SLATE", "EXACT_COLORVOID", "EXACT_LOCKDOWN", "EXACT_DOOM_CARD", "EXACT_DO_OVER", "EXACT_LEVEL_DOWN", "EXACT_EARTH_SHUTDOWN"}:
        tags.add("disruption")
    if eid in {"EXACT_A_HAND_UP", "EXACT_LEVEL_DOWN", "EXACT_COLOR_SWAP", "EXACT_ALICES_SURPRISE"}:
        tags.add("comeback")
    if eid in {"EXACT_DO_OVER", "EXACT_RETURN_USED_ABILITY", "ROLL_RECOVER"}:
        tags.add("resource")
    return tags


def gate_tags(card: GateCard) -> Set[str]:
    eid = card.effect_id
    tags: Set[str] = set()
    avg_bonus = sum(card.bonuses.values()) / max(1, len(card.bonuses))
    if avg_bonus >= 100:
        tags.add("raw_bonus")
    if eid in {"GATE_EXACT_RETURN_ALL_USED", "GATE_EXACT_ABILITY_USED_SCALING", "GATE_EXACT_GATE_WON_SCALING", "GATE_EXACT_DOUBLE_ABILITY_BOOSTS"}:
        tags.update({"resource", "combo"})
    if eid in {"GATE_EXACT_SWAP_ORIGINAL_G", "GATE_EXACT_DOUBLE_LOWER_ORIGINAL_G", "GATE_EXACT_SWAP_ORIGINAL_G_IF_AQUOS", "GATE_EXACT_BAKUGAN_SWAP", "GATE_EXACT_BAIT"}:
        tags.update({"swing", "trick"})
    if eid in {"GATE_EXACT_NO_ABILITIES"}:
        tags.add("disruption")
    return tags


def bakugan_profile_value(profile: PlayerProfile, bakugan: Bakugan, active_gates: Optional[List[GateCard]] = None, meta: Optional[Dict[str, object]] = None, intelligence_override: Optional[float] = None) -> float:
    smartness = clamp(intelligence_override if intelligence_override is not None else profile.intelligence, 0.2, 0.99)
    w = profile_archetype_weights(profile)
    active_gates = active_gates if active_gates is not None else (profile.active_gates() or profile.collection_gates[:3])
    meta_attr = meta.get("dominant_attr") if meta else None
    gate_fit = max((g.bonuses.get(bakugan.attribute, 0) for g in active_gates), default=0)
    score = bakugan.base_g * (1.02 + 0.18 * smartness) * w["bakugan_power"]
    if bakugan.attribute == profile.chosen_attribute:
        score += (18 + 28 * smartness) * w["bakugan_attribute_fit"]
    elif meta_attr is not None and bakugan.attribute == meta_attr:
        score += (8 + 12 * smartness) * 0.8
    score += gate_fit * (0.16 + 0.22 * smartness) * w["synergy"]
    unique_attr_bonus = len({bakugan.attribute} | {b.attribute for b in (profile.active_bakugan() or [])})
    score += unique_attr_bonus * 6 * w["coverage"]
    return score


def gate_profile_archetype_bonus(profile: PlayerProfile, gate: GateCard, active_bakus: List[Bakugan], meta: Optional[Dict[str, object]] = None, intelligence_override: Optional[float] = None) -> float:
    smartness = clamp(intelligence_override if intelligence_override is not None else profile.intelligence, 0.2, 0.99)
    w = profile_archetype_weights(profile)
    tags = gate_tags(gate)
    chosen_fit = max((gate.bonuses.get(b.attribute, 0) for b in active_bakus), default=gate.bonuses.get(profile.chosen_attribute, 0))
    score = chosen_fit * 0.35 * (0.8 + 0.5 * smartness) * w["gate_bonus_fit"]
    if "raw_bonus" in tags:
        score += 26 * w["gate_bonus_fit"]
    if "combo" in tags:
        score += 28 * w["gate_effect"]
    if "resource" in tags:
        score += 20 * w["synergy"]
    if "swing" in tags:
        score += 18 * w["gate_effect"]
    if "trick" in tags:
        score += 12 * w["gate_effect"]
    if "disruption" in tags:
        score += 18 * w["ability_disruption"]
    if meta is not None and meta.get("dominant_attr") is not None:
        score += gate.bonuses.get(meta["dominant_attr"], 0) * 0.10 * w["coverage"]
    return score


def ability_profile_archetype_bonus(profile: PlayerProfile, ability: AbilityCard, active_bakus: List[Bakugan],
                                    active_gates: Optional[List[GateCard]] = None, meta: Optional[Dict[str, object]] = None,
                                    intelligence_override: Optional[float] = None) -> float:
    smartness = clamp(intelligence_override if intelligence_override is not None else profile.intelligence, 0.2, 0.99)
    w = profile_archetype_weights(profile)
    tags = ability_tags(ability)
    live_rate = ability_live_rate(profile, ability, active_bakus, active_gates)
    gate_synergy = ability_gate_synergy_score(profile, ability, active_bakus, active_gates, meta)
    score = 0.0
    if "raw_power" in tags:
        score += (24 + 14 * smartness) * w["ability_raw_power"]
    if "combo" in tags:
        score += (20 + 18 * smartness) * w["ability_combo"]
    if "disruption" in tags:
        score += (20 + 16 * smartness) * w["ability_disruption"]
    if "comeback" in tags:
        score += 10 + 8 * smartness
    if "resource" in tags:
        score += 8 + 8 * smartness
    text_blob = f"{ability.name} {ability.description} {ability.effect_id}".lower()
    attr_hits = sum(1 for b in active_bakus if b.attribute.value.lower() in text_blob)
    score += attr_hits * 5 * w["synergy"]
    score += gate_synergy * 0.35
    score += live_rate * (8 + 16 * smartness)
    if profile.style == PlayerStyle.COMBO and "combo" in tags:
        score += 14
    if profile.style == PlayerStyle.DEFENSIVE and "disruption" in tags:
        score += 12
    if profile.style == PlayerStyle.RECKLESS and "raw_power" in tags:
        score += 10
    if profile.style == PlayerStyle.AGGRESSIVE and "raw_power" in tags:
        score += 10
    if profile.style == PlayerStyle.PATIENT and ("resource" in tags or "comeback" in tags):
        score += 10
    if profile.style == PlayerStyle.ADAPTIVE:
        score += 6
    if profile.style == PlayerStyle.OPPORTUNIST and ("disruption" in tags or "comeback" in tags):
        score += 10
    return score


def shop_category_weights(profile: PlayerProfile) -> Dict[str, float]:
    base = {"baku": 1.0, "gate": 1.0, "ability": 1.0, "loot": 0.8}
    archetype = getattr(profile, "archetype", PlayerArchetype.BALANCED_TEMPO)
    if archetype == PlayerArchetype.POWER_RUSH:
        base["baku"] += 0.50
        base["ability"] += 0.20
    elif archetype == PlayerArchetype.GATE_CONTROL:
        base["gate"] += 0.60
        base["ability"] += 0.15
    elif archetype == PlayerArchetype.COMBO_SETUP:
        base["ability"] += 0.55
        base["gate"] += 0.20
    elif archetype == PlayerArchetype.COUNTER:
        base["ability"] += 0.45
        base["gate"] += 0.22
    elif archetype == PlayerArchetype.ATTRITION:
        base["gate"] += 0.35
        base["ability"] += 0.25
    elif archetype == PlayerArchetype.RESOURCE_LOOP:
        base["ability"] += 0.55
        base["loot"] += 0.10
    elif archetype == PlayerArchetype.HIGH_ROLL:
        base["baku"] += 0.30
        base["loot"] += 0.25
    elif archetype == PlayerArchetype.TEMPO_PIVOT:
        base["baku"] += 0.20
        base["gate"] += 0.20
        base["ability"] += 0.20
    return base


def choose_weighted_category(rng: random.Random, categories: List[Tuple[float, str]]) -> str:
    total = sum(max(0.01, w) for w, _ in categories)
    roll = rng.random() * total
    running = 0.0
    pick = categories[0][1]
    for weight, category in categories:
        running += max(0.01, weight)
        if running >= roll:
            pick = category
            break
    return pick



def optimise_profile_loadout(profile: PlayerProfile, meta: Optional[Dict[str, object]] = None, rng: Optional[random.Random] = None) -> None:
    rng = rng or random.Random()
    smartness = clamp(profile.intelligence, 0.2, 0.99)
    if not getattr(profile, "archetype", None):
        profile.archetype = derive_archetype_for_profile(profile, rng)

    def baku_score_idx(idx: int) -> float:
        b = profile.collection_bakugan[idx]
        score = bakugan_profile_value(profile, b, meta=meta, intelligence_override=smartness)
        score += rng.uniform(-24, 24) * (1.0 - smartness)
        return score

    baku_ranked = sorted(range(len(profile.collection_bakugan)), key=baku_score_idx, reverse=True)
    baku_pool = baku_ranked[:min(len(baku_ranked), 8)]
    baku_combos = list(combinations(baku_pool, 3)) if len(baku_pool) >= 3 else []
    if not baku_combos and len(baku_ranked) >= 3:
        baku_combos = [tuple(baku_ranked[:3])]

    def baku_triplet_score(combo: Tuple[int, int, int]) -> float:
        team = [profile.collection_bakugan[i] for i in combo]
        w = profile_archetype_weights(profile)
        raw = sum(b.base_g for b in team) * w["bakugan_power"]
        chosen_attr_count = sum(1 for b in team if b.attribute == profile.chosen_attribute)
        unique_attrs = len({b.attribute for b in team})
        score = raw
        score += chosen_attr_count * (24 + 26 * smartness) * w["bakugan_attribute_fit"]
        score += unique_attrs * 18 * w["coverage"]
        gate_synergy = 0.0
        named_gate_hits = 0
        for b in team:
            gate_synergy += max((g.bonuses.get(b.attribute, 0) for g in profile.collection_gates), default=0)
            named_gate_hits += sum(1 for g in profile.collection_gates if _gate_targets_bakugan_name(g, b))
        score += gate_synergy * 0.18 * w["synergy"]
        score += named_gate_hits * (10 + 10 * smartness)
        sorted_g = sorted((b.base_g for b in team), reverse=True)
        if len(sorted_g) == 3:
            score += sorted_g[0] * 0.08 + sorted_g[1] * 0.05 + min(sorted_g[2], 560) * 0.03
            if sorted_g[0] - sorted_g[2] > 220:
                score -= 12 * smartness
        family_counts = {}
        for b in team:
            key = normalize_named_bakugan_token(b.name)
            family_counts[key] = family_counts.get(key, 0) + 1
        score -= sum((count - 1) * (18 + 20 * smartness) for count in family_counts.values() if count > 1)
        if profile.archetype == PlayerArchetype.POWER_RUSH:
            score += max(b.base_g for b in team) * 0.45
        elif profile.archetype == PlayerArchetype.BALANCED_TEMPO:
            score += unique_attrs * 10
        elif profile.archetype == PlayerArchetype.COMBO_SETUP:
            score += sum(1 for b in team if b.base_g <= 410) * 10
        elif profile.archetype == PlayerArchetype.GATE_CONTROL:
            score += named_gate_hits * 8
        score += rng.uniform(-18, 18) * (1.0 - smartness)
        return score

    chosen_baku = list(max(baku_combos, key=baku_triplet_score)) if baku_combos else list(baku_ranked[:3])
    active_bakus = [profile.collection_bakugan[i] for i in chosen_baku]

    def top_by_type(gate_type: GateType, limit: int = 6) -> List[int]:
        typed = [i for i, g in enumerate(profile.collection_gates) if g.gate_type == gate_type]
        typed.sort(
            key=lambda i: gate_profile_value(profile, profile.collection_gates[i], active_bakus=active_bakus, meta=meta, intelligence_override=smartness)
            + gate_profile_archetype_bonus(profile, profile.collection_gates[i], active_bakus, meta=meta, intelligence_override=smartness),
            reverse=True,
        )
        return typed[:min(limit, len(typed))]

    gold_sorted = top_by_type(GateType.GOLD)
    silver_sorted = top_by_type(GateType.SILVER)
    bronze_sorted = top_by_type(GateType.BRONZE)
    gate_combos = [(g, s, b) for g in gold_sorted for s in silver_sorted for b in bronze_sorted]

    def gate_triplet_score(combo: Tuple[int, int, int]) -> float:
        chosen = [profile.collection_gates[i] for i in combo]
        score = 0.0
        seen_tags: Set[str] = set()
        for gate in chosen:
            score += gate_profile_value(profile, gate, active_bakus=active_bakus, meta=meta, intelligence_override=smartness)
            score += gate_profile_archetype_bonus(profile, gate, active_bakus, meta=meta, intelligence_override=smartness)
            seen_tags |= gate_tags(gate)
        score += len(seen_tags) * 8 * profile_archetype_weights(profile)["coverage"]
        score += rng.uniform(-12, 12) * (1.0 - smartness)
        return score

    chosen_gates = list(max(gate_combos, key=gate_triplet_score)) if gate_combos else [lst[0] for lst in [gold_sorted, silver_sorted, bronze_sorted] if lst][:3]
    active_gates = [profile.collection_gates[i] for i in chosen_gates]

    def top_by_color(color: AbilityColor, limit: int = 8) -> List[int]:
        typed = [i for i, a in enumerate(profile.collection_abilities) if a.color == color]
        if smartness >= 0.72:
            live_typed = [i for i in typed if ability_live_rate(profile, profile.collection_abilities[i], active_bakus, active_gates) >= 0.20]
            if live_typed:
                typed = live_typed
        typed.sort(
            key=lambda i: ability_profile_value(
                profile, profile.collection_abilities[i], active_bakus=active_bakus, active_gates=active_gates, meta=meta, intelligence_override=smartness
            ) + ability_profile_archetype_bonus(
                profile, profile.collection_abilities[i], active_bakus, active_gates=active_gates, meta=meta, intelligence_override=smartness
            ) + 0.20 * sum(ability_context_scores(profile, profile.collection_abilities[i], active_bakus, active_gates, meta).values()),
            reverse=True,
        )
        return typed[:min(limit, len(typed))]

    red_sorted = top_by_color(AbilityColor.RED)
    blue_sorted = top_by_color(AbilityColor.BLUE)
    green_sorted = top_by_color(AbilityColor.GREEN)
    ability_combos = [(r, b, g) for r in red_sorted for b in blue_sorted for g in green_sorted]
    w = profile_archetype_weights(profile)

    def ability_triplet_score(combo: Tuple[int, int, int]) -> float:
        chosen = [profile.collection_abilities[i] for i in combo]
        score = 0.0
        seen_tags: Set[str] = set()
        live_rates: List[float] = []
        role_counts = {"raw_power": 0, "combo": 0, "disruption": 0, "comeback": 0, "resource": 0}
        ctx_totals = {"opening": 0.0, "behind": 0.0, "finisher": 0.0, "reliability": 0.0, "strategy": 0.0}
        for ability in chosen:
            live_rate = ability_live_rate(profile, ability, active_bakus, active_gates)
            ceiling = ability_ceiling_score(profile, ability, active_bakus, active_gates, meta)
            gate_synergy = ability_gate_synergy_score(profile, ability, active_bakus, active_gates, meta)
            base = ability_profile_value(profile, ability, active_bakus=active_bakus, active_gates=active_gates, meta=meta, intelligence_override=smartness)
            arch = ability_profile_archetype_bonus(profile, ability, active_bakus, active_gates=active_gates, meta=meta, intelligence_override=smartness)
            ctx = ability_context_scores(profile, ability, active_bakus, active_gates, meta)
            score += base + arch
            score += live_rate * (18 + 24 * smartness)
            score += ceiling * 0.18
            score += gate_synergy * 0.45
            live_rates.append(live_rate)
            tags = ability_tags(ability)
            seen_tags |= tags
            for tag in role_counts:
                if tag in tags:
                    role_counts[tag] += 1
            for key in ctx_totals:
                ctx_totals[key] += ctx[key]

        avg_live = sum(live_rates) / max(1, len(live_rates))
        min_live = min(live_rates) if live_rates else 0.0
        score += avg_live * (25 + 40 * smartness)
        score += min_live * (8 + 25 * smartness)
        score += len(seen_tags) * 8 * w["coverage"]
        if role_counts["raw_power"] > 0:
            score += 10 * w["ability_raw_power"]
        if role_counts["disruption"] > 0:
            score += 10 * w["ability_disruption"]
        if role_counts["combo"] > 0:
            score += 10 * w["ability_combo"]
        if sum(1 for k in ("raw_power", "disruption", "combo") if role_counts[k] > 0) >= 2:
            score += 14 * w["coverage"]

        needs = ability_role_need(profile, chosen)
        score += ctx_totals["opening"] * 0.25 * needs["opening"]
        score += ctx_totals["behind"] * 0.30 * needs["behind"]
        score += ctx_totals["finisher"] * 0.22 * needs["finisher"]
        score += ctx_totals["reliability"] * 0.20 * needs["reliability"]
        score += ctx_totals["strategy"] * (0.20 + 0.18 * smartness) * needs["strategy"]

        dead_count = sum(1 for lr in live_rates if lr < 0.20)
        if dead_count:
            score -= dead_count * (40 + 120 * smartness)
        if min_live <= 0.0:
            score -= 120 + 220 * smartness

        gate_text = " ".join(g.effect_id for g in active_gates)
        if profile.archetype == PlayerArchetype.COMBO_SETUP and ("ABILITY_USED_SCALING" in gate_text or "DOUBLE_ABILITY_BOOSTS" in gate_text):
            score += 18
        if profile.archetype == PlayerArchetype.COUNTER and role_counts["disruption"] == 0:
            score -= 14
        if profile.archetype == PlayerArchetype.POWER_RUSH and role_counts["raw_power"] == 0:
            score -= 12
        score += rng.uniform(-8, 8) * (1.0 - smartness)
        return score

    chosen_abilities = list(max(ability_combos, key=ability_triplet_score)) if ability_combos else [lst[0] for lst in [red_sorted, blue_sorted, green_sorted] if lst][:3]

    # Post-selection sanity pass: replace dead abilities with the best live same-colour option.
    chosen_set = set(chosen_abilities)
    for pos, idx in enumerate(list(chosen_abilities)):
        ability = profile.collection_abilities[idx]
        if ability_is_live_for_team(profile, ability, active_bakus, active_gates):
            continue
        same_colour = [
            i for i, a in enumerate(profile.collection_abilities)
            if a.color == ability.color and (i == idx or i not in chosen_set)
        ]
        same_colour.sort(
            key=lambda i: ability_profile_value(
                profile, profile.collection_abilities[i], active_bakus=active_bakus, active_gates=active_gates, meta=meta, intelligence_override=smartness
            ) + ability_profile_archetype_bonus(
                profile, profile.collection_abilities[i], active_bakus, active_gates=active_gates, meta=meta, intelligence_override=smartness
            ),
            reverse=True,
        )
        for cand in same_colour:
            if ability_is_live_for_team(profile, profile.collection_abilities[cand], active_bakus, active_gates):
                chosen_set.discard(idx)
                chosen_abilities[pos] = cand
                chosen_set.add(cand)
                break

    profile.active_bakugan_idx = chosen_baku[:3]
    profile.active_gate_idx = chosen_gates[:3]
    profile.active_ability_idx = chosen_abilities[:3]
    profile.ensure_valid_loadout()
    profile.update_signature()



def profile_has_minimum_legal_loadout(profile: PlayerProfile) -> bool:
    profile.ensure_valid_loadout()
    baku_ok, _ = validate_bakugan_selection(profile.active_bakugan_idx, profile.collection_bakugan)
    gate_ok, _ = validate_gate_selection(profile.active_gate_idx, profile.collection_gates)
    ability_ok, _ = validate_ability_selection(profile.active_ability_idx, profile.collection_abilities)
    return baku_ok and gate_ok and ability_ok


def enforce_minimum_tournament_eligibility(profile: PlayerProfile, rng: random.Random, templates: List[BakuganTemplate], gates: List[GateCard], abilities: List[AbilityCard], max_attempts: int = 40, season_bans: Optional[Dict[str, object]] = None) -> bool:
    """Ensure a profile can legally enter a tournament with 3 Bakugan, 1 gold/silver/bronze gate, and 1 red/blue/green ability."""
    def baku_key(b: Bakugan) -> Tuple[str, Attribute]:
        return (b.name, b.attribute)

    profile.ensure_valid_loadout()

    for _ in range(max_attempts):
        # Guarantee at least 3 distinct exact Bakugan in collection
        distinct = {baku_key(b) for b in profile.collection_bakugan}
        while len(distinct) < 3:
            t = rng.choice(templates)
            cand = t.roll_instance(profile.name, rng)
            key = baku_key(cand)
            if key in distinct:
                continue
            profile.collection_bakugan.append(cand)
            distinct.add(key)

        # Guarantee one of each gate type in collection
        gate_types = {g.gate_type for g in profile.collection_gates}
        for needed in (GateType.GOLD, GateType.SILVER, GateType.BRONZE):
            if needed not in gate_types:
                choices = [g for g in gates if g.gate_type == needed]
                if choices:
                    profile.collection_gates.append(clone_gate(rng.choice(choices)))
                    gate_types.add(needed)

        # Guarantee one of each ability colour in collection
        colors = {a.color for a in profile.collection_abilities}
        for needed in (AbilityColor.RED, AbilityColor.BLUE, AbilityColor.GREEN):
            if needed not in colors:
                choices = [a for a in abilities if a.color == needed]
                if choices:
                    profile.collection_abilities.append(clone_ability(rng.choice(choices)))
                    colors.add(needed)

        optimise_profile_loadout_with_bans(profile, season_bans)
        profile.ensure_valid_loadout()
        if profile_has_minimum_legal_loadout(profile) and not profile_uses_banned_active(profile, season_bans):
            return True

        # Last resort: hard reset active loadout from first legal non-banned unique pieces
        if apply_ban_safe_fallback_loadout(profile, season_bans):
            return True

    return False


def apply_training(profile: PlayerProfile, rng: random.Random, intensity: float = 1.0) -> None:
    points = profile.training_points
    if points <= 0:
        return
    steps = min(points, max(1, int(2 * intensity + points // 4)))
    for _ in range(steps):
        bump = 0.01
        focus = profile.development_focus
        if focus == "Power":
            profile.aggression = clamp(round(profile.aggression + bump * rng.uniform(0.4, 1.0), 2), 0.2, 0.99)
            profile.risk = clamp(round(profile.risk + bump * rng.uniform(0.2, 0.8), 2), 0.2, 0.99)
        elif focus == "Control":
            profile.rolling_skill = clamp(round(profile.rolling_skill + bump * rng.uniform(0.4, 1.0), 2), 0.3, 0.99)
        elif focus == "Strategy":
            profile.intelligence = clamp(round(profile.intelligence + bump * rng.uniform(0.4, 1.0), 2), 0.3, 0.99)
        elif focus == "Aggro":
            profile.aggression = clamp(round(profile.aggression + bump * rng.uniform(0.5, 1.0), 2), 0.2, 0.99)
            profile.rolling_skill = clamp(round(profile.rolling_skill + bump * rng.uniform(0.1, 0.5), 2), 0.3, 0.99)
        elif focus == "Greed":
            profile.intelligence = clamp(round(profile.intelligence + bump * rng.uniform(0.2, 0.6), 2), 0.3, 0.99)
            profile.risk = clamp(round(profile.risk + bump * rng.uniform(0.2, 0.6), 2), 0.2, 0.99)
        else:
            stat = rng.choice(["rolling_skill", "intelligence", "aggression", "risk"])
            setattr(profile, stat, clamp(round(getattr(profile, stat) + bump, 2), 0.2, 0.99))
    profile.training_points = max(0, profile.training_points - steps)


def trim_profile_collections(profile: PlayerProfile, rng: random.Random, meta: Optional[Dict[str, object]] = None) -> None:
    if len(profile.collection_bakugan) > MAX_COLLECTION_BAKUGAN:
        scored = sorted(profile.collection_bakugan, key=lambda b: (b.attribute == profile.chosen_attribute, b.base_g), reverse=True)[:MAX_COLLECTION_BAKUGAN]
        profile.collection_bakugan = [Bakugan(b.name, b.attribute, b.base_g, b.price, profile.name, False) for b in scored]
    if len(profile.collection_gates) > MAX_COLLECTION_GATES:
        def gscore(g):
            return g.bonuses.get(profile.chosen_attribute, 0) + sum(g.bonuses.values()) * 0.2
        chosen = []
        for gt in [GateType.GOLD, GateType.SILVER, GateType.BRONZE]:
            options = [g for g in profile.collection_gates if g.gate_type == gt]
            if options:
                chosen.append(max(options, key=gscore))
        remainder = [g for g in sorted(profile.collection_gates, key=gscore, reverse=True) if g not in chosen]
        keep = (chosen + remainder)[:MAX_COLLECTION_GATES]
        profile.collection_gates = [clone_gate(g) for g in keep]
    if len(profile.collection_abilities) > MAX_COLLECTION_ABILITIES:
        def ascore(a):
            base = 4 if a.color == AbilityColor.GREEN else 3 if a.color == AbilityColor.BLUE else 2
            return base
        chosen = []
        for c in [AbilityColor.RED, AbilityColor.BLUE, AbilityColor.GREEN]:
            options = [a for a in profile.collection_abilities if a.color == c]
            if options:
                chosen.append(max(options, key=ascore))
        remainder = [a for a in sorted(profile.collection_abilities, key=ascore, reverse=True) if a not in chosen]
        keep = (chosen + remainder)[:MAX_COLLECTION_ABILITIES]
        profile.collection_abilities = [clone_ability(a) for a in keep]
    profile.ensure_valid_loadout()




def consume_stock_bucket(stock: Dict[str, object], category: str, code: str, qty: int = 1) -> bool:
    bucket = stock.setdefault(category, {})
    if bucket.get(code, 0) < qty:
        return False
    bucket[code] -= qty
    return True



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

def npc_market_progression(profile: PlayerProfile, rng: random.Random, templates: List[BakuganTemplate], gates: List[GateCard], abilities: List[AbilityCard], meta: Optional[Dict[str, object]] = None, stock_context: Optional[Dict[str, Dict[str, int]]] = None, debug_cb=None) -> None:
    trim_profile_collections(profile, rng, meta=meta)
    before_loadout = (tuple(profile.active_bakugan_idx), tuple(profile.active_gate_idx), tuple(profile.active_ability_idx))
    optimise_profile_loadout(profile, meta=meta, rng=rng)
    smartness = clamp(profile.intelligence, 0.2, 0.99)
    reserve_ratio = 0.10 + smartness * 0.22 + (0.12 if profile.glicko.rating > 1650 else 0.0) - profile.risk * 0.10
    if profile.money < 250 and smartness > 0.7:
        reserve_ratio += 0.12
    reserve = max(80, int(profile.money * clamp(reserve_ratio, 0.05, 0.45)))
    spendable = max(0, profile.money - reserve)
    if spendable < 100:
        return

    baku_count = len(profile.collection_bakugan)
    gate_types_owned = {g.gate_type for g in profile.collection_gates}
    ability_colors_owned = {a.color for a in profile.collection_abilities}
    need_baku = baku_count < 5
    need_gate_type = len(gate_types_owned) < 3
    need_ability_color = len(ability_colors_owned) < 3
    purchase_attempts = 1 + (1 if profile.career_stage in {"Veteran", "Contender"} else 0) + (1 if profile.career_stage in {"Star", "Champion"} else 0)
    if smartness > 0.82:
        purchase_attempts += 1

    meta_attr = meta.get("dominant_attr") if meta else None

    def baku_value(t: BakuganTemplate) -> float:
        attr = profile.chosen_attribute if profile.chosen_attribute in t.allowed_attributes else (meta_attr if meta_attr in t.allowed_attributes else t.allowed_attributes[0])
        sample = Bakugan(t.name, attr, max(t.g_powers), t.price, profile.name, False)
        value = bakugan_profile_value(profile, sample, active_gates=profile.active_gates() or profile.collection_gates[:3], meta=meta, intelligence_override=smartness)
        value += loadout_upgrade_delta(profile, sample, "baku", meta) * (0.85 + 0.50 * smartness)
        value -= bakugan_shop_price(t) * (0.24 + 0.18 * smartness) / max(0.75, profile_archetype_weights(profile)["economy"])
        return value

    def gate_value(g: GateCard) -> float:
        active_bakus = profile.active_bakugan() or profile.collection_bakugan[:3]
        value = gate_profile_value(profile, g, active_bakus=active_bakus, meta=meta, intelligence_override=smartness)
        value += gate_profile_archetype_bonus(profile, g, active_bakus, meta=meta, intelligence_override=smartness)
        value += loadout_upgrade_delta(profile, g, "gate", meta) * (0.80 + 0.45 * smartness)
        value -= card_shop_price(g) * (0.18 + 0.12 * smartness) / max(0.75, profile_archetype_weights(profile)["economy"])
        return value

    def ability_value(a: AbilityCard) -> float:
        active_bakus = profile.active_bakugan() or profile.collection_bakugan[:3]
        active_gates = profile.active_gates() or profile.collection_gates[:3]
        value = ability_profile_value(profile, a, active_bakus=active_bakus, active_gates=active_gates, meta=meta, intelligence_override=smartness)
        value += ability_profile_archetype_bonus(profile, a, active_bakus, active_gates=active_gates, meta=meta, intelligence_override=smartness)
        value += loadout_upgrade_delta(profile, a, "ability", meta) * (0.90 + 0.55 * smartness)
        if smartness >= 0.75 and not ability_is_live_for_team(profile, a, active_bakus, active_gates):
            value -= 80 + 90 * smartness
        value -= card_shop_price(a) * (0.18 + 0.12 * smartness) / max(0.75, profile_archetype_weights(profile)["economy"])
        return value

    def npc_bakugan_rarity(template: BakuganTemplate) -> str:
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

    def npc_card_rarity(card) -> str:
        price = getattr(card, 'price', 100)
        if price >= 160:
            return "Legendary"
        if price >= 130:
            return "Epic"
        if price >= 105:
            return "Rare"
        return "Common"

    for _ in range(purchase_attempts):
        spendable = max(0, profile.money - reserve)
        if spendable < 100:
            break

        loot_bucket = (stock_context or {}).get("loot_boxes_npc", {}) if stock_context is not None else {}
        allowed_bakugan = set((stock_context or {}).get("bakugan_selection", [])) if stock_context is not None else None
        allowed_gates = set((stock_context or {}).get("gate_selection", [])) if stock_context is not None else None
        allowed_abilities = set((stock_context or {}).get("ability_selection", [])) if stock_context is not None else None
        loot_options = []
        if spendable >= 150 and loot_bucket.get("L0", 0) > 0:
            loot_options.append(("L0", 150, 0.6))
        if spendable >= 220 and loot_bucket.get("L1", 0) > 0:
            loot_options.append(("L1", 220, 1.0 if smartness < 0.8 else 0.45))
        if spendable >= 320 and loot_bucket.get("L2", 0) > 0:
            loot_options.append(("L2", 320, 0.8 if profile.risk > 0.65 else 0.25))

        archetype_bias = shop_category_weights(profile)
        categories: List[Tuple[float, str]] = []
        categories.append((((3.0 if need_baku else 1.2) * archetype_bias["baku"]), "baku"))
        categories.append((((2.6 if need_gate_type else 1.0) * archetype_bias["gate"]), "gate"))
        categories.append((((2.6 if need_ability_color else 1.0) * archetype_bias["ability"]), "ability"))
        if loot_options:
            categories.append((((0.9 if smartness > 0.75 else 1.4) * archetype_bias["loot"]), "loot"))
        pick = choose_weighted_category(rng, sorted(categories, reverse=True)) if smartness > 0.58 else rng.choice([c for _, c in categories])

        if pick == "baku":
            affordable = [t for t in templates if t.price <= spendable and (allowed_bakugan is None or template_stock_key(t) in allowed_bakugan) and (stock_context is None or stock_context.get("bakugan_npc", {}).get(template_stock_key(t), 0) > 0)]
            if not affordable:
                continue
            ranked = sorted(affordable, key=baku_value, reverse=True)
            window = max(1, 5 - int(smartness * 3))
            cand = ranked[rng.randint(0, min(len(ranked)-1, window-1))]
            forced = None
            if profile.chosen_attribute in cand.allowed_attributes and (smartness > 0.6 or rng.random() < 0.65):
                forced = profile.chosen_attribute
            elif meta_attr in cand.allowed_attributes and smartness > 0.82:
                forced = meta_attr
            bought_b = cand.roll_instance(profile.name, rng, forced)
            profile.collection_bakugan.append(bought_b)
            purchase_price = bakugan_shop_price(cand)
            profile.money -= purchase_price
            if stock_context is not None:
                consume_stock_bucket(stock_context, "bakugan_npc", template_stock_key(cand), 1)
            if debug_cb is not None:
                remaining = stock_context.get("bakugan_npc", {}).get(template_stock_key(cand), 0) if stock_context is not None else "?"
                debug_cb(f"NPC market: {profile.name} bought Bakugan {bought_b.name} ({bought_b.attribute.value}, {bought_b.base_g} G) for £{purchase_price} | Stock left {remaining}")
            need_baku = len(profile.collection_bakugan) < 5

        elif pick == "loot":
            if not loot_options:
                continue
            weighted = []
            for code, price, weight in loot_options:
                weighted.extend([code] * max(1, int(weight * 10)))
            chosen_code = rng.choice(weighted)
            chosen_price = 150 if chosen_code == "L0" else 220 if chosen_code == "L1" else 320
            baku_tiers = {"L0": {"Common": 82, "Rare": 16, "Epic": 2, "Legendary": 0}, "L1": {"Common": 45, "Rare": 38, "Epic": 15, "Legendary": 2}, "L2": {"Common": 18, "Rare": 35, "Epic": 32, "Legendary": 15}}[chosen_code]
            card_tiers = {"L0": {"Common": 78, "Rare": 18, "Epic": 4, "Legendary": 0}, "L1": {"Common": 40, "Rare": 38, "Epic": 18, "Legendary": 4}, "L2": {"Common": 15, "Rare": 30, "Epic": 35, "Legendary": 20}}[chosen_code]

            def weighted_pick_by_rarity(items, rarity_fn, weights):
                pool = []
                for item in items:
                    w = weights.get(rarity_fn(item), 0)
                    if w > 0:
                        pool.extend([item] * w)
                return rng.choice(pool) if pool else None

            chosen_template = weighted_pick_by_rarity(templates, npc_bakugan_rarity, baku_tiers)
            if chosen_template is None:
                continue
            forced = profile.chosen_attribute if profile.chosen_attribute in chosen_template.allowed_attributes and (smartness > 0.6 or rng.random() < 0.65) else None
            bought_b = chosen_template.roll_instance(profile.name, rng, forced)
            profile.collection_bakugan.append(bought_b)

            card_pool = gates + abilities
            chosen_card = weighted_pick_by_rarity(card_pool, npc_card_rarity, card_tiers)
            if isinstance(chosen_card, GateCard):
                profile.collection_gates.append(clone_gate(chosen_card))
                card_desc = f"Gate Card {chosen_card.name} [{chosen_card.gate_type.value}]"
            elif isinstance(chosen_card, AbilityCard):
                profile.collection_abilities.append(clone_ability(chosen_card))
                card_desc = f"Ability Card {chosen_card.name} [{chosen_card.color.value}]"
            else:
                card_desc = "No bonus card"
            profile.money -= chosen_price
            if stock_context is not None:
                consume_stock_bucket(stock_context, "loot_boxes_npc", chosen_code, 1)
            if debug_cb is not None:
                remaining = stock_context.get("loot_boxes_npc", {}).get(chosen_code, 0) if stock_context is not None else "?"
                debug_cb(f"NPC market: {profile.name} opened {chosen_code} loot box and got {bought_b.name} ({bought_b.attribute.value}, {bought_b.base_g} G) plus {card_desc} for £{chosen_price} | Stock left {remaining}")
            need_baku = len(profile.collection_bakugan) < 5
            gate_types_owned = {g.gate_type for g in profile.collection_gates}
            ability_colors_owned = {a.color for a in profile.collection_abilities}
            need_gate_type = len(gate_types_owned) < 3
            need_ability_color = len(ability_colors_owned) < 3

        elif pick == "gate":
            affordable = [clone_gate(g) for g in gates if g.price <= spendable and (allowed_gates is None or gate_stock_key(g) in allowed_gates) and (stock_context is None or stock_context.get("gates_npc", {}).get(gate_stock_key(g), 0) > 0)]
            if not affordable:
                continue
            missing_types = [gt for gt in GateType if gt not in {g.gate_type for g in profile.collection_gates}]
            if missing_types and smartness > 0.6:
                affordable = [g for g in affordable if g.gate_type in missing_types] or affordable
            ranked = sorted(affordable, key=gate_value, reverse=True)
            window = max(1, 6 - int(smartness * 4))
            cand = ranked[rng.randint(0, min(len(ranked)-1, window-1))]
            profile.collection_gates.append(cand)
            purchase_price = card_shop_price(cand)
            profile.money -= purchase_price
            if stock_context is not None:
                consume_stock_bucket(stock_context, "gates_npc", gate_stock_key(cand), 1)
            if debug_cb is not None:
                remaining = stock_context.get("gates_npc", {}).get(gate_stock_key(cand), 0) if stock_context is not None else "?"
                debug_cb(f"NPC market: {profile.name} bought Gate Card {cand.name} [{cand.gate_type.value}] for £{purchase_price} | Stock left {remaining}")
            need_gate_type = len({g.gate_type for g in profile.collection_gates}) < 3

        else:
            affordable = [clone_ability(a) for a in abilities if a.price <= spendable and (allowed_abilities is None or ability_stock_key(a) in allowed_abilities) and (stock_context is None or stock_context.get("abilities_npc", {}).get(ability_stock_key(a), 0) > 0)]
            if not affordable:
                continue
            missing_colors = [c for c in AbilityColor if c not in {a.color for a in profile.collection_abilities}]
            if missing_colors and smartness > 0.6:
                affordable = [a for a in affordable if a.color in missing_colors] or affordable
            ranked = sorted(affordable, key=ability_value, reverse=True)
            window = max(1, 7 - int(smartness * 5))
            cand = ranked[rng.randint(0, min(len(ranked)-1, window-1))]
            profile.collection_abilities.append(cand)
            purchase_price = card_shop_price(cand)
            profile.money -= purchase_price
            if stock_context is not None:
                consume_stock_bucket(stock_context, "abilities_npc", ability_stock_key(cand), 1)
            if debug_cb is not None:
                remaining = stock_context.get("abilities_npc", {}).get(ability_stock_key(cand), 0) if stock_context is not None else "?"
                debug_cb(f"NPC market: {profile.name} bought Ability Card {cand.name} [{cand.color.value}] for £{purchase_price} | Stock left {remaining}")
            need_ability_color = len({a.color for a in profile.collection_abilities}) < 3

    trim_profile_collections(profile, rng, meta=meta)
    before_loadout = (tuple(profile.active_bakugan_idx), tuple(profile.active_gate_idx), tuple(profile.active_ability_idx))
    optimise_profile_loadout(profile, meta=meta, rng=rng)


def tournament_payout_table(finish: int, participant_count: int, tournament_type: TournamentType) -> int:
    base = 90 if tournament_type == TournamentType.SWISS else 110
    if finish == 1:
        return base * participant_count // 2 + 250
    if finish == 2:
        return base * participant_count // 3 + 140
    if finish <= 3:
        return base * participant_count // 5 + 80
    if finish <= 8:
        return base * participant_count // 8 + 50
    if finish <= max(8, participant_count // 2):
        return 70
    return 30


def apply_tournament_career_update(profile: PlayerProfile, finish: int, participant_count: int, tournament_type: TournamentType, rng: random.Random, payout: Optional[int] = None) -> int:
    payout = payout if payout is not None else tournament_payout_table(finish, participant_count, tournament_type)
    sponsor_bonus = max(0, profile.sponsorship) * 10
    total_payout = payout + sponsor_bonus

    previous_stage = profile.career_stage
    previous_peak = profile.peak_rating

    profile.tournaments_entered += 1
    profile.career_earnings += total_payout
    profile.money += total_payout
    profile.peak_rating = max(profile.peak_rating, profile.glicko.rating)
    profile.fame += max(1, participant_count // max(1, finish))
    profile.training_points += 2

    if finish <= min(8, participant_count):
        profile.top8s += 1
        profile.training_points += 1
    if finish <= min(3, participant_count):
        profile.podiums += 1
        profile.fame += 4
        profile.training_points += 2
    if finish <= 2:
        profile.finals += 1
        profile.fame += 6
        profile.sponsorship += 1
    if finish == 1:
        profile.tournament_titles += 1
        profile.fame += 10
        profile.training_points += 3

    if rng.random() < 0.15:
        profile.development_focus = rng.choice(["Balanced", "Power", "Control", "Strategy", "Aggro", "Greed"])

    profile.tournament_history.append({
        "finish": finish,
        "participants": participant_count,
        "type": tournament_type.value,
        "rating": round(profile.glicko.rating, 1),
        "money": profile.money,
        "payout": total_payout,
        "peak_improved": profile.peak_rating > previous_peak,
        "title_won": finish == 1,
    })
    profile.tournament_history = profile.tournament_history[-20:]
    profile.update_career_stage()
    profile.update_signature()
    if profile.career_stage != previous_stage:
        profile.story_flags["last_stage_change_event"] = profile.story_flags.get("last_active_tournament", 0)
    return total_payout


def simulate_offscreen_circuit(npcs: List[PlayerProfile], rng: random.Random, templates: List[BakuganTemplate], gates: List[GateCard], abilities: List[AbilityCard], world_tournament_no: int, meta: Optional[Dict[str, object]] = None, stock_context: Optional[Dict[str, Dict[str, int]]] = None) -> None:
    if len(npcs) < 4:
        return
    candidates = weighted_sample_without_replacement(
        npcs,
        min(len(npcs), max(8, len(npcs) // 4)),
        rng,
        lambda p: 1.0 + p.fame * 0.03 + max(0.0, p.glicko.rating - 1450) / 120.0,
    )
    rng.shuffle(candidates)
    for i in range(0, len(candidates) - 1, 2):
        p1, p2 = candidates[i], candidates[i + 1]
        score1 = glicko2_expected_score(p1.glicko, p2.glicko) + (profile_strength_score(p1) - profile_strength_score(p2)) / 5000.0
        score2 = glicko2_expected_score(p2.glicko, p1.glicko) + (profile_strength_score(p2) - profile_strength_score(p1)) / 5000.0
        win1 = rng.random() < clamp(score1, 0.1, 0.9)
        s1, s2 = (0.8, 0.2) if win1 else (0.2, 0.8)
        old1, old2 = p1.glicko.copy(), p2.glicko.copy()
        p1.glicko = glicko2_update(old1, old2, s1)
        p2.glicko = glicko2_update(old2, old1, s2)
        if win1:
            p1.wins += 1
            p2.losses += 1
            p1.fame += 1
        else:
            p2.wins += 1
            p1.losses += 1
            p2.fame += 1
        p1.training_points += 1
        p2.training_points += 1
        p1.story_flags["last_active_tournament"] = world_tournament_no
        p2.story_flags["last_active_tournament"] = world_tournament_no
        p1.record_matchup(p2.name, win1)
        p2.record_matchup(p1.name, not win1)
        apply_training(p1, rng, 0.6)
        apply_training(p2, rng, 0.6)
        meta_now = meta or build_meta_snapshot(npcs)
        if rng.random() < 0.35:
            p1.development_focus = choose_career_focus(p1, rng, meta_now)
        if rng.random() < 0.35:
            p2.development_focus = choose_career_focus(p2, rng, meta_now)
        npc_market_progression(p1, rng, templates, gates, abilities, meta=meta_now, stock_context=stock_context)
        npc_market_progression(p2, rng, templates, gates, abilities, meta=meta_now, stock_context=stock_context)
        p1.peak_rating = max(p1.peak_rating, p1.glicko.rating)
        p2.peak_rating = max(p2.peak_rating, p2.glicko.rating)
        p1.update_career_stage()
        p2.update_career_stage()



def apply_matchup_results(matchups: List[Tuple[str, str, bool]], profile_map: Dict[str, PlayerProfile]) -> None:
    for p1_name, p2_name, p1_won in matchups:
        p1 = profile_map.get(p1_name)
        p2 = profile_map.get(p2_name)
        if p1 is None or p2 is None:
            continue
        p1.record_matchup(p2_name, p1_won)
        p2.record_matchup(p1_name, not p1_won)

# ============================================================
# STORY MODE APP
# ============================================================

