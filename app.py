"""
app.py
Flask web application for the MMU Modern Parking System.

Routes:
- /            : visual display of available slots (before entry)
- /enter       : records a vehicle on arrival
- /exit        : calculates time/fee, handles payment, opens barrier, frees slot
"""

from flask import Flask, render_template, request, redirect, url_for, flash
from park.models import ParkingSystem

app = Flask(__name__)
app.secret_key = "mmu-parking-secret"  # needed for flash messages

# One shared ParkingSystem instance for the running app.
parking = ParkingSystem()


@app.route("/")
def index():
    """Visual display: shows which slots are free before entry."""
    free_slots = parking.available_slots()
    total = len(parking.slots)
    return render_template("index.html", free_slots=free_slots, total=total)


@app.route("/enter", methods=["GET", "POST"])
def enter():
    if request.method == "POST":
        plate = request.form.get("plate_number", "").strip().upper()
        if not plate:
            flash("Please enter a plate number.")
            return redirect(url_for("enter"))

        success, result = parking.park_vehicle(plate)
        if success:
            flash(f"Vehicle {plate} parked in slot {result}.")
        else:
            flash(result)  # error message, e.g. "Parking full."
        return redirect(url_for("index"))

    return render_template("enter.html")


@app.route("/exit", methods=["GET", "POST"])
def exit_vehicle():
    if request.method == "POST":
        plate = request.form.get("plate_number", "").strip().upper()
        action = request.form.get("action")

        if action == "calculate":
            success, result = parking.exit_vehicle(plate)
            if not success:
                flash(result)
                return redirect(url_for("exit_vehicle"))
            # Show the fee/duration and ask for payment confirmation
            return render_template("exit.html", bill=result)

        elif action == "pay":
            db_id = int(request.form.get("db_id"))
            # Note: we deliberately ignore any "fee" field from the form here.
            # The fee is recalculated server-side inside confirm_payment,
            # so a tampered hidden field can't reduce what's charged.
            success, fee = parking.confirm_payment(plate, db_id)
            if not success:
                flash("Vehicle not found — payment could not be processed.")
                return redirect(url_for("exit_vehicle"))
            flash(f"Payment of Kshs. {fee} received. Barrier open — safe travels, {plate}.")
            return redirect(url_for("index"))

    return render_template("exit.html", bill=None)


if __name__ == "__main__":
    app.run(debug=True)