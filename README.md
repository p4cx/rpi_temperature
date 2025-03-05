RPI Temperature collecting and processing unit

Project is under active development, be patient :)

### tl;dr

This repository is an instruction and code at the same time to collect temperature data from Xiaomi Mijia temperature and humidity sensors via Bluetooth LE on a Raspberry Pi 3A+. That Pi shows the collected data on an e-ink Display and pushes the data to an InfluxDB instance on a different machine, which also runs Grafana to show the data as nice graphs.

### Overview

#TODO insert a picture with schematic overview on data being sent
#TODO insert a picture of Pi with Xiaomi temp sensors next to it
#TODO insert a picture of Grafana

# HowTo

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

## Temperature sensors
For this project, I got cheap digital Xiaomi temperature monitors, which are Bluetooth Low Energy (BLE) capable. To get the correct devices (there are alternatives to the Xiaomi ones), please check out the [ATC_MiThermometer repository by pvvx](https://github.com/pvvx/ATC_MiThermometer), as not all devices have the same features.

The idea in general is to get rid of the standard firmware and flash a custom one on it, especially to get rid of the vendor lock (Xiaomi App) and to activate the BLE broadcasting.

After you got your

TODO

## Raspberry Pi with e-ink Display

### Operating system
I have used the Raspberry Pi image creation tool (which I actually can recommend). To get it, just install it on your machine: ´sudo apt install rpi-imager´. I used the [Raspberry Pi OS Lite 64bit image based on Debian Bookworm](https://www.raspberrypi.com/software/operating-systems/#raspberry-pi-os-64-bit). In the setup you can already enter your wifi data and also activate SSH.

### e-Paper display
The vendor of the display does provide a [small test program](https://github.com/waveshareteam/e-Paper/blob/master/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epd2in13_V4.py) to test if the display works properly. That test program can be used, but it is not mandatory for this project.

The following steps are necessary:
- [activate SPI on RPI with ´raspi_config´](https://www.raspberrypi.com/documentation/computers/configuration.html) to activate the communication pipeline between the display board and the RPi.

### Code
Check out the code in your user directory of your RPi, set up a virtual environment and install the needed requirements:
git clone https://github.com/p4cx/rpi_temperature.git
python3 -m venv venv
pip3 install -r requirements.txt

On my machine it used Python 3.11.2, I did not updated the installed version from Raspberry Pi OS. 



Initial setup repository
- git clone


pip3 install -r requirements.txt 


requirements.txt maybe
pillow==11.1.0
RPi.GPIO==0.7.1
spidev==3.6
waveshare-epaper==1.3.0


Setup service to have the code automatically updated on each startup and the python program started afterwards

sudo cp ./service/update_rpi_temperature.service /etc/systemd/user/




The FontStruction “Boxy Bold” (https://fontstruct.com/fontstructions/show/855993) by “william.thompsonj” is licensed under a Creative Commons Attribution license (http://creativecommons.org/licenses/by/3.0/).
[ancestry]

