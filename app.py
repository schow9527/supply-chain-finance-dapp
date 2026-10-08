"""
Root entrypoint for Render and local quick start.
Delegates to backend application factory.
"""
from backend.app import app

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
