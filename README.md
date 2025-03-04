RPI Temperature collecting and processing unit

Project is under active development, be patient :)

### tl;dr

This repository is an instruction and code at the same time to collect temperature data from Xiaomi Mijia temperature and humidity sensors via Bluetooth LE on a Raspberry Pi 3A+. That Pi shows the collected data on an e-ink Display and pushes the data to an InfluxDB instance on a different machine, which also runs Grafana to show the data as nice graphs.

### Overview

#TODO insert a picture with schematic overview on data being sent
#TODO insert a picture of Pi with Xiaomi temp sensors next to it
#TODO insert a picture of Grafana

### HowTo

(My) hardware bill of materials:
- 3x Xiaomi LYWSD03MMC temperature sensors
- 1x Raspberry Pi 3A+
- 1x [Wavelength e-Paper display 2.13 inch HAT+](https://www.waveshare.com/product/raspberry-pi/displays/e-paper/2.13inch-e-paper-hat-plus.htm) V4
- 1x Acrylic case for RPI 3A+, some screws and a piece of metal to allow it to stand upright

This section is seperated into different steps, as not each step is interesting for everybody:
- Temperature sensors
- Raspberry Pi with e-ink Display
- Data transfer to InfluxDB
- Grafana

#### Temperature sensors
For this project, I got cheap digital Xiaomi temperature monitors, which are Bluetooth Low Energy (BLE) capable. To get the correct devices (there are alternatives to the Xiaomi ones), please check out the [ATC_MiThermometer repository by pvvx](https://github.com/pvvx/ATC_MiThermometer), as not all devices have the same features.

The idea in general is to get rid of the standard firmware and flash a custom one on it, especially to get rid of the vendor lock (Xiaomi App) and to activate the BLE broadcasting.

After you got your

TODO