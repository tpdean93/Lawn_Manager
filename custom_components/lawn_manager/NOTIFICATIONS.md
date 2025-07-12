# Lawn Manager Smart Notifications

Get intelligent mobile notifications for your lawn care! These optional blueprints integrate with your Lawn Manager sensors to send timely alerts and recommendations.

## 🚀 Quick Start

1. **Copy Blueprint Files**: Copy the blueprint files to your Home Assistant `blueprints/automation/` directory
2. **Import Blueprint**: Go to Settings > Automations & Scenes > Blueprints > Import Blueprint
3. **Configure**: Create an automation from the blueprint and configure your preferences

## 📱 Notification Types

### 🌱 Mowing Notifications
- **Overdue Alerts**: "🚨 Lawn Mowing Overdue!" - High priority alerts when mowing is overdue
- **Good Weather Alerts**: "🌱 Good Day to Mow!" - Notifications when weather is perfect for mowing

### 🌿 Chemical Application Notifications  
- **Fertilizer Opportunities**: "🌿 Good Day to Fertilize!" - When conditions are perfect for fertilizer
- **Herbicide Opportunities**: "🚫 Good Day for Herbicide!" - When conditions are perfect for herbicide
- **Rain Alerts**: "⛈️ Rain Alert" - Warns about rain affecting recent chemical applications

### 📅 Seasonal Task Notifications
- **High Priority Tasks**: Seasonal reminders for critical lawn care tasks
- **Chemical Recommendations**: Seasonal timing for pre-emergent, fertilizer, etc.
- **Temperature Alerts**: "🌡️ Temperature Alert" - Heat/cold warnings

## 🎯 Available Blueprints

### 1. Lawn Manager Smart Notifications (Advanced)
**File**: `blueprints/lawn_manager_notifications.yaml`

**Features**:
- ✅ All notification types
- ✅ Fully customizable timing and thresholds
- ✅ Weather-based intelligence
- ✅ Seasonal task integration
- ✅ Priority-based alerts

**Best For**: Power users who want comprehensive lawn care notifications

### 2. Lawn Manager Basic Notifications (Simple)
**File**: `blueprints/lawn_manager_basic_notifications.yaml`

**Features**:
- ✅ Mowing overdue alerts
- ✅ Good weather notifications
- ✅ Simple setup
- ✅ Essential notifications only

**Best For**: Users who want simple, essential notifications

## ⚙️ Configuration Options

### Smart Notifications (Advanced)
- **Notification Device**: Your mobile device
- **Notification Time**: Daily check time (default: 8:00 AM)
- **Enable/Disable**: Toggle each notification type
- **Overdue Threshold**: Days before urgent alerts (default: 3)
- **Weather Opportunity Threshold**: Days of good weather before alerts (default: 2)

### Basic Notifications (Simple)
- **Notification Device**: Your mobile device  
- **Daily Check Time**: When to check for notifications (default: 8:00 AM)
- **Overdue Alert**: Days before overdue alert (default: 2)

## 📲 Example Notifications

### Mowing Notifications
```
🚨 Lawn Mowing Overdue!
Your lawn is 3 days overdue for mowing.
Good conditions - no rain for 2 days, grass should be dry.
```

```
🌱 Good Day to Mow!
Mowing is due (1 days).
Perfect conditions - no rain expected for 6 hours.
```

### Chemical Notifications
```
🌿 Good Day to Fertilize!
Good conditions for fertilizer - light rain expected in 4 hours will help absorption.
```

```
🚫 Good Day for Herbicide!
Perfect conditions - no rain for 3 days, no rain expected for 24 hours.
```

### Seasonal Notifications
```
📅 Seasonal Lawn Care Reminder
High Priority Tasks: Apply pre-emergent herbicide, Service mower and equipment.
High Priority Chemicals: Pre-emergent, Fertilizer.
```

### Weather Alerts
```
⛈️ Rain Alert - Chemical Application
Rain detected - herbicide applied 2 hours ago may be affected.
```

```
🌡️ Temperature Alert
Very hot - avoid mowing during peak heat (10am-4pm). High heat stress - avoid fertilizer applications.
```

## 🛠️ Installation Steps

### Method 1: Manual Installation
1. Create directory: `config/blueprints/automation/lawn_manager/`
2. Copy blueprint files to this directory
3. Restart Home Assistant
4. Go to Settings > Automations & Scenes > Blueprints
5. Click "Import Blueprint" and select your blueprint

### Method 2: Blueprint URL (if hosted)
1. Go to Settings > Automations & Scenes > Blueprints
2. Click "Import Blueprint"
3. Enter the raw GitHub URL of the blueprint
4. Configure and save

## 🎨 Customization

### Notification Timing
- **Daily Checks**: Set your preferred time for daily notifications
- **Immediate Alerts**: Some notifications trigger immediately on state changes
- **Overdue Thresholds**: Customize when "overdue" alerts trigger

### Message Customization
Edit the blueprint YAML to customize:
- Notification titles and messages
- Emoji usage
- Priority levels
- Tags for grouping notifications

### Advanced Logic
The blueprints use Home Assistant templating to:
- Check weather conditions
- Evaluate sensor states
- Combine multiple data sources
- Provide contextual recommendations

## 🔧 Troubleshooting

### Common Issues

**Notifications Not Sending**:
- Verify mobile app is set up correctly
- Check entity names match your sensors
- Ensure blueprint is enabled

**Wrong Device Name**:
- Check device name in Home Assistant
- Blueprint auto-generates service name from device name
- Spaces become underscores, uppercase becomes lowercase

**Template Errors**:
- Verify all sensor entities exist
- Check entity names in blueprint configuration
- Review Home Assistant logs for template errors

### Testing Notifications
1. Create test automation from blueprint
2. Set notification time to a few minutes in the future
3. Check if notification arrives
4. Review automation traces for debugging

## 🌟 Tips for Best Results

1. **Start Simple**: Begin with basic notifications, then upgrade to smart notifications
2. **Test Thoroughly**: Set up test notifications to verify everything works
3. **Customize Timing**: Adjust notification times to match your schedule
4. **Monitor Performance**: Check that notifications aren't too frequent or annoying
5. **Seasonal Adjustments**: Consider different notification needs by season

## 🔄 Updates and Maintenance

- **Blueprint Updates**: Re-import blueprints when new versions are available
- **Sensor Changes**: Update blueprint configurations if sensor names change
- **Seasonal Tuning**: Adjust thresholds based on your lawn's needs

---

**Need Help?** Check the main Lawn Manager documentation or create an issue in the repository. 
