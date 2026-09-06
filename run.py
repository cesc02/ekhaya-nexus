import sys
import os
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)
from app import app

if __name__ == "__main__":
    # Render injects $PORT; fall back to CLI arg, then 5000.
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 5000))
    ssl = None
    if "--https" in sys.argv:
        ssl = (os.path.join(BASE, "cert.pem"), os.path.join(BASE, "key.pem"))
    app.run(debug=False, host="0.0.0.0", port=port, ssl_context=ssl)