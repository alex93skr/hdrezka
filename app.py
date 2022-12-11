from flask import Flask, redirect

from hdrezka import Checker_timer, Appdata, Updater

app = Flask(__name__)

checker_timer = Checker_timer()
checker_timer.start()
# checker_timer.join()


@app.route('/', methods=['GET'])
def index():
    # return render_template()
    # return redirect('http://hdrezkahffrtq.net', code, response = None)
    return redirect(Appdata.REZKA_URL)


@app.route('/up', methods=['GET'])
def update():
    updater = Updater()
    updater.start()
    updater.go()
    updater.join()
    return redirect(Appdata.REZKA_URL)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
