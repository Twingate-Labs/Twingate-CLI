import json
import pandas as pd

MINVAL = 0
MAXVAL = 365

def ValidateExpiration(expiration):
    if not expiration.isnumeric():
        return False,"Expiration should be a number between "+str(MINVAL)+" and "+str(MAXVAL)
    
    ExpirationVal = int(expiration)
    if ExpirationVal < 0 or ExpirationVal > 365:
        return False,"Expiration should be a number between "+str(MINVAL)+" and "+str(MAXVAL)
    
    return True,ExpirationVal
