from flask import session, redirect, render_template, request

from main import app

@app.route('/dashboard_rec')
def dashboard_rec():
    return render_template('receptionist/dashboard_rec.html')