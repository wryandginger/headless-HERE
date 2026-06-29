# headless-HERE-TTN
A set of python scripts that pull and assemble HERE and TTN Traffic and Weather data from nrsc5.
This is designed to be run as a cronjob periodically so you can see weather and traffic on a Home Assistant dashboard.

(This was vibecoded, but I did my best to clean up the code. Sorry.) 

Note: the TTN.py map and coordinate logic were adapted from an old release of [KYDronePilot/hdfm](https://github.com/KYDronePilot/hdfm), which is licensed under GPL-3.

# Requirements:
- An SDR Dongle (nooelec smart nesdr, rtl-sdr, etc.)
- A working install of [nrsc5](https://github.com/theori-io/nrsc5)
- Python 3
- Pillow
- A server running debian linux
- An installation of Home Assistant with Samba access

# What's included:
- [TTN.py](https://github.com/wryandginger/headless-HERE-TTN/blob/main/ttn.py)  - Runs nrsc5 for up to 5 minutes while the TTN weather and traffice data is received by your SDR. Once the files are received, nrsc5 stops and final images are assembled in ~/outputs/ttn
- [gif_ttn.py](https://github.com/wryandginger/headless-HERE-TTN/blob/main/gif_ttn.py) - Takes the TTN files located in ~/outputs/ttn and:
   1. Makes a copy of the weather image and saves it in ~/outputs/ttn/gif
   2. It creates a gif from the last 15 radar images
   3. Uploads the TTN traffic, weather, and gif to /config/www/ttn on your Home Assistant instance
   4. Cleans up / deletes the files you uploaded from the server
- [HERE.py](https://github.com/wryandginger/headless-HERE-TTN/blob/main/here.py)  - Runs nrsc5 for up to 5 minutes while the HERE weather and traffice data is received by your SDR. Once the files are received, nrsc5 stops and final images are assembled in ~/outputs/here
- [gif_here.py](https://github.com/wryandginger/headless-HERE-TTN/blob/main/gif_here.py) - Takes the here files located in ~/outputs/here and:
   1. Makes a copy of the weather image and saves it in ~/outputs/here/gif
   2. It creates a gif from the last 15 radar images
   3. Uploads the TTN traffic, weather, and gif to /config/www/here on your Home Assistant instance
   4. Cleans up / deletes the files you uploaded from the server
- [ttnhere.sh](https://github.com/wryandginger/headless-HERE-TTN/blob/main/ttnhere.sh)  - A bash script that first runs the TTN and then the HERE python files, takes a break and then restarts in an endless loop.


# How To Install and Run
1. Download the contents of this repo to the home directory of your linux install
2. Edit ttn.py and/or here.py for your desired frequency and timezone. (This is automatically configured for Seattle, WA)
   - ttn.py requires tuning to an iHeartRadio station (95.7 MHz or 106.1 MHz in Seattle)
   - here.py requires tuning to an Audacy station (99.9 MHz or 100.7 in Seattle) or Bonneville station (97.3 MHz in Seattle)
4. Edit gif_ttn.py and/or for the IP and Samba credentials of your Home Assistant Image
5. Edit the ttnhere.sh script so it directs to the correct home directory
6. Optionally, you can disable TTN or HERE data in the ttnhere.sh file if you want to exclude one data source.
7. Run crontab -e (not as root) and add the following to the bottom:
```
@reboot /bin/bash /home/USER/ttnhere.sh > /dev/null 2>&1
```
7. To be safe, make sure you have a ttn and here folder inside /config/www on your Home Assistant installation.
8. Reboot your server and the ttnhere.sh script should collect the Traffic and Weather data every 5 minutes.
