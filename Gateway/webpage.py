from flask import Flask, render_template, request
from markupsafe import escape

import os
import json
import datetime
import time

app = Flask(__name__)
time_in_air = 1.5

@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if request.form.get('turn_on') == 'ON':
            # pump_state = 'on'
            os.system("bash -c 'echo turn_on >/dev/tcp/127.0.0.1/2137'")
        elif  request.form.get('turn_off') == 'OFF':
            # pump_state = 'off'
            os.system("bash -c 'echo turn_off >/dev/tcp/127.0.0.1/2137'")
        time.sleep(time_in_air)
    
    try:
        with open("exchange.json", "r") as f:
            message = json.loads(f.readline())[-1]
            pump_state = message["data"]["status"]
            overpressure = message["data"]["overpressure"]
            below_level = message["data"]["below_level"]
    except:
        pump_state = False
        overpressure = False
        below_level = False
    
    return render_template("index.html", state=pump_state, overpressure=overpressure, below_level=below_level)

@app.route("/info", methods=['GET', 'POST'])
def info():
    global time_in_air
    if request.method == 'POST':
        if request.form.get('kasowanie') == 'kasowanie':
            # pump_state = 'on'
            os.system("bash -c 'echo [] > /home/pi/Pompa/exchange.json'")
        elif request.form.get('get_info') == 'Get status':
            os.system(f"bash -c 'echo get_info >/dev/tcp/127.0.0.1/2137'")
        time.sleep(time_in_air)
        
    try:
        with open("exchange.json", "r") as f:
            messages = json.loads(f.readline())
    except:
        messages = [{"time" : None, "data" : None}]
        
    return render_template("info.html", messages=reversed(messages))
    #get pump status info
    
@app.route("/send/<command>", methods=['GET', 'POST'])
def send_command(command):
    os.system(f"bash -c 'echo {escape(command)} >/dev/tcp/127.0.0.1/2137'")
    return f"Command {escape(command)} has been sent"
    #get pump status info

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)