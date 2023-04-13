import json
import pandas as pd

def ValidateRole(role):
    possible_roles = ["ADMIN","DEVOPS","SUPPORT","MEMBER"]
    if role.upper() in possible_roles:
        return True,role.upper()
    else:
        return False,role