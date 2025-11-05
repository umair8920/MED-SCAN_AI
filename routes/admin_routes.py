from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
import bcrypt



admin_bp = Blueprint('admin', __name__)





# Admin Signup Route
@admin_bp.route('/admin/admin_signup', methods=['GET', 'POST'])
def admin_signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cur = current_app.config['MYSQL'].connection.cursor()
        cur.execute("INSERT INTO admin (name, email, hashed_password) VALUES (%s, %s, %s)", (name, email, hashed_password))
        current_app.config['MYSQL'].connection.commit()
        cur.close()
        
        flash('Admin account created!', 'success')
        return redirect(url_for('admin.admin_login'))
    return render_template('Admin/admin_signup.html')



# Admin Login Route
@admin_bp.route('/admin/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cur = current_app.config['MYSQL'].connection.cursor()
        current_app.config['MYSQL'].connection.commit()
        cur.execute("SELECT a_id, name, hashed_password FROM admin WHERE email = %s", (email,))
        admin_data = cur.fetchone()
        cur.close()
        
        if admin_data and bcrypt.checkpw(password.encode('utf-8'), admin_data[2].encode('utf-8')):
            session['admin_id'] = admin_data[0]
            session['admin_name'] = admin_data[1]
            session['admin_email'] = email
            return redirect(url_for('admin.admin_dashboard'))
        else:
            flash('Login failed. Please check your credentials.', 'error')
            return redirect(url_for('admin.admin_login'))
    return render_template('Admin/admin_login.html')




# Admin Dashboard Route
@admin_bp.route('/admin/admin_dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        flash('You must be logged in as admin to access the dashboard.', 'error')
        return redirect(url_for('admin.admin_login'))
    cur = current_app.config['MYSQL'].connection.cursor()
    current_app.config['MYSQL'].connection.commit()
    
    # Fetch all doctors with status 'pending'
    cur.execute("SELECT d_id, name, email, specialization FROM doctor WHERE status = 'pending'")
    pending_doctors = cur.fetchall()

        # Get the count of pending doctors
    cur.execute("SELECT COUNT(*) FROM doctor WHERE status = 'pending'")
    pending_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM doctor")
    doctors_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM doctor WHERE sex = 'male'")
    male_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM doctor WHERE sex = 'female'")
    female_count = cur.fetchone()[0]
    
    # Fetch all patients
    cur.execute("SELECT * FROM patient")
    patients = cur.fetchall()

        # Fetch all doctors
    cur.execute("SELECT * FROM doctor")
    doctors = cur.fetchall()

    cur.close()
    
    return render_template('Admin/Admin-dashboard.html', 
                           pending_doctors=pending_doctors,
                           pending_count=pending_count,
                           doctors = doctors, 
                           patients=patients,
                            doctors_count=doctors_count,
                             male_count=male_count,
                            female_count=female_count,
                           admin_name=session.get('admin_name'),
                           admin_email=session.get('admin_email'))





@admin_bp.route('/admin/approve_doctor/<int:doctor_id>', methods=['POST'])
def approve_doctor(doctor_id):
    if 'admin_id' not in session:
        flash('You must be logged in as admin to approve doctors.', 'error')
        return redirect(url_for('admin.admin_login'))
    cur = current_app.config['MYSQL'].connection.cursor()
    
    
    # Update the doctor's status to 'Approved' and set 'is_approved' to '1'
    cur.execute("UPDATE doctor SET status = 'Approved', is_approved = '1' WHERE d_id = %s", (doctor_id,))
    current_app.config['MYSQL'].connection.commit()
    cur.close()
    
    flash('Doctor approved successfully!', 'success')
    return redirect(url_for('admin.admin_dashboard'))





@admin_bp.route('/admin/doctor-pending')
def doctor_pending():
    if 'admin_id' not in session:
        flash('You must be logged in as admin to view this page.', 'error')
        return redirect(url_for('admin.admin_login'))
    cur = current_app.config['MYSQL'].connection.cursor()
    current_app.config['MYSQL'].connection.commit()
    # Get the count of pending doctors
    cur.execute("SELECT COUNT(*) FROM doctor WHERE status = 'pending'")
    pending_count = cur.fetchone()[0]
    
    # Get the list of pending doctors
    cur.execute("SELECT d_id, name, email, specialization FROM doctor WHERE status = 'pending'")
    pending_doctors = cur.fetchall()
    cur.close()
    
    return render_template('Admin/doctor-pending.html', pending_count=pending_count, pending_doctors=pending_doctors)




# Admin Change Password Route
@admin_bp.route('/admin/admin_change_password', methods=['GET', 'POST'])
def admin_change_password():
    if 'admin_id' not in session:
        flash('You must be logged in to change your password.', 'error')
        return redirect(url_for('admin.admin_login'))
    
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('admin_change_password'))
        cur = current_app.config['MYSQL'].connection.cursor()
        current_app.config['MYSQL'].connection.commit()
        cur.execute("SELECT hashed_password FROM admin WHERE a_id = %s", (session['admin_id'],))
        admin_data = cur.fetchone()
        
        if admin_data and bcrypt.checkpw(current_password.encode('utf-8'), admin_data[0].encode('utf-8')):
            hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur.execute("UPDATE admin SET hashed_password = %s WHERE a_id = %s", (hashed_new_password, session['admin_id']))
            current_app.config['MYSQL'].connection.commit()
            cur.close()
            flash('Password updated successfully.', 'success')
            return redirect(url_for('admin.admin_dashboard'))
        else:
            flash('Current password is incorrect.', 'error')
            cur.close()
            return redirect(url_for('admin.admin_change_password'))
    
    return render_template('Admin/admin_change_password.html')






# Admin Logout Route
@admin_bp.route('/admin/admin_logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    session.pop('admin_email', None)
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('admin.admin_login'))

