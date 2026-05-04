from datetime import date

# Set Date format like: YYYY, MM, DD
# Note that FIND_FIRST_DATE uses START_DATE as default start date
START_DATE = date(1997, 1, 1)
END_DATE = date(2026, 5, 1)

# set to "metric" or "imperial"
UNIT_SYSTEM = "imperial"
# UNIT_SYSTEM = "imperial"

# Automatically find first date where data is logged
FIND_FIRST_DATE = True