import webbrowser
from app import create_app
from app.utils import data_path

app = create_app()

if __name__ == "__main__":
    webbrowser.open("http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=False)
