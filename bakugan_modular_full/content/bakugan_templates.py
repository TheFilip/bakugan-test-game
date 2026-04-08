"""Bakugan template data."""

G_POWER_RANGE = 130
PRICE_MODIFIER = 1.0
# Economy tuning knobs
BAKUGAN_BASE_PRICE = 65
BAKUGAN_GPOWER_MULTIPLIER = 0.50
BAKUGAN_HIGH_G_STEP = 0.22
BAKUGAN_ONE_ATTR_BONUS = 18
BAKUGAN_TWO_ATTR_BONUS = 10
BAKUGAN_THREE_ATTR_BONUS = 5
BAKUGAN_ICONIC_BONUS = {
    "Leonidas": 18,
    "Omega Leonidas": 42,
    "Dragonoid": 24,
    "Delta Dragonoid II": 34,
    "Ultimate Dragonoid": 42,
    "Neo Dragonoid": 28,
    "Hydranoid": 20,
    "Dual Hydranoid": 34,
    "Vladitor": 24,
    "Battle Ax Vladitor": 40,
    "Helios": 20,
    "Viper Helios": 30,
    "Cyborg Helios": 42,
    "Naga": 44,
    "Wavern": 40,
    "Apollonir": 26,
    "Clayf": 24,
    "Exedra": 24,
    "Frosch": 24,
    "Lars Lion": 22,
    "Oberus": 22,
}

BAKUGAN_MANUAL_PRICE_OVERRIDES = {
    # Late-game non-evolved 500G/550G usage-based adjustments
    "Apollonir": 295,
    "Clayf": 285,
    "Exedra": 260,
    "Frosch": 290,
    "Lars Lion": 280,
    "Oberus": 290,
    "Naga": 370,
    "Wavern": 405,

    # Evolved Bakugan usage-based adjustments
    "Ultimate Dragonoid": 405,
    "Dual Hydranoid": 350,
    "Master Ingram": 280,
    "Minx Elfin": 260,
    "Rex Vulcan": 255,
    "Cyborg Helios": 335,
    "Thunder Wilda": 270,
    "Mega Brontes": 260,
    "Blade Tigrerra": 250,
    "Battle Ax Vladitor": 335,
    "Neo Dragonoid": 250,
    "Delta Dragonoid II": 275,
}

def _round_price(value):
    return int(round(float(value) / 5.0) * 5)


def _scaled_price(value):
    return max(1, _round_price(float(value) * PRICE_MODIFIER))


def _priced_bakugan(entry):
    name = entry['name']
    manual_price = BAKUGAN_MANUAL_PRICE_OVERRIDES.get(name)
    if manual_price is not None:
        return _scaled_price(manual_price)

    g = int(entry['min_g_power'])
    attr_count = len(entry.get('allowed_attributes', []))
    price = BAKUGAN_BASE_PRICE + max(0, g - 180) * BAKUGAN_GPOWER_MULTIPLIER
    if g > 420:
        price += (g - 420) * BAKUGAN_HIGH_G_STEP
    if attr_count <= 1:
        price += BAKUGAN_ONE_ATTR_BONUS
    elif attr_count == 2:
        price += BAKUGAN_TWO_ATTR_BONUS
    elif attr_count == 3:
        price += BAKUGAN_THREE_ATTR_BONUS
    price += BAKUGAN_ICONIC_BONUS.get(name, 0)
    return _scaled_price(price)

_RAW_BAKUGAN_TEMPLATES_INPUT = [
    {'name': 'Serpenoid', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 190, 'price': 120},
    {'name': 'Juggernoid', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 200, 'price': 120},
    {'name': 'Robotallion', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 200, 'price': 120},
    {'name': 'Saurus', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 210, 'price': 120},
    {'name': 'Falconeer', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 210, 'price': 120},
    {'name': 'Manion', 'allowed_attributes': ['SUBTERRA', 'HAOS', 'VENTUS'], 'min_g_power': 300, 'price': 150},
    {'name': 'Ravenoid', 'allowed_attributes': ['PYRUS', 'HAOS', 'VENTUS'], 'min_g_power': 300, 'price': 150},
    {'name': 'Stinglash', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 230, 'price': 130},
    {'name': 'Centipoid', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 240, 'price': 135},
    {'name': 'Gargonoid', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'DARKUS', 'VENTUS'], 'min_g_power': 250, 'price': 125},
    {'name': 'Fear Ripper', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 270, 'price': 135},
    {'name': 'Siege', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 270, 'price': 145},
    {'name': 'Monarus', 'allowed_attributes': ['PYRUS', 'HAOS', 'VENTUS'], 'min_g_power': 300, 'price': 160},
    {'name': 'Griffon', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 300, 'price': 150},
    {'name': 'Terrorclaw', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS'], 'min_g_power': 320, 'price': 160},
    {'name': 'Laserman', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 370, 'price': 185},
    {'name': 'Reaper', 'allowed_attributes': ['AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 380, 'price': 190},
    {'name': 'Leonidas', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 340, 'price': 225},
    {'name': 'Omega Leonidas', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 470, 'price': 380},
    {'name': 'Fourtress', 'allowed_attributes': ['PYRUS'], 'min_g_power': 390, 'price': 195},
    {'name': 'Dragonoid', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 340, 'price': 250},
    {'name': 'Delta Dragonoid II', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 450, 'price': 300},
    {'name': 'Sirenoid', 'allowed_attributes': ['AQUOS'], 'min_g_power': 390, 'price': 195},
    {'name': 'Preyas', 'allowed_attributes': ['AQUOS'], 'min_g_power': 300, 'price': 190},
    {'name': 'Cycloid', 'allowed_attributes': ['SUBTERRA'], 'min_g_power': 390, 'price': 195},
    {'name': 'Gorem', 'allowed_attributes': ['SUBTERRA'], 'min_g_power': 380, 'price': 200},
    {'name': 'Hammer Gorem', 'allowed_attributes': ['SUBTERRA'], 'min_g_power': 450, 'price': 220},
    {'name': 'Tentaclear', 'allowed_attributes': ['HAOS'], 'min_g_power': 390, 'price': 195},
    {'name': 'Tigrerra', 'allowed_attributes': ['HAOS'], 'min_g_power': 340, 'price': 200},
    {'name': 'Blade Tigrerra', 'allowed_attributes': ['HAOS'], 'min_g_power': 500, 'price': 250},
    {'name': 'Hydranoid', 'allowed_attributes': ['DARKUS'], 'min_g_power': 450, 'price': 235},
    {'name': 'Dual Hydranoid', 'allowed_attributes': ['DARKUS'], 'min_g_power': 550, 'price': 325},
    {'name': 'Vladitor', 'allowed_attributes': ['DARKUS'], 'min_g_power': 340, 'price': 300},
    {'name': 'Battle Ax Vladitor', 'allowed_attributes': ['DARKUS'], 'min_g_power': 470, 'price': 390},
    {'name': 'Harpus', 'allowed_attributes': ['VENTUS'], 'min_g_power': 390, 'price': 195},
    {'name': 'Skyress', 'allowed_attributes': ['VENTUS'], 'min_g_power': 360, 'price': 200},
    {'name': 'Storm Skyress', 'allowed_attributes': ['VENTUS'], 'min_g_power': 450, 'price': 250},
    {'name': 'Preyas II Angelo/Diablo', 'allowed_attributes': ['AQUOS'], 'min_g_power': 450, 'price': 280},
    {'name': 'Ultimate Dragonoid', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 550, 'price': 360},
    {'name': 'Neo Dragonoid', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 400, 'price': 285},
    {'name': 'Ingram', 'allowed_attributes': ['PYRUS', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 340, 'price': 185},
    {'name': 'Master Ingram', 'allowed_attributes': ['VENTUS'], 'min_g_power': 500, 'price': 250},
    {'name': 'Percival', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'DARKUS', 'VENTUS'], 'min_g_power': 360, 'price': 195},
    {'name': 'Knight Percival', 'allowed_attributes': ['DARKUS'], 'min_g_power': 500, 'price': 225},
    {'name': 'Elfin', 'allowed_attributes': ['AQUOS', 'VENTUS', 'DARKUS'], 'min_g_power': 330, 'price': 185},
    {'name': 'Minx Elfin', 'allowed_attributes': ['AQUOS'], 'min_g_power': 500, 'price': 225},
    {'name': 'Helios', 'allowed_attributes': ['DARKUS'], 'min_g_power': 380, 'price': 200},
    {'name': 'Viper Helios', 'allowed_attributes': ['DARKUS'], 'min_g_power': 500, 'price': 250},
    {'name': 'Cyborg Helios', 'allowed_attributes': ['DARKUS'], 'min_g_power': 580, 'price': 330},
    {'name': 'Nemus', 'allowed_attributes': ['HAOS', 'VENTUS'], 'min_g_power': 350, 'price': 190},
    {'name': 'Mega Nemus', 'allowed_attributes': ['HAOS'], 'min_g_power': 500, 'price': 225},
    {'name': 'Brontes', 'allowed_attributes': ['HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 360, 'price': 195},
    {'name': 'Mega Brontes', 'allowed_attributes': ['HAOS'], 'min_g_power': 500, 'price': 250},
    {'name': 'Wilda', 'allowed_attributes': ['SUBTERRA'], 'min_g_power': 380, 'price': 200},
    {'name': 'Thunder Wilda', 'allowed_attributes': ['SUBTERRA'], 'min_g_power': 500, 'price': 265},
    {'name': 'Vulcan', 'allowed_attributes': ['SUBTERRA'], 'min_g_power': 400, 'price': 215},
    {'name': 'Rex Vulcan', 'allowed_attributes': ['SUBTERRA'], 'min_g_power': 500, 'price': 225},
    {'name': 'El Condor', 'allowed_attributes': ['AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 340, 'price': 150},
    {'name': 'Warius', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 370, 'price': 170},
    {'name': 'Apollonir', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 500, 'price': 260},
    {'name': 'Clayf', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'DARKUS'], 'min_g_power': 500, 'price': 275},
    {'name': 'Exedra', 'allowed_attributes': ['SUBTERRA', 'DARKUS', 'VENTUS'], 'min_g_power': 500, 'price': 260},
    {'name': 'Frosch', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'DARKUS', 'VENTUS'], 'min_g_power': 500, 'price': 275},
    {'name': 'Lars Lion', 'allowed_attributes': ['PYRUS', 'AQUOS', 'HAOS'], 'min_g_power': 500, 'price': 260},
    {'name': 'Oberus', 'allowed_attributes': ['AQUOS', 'SUBTERRA', 'DARKUS', 'VENTUS'], 'min_g_power': 500, 'price': 260},
    {'name': 'Naga', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 550, 'price': 340},
    {'name': 'Wavern', 'allowed_attributes': ['PYRUS', 'AQUOS', 'SUBTERRA', 'HAOS', 'DARKUS', 'VENTUS'], 'min_g_power': 550, 'price': 360}
]

RAW_BAKUGAN_TEMPLATES = [
    {
        **entry,
        'min_g_power': int(entry['min_g_power']),
        'max_g_power': int(entry['min_g_power']) + G_POWER_RANGE,
        'price': _priced_bakugan(entry),
    }
    for entry in _RAW_BAKUGAN_TEMPLATES_INPUT
]
