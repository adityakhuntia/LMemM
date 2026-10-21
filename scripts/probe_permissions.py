"""Fresh-process screen permission probe; never prompts."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from permissions import screen_allowed_here
if __name__=='__main__':print(int(screen_allowed_here()))
