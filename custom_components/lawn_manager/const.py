DOMAIN = "lawn_manager"

CONF_NAME = "name"
CONF_LOCATION = "location"
CONF_GRASS_TYPE = "grass_type"
CONF_MOW_INTERVAL = "mow_interval"

DEFAULT_NAME = "Lawn Manager"
DEFAULT_MOW_INTERVAL = 7

# STORAGE_KEY = "lawn_manager_data" # OLD - shared across all zones
# Now we need zone-specific storage - use get_storage_key(entry_id) function instead
EQUIPMENT_STORAGE_KEY = "lawn_manager_equipment"
STORAGE_VERSION = 1

# Equipment management constants
EQUIPMENT_TYPES = ["sprayer", "spreader"]
EQUIPMENT_BRANDS = ["Chapin", "Solo", "Echo", "Husqvarna", "Craftsman", "Ryobi", "Scott's", "Earthway", "Agri-Fab", "Other"]
CAPACITY_UNITS = ["gallons", "liters", "pounds", "kg"]

GRASS_TYPES = {
    "Bermuda": {"season": "warm", "peak_months": [5, 6, 7, 8, 9], "dormant_months": [11, 12, 1, 2]},
    "Zoysia": {"season": "warm", "peak_months": [5, 6, 7, 8, 9], "dormant_months": [11, 12, 1, 2]},
    "St. Augustine": {"season": "warm", "peak_months": [4, 5, 6, 7, 8, 9], "dormant_months": [12, 1, 2]},
    "Centipede": {"season": "warm", "peak_months": [5, 6, 7, 8, 9], "dormant_months": [11, 12, 1, 2]},
    "Fescue": {"season": "cool", "peak_months": [3, 4, 5, 9, 10, 11], "dormant_months": [7, 8]},
    "Kentucky Bluegrass": {"season": "cool", "peak_months": [3, 4, 5, 9, 10, 11], "dormant_months": [7, 8]},
    "Ryegrass": {"season": "cool", "peak_months": [3, 4, 5, 9, 10, 11], "dormant_months": [7, 8]},
    "Fine Fescue": {"season": "cool", "peak_months": [3, 4, 5, 9, 10, 11], "dormant_months": [7, 8]},
}

# For backward compatibility
GRASS_TYPE_LIST = list(GRASS_TYPES.keys())

def get_storage_key(entry_id: str) -> str:
    """Get zone-specific storage key to ensure proper zone isolation."""
    return f"lawn_manager_data_{entry_id}"

CHEMICALS = {
    "Fertilizer 10-10-10": {
        "interval_days": 30,
        "amount_lb_per_1000sqft": 10.0,  # 10 lbs per 1,000 sq ft for 1 lb N
        "notes": "10% nitrogen - apply via spreader"
    },
    "Weed Preventer": {
        "interval_days": 90,
        "amount_lb_per_1000sqft": 3.5,  # 3-4 lbs granular per 1,000 sq ft
        "liquid_oz_per_1000sqft": 0.185,  # 0.185 oz of 65% WDG per 1,000 sq ft
        "notes": "Pre-emergent (Prodiamine) - timing critical for weed control"
    },
    "Grub Killer": {
        "interval_days": 180,
        "amount_lb_per_1000sqft": 3.0,  # 2-4 lbs curative (Dylox) per 1,000 sq ft
        "preventative_grams_per_1000sqft": 4.5,  # 3-6 grams Imidacloprid per 1,000 sq ft
        "notes": "Imidacloprid = early summer prevention; Dylox = curative (active grubs)"
    },
    "Iron Supplement": {
        "interval_days": 45,
        "amount_lb_per_1000sqft": 0.75,  # 0.5-1 lb granular per 1,000 sq ft
        "liquid_oz_per_1000sqft": 2.0,  # 2 oz per 1,000 sq ft (adjusted)
        "water_gal_per_1000sqft": 1.0,  # 1 gallon water per 1,000 sq ft for 2 oz/gal ratio
        "notes": "Chelated Iron or Ferrous Sulfate - 2 oz per gallon water"
    },
    "Urea": {
        "interval_days": 30,
        "amount_lb_per_1000sqft": 1.6,  # 1-2.2 lbs for 0.5-1 lb N (46% N)
        "notes": "46-0-0 nitrogen - 2.2 lbs Urea = 1 lb nitrogen"
    },
    "T-Nex / PGR": {
        "interval_days": 24,  # Every 3-4 weeks
        "liquid_oz_per_1000sqft": 0.375,  # Adjusted for better mixing ratio
        "water_gal_per_1000sqft": 1.5,  # 1-2 gallons water per 1,000 sq ft
        "notes": "Trinexapac-ethyl - rate depends on grass height & mowing frequency"
    },
    "Disease Preventer": {
        "interval_days": 30,
        "liquid_oz_per_1000sqft": 1.5,  # 1-2 oz Propiconazole per 1,000 sq ft
        "water_gal_per_1000sqft": 1.0,  # 1 gallon water per 1,000 sq ft
        "azoxystrobin_oz_per_1000sqft": 0.58,  # 0.38-0.77 oz per 1,000 sq ft
        "notes": "Propiconazole or Azoxystrobin - timing and temperature sensitive"
    },
    "Soil Conditioner": {
        "interval_days": 60,
        "amount_lb_per_1000sqft": 2.0,  # 1-3 lbs granular per 1,000 sq ft
        "liquid_oz_per_1000sqft": 3.0,  # 3 oz per 1,000 sq ft (adjusted)
        "water_gal_per_1000sqft": 2.0,  # 2 gallons water per 1,000 sq ft
        "notes": "Humic Acid, Seaweed Extract - improves soil structure"
    },
    "Insecticide": {
        "interval_days": 120,
        "amount_lb_per_1000sqft": 3.0,  # 2-4 lbs granular per 1,000 sq ft
        "liquid_oz_per_1000sqft": 0.75,  # 0.5-1 oz liquid per 1,000 sq ft
        "notes": "Bifenthrin - broad spectrum insect control"
    }
}

# amount_lb_per_1000sqft refers to how many pounds of product are applied to 1,000 square feet.
# Example: 1.0 lb/1000 sqft ≈ 16 ounces of product per 1000 sqft.
