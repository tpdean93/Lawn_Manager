# Lawn Manager - Home Assistant Integration

A comprehensive Home Assistant integration for intelligent lawn care management with **professional-grade chemical calculations**, **multi-zone tracking**, **equipment management**, **seasonal intelligence**, and **smart notifications**.

## Quick Installation

### Easy Installation via HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tpdean93&repository=Lawn_Manager&category=integration)

**Or manually add via HACS:**
1. Go to HACS → Integrations
2. Click the 3-dot menu → Custom repositories
3. Add: `https://github.com/tpdean93/Lawn_Manager`
4. Category: Integration
5. Install "Lawn Manager"
6. Restart Home Assistant
7. Go to Settings → Devices & Services → Add Integration
8. Search for "Lawn Manager" and configure

### Manual Installation
1. Download the latest release
2. Copy `custom_components/lawn_manager/` to your Home Assistant `custom_components/` directory
3. Restart Home Assistant
4. Add the integration via Settings → Devices & Services

---

## What's New in v1.1.0

### Reconfigure Without Reinstalling
- **Options Flow**: Click "Configure" on any zone to change settings without uninstalling
- **Change Mow Interval**: Update your mowing schedule any time (no reinstall needed!)
- **Change Weather Source**: Switch between weather entities or add AWN weather station
- **Change Grass Type**: Update grass type as needed for accurate seasonal recommendations

### AWN Weather Station Support
- **Ambient Weather Network**: Select your local AWN weather station as the weather source
- **More Accurate Data**: Use hyperlocal weather data from your own weather station
- **Auto-Detection**: AWN entities are automatically discovered and labeled in the setup flow

### Split Controls
- **Mowing Controls**: Activity type, height of cut, and log button grouped together
- **Chemical Controls**: Chemical selection, rate, equipment, and log button grouped separately
- **Calculate Application Rate Button**: Get mixing instructions right from the controls — no dev tools needed

### Custom Chemical Amounts
- **Actual Units**: Specify rates in oz, lb, or ml per 1,000 sq ft (not just percentages)
- **Custom Rate Unit Selector**: Choose between multiplier, oz/1000sqft, lb/1000sqft, or ml/1000sqft
- **Precise Control**: Enter the exact amount from your product label

### Custom Products Inventory
- **My Products**: Add your own chemicals/products with custom rates and intervals
- **Shared Across Zones**: Products are available for all lawn zones
- **Full Details**: Store product type, application rates (liquid & granular), interval, and notes
- **Services**: `add_custom_product`, `list_custom_products`, `delete_custom_product`

### Equipment Maintenance Log
- **Track Maintenance**: Log blade sharpening, oil changes, air filters, spark plugs, and more
- **Cost Tracking**: Optionally record maintenance costs
- **Full History**: View all maintenance activities with `get_maintenance_log` service
- **13 Maintenance Types**: Blade Sharpening, Oil Change, Air Filter, Spark Plug, Belt Replacement, Tire/Wheel Service, Cleaning, Winterization, Spring Prep, Calibration, Nozzle Replacement, General Service, Other

### Unified Activity History
- **All-in-One View**: See mowing, chemical applications, and maintenance in a single sensor
- **Cross-Zone History**: `get_activity_history` service shows activities across all zones
- **Activity History Sensor**: Per-zone sensor with recent activities in the attributes

### Enhanced Seasonal Intelligence
- **Pre-Emergent Timing**: Detailed recommendations based on estimated soil temperature
- **Scalping Recommendations**: When and how to scalp warm-season grass
- **Dethatching Guidance**: Season-specific dethatching recommendations with alternatives
- **Aeration Timing**: Best times to core aerate based on grass type
- **Soil Temperature Estimates**: Calculated from air temperature with seasonal offsets
- **Weather-Based Alerts**: Wind speed warnings for spray drift, humidity for disease risk, heat stress alerts

### Equipment Persistence
- **Shared Equipment**: When adding a new zone, existing equipment is detected and shown
- **Skip or Add More**: Option to use existing equipment or add additional pieces
- **No Duplicate Entry**: Equipment carries across all zones automatically

### Better Date Handling
- **Activity Date**: Renamed from "Application Date" for clarity
- **Back-Date Activities**: Set the date picker to any past date to log historical activities
- **Up to 1 Year Back**: Log activities from up to 365 days ago

### HACS Branding
- **Proper Logo**: 512x512 icon and logo PNG files for HACS integration page
- **Clean Manifest**: Removed non-standard fields for better compatibility

---

## Features

### Professional Chemical Calculations
- **Accurate Application Rates**: Based on manufacturer specifications for 10+ chemicals
- **Equipment-Specific Mixing**: Custom mixing instructions for your exact equipment
- **Kitchen Measurements**: Cups, tablespoons, and teaspoons for easy measuring
- **Water Requirements**: Proper dilution ratios for liquid applications
- **Zone-Based Calculations**: Uses your specific lawn size for precise amounts
- **In-Control Calculator**: Calculate rates directly from the UI with the "Calculate Application Rate" button

### Equipment Management
- **Multi-Step Setup**: Guided configuration flow for zones and equipment
- **Equipment Inventory**: Track sprayers, spreaders, and their capacities
- **Maintenance Logging**: Track blade sharpening, oil changes, and other maintenance
- **Smart Defaults**: Equipment Selection defaults to your actual equipment
- **Multi-Zone Friendly**: Equipment is shared across all lawn zones

### Smart Tracking & Intelligence
- **Mowing Tracking**: Track last mow date and due dates with customizable intervals
- **Chemical Application Tracking**: Monitor fertilizer, herbicide, and other chemical applications
- **Weather Intelligence**: Smart weather-based recommendations for lawn activities
- **Seasonal Intelligence**: Grass-type aware seasonal recommendations and task management
- **Activity History**: Unified history of all lawn care activities per zone
- **Smart Notifications**: Optional mobile notifications for optimal lawn care timing

### Seasonal Intelligence
- **Pre-Emergent Alerts**: Soil temperature-based timing for crabgrass prevention
- **Scalping Guidance**: When to scalp warm-season grass in spring
- **Dethatching Windows**: Best times to dethatch with alternatives
- **Aeration Scheduling**: Season-specific core aeration recommendations
- **Temperature Warnings**: Heat stress, freeze, and wind alerts
- **Disease Risk**: High humidity + warmth = fungal disease warnings

---

## Setup Guide

### 3-Step Configuration Flow

**Step 1: Basic Configuration**
- **Zone Name**: "Front Yard", "Back Yard", etc.
- **Location**: Your city/state for seasonal intelligence
- **Lawn Size**: Square footage for accurate calculations
- **Mowing Schedule**: Human-readable options from "Every 3 days" to "Monthly"
- **Weather Entity**: Select standard weather or AWN weather station
- **Grass Type**: Choose your specific grass type

**Step 2: Equipment Collection**
- Shows existing equipment if any (shared across zones)
- Option to add new equipment or use existing
- **Type**: Sprayer or Spreader
- **Brand**: Any brand name
- **Capacity**: Equipment capacity with units

**Step 3: Confirmation**
- Review all settings and equipment

### Reconfiguring (No Reinstall Needed!)
1. Go to Settings → Devices & Services → Lawn Manager
2. Click "Configure" on any zone
3. Choose what to change: Zone Settings, Weather Source, or Grass Type
4. Save — the integration reloads automatically

---

## Dashboard Setup

### Example Dashboard YAML

Add these entities to your Lovelace dashboard. Replace `{entry_id}` with your zone's entry ID:

```yaml
type: entities
title: Mowing Controls
entities:
  - entity: select.lawn_manager_{entry_id}_activity_type_selection
  - entity: number.lawn_manager_{entry_id}_height_of_cut
  - entity: date.lawn_manager_{entry_id}_application_date
  - entity: button.lawn_manager_{entry_id}_log_mow
```

```yaml
type: entities
title: Chemical Application
entities:
  - entity: select.lawn_manager_{entry_id}_chemical_selection
  - entity: text.lawn_manager_{entry_id}_custom_chemical_name
  - entity: select.lawn_manager_{entry_id}_application_rate
  - entity: select.lawn_manager_{entry_id}_custom_rate_unit
  - entity: text.lawn_manager_{entry_id}_custom_rate_multiplier
  - entity: select.lawn_manager_{entry_id}_equipment_select
  - entity: button.lawn_manager_{entry_id}_log_chemical
  - entity: button.lawn_manager_{entry_id}_calculate_rate
```

```yaml
type: entities
title: Zone Status
entities:
  - entity: sensor.{zone_name}_last_lawn_activity
  - entity: sensor.{zone_name}_mow_due_date
  - entity: binary_sensor.{zone_name}_needs_mowing
  - entity: sensor.{zone_name}_weather_conditions
  - entity: sensor.{zone_name}_seasonal_intelligence
  - entity: sensor.{zone_name}_activity_history
  - entity: sensor.{zone_name}_equipment_inventory
  - entity: sensor.{zone_name}_application_rate_calculator
```

---

## Chemical Application Calculator

### Supported Chemicals

| Chemical | Liquid Rate (Sprayer) | Granular Rate (Spreader) | Notes |
|----------|----------------------|-------------------------|-------|
| **Fertilizer 10-10-10** | - | 10 lbs per 1,000 sq ft | Granular only |
| **T-Nex / PGR** | 0.375 oz per 1,000 sq ft | - | Liquid only |
| **Weed Preventer** | 0.185 oz per 1,000 sq ft | 3.5 lbs per 1,000 sq ft | Pre-emergent |
| **Iron Supplement** | 2 oz per 1,000 sq ft | 0.75 lbs per 1,000 sq ft | 2 oz/gal water |
| **Disease Preventer** | 1.5 oz per 1,000 sq ft | - | Liquid only |
| **Insecticide** | 0.75 oz per 1,000 sq ft | 3.0 lbs per 1,000 sq ft | Broad spectrum |
| **Soil Conditioner** | 3.0 oz per 1,000 sq ft | 2.0 lbs per 1,000 sq ft | Humic acid |
| **Urea** | 1.2 oz per 1,000 sq ft | 1.6 lbs per 1,000 sq ft | 46-0-0 nitrogen |
| **Grub Killer** | - | 3.0 lbs per 1,000 sq ft | Curative |

### Kitchen Measurements

Get mixing instructions in kitchen-friendly measurements:

```
Example (T-Nex, 5,000 sq ft, 4-gallon sprayer):
  Total needed: 1.875 oz (3.8 tbsp)
  Mix 1.0 oz per 4-gallon tank (2.0 tbsp or 1/8 cup)
  Per gallon: 0.25 oz (0.5 tbsp per gallon)
```

---

## Services Reference

### Core Services
```yaml
# Log mowing / lawn activity
service: lawn_manager.log_lawn_activity
data:
  zone: <config_entry_id>
  cut_type: "Regular Maintenance"
  height_of_cut: 2.5
  application_date: "2026-02-15"  # Back-date up to 1 year

# Log chemical application
service: lawn_manager.log_application
data:
  chemical_select: "Fertilizer 10-10-10"
  method: "Sprayer"
  rate_override: "Custom"
  custom_rate: "2.5"
  custom_rate_unit: "oz per 1,000 sq ft"
  application_date: "2026-02-15"

# Calculate application rates (from controls button or dev tools)
service: lawn_manager.calculate_application_rate
data:
  chemical: "T-Nex / PGR"
  equipment_name: "Ryobi 4 gallon Sprayer"
  zone: "Front Yard"
```

### Custom Products Inventory
```yaml
# Add a custom product
service: lawn_manager.add_custom_product
data:
  product_name: "Milorganite 6-4-0"
  product_type: "fertilizer"
  rate_lb_per_1000sqft: 8.0
  interval_days: 45
  application_method: "spreader"
  notes: "Organic slow-release nitrogen"

# List all custom products
service: lawn_manager.list_custom_products

# Delete a custom product
service: lawn_manager.delete_custom_product
data:
  product_id: "abc12345"
```

### Equipment Maintenance
```yaml
# Log maintenance
service: lawn_manager.log_maintenance
data:
  equipment_name: "Ryobi 4 gallon Sprayer"
  maintenance_type: "Nozzle Replacement"
  notes: "Replaced with TeeJet XR11002"
  cost: 12.50

# View maintenance log
service: lawn_manager.get_maintenance_log
data:
  equipment_name: "Ryobi 4 gallon Sprayer"  # Optional filter
```

### Activity History
```yaml
# Get unified history across all zones
service: lawn_manager.get_activity_history
```

### Equipment Services
```yaml
service: lawn_manager.add_equipment
data:
  equipment_type: "sprayer"
  brand: "Ryobi"
  capacity: 4
  capacity_unit: "gallons"

service: lawn_manager.get_equipment_options
service: lawn_manager.get_zone_options
service: lawn_manager.list_calculation_options
service: lawn_manager.delete_equipment
service: lawn_manager.refresh_equipment_entity
service: lawn_manager.reload
```

---

## Smart Notifications (Optional)

Get intelligent mobile notifications for optimal lawn care timing!

### Available Blueprints
- **Smart Notifications**: Advanced notifications with weather intelligence and seasonal awareness
- **Basic Notifications**: Simple overdue alerts and good weather notifications

### Notification Types
- **Mowing Overdue**: High priority alerts when mowing is overdue
- **Good Weather**: Notifications when conditions are perfect for lawn activities
- **Chemical Opportunities**: Optimal timing for fertilizer and herbicide applications
- **Weather Alerts**: Rain warnings for recent chemical applications
- **Seasonal Tasks**: High priority seasonal lawn care reminders
- **Temperature Alerts**: Heat/cold warnings for lawn activities

See [NOTIFICATIONS.md](custom_components/lawn_manager/NOTIFICATIONS.md) for detailed setup instructions.

---

## Grass Type Support

### Warm Season
Bermuda, Zoysia, St. Augustine, Centipede

### Cool Season
Fescue, Kentucky Bluegrass, Ryegrass, Fine Fescue

### Custom
Enter any grass type with warm, cool, or transition zone classification.

---

## Weather Intelligence

- **Recent Rain Detection**: Checks for rain and high humidity
- **Future Rain Forecasting**: Looks ahead for rain in the forecast
- **Drying Time Logic**: Ensures grass is dry before mowing recommendations
- **Chemical-Specific Logic**: Different weather requirements for fertilizers vs herbicides
- **Wind Speed Warnings**: Spray drift alerts for windy conditions
- **AWN Support**: Use your local Ambient Weather Network station for hyperlocal data

---

## Troubleshooting

### Common Issues
- **Logo Not Showing**: Restart Home Assistant after installation
- **Equipment Not Showing**: Reload integration after adding equipment via service
- **Can't Change Mow Interval**: Use the "Configure" button on the integration (no reinstall needed!)
- **Chemical Calculations Showing Zero**: Ensure equipment type matches (Sprayer for liquids, Spreader for granular)
- **AWN Not Listed**: Ensure your AWN integration is set up and entities are available in HA
- **Services Not Updating**: Restart Home Assistant after initial setup

### Logs
Check Home Assistant logs for: `custom_components.lawn_manager`

---

## File Structure

```
lawn_manager/
├── __init__.py              # Integration setup, services, options flow support
├── manifest.json            # Integration metadata (v1.1.0)
├── config_flow.py           # 3-step config + options flow for reconfiguring
├── const.py                 # Chemical rates, grass types, constants
├── sensor.py                # Sensors (mow, chemical, weather, seasonal, history, rate calc)
├── binary_sensor.py         # Binary sensor (needs mowing)
├── button.py                # Buttons (log mow, log chemical, calculate rate)
├── select.py                # Select entities (activity type, chemical, equipment, rate)
├── text.py                  # Text entities (custom chemical name, custom rate)
├── number.py                # Number entities (height of cut)
├── date.py                  # Date entities (activity date for back-dating)
├── services.py              # All service implementations
├── services.yaml            # Service definitions (17 services)
├── weather_helper.py        # Weather intelligence + AWN support
├── seasonal_helper.py       # Seasonal intelligence (pre-emergent, scalp, dethatch, aerate)
├── icon.png                 # Integration icon (512x512)
├── logo.png                 # Integration logo (512x512)
├── hacs.json                # HACS configuration
├── translations/en.json     # UI translations (config + options flow)
├── blueprints/              # Notification blueprints
│   ├── lawn_manager_notifications.yaml
│   └── lawn_manager_basic_notifications.yaml
└── NOTIFICATIONS.md         # Notification setup guide
```

---

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License.

---

**Professional lawn care made simple with Home Assistant intelligence!**
