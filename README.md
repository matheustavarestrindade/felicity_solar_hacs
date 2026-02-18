# ☀️ Felicity Solar for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)

A custom integration for Home Assistant to monitor your Felicity Solar setup. This integration securely connects to the Shine Felicity Solar API to fetch real-time data for your High Frequency Inverters and Lithium Battery Packs, automatically creating native Home Assistant sensors and supporting the built-in Energy Dashboard.

> **Note:** This integration was _VibeTranslated_ to Python directly from my original NodeJS FelicityAPI implementation! ⚡️

## ✨ Features

- **UI Configuration:** Easy setup via the Home Assistant UI (no YAML required).
- **Auto-Discovery:** Automatically detects all registered Inverters and Batteries tied to your account.
- **Inverter Sensors:** AC Input/Output, PV Voltage/Power, Load Percentage, Temperatures, and more.
- **Battery Sensors:** State of Charge (SOC), State of Health (SOH), Voltage, Current, and Rated Energy.
- **Energy Dashboard Ready:** Includes `total_increasing` energy sensors (Energy PV Today, Load Today, Total Energy) ready to be plugged directly into the HA Energy Dashboard.

## 🛠️ Installation

### Method 1: HACS (Recommended)

1. Open Home Assistant and go to **HACS**.
2. Click on the three dots in the top right corner and select **Custom repositories**.
3. Paste the URL of this repository into the repository field.
4. Select **Integration** as the category and click **Add**.
5. Click on **Felicity Solar** in the HACS integrations list and click **Download**.
6. **Restart Home Assistant**.

### Method 2: Manual

1. Download the latest release from this repository.
2. Copy the `custom_components/felicity_solar` folder into your Home Assistant `/config/custom_components/` directory.
3. **Restart Home Assistant**.

## ⚙️ Configuration

1. In Home Assistant, go to **Settings** > **Devices & Services**.
2. Click the **+ Add Integration** button in the bottom right.
3. Search for **Felicity Solar**.
4. Enter your Shine Felicity Solar login credentials (Email and Password).
5. The integration will authenticate, extract the necessary security keys, and automatically pull your devices!

## 👨‍💻 Author & Credits

Created and maintained by **Matheus Trindade**.

- **GitHub:** [@matheustavarestrindade](https://github.com/matheustavarestrindade)
- **LinkedIn:** [Matheus Tavares Trindade](https://www.linkedin.com/in/matheus-tavares-trindade/)
- **Website:** [matheustavarestrindade.com](https://matheustavarestrindade.com)

If you find this integration helpful, feel free to reach out or contribute to the repository!
