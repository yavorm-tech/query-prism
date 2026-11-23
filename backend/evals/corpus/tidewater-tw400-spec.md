# Tidewater TW-400 — Product Specification

Status: released. Product manager: Ines Calloway. Hardware lead: Daniel Ruiz-Okafor.

## Overview

The Tidewater TW-400 is Halvard's ocean water-quality sensor for aquaculture farms, harbours and research buoys. It replaces the TW-300, adding salinity measurement and a longer battery life. The TW-400 launched in Q3 2026.

## Measurements

| Parameter | Range | Accuracy |
|---|---|---|
| Salinity | 0–70 PSU | ±0.1 PSU |
| Temperature | −5 to 40 °C | ±0.05 °C |
| Dissolved oxygen | 0–50 mg/L | ±1 % of reading |
| Depth (pressure) | 0–200 m | ±0.1 % full scale |

## Physical

- Depth rating: IP68, rated to 200 metres.
- Housing: glass-filled polycarbonate, supplied by Brennick Plastics.
- Weight: 1.9 kg without mounting bracket.
- Dimensions: 340 mm long, 75 mm diameter.

## Power

The TW-400 runs on a replaceable lithium thionyl chloride pack. Battery life is 18 months at the default 15-minute sampling interval, or about 6 months at a 1-minute interval. A low-battery warning is sent when 10 % capacity remains.

## Connectivity

LoRaWAN (EU868 and US915 variants) with a range of up to 15 km over open water. An optional cellular modem (LTE-M) is available as the TW-400C variant.

## Firmware

Firmware 2.4 added over-the-air (OTA) updates and on-device calibration drift detection. Firmware 2.5, planned for Q1 2027, will add adaptive sampling.

## Pricing

List price is €1,450 per unit; the TW-400C cellular variant is €1,690. Volume discounts start at 50 units.

## Calibration and service

Factory calibration is valid for 12 months. Recalibration is done at the Halvard service centre in Gdańsk, with a turnaround of 10 working days.
