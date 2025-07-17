DOMAIN = "lawn_manager"

CONF_NAME = "name"
CONF_LOCATION = "location"
CONF_GRASS_TYPE = "grass_type"
CONF_MOW_INTERVAL = "mow_interval"

DEFAULT_NAME = "Lawn Manager"
DEFAULT_MOW_INTERVAL = 7

STORAGE_KEY = "lawn_manager_data"
STORAGE_VERSION = 1

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

CHEMICALS = {
    "Fertilizer 10-10-10": {
        "interval_days": 30,
        "amount_lb_per_1000sqft": 1.0
    },
    "Weed Preventer": {
        "interval_days": 90,
        "amount_lb_per_1000sqft": 2.0
    },
    "Grub Killer": {
        "interval_days": 180,
        "amount_lb_per_1000sqft": 2.5
    },
    "Iron Supplement": {
        "interval_days": 45,
        "amount_lb_per_1000sqft": 0.5
    },
    "Urea": {
        "interval_days": 30,
        "amount_lb_per_1000sqft": 0.75
    },
    "T-Nex / PGR": {
        "interval_days": 21,
        "amount_lb_per_1000sqft": 0.0
    },
    "Disease Preventer": {
        "interval_days": 30,
        "amount_lb_per_1000sqft": 1.0
    },
    "Soil Conditioner": {
        "interval_days": 60,
        "amount_lb_per_1000sqft": 1.0
    },
    "Insecticide": {
        "interval_days": 120,
        "amount_lb_per_1000sqft": 1.5
    }
}

# amount_lb_per_1000sqft refers to how many pounds of product are applied to 1,000 square feet.
# Example: 1.0 lb/1000 sqft ≈ 16 ounces of product per 1000 sqft.
