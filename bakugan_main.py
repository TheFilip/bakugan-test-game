
from __future__ import annotations

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

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

from bakugan_content import RAW_BAKUGAN_TEMPLATES, RAW_ABILITY_CARDS, RAW_GATE_CARDS


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
    g_powers: List[int]
    price: int

    def roll_instance(self, owner_name: str, rng: random.Random, forced_attribute: Optional[Attribute] = None) -> Bakugan:
        attr = forced_attribute if forced_attribute in self.allowed_attributes else rng.choice(self.allowed_attributes)
        g = rng.choice(self.g_powers)
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


@dataclass
class GateCard:
    name: str
    gate_type: GateType
    bonuses: Dict[Attribute, int]
    description: str
    effect_id: str
    price: int = 110
    used: bool = False


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
    signature_bakugan: str = ""
    rivals: List[str] = field(default_factory=list)
    head_to_head: Dict[str, Dict[str, int]] = field(default_factory=dict)
    story_flags: Dict[str, int] = field(default_factory=dict)
    tournament_history: List[Dict[str, object]] = field(default_factory=list)

    def clone_for_match(self) -> "PlayerProfile":
        def clone_baku(b: Bakugan) -> Bakugan:
            return Bakugan(b.name, b.attribute, b.base_g, b.price, b.owner_name, False)

        def clone_gate(g: GateCard) -> GateCard:
            return GateCard(g.name, g.gate_type, dict(g.bonuses), g.description, g.effect_id, g.price, False)

        def clone_ability(a: AbilityCard) -> AbilityCard:
            return AbilityCard(a.name, a.color, a.timing, a.description, a.effect_id, a.price, False)

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
                item["g_powers"],
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
    return GateCard(g.name, g.gate_type, dict(g.bonuses), g.description, g.effect_id, g.price, False)


def clone_ability(a: AbilityCard) -> AbilityCard:
    return AbilityCard(a.name, a.color, a.timing, a.description, a.effect_id, a.price, False)


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
        f"Focus {player.development_focus} | Signature {player.signature_bakugan or 'N/A'}"
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

        own_attrs = [player.collection_bakugan[i].attribute for i in player.active_bakugan_idx]
        score_map = []
        for idx in options:
            gate = player.collection_gates[idx]
            score = sum(gate.bonuses.get(a, 0) for a in own_attrs) + player.intelligence * 50
            if player.style == PlayerStyle.TACTICAL:
                score += 20
            if player.style == PlayerStyle.DEFENSIVE and gate.gate_type == GateType.SILVER:
                score += 15
            if player.style == PlayerStyle.COMBO and gate.gate_type == GateType.GOLD:
                score += 10
            score += self.random.uniform(-40, 40) * (1.0 - player.intelligence)
            score_map.append((score, idx))
        score_map.sort(reverse=True)
        return score_map[0][1]

    def choose_bakugan_to_roll(self, player: PlayerProfile) -> int:
        remaining = self._remaining_bakugan_for_turn(player)
        if self.player_is_manual(player):
            manual_choice = self.manual_handler.choose_bakugan_to_roll(player, remaining)
            if not getattr(self.manual_handler, "auto_rest", False):
                return manual_choice

        def score_idx(idx: int) -> float:
            b = player.collection_bakugan[idx]
            total = b.base_g
            for fg in self.field:
                total += self._best_gate_bonus_for_bakugan(b, fg.gate_card) * (0.3 + player.intelligence)
                opp = fg.get_single_opponent_of(player.name)
                if opp:
                    total += (b.base_g - opp.base_g) * (0.2 + player.aggression)
            total += self.random.uniform(-60, 60) * (1.0 - player.intelligence)
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

        scores = []
        for i, fg in enumerate(self.field):
            score = self._best_gate_bonus_for_bakugan(bakugan, fg.gate_card) * (0.7 + player.intelligence)
            if fg.is_empty():
                score += 25 * (1.0 - player.aggression)
            if fg.has_opponent_of(player.name):
                opp = fg.get_single_opponent_of(player.name)
                if opp:
                    projection = bakugan.base_g + self._best_gate_bonus_for_bakugan(bakugan, fg.gate_card) - opp.base_g
                    score += projection * (0.45 + player.intelligence)
                    score += 60 * player.aggression
                    score -= max(0, -projection) * (0.7 - player.risk * 0.4)
            if fg.has_friendly_of(player.name) and not fg.has_opponent_of(player.name):
                score -= 100 * player.intelligence
            score += self.random.uniform(-55, 55) * (1.0 - player.intelligence)
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

        bakugan = player.collection_bakugan[bakugan_idx]
        target_gate = self.field[target_gate_idx]
        scored = []
        for idx in options:
            ability = player.collection_abilities[idx]
            score = -999.0
            if ability.effect_id == "EXACT_A_HAND_UP":
                score = 80 if self._has_attribute(bakugan, Attribute.HAOS) else -999
            elif ability.effect_id == "EXACT_CLEAN_SLATE":
                occupied = sum(len(fg.bakugan_on_card) for fg in self.field)
                score = 70 + occupied * 15 if self._has_attribute(bakugan, Attribute.DARKUS) and occupied else -999
            elif ability.effect_id == "EXACT_COMBO_BATTLE":
                score = 65 if target_gate.has_opponent_of(player.name) else 35
            elif ability.effect_id == "ROLL_PLUS":
                score = 35
            elif ability.effect_id == "ROLL_CHOOSE_BEST":
                score = 30
            elif ability.effect_id == "ROLL_RECOVER":
                score = 28
            elif ability.effect_id == "ROLL_IGNORE_BAD_MATCH":
                score = 26
            elif ability.effect_id == "ROLL_BATTLE_BONUS":
                score = 24
            if score > -999:
                score += self.random.uniform(-10, 10) * (1.0 - player.intelligence)
                scored.append((score, idx))
        if not scored:
            return None
        scored.sort(reverse=True)
        best_score, best_idx = scored[0]
        return best_idx if best_score > 20 else None

    def apply_roll_ability(self, player: PlayerProfile, ability_idx: int, bakugan_idx: int) -> None:
        ability = player.collection_abilities[ability_idx]
        bakugan = player.collection_bakugan[bakugan_idx]
        self.used_ability_idx[player.name].append(ability_idx)
        self.match_stats[player.name].abilities_used += 1

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
            moved = fg.bakugan_on_card.pop()
            other_idx = 1 - landed_gate_idx
            self.field[other_idx].bakugan_on_card.append(moved)
            self.log(f"{moved.name} shifts to {self.field[other_idx].gate_card.name}")
            return other_idx
        return landed_gate_idx

    def choose_battle_ability(self, player: PlayerProfile, attacker_slot: bool, context: str, active_baku: Bakugan, other_baku: Bakugan, field_gate: FieldGate, state: BattleState) -> Optional[int]:
        options = self._unused_abilities(player, [Timing.DURING_BATTLE, Timing.FLEXIBLE])
        if not options:
            return None
        if self.player_is_manual(player):
            manual_choice = self.manual_handler.choose_battle_ability(player, options, context)
            if not getattr(self.manual_handler, "auto_rest", False):
                return manual_choice

        def estimate(idx: int) -> float:
            ability = player.collection_abilities[idx]
            eff_other_attr = self._effective_attribute(other_baku, state, not attacker_slot)
            if ability.effect_id == "EXACT_ALICES_SURPRISE":
                if self._used_ability_count(self.other_player() if self.current_player().name == player.name else self.current_player()) <= self._used_ability_count(player):
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
                return 90 if self._used_gate_count(self.other_player() if self.current_player().name == player.name else self.current_player()) > self._used_gate_count(player) else -999
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
                return 100 if self._has_attribute(active_baku, Attribute.AQUOS) else -999
            if ability.effect_id == "EXACT_DARKUS_ONLY":
                return 100 if self._has_attribute(active_baku, Attribute.DARKUS) else -999
            if ability.effect_id == "EXACT_STANDING_ATTR_SCALING":
                return 20 * max(1, len(self._standing_attributes()))
            if ability.effect_id == "EXACT_LOWEST_G_BONUS":
                return 80 if active_baku.base_g < other_baku.base_g else -999
            # fallback simplified values
            return 50

        scored = []
        for idx in options:
            val = estimate(idx)
            if val > -999:
                val += self.random.uniform(-8, 8) * (1.0 - player.intelligence)
                scored.append((val, idx))
        if not scored:
            return None
        scored.sort(reverse=True)
        return scored[0][1] if scored[0][0] > 0 else None

    def apply_gate_effect(self, field_gate: FieldGate, atk_baku: Bakugan, def_baku: Bakugan, state: BattleState) -> None:
        gid = field_gate.gate_card.effect_id
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

        def commit_use():
            self.used_ability_idx[player.name].append(ability_idx)
            self.match_stats[player.name].abilities_used += 1
            self.log(f"{player.name} uses {ability.name}")

        opp_effective_attr = self._effective_attribute(other_baku, state, not attacker_slot)

        if ability.effect_id == "EXACT_ALICES_SURPRISE":
            opponent = self.other_player() if self.current_player().name == player.name else self.current_player()
            if self._used_ability_count(opponent) <= self._used_ability_count(player):
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            bonus_map = {Attribute.PYRUS:50, Attribute.AQUOS:50, Attribute.SUBTERRA:100, Attribute.HAOS:100, Attribute.DARKUS:120, Attribute.VENTUS:120}
            bonus = self._best_value_for_bakugan(active_baku, bonus_map)
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + bonus)
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "EXACT_BIG_BRAWL":
            bonus_map = {Attribute.PYRUS:20, Attribute.AQUOS:40, Attribute.SUBTERRA:10, Attribute.HAOS:30, Attribute.DARKUS:20, Attribute.VENTUS:30}
            per_attr = self._best_value_for_bakugan(active_baku, bonus_map)
            bonus = per_attr * max(1, len(self._standing_attributes()))
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + bonus)
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
            setattr(state, own_g, getattr(state, own_g) + bonus)
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
            setattr(state, own_g, getattr(state, own_g) + bonus)
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
            setattr(state, own_g, getattr(state, own_g) + bonus)
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "EXACT_LEVEL_DOWN":
            if other_baku.base_g <= active_baku.base_g:
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            commit_use()
            setattr(state, opp_g, getattr(state, opp_g) - 100)
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
            setattr(state, own_g, getattr(state, own_g) + bonus)
            own_log.append(f"{ability.name}: +{bonus} from won gates")
            return active_baku
        elif ability.effect_id == "EXACT_USED_ABILITY_SCALING":
            bonus = 40 * self._used_ability_count(player)
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + bonus)
            own_log.append(f"{ability.name}: +{bonus} from used abilities")
            return active_baku
        elif ability.effect_id == "EXACT_AQUOS_ONLY":
            if not self._has_attribute(active_baku, Attribute.AQUOS):
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + 100)
            own_log.append(f"{ability.name}: Aquos +100")
            return active_baku
        elif ability.effect_id == "EXACT_DARKUS_ONLY":
            if not self._has_attribute(active_baku, Attribute.DARKUS):
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + 100)
            own_log.append(f"{ability.name}: Darkus +100")
            return active_baku
        elif ability.effect_id == "EXACT_STANDING_ATTR_SCALING":
            bonus = 20 * max(1, len(self._standing_attributes()))
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + bonus)
            own_log.append(f"{ability.name}: +{bonus} from standing attributes")
            return active_baku
        elif ability.effect_id == "EXACT_LOWEST_G_BONUS":
            if active_baku.base_g >= other_baku.base_g:
                self.log(f"{player.name} cannot use {ability.name}")
                return active_baku
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + 80)
            own_log.append(f"{ability.name}: lower original G +80")
            return active_baku
        elif ability.effect_id == "GREEN_BLOCK_ENEMY":
            commit_use()
            setattr(state, opp_block, True)
            own_log.append(f"{ability.name}: blocks enemy ability")
            return active_baku
        elif ability.effect_id == "BATTLE_PLUS_80":
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + 80)
            own_log.append(f"{ability.name}: +80")
            return active_baku
        elif ability.effect_id == "BATTLE_PLUS_120":
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + 120)
            own_log.append(f"{ability.name}: +120")
            return active_baku
        elif ability.effect_id == "BATTLE_PYRUS_BOOST":
            bonus = 120 if self._has_attribute(active_baku, Attribute.PYRUS) else 70
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + bonus)
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "BATTLE_PLUS_60":
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + 60)
            own_log.append(f"{ability.name}: +60")
            return active_baku
        elif ability.effect_id == "BATTLE_DARKUS_BOOST":
            bonus = 130 if self._has_attribute(active_baku, Attribute.DARKUS) else 65
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + bonus)
            own_log.append(f"{ability.name}: +{bonus}")
            return active_baku
        elif ability.effect_id == "GREEN_BEST_GATE_MATCH":
            best_bonus = max(field_gate.gate_card.bonuses.values())
            current_bonus = self._best_gate_bonus_for_bakugan(active_baku, field_gate.gate_card)
            extra = max(0, best_bonus - current_bonus)
            commit_use()
            setattr(state, own_g, getattr(state, own_g) + extra)
            own_log.append(f"{ability.name}: +{extra}")
            return active_baku
        elif ability.effect_id == "GREEN_SABOTAGE_100":
            commit_use()
            setattr(state, opp_g, getattr(state, opp_g) - 100)
            own_log.append(f"{ability.name}: opponent -100")
            return active_baku
        return active_baku

    def standard_gate_bonus(self, gate: GateCard, effective_attribute, mult: float, extra: int) -> int:
        if isinstance(effective_attribute, list):
            raw = max(gate.bonuses.get(attr, 0) for attr in effective_attribute)
        else:
            raw = gate.bonuses.get(effective_attribute, 0)
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
                    candidates.sort(reverse=True)
                    sup_idx = candidates[0][1]
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
        atk_bonus = self.standard_gate_bonus(fg.gate_card, atk_bonus_attrs, state.attacker_bonus_multiplier, state.attacker_flat_gate_bonus_extra)
        def_bonus = self.standard_gate_bonus(fg.gate_card, def_bonus_attrs, state.defender_bonus_multiplier, state.defender_flat_gate_bonus_extra)
        state.attacker_g += atk_bonus
        state.defender_g += def_bonus
        state.attacker_mod_log.append(f"Gate bonus +{atk_bonus} ({atk_attr.value})")
        state.defender_mod_log.append(f"Gate bonus +{def_bonus} ({def_attr.value})")

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
        lines.append(f"{'Pos':<4}{'Name':<20}{'Pts':<6}{'Wins':<6}{'Losses':<8}{'Buch':<8}{'GateDiff':<10}{'BattleDiff':<12}{'AvgPerf':<10}{'Rating':<10}")
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

    def round_finish_spot(self, round_size: int) -> int:
        return 2 if round_size == 2 else round_size

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

                self.result.placements[loser.name] = self.round_finish_spot(len(current))
                winners.append(p1 if winner.name == p1.name else p2)
                round_records.append((p1.name, p2.name, winner.name))
                print(f"Winner: {winner.name} | {p1.name} perf {perf[p1.name]:.1f} | {p2.name} perf {perf[p2.name]:.1f} | Gates {len(match.captured[p1.name])}-{len(match.captured[p2.name])}")

                self.play_logs.append(f"========== {round_name.upper()} ==========")
                self.play_logs.extend(lines)
                self.play_logs.append("")

            self.result.rounds.append(round_records)
            current = winners

        champion = current[0]
        self.result.champion = champion
        self.result.placements[champion.name] = 1

        print("\n========== KNOCKOUT FINAL PLACINGS ==========")
        ordered = sorted(self.result.placements.items(), key=lambda x: x[1])
        for pos, (name, finish) in enumerate(ordered, start=1):
            player = next(p for p in self.players if p.name == name)
            print(f"{pos:>2}. {name:<20} Finish {finish:<3d} Rating {player.glicko.rating:>7.1f}")
        return self.result

    def export_files(self, seed: int = 42, save_play_by_play: bool = True) -> Tuple[Path, Optional[Path]]:
        summary_path = get_current_output_dir() / build_output_filename("knockout_tournament", len(self.players), None, random_suffix(random.Random(seed + 2001)))
        lines = ["========== KNOCKOUT FINAL PLACINGS =========="]
        ordered = sorted(self.result.placements.items(), key=lambda x: x[1])
        for pos, (name, finish) in enumerate(ordered, start=1):
            player = next(p for p in self.players if p.name == name)
            lines.append(f"{pos:>2}. {name:<20} Finish {finish:<3d} Rating {player.glicko.rating:>7.1f}")
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
        "signature_bakugan": p.signature_bakugan,
        "rivals": list(p.rivals),
        "head_to_head": {k: {"wins": int(v.get("wins", 0)), "losses": int(v.get("losses", 0))} for k, v in p.head_to_head.items()},
        "story_flags": dict(p.story_flags),
        "tournament_history": [dict(x) for x in p.tournament_history[-20:]],
    }


def deserialize_profile(d: Dict) -> PlayerProfile:
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
        signature_bakugan=d.get("signature_bakugan", ""),
        rivals=list(d.get("rivals", [])),
        head_to_head={k: {"wins": int(v.get("wins", 0)), "losses": int(v.get("losses", 0))} for k, v in d.get("head_to_head", {}).items()},
        story_flags=dict(d.get("story_flags", {})),
        tournament_history=[dict(x) for x in d.get("tournament_history", [])],
    )
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
            if finish <= 4:
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
        lines.append(f"  Event {event_no}: {winner} | {arc.get('tournament_type', '?')} | {participant_count} players | Winning rating {winner_rating:.0f}")

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
        lines.append(f"    Event {event_no}: {name} at {rating:.0f}")

    if player_name:
        lines.append("")
        lines.append(f"Player season view: {player_name}")
        if player_finishes:
            avg_finish = sum(player_finishes) / len(player_finishes)
            best_finish = min(player_finishes)
            titles = sum(1 for x in player_finishes if x == 1)
            podium_count = sum(1 for x in player_finishes if x <= 4)
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
                        lines.append(f"    Event {int(arc.get('event_no',0))}: Finish {int(row.get('finish', 0))} | Rating {float(row.get('rating', 0.0)):.1f} | Money £{int(row.get('money', 0))}")
                        break
        else:
            lines.append("  Player did not appear in this season's archived tournaments.")

    return lines


def make_tournament_archive(season: int, event_no: int, tournament_type: TournamentType, participant_count: int, entrants: List[PlayerProfile], finish_map: Dict[str, int], winner_name: str, summary_path: Optional[Path], play_path: Optional[Path]) -> Dict:
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
        "tournament_type": tournament_type.value,
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

NAME_PARTS_1 = [
    "Alice", "Arthur", "Audrey", "Caleb", "Chloe", "Clara", "Daniel", "Eleanor", "Elijah", "Emma",
    "Ethan", "Eva", "Felix", "Fiona", "Grace", "Hazel", "Henry", "Hugo", "Iris", "Jack",
    "Jasper", "Leo", "Liam", "Lily", "Lucy", "Maeve", "Maya", "Mila", "Nora", "Oliver",
    "Oscar", "Rose", "Ruby", "Samuel", "Theo", "Violet", "William", "Aoife", "Cian", "Ciara",
    "Finn", "Niamh", "Ronan", "Saoirse", "Aiko", "Akira", "Haru", "Hina", "Kaori", "Kenji",
    "Mina", "Ren", "Sora", "Yui", "Aaliyah", "Amira", "Hassan", "Layla", "Omar", "Zayn"
]
NAME_PARTS_2 = [
    "Adair", "Arden", "Avery", "Bellamy", "Briar", "Callan", "Corin", "Darcy", "Ellis", "Emery",
    "Finley", "Hayden", "Hollis", "Jordan", "Keegan", "Kieran", "Lennon", "Morgan", "Parker", "Quinn",
    "Riley", "Rowan", "Sawyer", "Shay", "Sloan", "Tatum", "Aisling", "Briony", "Caoimhe", "Deirdre",
    "Eilis", "Orla", "Roisin", "Tadhg", "Amani", "Farah", "Iman", "Jamal", "Nadia", "Samir",
    "Aya", "Hikari", "Izumi", "Kaede", "Makoto", "Nao", "Rei", "Yuki", "Asher", "Bennett",
    "Everett", "Graham", "Miles", "Silas", "Wesley", "Zara"
]


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


def draft_starting_profile(name: str, chosen_attribute: Attribute, rng: random.Random, is_human: bool = False, stat_priority: Optional[List[str]] = None) -> PlayerProfile:
    templates = make_bakugan_templates()
    abilities = make_ability_cards()
    gates = make_gate_cards()

    beginner_names = {"Dragonoid", "Preyas", "Diablo/Angelo", "Angelo/Diablo Preyas", "Elfin", "Tigrerra", "Nemus", "Gorem", "Skyress", "Ingram", "Percival", "Brontes", "Akwimos"}
    beginner_pool = [t for t in templates if t.name in beginner_names]
    bakugan = [t.roll_instance(name, rng, chosen_attribute if chosen_attribute in t.allowed_attributes and rng.random() < 0.45 else None) for t in rng.sample(beginner_pool, 3)]
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
            "roll": round(rng.uniform(0.45, 0.95), 2),
            "int": round(rng.uniform(0.40, 0.95), 2),
            "agg": round(rng.uniform(0.25, 0.95), 2),
            "risk": round(rng.uniform(0.20, 0.95), 2),
        }
    else:
        stat_map = generate_stats_from_priority(stat_priority, rng)

    profile = PlayerProfile(
        name=name,
        chosen_attribute=chosen_attribute,
        style=rng.choice(list(PlayerStyle)),
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
    profile.ensure_valid_loadout()
    profile.update_career_stage()
    profile.update_rivals()
    profile.update_signature()
    return profile


def generate_npc_pool(count: int, existing: List[PlayerProfile], rng: random.Random) -> List[PlayerProfile]:
    used_names = {p.name for p in existing}
    profiles = existing[:]
    while len(profiles) < count:
        name = random_name(rng, used_names)
        attr = rng.choice(all_attributes())
        npc = draft_starting_profile(name, attr, rng, False)
        npc.money = rng.randint(150, 1100)
        npc.development_focus = rng.choice(["Balanced", "Power", "Control", "Strategy", "Aggro", "Greed"])
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


def optimise_profile_loadout(profile: PlayerProfile, meta: Optional[Dict[str, object]] = None, rng: Optional[random.Random] = None) -> None:
    rng = rng or random.Random()
    smartness = clamp(profile.intelligence, 0.2, 0.99)
    meta_attr = meta.get("dominant_attr") if meta else None

    def baku_score(b: Bakugan) -> float:
        score = b.base_g * (1.15 - 0.35 * (1.0 - smartness))
        if b.attribute == profile.chosen_attribute:
            score += 20 + 25 * smartness
        coverage_bonus = 12 if b.attribute != profile.chosen_attribute else 0
        if meta_attr is not None and b.attribute == meta_attr and b.attribute != profile.chosen_attribute and smartness > 0.7:
            coverage_bonus += 10
        score += coverage_bonus
        if profile.style == PlayerStyle.COMBO:
            score += 8
        if profile.style == PlayerStyle.DEFENSIVE and b.base_g >= 400:
            score += 14
        if profile.style == PlayerStyle.RECKLESS:
            score += (b.base_g - 360) * 0.08
        return score + rng.uniform(-40, 40) * (1.0 - smartness)

    baku_sorted = sorted(range(len(profile.collection_bakugan)), key=lambda i: baku_score(profile.collection_bakugan[i]), reverse=True)
    chosen_baku = []
    seen_attrs = set()
    for idx in baku_sorted:
        b = profile.collection_bakugan[idx]
        if smartness > 0.7 and len(chosen_baku) < 2 and b.attribute in seen_attrs and any(profile.collection_bakugan[j].attribute == profile.chosen_attribute for j in chosen_baku):
            continue
        chosen_baku.append(idx)
        seen_attrs.add(b.attribute)
        if len(chosen_baku) == 3:
            break
    for nxt in baku_sorted:
        if len(chosen_baku) >= 3:
            break
        if nxt not in chosen_baku:
            chosen_baku.append(nxt)

    active_bakus = [profile.collection_bakugan[i] for i in chosen_baku]
    active_attrs = {b.attribute for b in active_bakus}

    def gate_score(g: GateCard) -> float:
        total = sum(g.bonuses.values()) * 0.45
        total += g.bonuses.get(profile.chosen_attribute, 0) * (0.8 + 0.5 * smartness)
        total += sum(g.bonuses.get(a, 0) for a in active_attrs) * 0.55
        if meta_attr is not None and smartness > 0.68:
            total += g.bonuses.get(meta_attr, 0) * 0.25
        return total + rng.uniform(-25, 25) * (1.0 - smartness)

    gold_sorted = sorted([i for i, g in enumerate(profile.collection_gates) if g.gate_type == GateType.GOLD], key=lambda i: gate_score(profile.collection_gates[i]), reverse=True)
    silver_sorted = sorted([i for i, g in enumerate(profile.collection_gates) if g.gate_type == GateType.SILVER], key=lambda i: gate_score(profile.collection_gates[i]), reverse=True)
    bronze_sorted = sorted([i for i, g in enumerate(profile.collection_gates) if g.gate_type == GateType.BRONZE], key=lambda i: gate_score(profile.collection_gates[i]), reverse=True)

    def ability_score(a: AbilityCard) -> float:
        score = 8.0
        if a.color == AbilityColor.GREEN:
            score += 12 + 18 * smartness
            if profile.style in {PlayerStyle.TACTICAL, PlayerStyle.COMBO}:
                score += 12
        if a.color == AbilityColor.BLUE:
            score += 8 + profile.aggression * 10
            if profile.style in {PlayerStyle.RECKLESS, PlayerStyle.BALANCED}:
                score += 10
        if a.color == AbilityColor.RED:
            score += max(0.0, 0.72 - profile.rolling_skill) * 45
            if profile.style == PlayerStyle.CONTROL if False else False:
                score += 0
        text_blob = f"{a.name} {a.description} {a.effect_id}".lower()
        if smartness > 0.72:
            if profile.chosen_attribute.value.lower() in text_blob:
                score += 14
            if any(k in text_blob for k in ["swap", "replace", "doom", "shutdown", "block", "steal"]):
                score += 10
        return score + rng.uniform(-18, 18) * (1.0 - smartness)

    red_sorted = sorted([i for i, a in enumerate(profile.collection_abilities) if a.color == AbilityColor.RED], key=lambda i: ability_score(profile.collection_abilities[i]), reverse=True)
    blue_sorted = sorted([i for i, a in enumerate(profile.collection_abilities) if a.color == AbilityColor.BLUE], key=lambda i: ability_score(profile.collection_abilities[i]), reverse=True)
    green_sorted = sorted([i for i, a in enumerate(profile.collection_abilities) if a.color == AbilityColor.GREEN], key=lambda i: ability_score(profile.collection_abilities[i]), reverse=True)

    profile.active_bakugan_idx = chosen_baku[:3]
    profile.active_gate_idx = [lst[0] for lst in [gold_sorted, silver_sorted, bronze_sorted] if lst][:3]
    profile.active_ability_idx = [lst[0] for lst in [red_sorted, blue_sorted, green_sorted] if lst][:3]
    profile.ensure_valid_loadout()
    profile.update_signature()


def profile_has_minimum_legal_loadout(profile: PlayerProfile) -> bool:
    profile.ensure_valid_loadout()
    baku_ok, _ = validate_bakugan_selection(profile.active_bakugan_idx, profile.collection_bakugan)
    gate_ok, _ = validate_gate_selection(profile.active_gate_idx, profile.collection_gates)
    ability_ok, _ = validate_ability_selection(profile.active_ability_idx, profile.collection_abilities)
    return baku_ok and gate_ok and ability_ok


def enforce_minimum_tournament_eligibility(profile: PlayerProfile, rng: random.Random, templates: List[BakuganTemplate], gates: List[GateCard], abilities: List[AbilityCard], max_attempts: int = 40) -> bool:
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

        optimise_profile_loadout(profile)
        profile.ensure_valid_loadout()
        if profile_has_minimum_legal_loadout(profile):
            return True

        # Last resort: hard reset active loadout from first legal unique pieces
        profile.active_bakugan_idx = pick_unique_bakugan_indices(list(range(len(profile.collection_bakugan))), profile.collection_bakugan)
        profile.active_gate_idx = pick_unique_gate_indices(list(range(len(profile.collection_gates))), profile.collection_gates)
        profile.active_ability_idx = pick_unique_ability_indices(list(range(len(profile.collection_abilities))), profile.collection_abilities)
        if profile_has_minimum_legal_loadout(profile):
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
        attr_fit = 1 if profile.chosen_attribute in t.allowed_attributes else 0
        meta_fit = 1 if meta_attr in t.allowed_attributes else 0
        power = max(t.g_powers)
        value = power + attr_fit * (35 + 25 * smartness) + meta_fit * (10 if smartness > 0.7 else 0)
        value -= t.price * (0.25 + 0.20 * smartness)
        return value

    def gate_value(g: GateCard) -> float:
        value = g.bonuses.get(profile.chosen_attribute, 0) * (1.0 + smartness) + sum(g.bonuses.values()) * 0.25
        if meta_attr is not None and smartness > 0.65:
            value += g.bonuses.get(meta_attr, 0) * 0.25
        value -= g.price * (0.2 + 0.15 * smartness)
        return value

    def ability_value(a: AbilityCard) -> float:
        text_blob = f"{a.name} {a.description} {a.effect_id}".lower()
        value = 12.0
        if a.color == AbilityColor.GREEN:
            value += 16 + 18 * smartness
        elif a.color == AbilityColor.BLUE:
            value += 12 + profile.aggression * 10
        else:
            value += max(0.0, 0.72 - profile.rolling_skill) * 42
        if smartness > 0.72 and profile.chosen_attribute.value.lower() in text_blob:
            value += 10
        if smartness > 0.78 and any(k in text_blob for k in ["doom", "swap", "shutdown", "block", "steal", "replace"]):
            value += 8
        value -= a.price * (0.2 + 0.15 * smartness)
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

        categories: List[Tuple[float, str]] = []
        categories.append((3.0 if need_baku else 1.2, "baku"))
        categories.append((2.6 if need_gate_type else 1.0, "gate"))
        categories.append((2.6 if need_ability_color else 1.0, "ability"))
        if loot_options:
            categories.append((0.9 if smartness > 0.75 else 1.4, "loot"))
        if smartness > 0.7:
            categories.sort(reverse=True)
            pick = categories[0][1] if rng.random() < 0.75 else rng.choice([c for _, c in categories])
        else:
            pick = rng.choice([c for _, c in categories])

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
    if finish <= 4:
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

    if finish <= max(8, participant_count // 2):
        profile.top8s += 1
        profile.training_points += 1
    if finish <= 4:
        profile.podiums += 1
        profile.fame += 4
        profile.training_points += 2
    if finish <= 2:
        profile.finals += 1
        profile.fame += 6
        profile.sponsorship += 1
    if finish == 1:
        profile.tournament_titles += 1
        profile.wins += 1
        profile.fame += 10
        profile.training_points += 3
    else:
        profile.losses += 1

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

class StoryModeApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Bakugan Story Mode")
        self.db = NPCDatabase()
        self.rng = random.Random()
        self.player: Optional[PlayerProfile] = None
        self.current_save_stem = "session_unsaved"
        set_current_output_dir(self.current_save_stem)
        self.debug_var = tk.BooleanVar(value=True)

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
        self.npc_target_population = 192
        self.ensure_npc_universe()
        self.get_season_shop_stock()

        self.status_var = tk.StringVar(value="Create a character to begin.")
        self.build_ui()

    def build_ui(self) -> None:
        frm = ttk.Frame(self.root, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Bakugan Story Mode", font=("Arial", 16, "bold")).pack(anchor="w")
        ttk.Checkbutton(frm, text="Debug mode", variable=self.debug_var).pack(anchor="w", pady=(4, 10))

        ttk.Label(frm, textvariable=self.status_var, wraplength=700).pack(anchor="w", pady=(0, 10))

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=4)
        ttk.Button(btns, text="New Character", command=self.new_character).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(btns, text="View Loadout", command=self.view_loadout).grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(btns, text="Customise Loadout", command=self.customise_loadout).grid(row=0, column=2, padx=4, pady=4)
        ttk.Button(btns, text="Shop", command=self.open_shop).grid(row=0, column=3, padx=4, pady=4)
        ttk.Button(btns, text="Start Tournament", command=self.start_tournament).grid(row=0, column=4, padx=4, pady=4)
        ttk.Button(btns, text="NPC Rankings", command=self.view_npc_rankings).grid(row=0, column=5, padx=4, pady=4)
        ttk.Button(btns, text="Search Profile", command=self.search_profile_loadout).grid(row=0, column=6, padx=4, pady=4)
        ttk.Button(btns, text="Tournament History", command=self.view_tournament_history).grid(row=0, column=7, padx=4, pady=4)
        ttk.Button(btns, text="Season Summary", command=self.view_season_summary).grid(row=0, column=8, padx=4, pady=4)
        ttk.Button(btns, text="Save Game", command=self.save_character_json).grid(row=0, column=9, padx=4, pady=4)
        ttk.Button(btns, text="Load Game", command=self.load_character_json).grid(row=0, column=10, padx=4, pady=4)
        ttk.Button(btns, text="Card Reference", command=self.view_card_reference).grid(row=0, column=11, padx=4, pady=4)

        self.text = tk.Text(frm, width=110, height=30)
        self.text.pack(fill="both", expand=True)

    def append_text(self, text: str) -> None:
        self.text.insert("end", text + "\n")
        self.text.see("end")

    def debug_append(self, text: str) -> None:
        if bool(self.debug_var.get()):
            self.append_text(text)

    def require_player(self) -> bool:
        if self.player is None:
            messagebox.showerror("No character", "Create a character first.", parent=self.root)
            return False
        return True

    def refresh_status(self) -> None:
        if not self.player:
            self.status_var.set(
                f"Create a character to begin. World season {current_season}, event {current_event}, total events {self.world_total_tournaments}, NPCs {len(self.db.load_all_profiles())}"
            )
            return
        self.player.update_career_stage()
        self.status_var.set(
            f"{self.player.name} | {self.player.chosen_attribute.value} | £{self.player.money} | "
            f"Rating {self.player.glicko.rating:.0f} | Stage {self.player.career_stage} | "
            f"Titles {self.player.tournament_titles} | Podiums {self.player.podiums} | "
            f"Entered {self.player.tournaments_entered} | Season {self.world_season} Event {self.world_tournament_no} | Total Events {self.world_total_tournaments}"
        )

    def ensure_npc_universe(self) -> None:
        existing = [p for p in self.db.load_all_profiles() if not p.is_human]
        pool = generate_npc_pool(self.npc_target_population, existing, self.rng)
        for npc in pool:
            npc.ensure_valid_loadout()
            npc.update_career_stage()
            npc.update_rivals()
            npc.update_signature()
        self.db.save_profiles(pool)

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
            lines.append(
                f"{i:>2}. {prof.name} | {prof.career_stage} | Rating {prof.glicko.rating:.0f} | "
                f"Titles {prof.tournament_titles} | Podiums {prof.podiums} | Fame {prof.fame} | "
                f"Sig {prof.signature_bakugan}{player_tag}"
            )
        if self.player is not None and player_rank is not None:
            prof = ranked[player_rank - 1]
            lines.append("")
            lines.append(f"Your rank: {player_rank}/{len(ranked)}")
            if player_rank > 20:
                lines.append(
                    f"{player_rank:>2}. {prof.name} | {prof.career_stage} | Rating {prof.glicko.rating:.0f} | "
                    f"Titles {prof.tournament_titles} | Podiums {prof.podiums} | Fame {prof.fame} | "
                    f"Sig {prof.signature_bakugan} | You"
                )
        self.append_text("\n".join(lines))

    def search_profile_loadout(self) -> None:
        profiles = list(self.all_npcs())
        if self.player is not None:
            profiles = [p for p in profiles if p.name != self.player.name] + [self.player]

        def ranked_profiles(sort_mode: str) -> List[PlayerProfile]:
            if sort_mode == "rating":
                return sorted(profiles, key=lambda p: (p.glicko.rating, p.tournament_titles, p.fame, p.name.lower()), reverse=True)
            if sort_mode == "titles":
                return sorted(profiles, key=lambda p: (p.tournament_titles, p.glicko.rating, p.fame, p.name.lower()), reverse=True)
            if sort_mode == "fame":
                return sorted(profiles, key=lambda p: (p.fame, p.glicko.rating, p.tournament_titles, p.name.lower()), reverse=True)
            # world ranking uses the same ordering as the world rankings view
            return sorted(profiles, key=lambda p: (p.glicko.rating, p.tournament_titles, p.fame, p.name.lower()), reverse=True)

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
            values=["world ranking", "rating", "titles", "fame"],
            state="readonly",
            width=16,
        )
        sort_box.pack(side="left", padx=(6, 0))

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
            if q:
                filtered = [p for p in latest_ranked if q in p.name.lower()]
            else:
                filtered = latest_ranked[:]
            listbox.delete(0, 'end')
            for p in filtered:
                player_tag = " | You" if self.player is not None and p.name == self.player.name else ""
                if sort_var.get() == "world ranking":
                    rank_no = latest_ranked.index(p) + 1
                    listbox.insert('end', f"#{rank_no} {p.name}{player_tag}")
                elif sort_var.get() == "rating":
                    listbox.insert('end', f"{p.name} | Rating {p.glicko.rating:.0f}{player_tag}")
                elif sort_var.get() == "titles":
                    listbox.insert('end', f"{p.name} | Titles {p.tournament_titles}{player_tag}")
                else:
                    listbox.insert('end', f"{p.name} | Fame {p.fame}{player_tag}")
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
            lines = [
                f"{prof.name}{' | You' if self.player is not None and prof.name == self.player.name else ''}",
                f"World Rank #{world_rank if world_rank is not None else 'N/A'}",
                f"Attribute {prof.chosen_attribute.value} | Style {prof.style.value}",
                f"Rating {prof.glicko.rating:.0f} | Titles {prof.tournament_titles} | Podiums {prof.podiums} | Fame {prof.fame}",
                f"Signature {prof.signature_bakugan or 'N/A'}",
            ]
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
            text_widget.insert('1.0', "\n".join(lines))

        query_var.trace_add('write', refresh_list)
        sort_var.trace_add('write', refresh_list)
        listbox.bind('<<ListboxSelect>>', show_selected)
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
        ttk.Label(left, text=f"Seasons played: {len(season_counts)}").pack(anchor="w", pady=(0, 8))

        listbox = tk.Listbox(left, width=44, height=34)
        listbox.pack(fill="y", expand=True)
        text_widget = tk.Text(right, width=90, height=40)
        text_widget.pack(fill="both", expand=True)

        display_items = []
        for arc in archives:
            label = f"S{int(arc['season']):02d} E{int(arc['event_no']):03d} | {arc['tournament_type']} | {arc['participant_count']} players | Winner {arc.get('winner','?')}"
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

        result = {"ok": False, "priority": None}

        def confirm() -> None:
            chosen = [v.get() for v in vars_]
            if sorted(chosen) != sorted(options):
                messagebox.showerror("Invalid priorities", "Choose each stat exactly once.", parent=win)
                return
            result["ok"] = True
            result["priority"] = chosen
            win.destroy()

        ttk.Button(win, text="Create Character", command=confirm).grid(row=5, column=0, padx=8, pady=8, sticky="w")
        ttk.Button(win, text="Cancel", command=win.destroy).grid(row=5, column=1, padx=8, pady=8, sticky="e")

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
        self.player = draft_starting_profile(name, chosen_attribute, self.rng, True, stat_priority=result["priority"])
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
            f"Stats: Roll {self.player.rolling_skill:.2f}, Int {self.player.intelligence:.2f}, Agg {self.player.aggression:.2f}, Risk {self.player.risk:.2f}"
        )

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

    def autosave_current_game(self) -> Optional[Path]:
        if self.player is None:
            return None
        payload = serialize_savegame(self.player, self.world_season, self.world_tournament_no, self.world_total_tournaments, self.world_seed)
        path = SAVE_DIR / "autosave_latest.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def save_character_json(self) -> None:
        if not self.require_player():
            return
        path = SAVE_DIR / build_save_filename(self.player.name, random_suffix(self.rng))
        payload = serialize_savegame(self.player, self.world_season, self.world_tournament_no, self.world_total_tournaments, self.world_seed)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.current_save_stem = Path(path).stem
        set_current_output_dir(self.current_save_stem)
        self.autosave_current_game()
        self.append_text(f"Saved game to {path}")
        self.append_text(f"Tournament exports for this save go to {get_current_output_dir()}")

    def load_character_json(self) -> None:
        initial = SAVE_DIR / "autosave_latest.json"
        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Load Save",
            initialdir=str(SAVE_DIR),
            initialfile=(initial.name if initial.exists() else ""),
            filetypes=[("JSON save", "*.json")],
        )
        if not file_path:
            return
        try:
            payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
            player, world_season, world_tournament_no, world_total_tournaments, world_seed = deserialize_savegame(payload)
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
            self.refresh_status()
            self.append_text(f"Loaded save from {file_path}")
            self.append_text(f"Tournament exports for this save go to {get_current_output_dir()}")
        except Exception as e:
            messagebox.showerror("Load failed", str(e), parent=self.root)

    def build_tournament_field(self, participant_count: int) -> List[PlayerProfile]:
        npcs = self.all_npcs()
        excluded = {self.player.name} if self.player else set()

        if self.player is not None:
            # Respect the player's chosen active loadout if it is already legal.
            if not profile_has_minimum_legal_loadout(self.player):
                if not enforce_minimum_tournament_eligibility(self.player, self.rng, self.templates, self.gates, self.abilities):
                    raise ValueError(f"Player {self.player.name} does not have a legal tournament loadout. A participant must have at least 3 distinct exact Bakugan, 1 Gold/1 Silver/1 Bronze gate, and 1 Red/1 Blue/1 Green ability.")

        candidates: List[PlayerProfile] = []
        for p in npcs:
            if p.name in excluded:
                continue
            if enforce_minimum_tournament_eligibility(p, self.rng, self.templates, self.gates, self.abilities):
                candidates.append(p)

        if self.player and self.player.rivals:
            rival_names = set(self.player.rivals)
        else:
            rival_names = set()

        def weight_fn(npc: PlayerProfile) -> float:
            weight = 1.0
            weight += max(0.0, npc.glicko.rating - 1450) / 120.0
            weight += npc.fame * 0.03
            weight += npc.tournament_titles * 0.5
            if npc.name in rival_names:
                weight += 2.5
            if self.player is not None and npc.chosen_attribute == self.player.chosen_attribute:
                weight += 0.4
            last_seen = npc.story_flags.get("last_seen_main_event", -999)
            if self.world_tournament_no - last_seen <= 2:
                weight += 0.6
            return weight

        if len(candidates) < participant_count - 1:
            raise ValueError(f"Not enough eligible NPCs to build a {participant_count}-player field. Eligible NPCs: {len(candidates)}")

        picked = weighted_sample_without_replacement(candidates, participant_count - 1, self.rng, weight_fn)
        for npc in picked:
            npc.story_flags["last_seen_main_event"] = self.world_tournament_no
            enforce_minimum_tournament_eligibility(npc, self.rng, self.templates, self.gates, self.abilities)
            optimise_profile_loadout(npc)
        return [self.player] + picked

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
            if name == self.player.name:
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

        not_in_event = [p for p in all_map.values() if p.name not in finish_map]
        simulate_offscreen_circuit(not_in_event, self.rng, self.templates, self.gates, self.abilities, self.world_tournament_no, meta=meta_snapshot, stock_context=shared_stock)
        for npc in not_in_event:
            if self.rng.random() < 0.55:
                npc.training_points += 1
                apply_training(npc, self.rng, 0.7)
            if self.rng.random() < 0.35:
                npc_market_progression(npc, self.rng, self.templates, self.gates, self.abilities, meta=meta_snapshot, stock_context=shared_stock, debug_cb=self.debug_append)
            npc.update_career_stage()
            npc.update_rivals()
            npc.update_signature()

        self.save_npcs(list(all_map.values()))
        self.save_season_shop_stock(shared_stock)

    def start_tournament(self) -> None:
        if not self.require_player():
            return

        current_season = self.world_season
        current_event = self.world_tournament_no

        participant_count = self.rng.choice([16, 16, 32, 32, 64])
        tournament_type = self.rng.choice(list(TournamentType))
        manual = messagebox.askyesno("Mode", "Play this tournament in manual mode?\n\nDuring manual prompts, type AUTO to simulate the rest of the tournament automatically.", parent=self.root)


        debug = bool(self.debug_var.get())
        handler = TkManualChoiceHandler(self.root) if manual else None

        entrants = self.build_tournament_field(participant_count)
        rounds = max(4, min(11, int(round(log2(participant_count)) + 2))) if tournament_type == TournamentType.SWISS else None

        self.append_text(
            f"Starting {tournament_type.value} tournament with {participant_count} participants in season {current_season}, event {current_event}"
        )
        logger = Logger(enabled=debug, prefix="story")

        finish_map: Dict[str, int] = {}
        winner_name = ""
        matchup_results: List[Tuple[str, str, bool]] = []
        if tournament_type == TournamentType.SWISS:
            tournament = SwissTournament(
                entrants,
                rounds=rounds,
                seed=self.rng.randint(1, 10_000_000),
                verbose_matches=debug,
                logger=logger,
                manual_handler=handler,
                manual_player_name=self.player.name if manual else None,
            )
            tournament.run()
            matchup_results = [(rec.player1, rec.player2, rec.winner == rec.player1) for rec in tournament.records]
            summary_path, play_path = tournament.export_files(seed=self.rng.randint(1, 10_000_000), save_play_by_play=True)
            standings = tournament.standings()
            for pos, p in enumerate(standings, start=1):
                finish_map[p.name] = pos
            winner_name = standings[0].name if standings else ""
            finish = finish_map.get(self.player.name, participant_count)
            payout = self.payout_for_finish(finish, participant_count, tournament_type)
            self.append_text(f"Finished {finish} in Swiss. Earned £{payout}.")
            self.append_text(f"Saved summary to {summary_path}")
            if play_path:
                self.append_text(f"Saved play by play to {play_path}")

        else:
            knockout = KnockoutTournament(
                entrants,
                seed=self.rng.randint(1, 10_000_000),
                verbose_matches=debug,
                logger=logger,
                manual_handler=handler,
                manual_player_name=self.player.name if manual else None,
            )
            result = knockout.run()
            matchup_results = []
            for round_records in result.rounds:
                for p1n, p2n, winner_n in round_records:
                    matchup_results.append((p1n, p2n, winner_n == p1n))
            summary_path, play_path = knockout.export_files(seed=self.rng.randint(1, 10_000_000), save_play_by_play=True)
            finish_map.update(result.placements)
            winner_name = result.champion.name if result.champion else ""
            finish = result.placements.get(self.player.name, participant_count)
            payout = self.payout_for_finish(finish, participant_count, tournament_type)
            self.append_text(f"Finished {finish} in Knockout. Earned £{payout}.")
            self.append_text(f"Saved summary to {summary_path}")
            if play_path:
                self.append_text(f"Saved play by play to {play_path}")

        profile_map = {p.name: p for p in entrants}
        if self.player is not None:
            profile_map[self.player.name] = self.player
        apply_matchup_results(matchup_results, profile_map)
        archive = make_tournament_archive(current_season, current_event, tournament_type, participant_count, entrants, finish_map, winner_name, summary_path, play_path)
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
            self.save_season_shop_stock(self._build_seasonal_shop_stock(self.world_season))

        self.append_text(f"Archived tournament history for Season {current_season} Event {current_event}. Offscreen circuits simulated for non-participating NPCs.")
        player_finish = finish_map.get(self.player.name, participant_count)
        latest = self.player.tournament_history[-1] if self.player.tournament_history else {}
        self.append_text(
            f"Career updated: finish {player_finish}, money £{self.player.money}, rating {self.player.glicko.rating:.0f}, peak {self.player.peak_rating:.0f}, "
            f"titles {self.player.tournament_titles}, podiums {self.player.podiums}, top8s {self.player.top8s}, stage {self.player.career_stage}"
        )
        self.autosave_current_game()
        self.refresh_status()

        if debug:
            debug_name = build_output_filename(
                "story_debug",
                participant_count,
                rounds if rounds is not None else None,
                random_suffix(self.rng),
            )
            path = logger.save(debug_name)
            self.append_text(f"Saved debug log to {path}")


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
        output_path.write_text("\n".join(text_lines), encoding="utf-8")
        print(f"Saved log to: {output_path}")
    return winner, perf, match, output_path


def run_bakugan_tournament(player_count: int = 16, rounds: int = 5, seed: int = 42, verbose_matches: bool = False) -> SwissTournament:
    players = generate_profiles(player_count, seed=seed)
    tournament = SwissTournament(players, rounds, seed=seed, verbose_matches=verbose_matches)
    tournament.run()

    rng = random.Random(seed + 3001)
    standings = tournament.standings()
    finish_map = {p.name: pos for pos, p in enumerate(standings, start=1)}
    for p in players:
        finish = finish_map.get(p.name, len(players))
        apply_tournament_career_update(p, finish, len(players), TournamentType.SWISS, rng)

    summary_path, play_path = tournament.export_files(seed=seed, save_play_by_play=True)
    print(f"Saved summary to: {summary_path}")
    if play_path:
        print(f"Saved play by play to: {play_path}")
    return tournament


def run_bakugan_knockout(player_count: int = 16, seed: int = 42, verbose_matches: bool = False) -> Tuple[KnockoutTournament, KnockoutResult]:
    players = generate_profiles(player_count, seed=seed)
    pow2 = 2 ** floor(log(player_count, 2))
    players = players[:pow2]
    knockout = KnockoutTournament(players, seed=seed, verbose_matches=verbose_matches)
    result = knockout.run()

    rng = random.Random(seed + 3002)
    for p in players:
        finish = result.placements.get(p.name, len(players))
        apply_tournament_career_update(p, finish, len(players), TournamentType.KNOCKOUT, rng)

    summary_path, play_path = knockout.export_files(seed=seed, save_play_by_play=True)
    print(f"Saved summary to: {summary_path}")
    if play_path:
        print(f"Saved play by play to: {play_path}")
    return knockout, result


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = StoryModeApp(root)
    root.mainloop()