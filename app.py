from flask import Flask, render_template, request, redirect, session
import mysql.connector, random
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- MYSQL ----------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="fraud_db"
)

cursor = db.cursor(dictionary=True)

# ---------------- OTP ----------------
def otp():
    return str(random.randint(100000,999999))

# ---------------- HOME ----------------
@app.route("/")
def index():
    tab = request.args.get("tab","user")
    msg = request.args.get("msg","")
    return render_template("index.html", tab=tab, msg=msg)

# ---------------- REGISTER ----------------
@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/register-user", methods=["POST"])
def register_user():

    acc = request.form["account"]

    # ✅ Duplicate check (IMPORTANT FIX)
    cursor.execute("SELECT * FROM users WHERE account=%s",(acc,))
    if cursor.fetchone():
        return redirect("/?msg=Account already exists")

    cursor.execute("""
    INSERT INTO users(account,phone,name,balance,card_number,expiry,cvv)
    VALUES(%s,%s,%s,%s,%s,%s,%s)
    """,(
        acc,
        request.form["phone"],
        request.form["name"],
        request.form["balance"],
        request.form["card"],
        request.form["expiry"],
        request.form["cvv"]
    ))

    db.commit()
    return redirect("/?msg=Registered Successfully")

# ---------------- USER LOGIN ----------------
@app.route("/user/send-otp", methods=["POST"])
def user_send():

    acc = request.form["account"]
    phone = request.form["phone"]

    cursor.execute("SELECT * FROM users WHERE account=%s AND phone=%s",(acc,phone))
    user = cursor.fetchone()

    if not user:
        return render_template("index.html", tab="user", msg="User not found")

    o = otp()
    session["otp"] = o
    session["acc"] = acc

    return render_template("index.html", tab="user", show_user_otp=True, otp=o)

@app.route("/user/verify-otp", methods=["POST"])
def verify():

    if request.form["otp"] != session.get("otp"):
        return render_template("index.html", tab="user", msg="Wrong OTP")

    return redirect("/dashboard")

# ---------------- USER DASHBOARD ----------------
@app.route("/dashboard")
def dash():

    if not session.get("acc"):
        return redirect("/")

    acc = session.get("acc")

    cursor.execute("SELECT * FROM users WHERE account=%s",(acc,))
    user = cursor.fetchone()

    return render_template("user_dashboard.html",
        name=user["name"],
        balance=user["balance"],
        phone=user["phone"],
        masked="XXXX"+acc[-4:]
    )

# ---------------- TRANSACTION ----------------
@app.route("/user/amount", methods=["GET","POST"])
def amount():

    if not session.get("acc"):
        return redirect("/")

    acc = session.get("acc")

    cursor.execute("SELECT * FROM users WHERE account=%s",(acc,))
    user = cursor.fetchone()

    # -------- GET --------
    if request.method == "GET":
        return render_template("user_amount.html",
            name=user["name"],
            balance=user["balance"]
        )

    # -------- POST --------
    amt = int(request.form["amount"])

    # ✅ Fraud logic
    status = "SAFE" if amt < 50000 else "FRAUD"

    # Save transaction
    cursor.execute("""
    INSERT INTO transactions(time,account,phone,amount,location,device,status)
    VALUES(%s,%s,%s,%s,%s,%s,%s)
    """,(datetime.now(), acc, user["phone"], amt, "India", "Browser", status))

    # Update balance if safe
    if status == "SAFE":
        new_bal = user["balance"] - amt
        cursor.execute("UPDATE users SET balance=%s WHERE account=%s",
                       (new_bal, acc))
        user["balance"] = new_bal  # update for display

    db.commit()

    # ✅ IMPORTANT FIX (RESULT SHOW)
    return render_template("user_amount.html",
        name=user["name"],
        balance=user["balance"],
        result=status,
        amount=amt
    )

# ---------------- ADMIN ----------------
@app.route("/admin/send-otp", methods=["POST"])
def admin_send():

    if request.form["admin_id"]!="admin" or request.form["password"]!="1234":
        return render_template("index.html", tab="admin", msg="Wrong credentials")

    o = otp()
    session["admin_otp"] = o
    session["admin_verified"] = False

    return render_template("index.html", tab="admin", show_admin_otp=True, otp=o)

@app.route("/admin/verify-otp", methods=["POST"])
def admin_verify():

    if request.form["otp"] != session.get("admin_otp"):
        return render_template("index.html", tab="admin", msg="Wrong OTP")

    session["admin_verified"] = True
    return redirect("/admin/dashboard")

@app.route("/admin/dashboard")
def admin_dash():

    if not session.get("admin_verified"):
        return redirect("/")

    cursor.execute("SELECT * FROM transactions")
    tx = cursor.fetchall()

    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    total = len(tx)
    safe = len([t for t in tx if t["status"]=="SAFE"])
    fraud = len([t for t in tx if t["status"]=="FRAUD"])

    return render_template("admin_dashboard.html",
        transactions=tx,
        users=users,
        user_count=len(users),
        kpis={
            "total": total,
            "safe": safe,
            "fraud": fraud,
            "fraud_rate": (fraud/total*100 if total else 0)
        }
    )

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)