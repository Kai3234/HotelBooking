from flask import session, redirect, render_template, request

from main import app

@app.route('/rooms_list')
def rooms_list():
    return render_template('/customer/rooms_list.html')

@app.route('/services')
def services():
    return render_template('/customer/services.html')

@app.route('/cart')
def cart():
    return render_template('/customer/cart.html')

@app.route('/profile')
def profile():
    return render_template('/customer/profile.html')

@app.route('/history')
def history():
    return render_template('/customer/history.html')