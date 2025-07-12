![Lawn Manager Banner](./banner.png)
# Lawn Manager - Home Assistant Integration

A comprehensive Home Assistant integration for intelligent lawn care management with weather awareness, seasonal intelligence, and smart notifications.

## 🌟 Features

### Core Functionality
- **Mowing Tracking**: Track last mow date and due dates with customizable intervals
- **Chemical Application Tracking**: Monitor fertilizer, herbicide, and other chemical applications
- **Weather Intelligence**: Smart weather-based recommendations for lawn activities
- **Seasonal Intelligence**: Grass-type aware seasonal recommendations and task management
- **Smart Notifications**: Optional mobile notifications for optimal lawn care timing

### Sensors Created
- **Last Mow Date**: Track when you last mowed
- **Mow Due Status**: Days until/since mowing is due with weather considerations
- **Weather Conditions**: Weather suitability for mowing and chemical applications
- **Seasonal Intelligence**: Comprehensive seasonal lawn care recommendations
- **Chemical Application Sensors**: Individual tracking for each chemical applied

### Services Available
- **Log Mowing**: Record mowing activities
- **Log Chemical Application**: Record chemical applications with rates and methods
- **Delete Chemical**: Remove chemical tracking

## 🚀 Quick Start

### Installation
1. **Download Integration**: Copy all files to `config/custom_components/lawn_manager/`
2. **Restart Home Assistant**
3. **Add Integration**: 
   - Go to Settings > Devices & Services 
   - Click "Add Integration"
   - Search for "Lawn Manager"
   - Click to configure

### Initial Configuration
4. **Basic Setup**:
   - **Yard Zone**: "Front Yard", "Back Yard", etc.
   - **Location**: Your city/state for seasonal intelligence
   - **Mow Interval**: How often you typically mow (7-14 days)
   - **Weather Entity**: Select your weather integration
   - **Grass Type**: Choose your specific grass type

5. **First Use**:
   - Log your last mow date using the service
   - Add any recent chemical applications
   - Check your new sensors in the dashboard

6. **Optional Notifications**: Install notification blueprints for mobile alerts

## 📱 Smart Notifications (Optional)

Get intelligent mobile notifications for optimal lawn care timing!

### Available Blueprints
- **Smart Notifications**: Advanced notifications with weather intelligence and seasonal awareness
- **Basic Notifications**: Simple overdue alerts and good weather notifications

### Notification Types
- 🚨 **Mowing Overdue**: High priority alerts when mowing is overdue
- 🌱 **Good Weather**: Notifications when conditions are perfect for lawn activities
- 🌿 **Chemical Opportunities**: Optimal timing for fertilizer and herbicide applications
- ⛈️ **Weather Alerts**: Rain warnings for recent chemical applications
- 📅 **Seasonal Tasks**: High priority seasonal lawn care reminders
- 🌡️ **Temperature Alerts**: Heat/cold warnings for lawn activities

See [NOTIFICATIONS.md](NOTIFICATIONS.md) for detailed setup instructions.

## 🧠 Seasonal Intelligence

### Grass Type Support
- **Warm Season**: Bermuda, Zoysia, St. Augustine, Centipede
- **Cool Season**: Fescue, Kentucky Bluegrass, Ryegrass, Fine Fescue

### Smart Recommendations
- **Seasonal Mowing Frequency**: Adjusts based on grass type and growing season
- **Chemical Timing**: Seasonal recommendations for pre-emergent, fertilizer, etc.
- **Temperature Warnings**: Heat stress and cold weather alerts
- **Application History**: Smart recommendations based on your actual application history

## 🌦️ Weather Intelligence

### Weather-Based Features
- **Recent Rain Detection**: Checks last 6 hours for rain/high humidity
- **Future Rain Forecasting**: Looks ahead 2-6 hours for rain
- **Drying Time Logic**: Ensures grass is dry before mowing recommendations
- **Chemical-Specific Logic**: Different weather requirements for fertilizers vs herbicides

### Smart Recommendations
- "Good conditions - no rain for 2 days, grass should be dry"
- "Rain expected in 1.2 hours - wait or finish quickly"
- "Light rain expected in 4 hours will help fertilizer absorption"

## 🔧 Configuration

### Basic Setup
- **Yard Zone**: Name for your lawn area
- **Location**: Geographic location for seasonal intelligence
- **Mow Interval**: Default mowing frequency (days)
- **Weather Entity**: Home Assistant weather entity for intelligence
- **Grass Type**: Your specific grass type for seasonal recommendations

### Advanced Features
- **Application Rate Override**: Customize chemical application rates
- **Seasonal Frequency**: Automatic mowing frequency based on growing season
- **Smart Task Reminders**: History-aware chemical application recommendations

## 📊 Example Sensors

### Mow Due Sensor
```yaml
State: 2  # Days since last mow
Attributes:
  last_mow: "2024-01-15"
  days_until_due: -2  # Negative means overdue
  weather_suitable_for_mowing: true
  weather_recommendation: "Good conditions - no rain for 2 days"
  seasonal_recommended_frequency: 7
  seasonal_frequency_reason: "Moderate growing season"
```

### Seasonal Intelligence Sensor
```yaml
State: "Spring - Growing Season"
Attributes:
  grass_type: "Bermuda"
  current_season: "spring"
  growing_season: true
  high_priority_chemicals: ["Pre-emergent"]
  high_priority_tasks: ["Apply pre-emergent herbicide"]
  temperature_warnings: ["Optimal growing conditions"]
```

### Chemical Application Sensor
```yaml
State: 45  # Days since last application
Attributes:
  last_applied: "2024-01-01"
  next_due: "2024-01-31"
  weather_suitable_for_application: true
  weather_recommendation: "Perfect conditions - no rain expected"
```

## 💡 Daily Usage

### Logging Activities
**After Mowing:**
- Use the "Log Mowing" service to record when you mowed
- The system automatically updates due dates and recommendations

**After Chemical Applications:**
- Log fertilizer, herbicide, or other chemical applications
- Include application rates and methods for better tracking
- System provides weather-aware recommendations for future applications

**Check Before Activities:**
- Review weather sensor for current conditions
- Check seasonal sensor for priority tasks
- Use notifications to get proactive alerts

### Dashboard Integration
Add sensors to your Home Assistant dashboard:
- **Mow Due Status**: Shows days until/overdue with weather info
- **Seasonal Intelligence**: Current season and priority tasks
- **Weather Conditions**: Suitability for lawn activities
- **Chemical Trackers**: Days since last application

### Automation Ideas
**Smart Irrigation:**
```yaml
# Turn off sprinklers when mowing is due and weather is good
- alias: "Pause Irrigation for Mowing"
  trigger:
    - platform: state
      entity_id: sensor.lawn_mow_due
  condition:
    - condition: template
      value_template: "{{ states('sensor.lawn_mow_due') | int >= 0 }}"
    - condition: state
      entity_id: sensor.lawn_weather_conditions
      attribute: mowing_suitable
      state: true
  action:
    - service: switch.turn_off
      entity_id: switch.irrigation_system
```

**Smart Lighting:**
```yaml
# Turn on outdoor lights when mowing is overdue (reminder)
- alias: "Mowing Overdue Light Reminder"
  trigger:
    - platform: state
      entity_id: sensor.lawn_mow_due
  condition:
    - condition: template
      value_template: "{{ states('sensor.lawn_mow_due') | int >= 3 }}"
  action:
    - service: light.turn_on
      entity_id: light.outdoor_lights
      data:
        color_name: orange
```

## 🛠️ Services

### Log Mowing
```yaml
service: lawn_manager.log_mowing
data:
  mow_date: "2024-01-15"  # Optional, defaults to today
```

### Log Chemical Application
```yaml
service: lawn_manager.log_chemical_application
data:
  chemical_name: "Fertilizer"
  application_date: "2024-01-15"
  amount_lb_per_1000sqft: 1.5
  rate_multiplier: 1.2
  rate_description: "Heavy feeding"
  method: "Broadcast spreader"
```

### Delete Chemical
```yaml
service: lawn_manager.delete_chemical
data:
  chemical_name: "Old Fertilizer"
```

## 📁 File Structure

```
lawn_manager/
├── __init__.py                           # Integration setup
├── manifest.json                         # Integration metadata
├── config_flow.py                        # Configuration UI
├── const.py                             # Constants and grass type data
├── sensor.py                            # Main sensor logic
├── binary_sensor.py                     # Binary sensors
├── services.py                          # Service implementations
├── services.yaml                        # Service definitions
├── weather_helper.py                    # Weather intelligence
├── seasonal_helper.py                   # Seasonal intelligence
├── blueprints/                          # Optional notification blueprints
│   ├── lawn_manager_notifications.yaml  # Advanced notifications
│   └── lawn_manager_basic_notifications.yaml # Simple notifications
├── NOTIFICATIONS.md                     # Notification setup guide
└── README.md                           # This file
```

## 🔄 Updates and Migration

The integration handles data migration automatically:
- **Storage Updates**: Automatic migration of stored data
- **Sensor Updates**: Graceful handling of new sensor types
- **Backward Compatibility**: Existing data preserved during updates

## ❓ FAQ

**Q: Do I need a weather integration?**
A: Weather integration is optional but highly recommended for intelligent recommendations. Works with any Home Assistant weather entity.

**Q: Can I track multiple lawn areas?**
A: Each integration instance tracks one lawn area. Add multiple instances for different areas (front yard, back yard, etc.).

**Q: What if I don't know my grass type?**
A: The integration defaults to Bermuda grass. You can change it later in the configuration. Check your local extension office for grass identification help.

**Q: How accurate are the seasonal recommendations?**
A: Recommendations are based on general seasonal patterns and your specific grass type. Local conditions may vary - use as a guide along with local expertise.

**Q: Can I use this without notifications?**
A: Absolutely! Notifications are completely optional. The core tracking and intelligence features work independently.

**Q: Does this work with robotic mowers?**
A: Yes! You can log mowing activities manually or integrate with robotic mower automations using the services.

## 🐛 Troubleshooting

### Common Issues
- **Seasonal Features Not Working**: Ensure `seasonal_helper.py` is present
- **Weather Recommendations Empty**: Check weather entity configuration
- **Notifications Not Sending**: Verify mobile app setup and blueprint configuration
- **Sensors Not Updating**: Check Home Assistant logs for errors
- **Wrong Grass Type**: Reconfigure integration to change grass type

### Logs
Check Home Assistant logs for:
- `custom_components.lawn_manager` - Integration logs
- Blueprint automation traces for notification issues

## 🤝 Contributing

Feel free to submit issues and enhancement requests!

## 📄 License

This project is licensed under the MIT License.

---

**Smart lawn care made simple with Home Assistant intelligence!** 🌱 
