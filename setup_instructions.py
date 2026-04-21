import os
import sys

# Define instructions
instruction_text = """
=========================================================
INTELLIGENT FALL DETECTION SYSTEM - MANUAL SETUP GUIDE
=========================================================

Since you selected Option B (Native Windows Setup), you need to manually install the following two services on your PC:

1. Mosquitto MQTT Broker:
   - Download: https://mosquitto.org/download/
   - Install using the Windows Installer (.exe).
   - Once installed, open your Windows Services app (services.msc), find "Mosquitto Broker", and ensure it is "Running".

2. PostgreSQL Database:
   - Download: https://www.postgresql.org/download/windows/
   - Install using the Windows Installer.
   - Note the password you set for the 'postgres' user!
   - (Optional) Install the TimescaleDB extension for Windows if you need massive scaling. Otherwise, standard Postgres works fine for the prototype.

=========================================================
NEXT STEPS ONCE INSTALLED:
=========================================================

1. Open 'pgAdmin' (it comes with the PostgreSQL installation).
2. Create a new Database named 'falldetection'.
3. Open the Query Tool on 'falldetection'.
4. Copy and paste the contents of `backend\\db_schema.sql` into the Query Tool and run it.

After doing this, the Core Backend and Dashboard will be fully operational natively!
"""

print(instruction_text)
