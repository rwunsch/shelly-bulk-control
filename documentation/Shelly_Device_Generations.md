# Shelly Device Generations

This document provides a comprehensive overview of Shelly device generations, their technical specifications, and connectivity features.

## Overview of Generations

Shelly devices are categorized into four generations, each with distinct characteristics:

| Generation | API Protocol | Key Features |
|------------|-------------|--------------|
| Gen1 | HTTP, CoAP | Basic Wi-Fi connectivity, CoAP protocol |
| Gen2 | HTTP, RPC | Enhanced Wi-Fi, RPC protocol, scripting support |
| Gen3 | HTTP, RPC | Wi-Fi, Bluetooth, Matter protocol support |
| Gen4 | HTTP, RPC | Wi-Fi, Bluetooth, Zigbee, Matter protocol support |

## Device Generations and Models

### Generation 1 (Gen1)

Gen1 devices use a RESTful HTTP API and CoAP protocol for connectivity.

#### Relays & Plugs

| Device Name | Model Number | Device Type | Connectivity | Features |
|-------------|--------------|-------------|--------------|----------|
| Shelly 1 | SHSW-1 | Relay Switch | Wi-Fi, CoAP | Power monitoring |
| Shelly 1PM | SHSW-PM | Relay with Power Metering | Wi-Fi, CoAP | Power monitoring, eco mode |
| Shelly 1L | SHSW-L | Relay Switch (No Neutral) | Wi-Fi, CoAP | No neutral wire operation |
| Shelly 2.5 | SHSW-25 | Dual Relay with Power Metering | Wi-Fi, CoAP | Power monitoring, roller mode |
| Shelly Plug | SHPLG-1 | Smart Plug | Wi-Fi, CoAP | Power monitoring |
| Shelly Plug S | SHPLG-S | Smart Plug (Compact) | Wi-Fi, CoAP | Power monitoring, eco mode |
| Shelly Plug US | SHPLG-U1 | Smart Plug (US Version) | Wi-Fi, CoAP | Power monitoring, eco mode |

#### Dimmers & Lighting

| Device Name | Model Number | Device Type | Connectivity | Features |
|-------------|--------------|-------------|--------------|----------|
| Shelly Dimmer 2 | SHDM-2 | Dimmer | Wi-Fi, CoAP | Dimming, overheating protection |
| Shelly RGBW2 | SHRGBW2 | RGBW Controller | Wi-Fi, CoAP | Color control |
| Shelly Duo | SHDUO | Smart Bulb | Wi-Fi | Dimming, color temperature |
| Shelly Duo GU10 | SHDUO-GU10 | Smart Bulb (GU10) | Wi-Fi | Dimming, color temperature |
| Shelly Duo RGBW | SHDUO-RGBW | RGBW Smart Bulb | Wi-Fi | Dimming, color control |
| Shelly Vintage | SHVIN | Vintage Smart Bulb | Wi-Fi | Dimming |

#### Sensors & Controllers

| Device Name | Model Number | Device Type | Connectivity | Features |
|-------------|--------------|-------------|--------------|----------|
| Shelly i3 | SHIX3 | Input Controller | Wi-Fi, CoAP | 3 buttons |
| Shelly EM | SHEM | Energy Monitor | Wi-Fi, CoAP | Power & energy monitoring |
| Shelly 3EM | SHEM-3 | 3-Phase Energy Monitor | Wi-Fi, CoAP | Power & energy monitoring |
| Shelly H&T | SHHT-1 | Temperature & Humidity Sensor | Wi-Fi | Battery powered |
| Shelly Flood | SHWT-1 | Water Leak Sensor | Wi-Fi | Water detection, battery powered |
| Shelly Button 1 | SHBTN-1 | Wireless Button | Wi-Fi | Momentary button, battery powered |
| Shelly Door/Window 2 | SHDW-2 | Door/Window Sensor | Wi-Fi | Contact & illumination sensor |
| Shelly Gas | SHGS-1 | Gas Sensor | Wi-Fi | Gas detection, alarm sound |
| Shelly Motion | SHMOS-01 | Motion Sensor | Wi-Fi | Motion & illumination detection |
| Shelly Motion 2 | SHMOS-02 | Motion Sensor (Updated) | Wi-Fi | Motion, illumination & vibration detection |
| Shelly UNI | SHUNI | Universal Module | Wi-Fi, CoAP | Analog/digital I/O |
| Shelly TRV | SHTRV-01 | Thermostatic Radiator Valve | Wi-Fi | Temperature control, battery powered |

### Generation 2 (Gen2)

Gen2 devices use an enhanced HTTP API with RPC (Remote Procedure Call) protocol and offer improved connectivity and scripting support.

#### Relays & Plugs

| Device Name | Model Number | Device Type | Connectivity | Features |
|-------------|--------------|-------------|--------------|----------|
| Shelly Plus 1 | Plus1 | Relay Switch | Wi-Fi, RPC | Scripting |
| Shelly Plus 1 UL | Plus1UL | Relay Switch (UL Certified) | Wi-Fi, RPC | UL certification, scripting |
| Shelly Plus 1PM | Plus1PM | Relay with Power Metering | Wi-Fi, RPC | Power monitoring, eco mode, scripting |
| Shelly Plus 1PM UL | Plus1PMUL | Relay with Power Metering (UL) | Wi-Fi, RPC | UL certification, power monitoring |
| Shelly Plus 2PM | Plus2PM | Dual Relay with Power Metering | Wi-Fi, RPC | Power monitoring, roller mode |
| Shelly Plus 2PM UL | Plus2PMUL | Dual Relay with Power Metering (UL) | Wi-Fi, RPC | UL certification |
| Shelly Plus 4 | Plus4 | 4-Channel Relay | Wi-Fi, RPC | Roller mode, scripting |
| Shelly Plus 4PM | Plus4PM | 4-Channel Relay with Power Metering | Wi-Fi, RPC | Power monitoring, roller mode |
| Shelly Plus Plug | PlusPlug | Smart Plug | Wi-Fi, RPC | Power monitoring, eco mode |
| Shelly Plus Plug S | PlusPlugS | Smart Plug (Compact) | Wi-Fi, RPC | Power monitoring, eco mode |
| Shelly Plus Plug IT | PlusPlugIT | Smart Plug (Italy) | Wi-Fi, RPC | Power monitoring, eco mode |
| Shelly Plus Plug UK | PlusPlugUK | Smart Plug (UK) | Wi-Fi, RPC | Power monitoring, eco mode |
| Shelly Plus Plug US | PlusPlugUS | Smart Plug (US) | Wi-Fi, RPC | Power monitoring, eco mode |
| Shelly Mini 1 | Mini1 | Mini Relay Switch | Wi-Fi, RPC | Compact design, scripting |
| Shelly Mini 1PM | Mini1PM | Mini Relay with Power Metering | Wi-Fi, RPC | Compact design, power monitoring |

#### Controllers & Sensors

| Device Name | Model Number | Device Type | Connectivity | Features |
|-------------|--------------|-------------|--------------|----------|
| Shelly Plus i4 | Plusi4 | Input Controller | Wi-Fi, RPC | 4 inputs, scripting |
| Shelly Plus i4 DC | Plusi4DC | Input Controller (DC) | Wi-Fi, RPC | 4 inputs, DC power, scripting |
| Shelly Plus H&T | PlusHT | Temperature & Humidity Sensor | Wi-Fi, Bluetooth | Temperature & humidity sensing |
| Shelly Plus Smoke | PlusSmoke | Smoke Detector | Wi-Fi | Smoke detection, alarm sound |
| Shelly Plus UNI | PlusUni | Universal Module | Wi-Fi, RPC | Digital I/O, scripting |

#### Lighting & Dimmers

| Device Name | Model Number | Device Type | Connectivity | Features |
|-------------|--------------|-------------|--------------|----------|
| Shelly Plus Wall Dimmer | PlusWallDim | Wall Dimmer | Wi-Fi, RPC | Dimming, wall mounting |
| Shelly Plus 0-10V Dimmer | Plus0-10V | 0-10V Dimmer | Wi-Fi, RPC | 0-10V dimming interface |
| Shelly Plus RGBW PM | PlusRGBWPM | RGBW Controller with Power Metering | Wi-Fi, RPC | Color control, power monitoring |

#### Pro Series (Gen2)

The Pro series offers enhanced reliability with DIN rail mounting options and ethernet connectivity.

| Device Name | Model Number | Device Type | Connectivity | Features |
|-------------|--------------|-------------|--------------|----------|
| Shelly Pro 1 | Pro1 | Professional Relay Switch | Wi-Fi, LAN, RPC | DIN rail mounting |
| Shelly Pro 1PM | Pro1PM | Professional Relay with Power Metering | Wi-Fi, LAN, RPC | Power monitoring, DIN rail mounting |
| Shelly Pro 2 | Pro2 | Professional Dual Relay | Wi-Fi, LAN, RPC | Roller mode, DIN rail mounting |
| Shelly Pro 2PM | Pro2PM | Professional Dual Relay with Power Metering | Wi-Fi, LAN, RPC | Power monitoring, roller mode |
| Shelly Pro 3 | Pro3 | Professional 3-Phase Relay | Wi-Fi, LAN, RPC | 3-phase support, DIN rail mounting |
| Shelly Pro 4PM | Pro4PM | Professional 4-Channel Relay with Power Metering | Wi-Fi, LAN, RPC | Power monitoring, roller mode |
| Shelly Pro EM | ProEM | Professional Energy Monitor | Wi-Fi, LAN, RPC | Power & energy monitoring |
| Shelly Pro 3EM | Pro3EM | Professional 3-Phase Energy Monitor | Wi-Fi, LAN, RPC | 3-phase energy monitoring |
| Shelly Pro 3EM-400 | Pro3EM400 | Professional 3-Phase Energy Monitor (400A) | Wi-Fi, LAN, RPC | 400A current sensing |
| Shelly Pro EM-50 | ProEM50 | Professional Energy Monitor (50A) | Wi-Fi, LAN, RPC | 50A current sensing |
| Shelly Pro 3EM-3CT63 | Pro3EM3CT63 | Professional 3-Phase Energy Monitor (3x63A) | Wi-Fi, LAN, RPC | 3x63A current sensing |
| Shelly Pro Dimmer | ProDimmer | Professional Dimmer | Wi-Fi, LAN, RPC | Dimming, LED control |
| Shelly Pro Dimmer 1PM | ProDim1PM | Professional Dimmer with Power Metering | Wi-Fi, LAN, RPC | Dimming, power monitoring |
| Shelly Pro Dimmer 2PM | ProDim2PM | Professional Dual Dimmer | Wi-Fi, LAN, RPC | Dual dimming channels |
| Shelly Pro Dimmer 0/1-10V PM | ProDim0-10V | Professional 0/1-10V Dimmer | Wi-Fi, LAN, RPC | 0/1-10V dimming interface |
| Shelly Pro RGBWW PM | ProRGBWWPM | Professional RGBWW Controller | Wi-Fi, LAN, RPC | RGB+WW control, power monitoring |
| Shelly Pro Dual Cover/Shutter PM | ProDualCover | Professional Shutter Controller | Wi-Fi, LAN, RPC | Dual shutter control |

#### Pro Mini Series (Gen2)

Compact versions of the Pro series.

| Device Name | Model Number | Device Type | Connectivity | Features |
|-------------|--------------|-------------|--------------|----------|
| Shelly Pro 1PM Mini | Pro1PMMini | Mini Professional Relay with Power Metering | Wi-Fi, LAN, RPC | Compact design, power monitoring |
| Shelly Pro 2PM Mini | Pro2PMMini | Mini Professional Dual Relay | Wi-Fi, LAN, RPC | Compact design, power monitoring |
| Shelly Pro 3 Mini | Pro3Mini | Mini Professional 3-Phase Relay | Wi-Fi, LAN, RPC | Compact design, 3-phase support |
| Shelly Pro 4PM Mini | Pro4PMMini | Mini Professional 4-Channel Relay | Wi-Fi, LAN, RPC | Compact design, power monitoring |
| Shelly Pro EM Mini | ProEMMini | Mini Professional Energy Monitor | Wi-Fi, LAN, RPC | Compact design, energy monitoring |
| Shelly Pro 3EM Mini | Pro3EMMini | Mini Professional 3-Phase Energy Monitor | Wi-Fi, LAN, RPC | Compact design, 3-phase monitoring |
| Shelly Pro Dimmer Mini | ProDimmerMini | Mini Professional Dimmer | Wi-Fi, LAN, RPC | Compact design, dimming |

### Generation 3 (Gen3)

Gen3 devices feature Wi-Fi, Bluetooth, and Matter protocol support for increased smart home ecosystem compatibility.

| Device Name | Model Number | Device Type | Connectivity | Features |
|-------------|--------------|-------------|--------------|----------|
| Shelly 1 Gen3 | S3SW-001X16EU | Relay Switch | Wi-Fi, Bluetooth, Matter | Matter support, scripting |
| Shelly 1PM Gen3 | S3SW-PM-001X16EU | Relay with Power Metering | Wi-Fi, Bluetooth, Matter | Power monitoring, Matter support |
| Shelly 2PM Gen3 | S3SW-2PM-001X16EU | Dual Relay with Power Metering | Wi-Fi, Bluetooth, Matter | Power monitoring, roller mode |
| Shelly i4 Gen3 | S3IX4-001X16EU | Input Controller | Wi-Fi, Bluetooth, Matter | 4 inputs, Matter support |
| Shelly H&T Gen3 | S3HT-001X16EU | Temperature & Humidity Sensor | Wi-Fi, Bluetooth, Matter | Battery powered, Matter support |
| Shelly Dimmer Gen3 | S3DM-001X16EU | Dimmer | Wi-Fi, Bluetooth, Matter | Dimming, Matter support |
| Shelly DALI Dimmer Gen3 | S3DALI-001X16EU | DALI Dimmer | Wi-Fi, Bluetooth, Matter | DALI control, Matter support |
| Shelly Plug S MTR Gen3 | S3PLG-S-001X16EU | Smart Plug with Power Metering | Wi-Fi, Bluetooth, Matter | Power monitoring, Matter support |
| Shelly Outdoor Plug S Gen3 | S3PLG-OUT-001X16EU | Outdoor Smart Plug | Wi-Fi, Bluetooth, Matter | Weather resistant, power monitoring |
| Shelly EM Gen3 | S3EM-001X16EU | Energy Monitor | Wi-Fi, Bluetooth, Matter | Power & energy monitoring |
| Shelly 3EM-63 Gen3 | S3EM-3-001X16EU | 3-Phase Energy Monitor | Wi-Fi, Bluetooth, Matter | 3-phase power monitoring |
| Shelly 1 Mini Gen3 | S3SW-MINI-001X16EU | Mini Relay Switch | Wi-Fi, Bluetooth, Matter | Compact design, Matter support |
| Shelly 1PM Mini Gen3 | S3SW-PM-MINI-001X16EU | Mini Relay with Power Metering | Wi-Fi, Bluetooth, Matter | Compact, power monitoring |

### Generation 4 (Gen4)

Gen4 devices add Zigbee connectivity in addition to Wi-Fi, Bluetooth, and Matter support.

| Device Name | Model Number | Device Type | Connectivity | Features |
|-------------|--------------|-------------|--------------|----------|
| Shelly 1 Gen4 | S4SW-001X16EU | Relay Switch | Wi-Fi, Bluetooth, Zigbee, Matter | Zigbee hub capability |
| Shelly 1PM Gen4 | S4SW-PM-001X16EU | Relay with Power Metering | Wi-Fi, Bluetooth, Zigbee, Matter | Power monitoring, Zigbee hub |
| Shelly 2PM Gen4 | S4SW-2PM-001X16EU | Dual Relay with Power Metering | Wi-Fi, Bluetooth, Zigbee, Matter | Power monitoring, roller mode |
| Shelly 1 Mini Gen4 | S4SW-MINI-001X16EU | Mini Relay Switch | Wi-Fi, Bluetooth, Zigbee, Matter | Compact design, Zigbee hub |
| Shelly 1PM Mini Gen4 | S4SW-PM-MINI-001X16EU | Mini Relay with Power Metering | Wi-Fi, Bluetooth, Zigbee, Matter | Compact, power monitoring |
| Shelly EM Mini Gen4 | S4EM-MINI-001X16EU | Mini Energy Monitor | Wi-Fi, Bluetooth, Zigbee, Matter | Compact, energy monitoring |

## Connectivity Protocols

### HTTP API
All Shelly devices provide a RESTful HTTP API for direct control and configuration.

### CoAP (Gen1)
Constrained Application Protocol - a specialized web transfer protocol for use with constrained nodes and networks, used by Gen1 devices.

### RPC (Gen2, Gen3, Gen4)
Remote Procedure Call protocol - allows for more complex commands and functionality, used by Gen2/Gen3/Gen4 devices.

### Matter (Gen3, Gen4)
A universal connectivity standard for smart home devices, enabling cross-platform compatibility.

### Zigbee (Gen4)
Low-power mesh networking protocol, allowing Gen4 devices to act as Zigbee hubs for other Zigbee devices.

## Device Generation Identification

Shelly devices can be identified by:

1. **Model Number**: Each generation follows specific naming conventions
   - Gen1: Traditional model names (SHSW-1, SHPLG-S, etc.)
   - Gen2: Plus/Pro prefix or suffix (Plus1PM, Pro1, etc.)
   - Gen3: S3 prefix in model number (S3SW-001X16EU)
   - Gen4: S4 prefix in model number (S4SW-001X16EU)

2. **API Endpoints**:
   - Gen1: Uses traditional REST endpoints (/settings, /status)
   - Gen2/Gen3/Gen4: Uses RPC endpoints (/rpc/Shelly.GetConfig, etc.)

## Parameter Discovery and Management

Each generation requires different approaches for parameter discovery:

- **Gen1**: Parameters are extracted from multiple API endpoints including /settings, /status, and device-specific endpoints
- **Gen2/Gen3/Gen4**: Parameters are discovered through the RPC interface, particularly through /rpc/Shelly.GetConfig and /rpc/Shelly.GetStatus

For more details on parameter discovery, refer to [Parameter_Management.md](Parameter_Management.md).

## References

- [Shelly Official Website](https://shelly.cloud)
- [Shelly API Documentation](https://shelly-api-docs.shelly.cloud)
- [Device Configuration](../config/device_types.yaml) 