from flask import Flask, render_template
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('login.html')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5055))
    set
    app.run(debug=True, port=port)