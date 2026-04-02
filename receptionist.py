from flask import session, redirect, render_template, request

from main import app

@app.route('/dashboard_rec')
def dashboard_rec():
    return render_template('receptionist/dashboard_rec.html')

@app.route('/rooms_layout_rec')
def rooms_layout_rec():
    return render_template('receptionist/rooms_layout_rec.html')

@app.route('/rooms_assign_rec')
def rooms_assign_rec():
    return render_template('receptionist/rooms_assign_rec.html')

@app.route('/checkin_rec')
def checkin_rec():
    return render_template('receptionist/checkin_rec.html')

@app.route('/checkout_rec')
def checkout_rec():
    return render_template('receptionist/checkout_rec.html')

@app.route('/services_manage_rec')
def services_manage_rec():
    return render_template('receptionist/services_manage_rec.html')

@app.route('/customer_list_rec')
def customer_list_rec():
    return render_template('receptionist/customer_list_rec.html')