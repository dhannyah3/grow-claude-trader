from growwapi import GrowwAPI
from config import config

groww = GrowwAPI(config.GROWW_ACCESS_TOKEN)

print("Ready to Grow!")

profile = groww.get_user_profile()

print(profile)
