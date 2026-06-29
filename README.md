# headless-HERE-TTN
A pair of python scripts that pull and assemble HERE and TTN Traffic and Weather data from nrsc5.
This is designed to be run as a cronjob periodically so you can see weather and traffic on other devices.

For example, the files would be awesome on a Home Assistant dashboard.

(this was vibecoded, but I did my best to clean up the code. sorry.) 

Note: the TTN.py script's map and coordinate logic were adapted from an old commit of KYDronePilot/hdfm.

# Requirements:
- An SDR Dongle (nooelec smart nesdr, rtl-sdr, etc.)
- A working install of nrsc5 (https://github.com/theori-io/nrsc5)
- Python 3
- Pillow
- This assumes you're running some flavor of debian linux

# How to get HERE data:
1. Download here.py to your home directory.
2. Adjust here.py Configurations to your desired frequency, destination path, and time zone.
3. Make sure you're running this on a station that broadcasts HERE data (e.g. Audacy and Bonneville stations.)
4. Run: python3 here.py
5. The program will quit when assembled.

# How to get TTN data:
1. Download the temp folder and ttn.py to your home directory.
2. Adjust ttn.py Configurations to your desired frequency, destination path, and time zone.
3. Make sure you're running this on a station that broadcasts TTN data (e.g. iHeartRadio stations.)
4. Run: python3 ttn.py
5. The program will quit when assembled.

# Want Both?:
1. Follow the steps above
2. Run: python3 here.py && python3 ttn.py
3. The program will quit when assembled.
