from FiinQuantX import FiinSession
from .config import CFG

def get_client():
    assert CFG.fiin_user and CFG.fiin_pass, "Missing FIIN_USER/FIIN_PASS"
    return FiinSession(username=CFG.fiin_user, password=CFG.fiin_pass).login()
