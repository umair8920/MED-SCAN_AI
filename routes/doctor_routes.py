from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from datetime import datetime
import bcrypt
import os
import base64
from io import BytesIO
from PIL import Image
import uuid



doctor_bp = Blueprint('doctor', __name__)



@doctor_bp.route('/doctor/doctor_signup', methods=['GET', 'POST'])
def doctor_signup():
    if request.method == 'POST':
        name = request.form['name']
        phone_number = request.form['phone_number']
        specialization = request.form['specialization']
        license_no = request.form['license_no']
        email = request.form['email']
        sex = request.form['sex']
        password = request.form['password']
        
        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cur = current_app.config['MYSQL'].connection.cursor()
        cur.execute("""
            INSERT INTO doctor (name, ph_no, specialization, license_no, email, sex, hashed_password, status, is_approved) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', '0')
        """, (name, phone_number, specialization, license_no, email, sex, hashed_password))
        current_app.config['MYSQL'].connection.commit()
        cur.close()
        
        # Flash message indicating account creation and approval pending
        flash('Your account has been created! Please wait for Admin approval.', 'success')
        
        # Instead of redirecting, render the signup page with the flash message
        return render_template('Doctor/dr_Signup.html')

    return render_template('Doctor/dr_Signup.html')



@doctor_bp.route('/doctor/doctor_login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Get a cursor for database operations
        cur = current_app.config['MYSQL'].connection.cursor()
        
        # Fetch the doctor's data based on the email
        cur.execute("SELECT d_id, name, hashed_password, is_approved FROM doctor WHERE email = %s", (email,))
        doctor_data = cur.fetchone()
        
        # Commit and close the database connection
        current_app.config['MYSQL'].connection.commit()
        cur.close()

        # Check if doctor data is found and the password matches
        if doctor_data and bcrypt.checkpw(password.encode('utf-8'), doctor_data[2].encode('utf-8')):
            # Check if the account is approved
            if doctor_data[3] == '1':  
                session['d_id'] = doctor_data[0]  # Store d_id in session instead of email
                return redirect(url_for('doctor.doctor_dashboard'))
            else:
                flash("Your account is pending and needs approval from admin.", "warning")
                return redirect(url_for('doctor.doctor_login'))
        else:
            flash("Login failed. Please check your credentials.", "error")
            return redirect(url_for('doctor.doctor_login'))
    
    # Render the login template for GET requests
    return render_template('Doctor/dr_login.html')




@doctor_bp.route('/doctor/pateint_listing')
def pateint_listing():
     # Check if the user is logged in by checking 'd_id' in session
    if 'd_id' not in session:
        flash("You must be logged in to access the dashboard.", "error")
        return redirect(url_for('doctor.doctor_login'))

    d_id = session['d_id']  # Get the logged-in doctor's ID from the session
    cur = current_app.config['MYSQL'].connection.cursor()

    try:
        # Fetch doctor's details using the d_id
        cur.execute("SELECT d_id, name, specialization FROM doctor WHERE d_id = %s", (d_id,))
        doctor_data = cur.fetchone()

        if not doctor_data:
            flash("Doctor data not found!", "error")
            return redirect(url_for('doctor.doctor_login'))

        # Get the count of pending payments specific to the doctor (using d_id directly)
        cur.execute("SELECT COUNT(*) FROM payment WHERE doctor_id = %s AND pay_status = 'unpaid'", (d_id,))
        pending_count = cur.fetchone()[0]

        # Fetch patients with a 'paid' status and their x-ray analysis and pending reports (using d_id directly)
        cur.execute("""
            SELECT 
                -- All columns from the patient table
                pt.p_id, pt.name, pt.email, pt.address, pt.sex, pt.age, pt.ph_no,
                
                -- All columns from the payment table
                p.pay_id, p.payment_date, p.amount, p.pay_status, p.image, p.patient_id AS payment_patient_id, p.doctor_id AS payment_doctor_id
                
            FROM 
                patient pt
            JOIN 
                payment p ON pt.p_id = p.patient_id
            LEFT JOIN 
                report r ON pt.p_id = r.patient_id AND p.pay_id = r.py_id
                
            WHERE 
                p.doctor_id = %s  -- Filter for the logged-in doctor
                AND p.pay_status = 'paid'  -- Only show patients with completed payments
                AND (r.status = 'done' )  -- Show only patients with a 'done' report status
        """, (d_id,))

        paid_patients = cur.fetchall()

        cur.close()

        # Render the dashboard template with context data
        return render_template(
            'Doctor/patient-listing.html',
            doctor_data=doctor_data,
            pending_count=pending_count,
            paid_patients=paid_patients
        )
    except Exception as e:
        cur.close()
        flash("An error occurred while fetching the dashboard data: " + str(e), "error")
        return redirect(url_for('doctor.doctor_login'))


@doctor_bp.route('/doctor/doctor_dashboard')
def doctor_dashboard():
    # Check if the user is logged in by checking 'd_id' in session
    if 'd_id' not in session:
        flash("You must be logged in to access the dashboard.", "error")
        return redirect(url_for('doctor.doctor_login'))

    d_id = session['d_id']  # Get the logged-in doctor's ID from the session
    cur = current_app.config['MYSQL'].connection.cursor()

    try:
        # Fetch doctor's details using the d_id
        cur.execute("SELECT d_id, name, specialization FROM doctor WHERE d_id = %s", (d_id,))
        doctor_data = cur.fetchone()

        if not doctor_data:
            flash("Doctor data not found!", "error")
            return redirect(url_for('doctor.doctor_login'))

        # Get the count of pending payments specific to the doctor (using d_id directly)
        cur.execute("SELECT COUNT(*) FROM payment WHERE doctor_id = %s AND pay_status = 'unpaid'", (d_id,))
        pending_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM patient")
        patients_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM patient WHERE sex = 'male'")
        male_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM patient WHERE sex = 'female'")
        female_count = cur.fetchone()[0]


        # Fetch pending payments for this doctor using doctor ID (d_id directly)
        cur.execute("""
        SELECT p.pay_id AS pay_id, p.payment_date AS payment_date, p.amount AS amount, p.image AS image, pt.name AS patient_name
        FROM payment p
        JOIN patient pt ON p.patient_id = pt.p_id
        WHERE p.doctor_id = %s AND p.pay_status = 'unpaid'
        """, (d_id,))
        pending_patient = cur.fetchall()

        # Fetch patients with a 'paid' status and their x-ray analysis and pending reports (using d_id directly)
        cur.execute("""
            SELECT 
                -- All columns from the patient table
                pt.p_id, pt.name, pt.email, pt.address, pt.sex, pt.age, pt.ph_no,
                
                -- All columns from the payment table
                p.pay_id, p.payment_date, p.amount, p.pay_status, p.image, p.patient_id AS payment_patient_id, p.doctor_id AS payment_doctor_id
                
            FROM 
                patient pt
            JOIN 
                payment p ON pt.p_id = p.patient_id
            LEFT JOIN 
                report r ON pt.p_id = r.patient_id AND p.pay_id = r.py_id
                
            WHERE 
                p.doctor_id = %s  -- Filter for the logged-in doctor
                AND p.pay_status = 'paid'  -- Only show patients with completed payments
                AND (r.status = 'pending' )  -- Show only patients with a 'pending' report status or no report yet
        """, (d_id,))

        paid_patients = cur.fetchall()

        cur.close()

        # Render the dashboard template with context data
        return render_template(
            'Doctor/Doctor-dashboard.html',
            doctor_data=doctor_data,
            pending_count=pending_count,
            pending_patient=pending_patient,
            paid_patients=paid_patients,
            patients_count=patients_count,
            male_count=male_count,
            female_count=female_count
        )
    except Exception as e:
        cur.close()
        flash("An error occurred while fetching the dashboard data: " + str(e), "error")
        return redirect(url_for('doctor.doctor_login'))



@doctor_bp.route('/doctor/approve_payment/<int:pay_id>', methods=['POST'])
def approve_payment(pay_id):
    # Check if 'd_id' is in session instead of 'email'
    if 'd_id' not in session:
        flash("You are not logged in!", "error")
        return redirect(url_for('doctor.doctor_login'))
    
    # Get the doctor's decision from the form ('yes' = approve, 'no' = reject)
    decision = request.form.get('approve')

    # Set the payment status based on the decision
    if decision == 'yes':
        pay_status = 'paid'  # Payment approved
    elif decision == 'no':
        pay_status = 'rejected'  # Payment rejected
    else:
        flash("Invalid action!", "error")
        return redirect(url_for('doctor.doctor_dashboard'))

    cur = current_app.config['MYSQL'].connection.cursor()

    try:
        # Get the doctor ID directly from the session
        doctor_id = session['d_id']

        # Verify that the payment belongs to the doctor
        cur.execute("SELECT doctor_id, patient_id FROM payment WHERE pay_id = %s", (pay_id,))
        payment_data = cur.fetchone()

        if not payment_data or payment_data[0] != doctor_id:
            flash("Unauthorized action or payment not found!", "error")
            return redirect(url_for('doctor.doctor_dashboard'))

        patient_id = payment_data[1]  # Get the patient_id from the payment record

        # Update the payment status in the database
        cur.execute("UPDATE payment SET pay_status = %s WHERE pay_id = %s", (pay_status, pay_id))

        # If the payment is approved, insert an entry into the report table with the status 'pending'
        if pay_status == 'paid':
            cur.execute("""
                INSERT INTO report (doctor_id, patient_id, status, py_id) 
                VALUES (%s, %s, 'pending', %s)
            """, (doctor_id, patient_id, pay_id))

        # Commit the transaction
        current_app.config['MYSQL'].connection.commit()

        flash("Payment status updated successfully, and report initialized.", "success")
    except Exception as e:
        current_app.config['MYSQL'].connection.rollback()  # Rollback in case of error
        flash("An error occurred while updating the payment status: " + str(e), "error")
    finally:
        cur.close()

    return redirect(url_for('doctor.doctor_dashboard'))



@doctor_bp.route('/doctor/patient-pending')
def doctor_pending():
    # Check if 'd_id' is in session instead of 'email'
    if 'd_id' not in session:
        flash('You must be logged in as a doctor to view this page.', 'error')
        return redirect(url_for('doctor.doctor_login'))

    cur = current_app.config['MYSQL'].connection.cursor()
    
    # Get the doctor ID directly from the session
    doctor_id = session['d_id']

    # Get the count of pending payments for this doctor
    cur.execute("SELECT COUNT(*) FROM payment WHERE doctor_id = %s AND pay_status = 'unpaid'", (doctor_id,))
    pending_count = cur.fetchone()[0]

    # Get the list of pending payments for this doctor
    cur.execute("""
        SELECT p.pay_id, p.payment_date, p.amount, p.image, pt.name AS patient_name
        FROM payment p
        JOIN patient pt ON p.patient_id = pt.p_id
        WHERE p.doctor_id = %s AND p.pay_status = 'unpaid'
    """, (doctor_id,))
    
    column_names = ['pay_id', 'payment_date', 'amount', 'image', 'patient_name']
    pending_patient = [dict(zip(column_names, row)) for row in cur.fetchall()]

    cur.close()

    return render_template('Doctor/patient-pending.html', pending_count=pending_count, pending_patient=pending_patient)



@doctor_bp.route('/doctor/generate_report/<int:patient_id>/<int:py_id>', methods=['GET', 'POST'])
def generate_report(patient_id, py_id):
    # Check if the doctor is logged in
    if 'd_id' not in session:
        flash("You must be logged in to generate reports.", "error")
        return redirect(url_for('doctor.doctor_login'))

    cur = current_app.config['MYSQL'].connection.cursor()

    try:
        # Fetch patient details and existing report based on py_id, including X-ray analysis
        cur.execute("""
            SELECT pt.p_id, pt.name AS patient_name, pt.age, pt.sex, pt.email, pt.ph_no, pt.address,
                x.study, x.technique, x.findings, x.impression, x.recommendations, x.summary, x.x_ray_image, x.py_id,
                r.details, r.r_date, r.status
            FROM patient pt
            LEFT JOIN report r ON pt.p_id = r.patient_id AND r.py_id = %s  -- Filter by specific report ID
            LEFT JOIN x_ray_analysis x ON pt.p_id = x.patient_id AND x.py_id = %s  -- Filter by specific x-ray analysis ID
            WHERE pt.p_id = %s
        """, (py_id, py_id, patient_id))

        patient_data = cur.fetchone()

        if not patient_data:
            flash("Patient data or report not found!", "error")
            return redirect(url_for('doctor.doctor_dashboard'))

        if request.method == 'POST':
            report_details = request.form.get('report_details')
            report_date = datetime.now()

            # Update the existing report data
            cur.execute("""
                UPDATE report 
                SET details = %s, r_date = %s, status = 'done'
                WHERE py_id = %s  -- Update the report identified by py_id
            """, (report_details, report_date, py_id))

            current_app.config['MYSQL'].connection.commit()

            flash('Report successfully updated.', 'success')
            return redirect(url_for('doctor.doctor_dashboard'))

    except Exception as e:
        flash("An error occurred while generating the report: " + str(e), "error")
        current_app.config['MYSQL'].connection.rollback()  # Rollback in case of an error
    finally:
        cur.close()

    return render_template('Doctor/view_report.html', patient_data=patient_data)



@doctor_bp.route('/doctor/analyze_xray/<int:patient_id>/<int:py_id>', methods=['GET', 'POST'])
def analyze_xray(patient_id, py_id):
    doctor_id = session.get('d_id')
    if not doctor_id:
        flash("You must be logged in to access this page.", "error")
        return redirect(url_for('doctor.doctor_login'))

    cur = current_app.config['MYSQL'].connection.cursor()
    try:
        if request.method == 'GET':
            # Fetch patient and specific X-ray analysis data using patient_id and py_id
            query = """
                SELECT 
                    p.p_id, p.name, p.ph_no, p.age, p.sex, p.address, 
                    x.x_ray_image, x.study, x.technique, x.findings, 
                    x.impression, x.recommendations, x.summary, x.x_ray_analysis_date, x.py_id
                FROM 
                    patient p
                JOIN 
                    x_ray_analysis x ON p.p_id = x.patient_id
                JOIN 
                    payment pay ON p.p_id = pay.patient_id
                WHERE 
                    p.p_id = %s 
                    AND x.py_id = %s
                    AND pay.doctor_id = %s
                    AND pay.pay_status = 'paid'
                    AND x.py_id = pay.pay_id
            """
            cur.execute(query, (patient_id, py_id, doctor_id))
            patient_data = cur.fetchone()

            if not patient_data:
                flash("Patient or X-ray analysis not found, or you don't have access to this patient.", "error")
                return redirect(url_for('doctor.doctor_dashboard'))

            return render_template('Doctor/analyze_xray.html', patient_data=patient_data)

        elif request.method == 'POST':
            data = request.get_json()
            annotated_image = data.get('annotatedImage')
            if not annotated_image:
                return jsonify({"success": False, "message": "No annotated image found."})

            # Verify that the patient_id and py_id from the URL match the data
            if str(patient_id) != str(data.get('patientId')) or str(py_id) != str(data.get('pyId')):
                return jsonify({"success": False, "message": "Invalid patient or analysis ID."})

            try:
                annotated_image_data = annotated_image.split(',')[1]
                annotation_layer = Image.open(BytesIO(base64.b64decode(annotated_image_data)))
            except Exception as e:
                return jsonify({"success": False, "message": f"Error processing image: {str(e)}"})

            # Load the original image from the database
            select_query = "SELECT x_ray_image FROM x_ray_analysis WHERE patient_id = %s AND py_id = %s"
            cur.execute(select_query, (patient_id, py_id))
            result = cur.fetchone()
            if not result:
                return jsonify({"success": False, "message": "Original image not found in the database."})
            
            original_image_path = result[0]
            if not os.path.exists(original_image_path):
                return jsonify({"success": False, "message": "Original image file not found on the server."})

            try:
                base_image = Image.open(original_image_path).convert("RGBA")
                annotation_layer = annotation_layer.resize(base_image.size, Image.LANCZOS)
                combined_image = Image.alpha_composite(base_image, annotation_layer)

                new_filename = f"{uuid.uuid4().hex}.png"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_filename)
                combined_image.save(file_path, format="PNG")

                update_query = """
                    UPDATE x_ray_analysis 
                    SET x_ray_image = %s 
                    WHERE patient_id = %s AND py_id = %s
                """
                cur.execute(update_query, (file_path, patient_id, py_id))
                current_app.config['MYSQL'].connection.commit()

                return jsonify({"success": True, "message": "Annotated image saved successfully."})
            except Exception as e:
                return jsonify({"success": False, "message": f"Error saving annotated image: {str(e)}"})

    except Exception as e:
        current_app.logger.error(f"Error in analyze_xray: {str(e)}")
        return jsonify({"success": False, "message": "An unexpected error occurred."})

    finally:
        cur.close()






# doctor Change Password Route
@doctor_bp.route('/doctor/doctor_change_password', methods=['GET', 'POST'])
def doctor_change_password():
    if 'd_id' not in session:
        flash('You must be logged in to change your password.', 'error')
        return redirect(url_for('doctor.doctor_login'))
    
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('doctor_change_password'))
        cur = current_app.config['MYSQL'].connection.cursor()
        current_app.config['MYSQL'].connection.commit()
        cur.execute("SELECT hashed_password FROM doctor WHERE d_id = %s", (session['d_id'],))
        doctor_data = cur.fetchone()
        
        if doctor_data and bcrypt.checkpw(current_password.encode('utf-8'), doctor_data[0].encode('utf-8')):
            hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur.execute("UPDATE doctor SET hashed_password = %s WHERE d_id = %s", (hashed_new_password, session['d_id']))
            current_app.config['MYSQL'].connection.commit()
            cur.close()
            flash('Password updated successfully.', 'success')
            return redirect(url_for('doctor.doctor_dashboard'))
        else:
            flash('Current password is incorrect.', 'error')
            cur.close()
            return redirect(url_for('doctor.doctor_change_password'))
    
    return render_template('Doctor/doctor_change_password.html')


@doctor_bp.route('/doctor/<int:d_id>/account_details', methods=['GET', 'POST'])
def account_details(d_id):
    # Ensure the user is logged in
    if 'd_id' not in session:
        flash('You must be logged in to update your account details.', 'error')
        return redirect(url_for('doctor.doctor_login'))
    
    if request.method == 'POST':
        # Retrieve form data
        account_number = request.form.get('Account_number')
        account_name = request.form.get('Account_name')
        bank_name = request.form.get('Bank_name')
        
        # Validate input
        if not (account_number and account_name and bank_name):
            flash('Please fill in all the fields.', 'error')
            return redirect(url_for('doctor.account_details', d_id=d_id))
        
        # Database connection and cursor setup
        cur = current_app.config['MYSQL'].connection.cursor()
        try:
            # Check if the doctor exists
            cur.execute("SELECT d_id FROM doctor WHERE d_id = %s", (d_id,))
            doctor = cur.fetchone()
            if not doctor:
                flash('No doctor found with the given ID.', 'error')
                return redirect(url_for('doctor.doctor_dashboard'))
            
            # Update the account details for the doctor
            cur.execute("""
            UPDATE doctor
            SET Account_number = %s, Account_name = %s, Bank_name = %s
            WHERE d_id = %s
            """, (account_number, account_name, bank_name, d_id))
            
            current_app.config['MYSQL'].connection.commit()  # Commit the changes
            
            flash('Account details updated successfully.', 'success')
            return redirect(url_for('doctor.doctor_dashboard'))
        
        except Exception as e:
            # Handle database errors
            print(f"Database error: {e}")
            flash('An error occurred while updating your account details. Please try again later.', 'error')
            return redirect(url_for('doctor.account_details', d_id=d_id))
        
        finally:
            # Ensure the cursor and connection are closed
            cur.close()

    # If it's a GET request, render the form with the doctor's account details (if needed)
    return render_template('Doctor/insert_account_details.html', d_id=d_id)








@doctor_bp.route('/doctor/logout_dr')
def dr_logout():
    if 'email' in session:
        session.pop('email', None)  # Remove the 'email' key from the session
    return redirect(url_for('doctor.doctor_login'))