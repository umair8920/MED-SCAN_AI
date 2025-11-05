from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session, current_app, jsonify
import bcrypt
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import pydicom
from PIL import Image
from config import Config
import tensorflow as tf
import numpy as np
import random
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import inch




patient_bp = Blueprint('patient', __name__)


@patient_bp.route('/patient/patient_signup', methods=['GET', 'POST'])
def patient_signup():
    if request.method == 'POST':
        name = request.form['name']
        phone_number = request.form['phone_number']
        add = request.form['add']
        sex = request.form['sex']
        age =request.form['age']
        email = request.form['email']
        password = request.form['password']
        
        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Insert into MySQL
        cur = current_app.config['MYSQL'].connection.cursor()
        cur.execute("INSERT INTO patient (name,ph_no,email,address,sex,password,age) VALUES (%s, %s, %s, %s, %s,%s,%s)", (name, phone_number,email,add,sex,hashed_password,age))
        current_app.config['MYSQL'].connection.commit()
        cur.close()
        
        flash('Your account has been created!', 'success')
        return redirect(url_for('patient.patient_login'))
    
    return render_template('Patient/pt_signup.html')



@patient_bp.route('/patient/patient_login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = current_app.config['MYSQL'].connection.cursor()
        
        try:
            # Execute query to get patient data based on the email/username
            cur.execute("SELECT p_id, name, age, password FROM patient WHERE email = %s", (username,))
            patient_data = cur.fetchone()

            if patient_data and bcrypt.checkpw(password.encode('utf-8'), patient_data[3].encode('utf-8')):
                # Store patient details in the session
                session['p_id'] = patient_data[0]  # p_id
                session['name'] = patient_data[1]  # name
                session['age'] = patient_data[2]   # age
                session['username'] = username     # email/username

                return redirect(url_for('patient.patient_dashboard'))
            else:
                flash("Login failed. Please check your credentials.", "error")
                return redirect(url_for('patient.patient_login'))

        except Exception as e:
            flash("An error occurred while processing your request.", "error")
            return redirect(url_for('patient.patient_login'))

        finally:
            current_app.config['MYSQL'].connection.commit()
            cur.close()

    return render_template('Patient/pt_login.html')



@patient_bp.route('/patient/patient_dashboard', methods=['GET', 'POST'])
def patient_dashboard():
    # Check if patient is logged in by checking session for p_id
    if 'p_id' not in session:
        flash("You are not logged in!", "error")
        return redirect(url_for('patient.patient_login'))

    # Get the p_id from session
    p_id = session['p_id']

    # Connect to the database
    cur = current_app.config['MYSQL'].connection.cursor()

    # Fetch patient data using p_id instead of username
    cur.execute("SELECT name, sex, age, email, p_id FROM patient WHERE p_id = %s", (p_id,))
    patient_data = cur.fetchone()

    if not patient_data:
        cur.close()
        flash("User data not found!", "error")
        return redirect(url_for('patient.patient_login'))

    # Fetch approved doctors' data
    cur.execute("SELECT d_id, name, email, specialization FROM doctor WHERE status = 'Approved'")
    approved_doctors = cur.fetchall()

    if request.method == 'POST':
        # Handle payment submission
        amount = request.form['amount']
        doctor_id = request.form['doctor_id']

        # Handle file upload
        image = request.files.get('image')
        if image and Config.allowed_file(image.filename):
            filename = secure_filename(image.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            image.save(file_path)
        else:
            file_path = None

        # Get current date
        payment_date = datetime.now()

        # Insert payment record into the database
        cur.execute("""
            INSERT INTO payment (payment_date, amount, pay_status, image, patient_id, doctor_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (payment_date, amount, 'unpaid', file_path, patient_data[4], doctor_id))

        flash("Payment recorded successfully!", "success")
        return redirect(url_for('patient.patient_dashboard'))

    current_app.config['MYSQL'].connection.commit()
    cur.close()

    return render_template('Patient/Patient-dashboard.html', 
                           patient_data=patient_data, 
                           approved_doctors=approved_doctors)


# Patient logout route
@patient_bp.route('/patient/logout_pt')
def pt_logout():
    # Clear session on logout
    session.clear()
    return render_template('home.html')



############################## Model functionality implementing ######################################################

# Set the directory where uploaded files will be saved



# List of classes for the prediction model
classes = ['Cardiomegaly', 'Hernia', 'Infiltration', 'Nodule', 'Emphysema', 'Effusion', 'Atelectasis', 'Pleural_Thickening', 'Pneumothorax', 'Mass', 'Fibrosis', 'Consolidation', 'Edema', 'Pneumonia']

# Disease descriptions
disease_descriptions = {
    'Cardiomegaly': "An abnormal enlargement of the heart, often indicative of underlying conditions such as heart failure or hypertension. It may require further investigation.",
    'Hernia': "A condition where an organ or tissue pushes through the wall of the cavity containing it. Common in the abdominal area, hernias may cause pain or discomfort and may require surgery.",
    'Infiltration': "Refers to the accumulation of substances, such as fluid or cells, in tissues where they normally do not belong. It is often associated with inflammation, infection, or malignancy.",
    'Nodule': "A small, round mass of tissue, which can be benign or malignant. Lung nodules are commonly found on chest X-rays and may require follow-up imaging or biopsy.",
    'Emphysema': "A chronic lung condition that causes shortness of breath due to damage to the alveoli. Often associated with smoking, it is a type of COPD that impairs lung function.",
    'Effusion': "The abnormal accumulation of fluid in the pleural space in the lungs. Causes include infections, heart failure, or malignancies, often requiring drainage and investigation.",
    'Atelectasis': "A condition where part or all of a lung collapses or does not inflate properly. It can lead to difficulty breathing and may require treatment depending on the cause.",
    'Pleural_Thickening': "Thickening of the pleura, often resulting from inflammation, infection, or exposure to asbestos. It can restrict lung function and may indicate chronic lung diseases.",
    'Pneumothorax': "The presence of air in the pleural space, causing lung collapse. It can occur spontaneously or due to trauma, and often requires urgent medical intervention.",
    'Mass': "A lump of tissue that could be benign or malignant. In the lungs, masses may indicate tumors or infections and usually require further diagnostic testing.",
    'Fibrosis': "Scarring of lung tissue resulting from infections, chronic inflammation, or environmental exposure. Pulmonary fibrosis can impair lung function and lead to respiratory difficulties.",
    'Consolidation': "A condition where lung tissue becomes firm due to fluid accumulation, often a sign of infection like pneumonia, impairing gas exchange and causing breathing issues.",
    'Edema': "The abnormal buildup of fluid in tissues, often due to heart or kidney problems. Pulmonary edema refers to fluid in the lungs, causing severe breathing difficulty.",
    'Pneumonia': "An infection of the lungs causing inflammation and fluid/pus in the air sacs. Symptoms include cough, fever, and breathing difficulty, often requiring medical treatment."
}

# Load the pre-trained model (adjust the path if necessary)
model = tf.keras.models.load_model('model//model121.h5')

# Function to preprocess the image
def preprocess_image(image):
    img = tf.image.decode_jpeg(image, channels=3)  # Decode the image as JPEG
    img = tf.image.resize(img, (600, 600))  # Resize to the input shape expected by the model
    img = img / 255.0  # Normalize pixel values to [0, 1]
    img = tf.expand_dims(img, 0)  # Add batch dimension
    return img


@patient_bp.route('/patient/predict', methods=['POST'])
def predict():
    # Check if the patient is logged in by verifying if p_id is in the session
    if 'p_id' not in session:
        flash("You are not logged in.", "error")
        return redirect(url_for('patient.patient_login'))

    # Get patient details from the session
    p_id = session.get('p_id')
    name = session.get('name')  # Now properly retrieving name from session
    age = session.get('age')    # Now properly retrieving age from session

    # Check if 'file' is in the request
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})

    file = request.files['file']

    # Check if the file has a filename
    if file.filename == '':
        return jsonify({'error': 'No selected file'})

    # Generate a unique filename based on patient details and a random number
    random_number = random.randint(1000, 9999)  # Generate a random 4-digit number
    filename = f"{p_id}_{name}_{age}_{random_number}"  # Append random number to the filename
    
    # Check if the file is a DICOM file or other valid format
    if file and Config.allowed_file(file.filename):
        # Save the file to the uploads folder
        if file.filename.lower().endswith('.dcm'):
            # Save DICOM file
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(f"{filename}.dcm"))
            file.save(filepath)

            # Process DICOM file into a JPG
            dicom_image = pydicom.dcmread(filepath)
            jpg_image = Image.fromarray(dicom_image.pixel_array)
            jpg_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(f"{filename}.jpg"))
            jpg_image.save(jpg_filepath)

            # Use the JPEG file for predictions
            filepath = jpg_filepath  # Use the saved JPEG path for further processing

        else:
            # Save other image formats directly
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(f"{filename}.{file.filename.rsplit('.', 1)[1].lower()}"))
            file.save(filepath)

        # Read the saved file and preprocess the image
        with open(filepath, 'rb') as f:
            image_bytes = f.read()

        # Preprocess the image
        img = preprocess_image(image_bytes)

        # Make predictions
        predictions = model.predict(img)

        # Get predicted label (class with highest confidence)
        predicted_label = np.argmax(predictions[0])
        predicted_class = classes[predicted_label]
        confidence = predictions[0][predicted_label] * 100

        # Get the disease description for the predicted class
        summary = disease_descriptions.get(predicted_class, "No specific description available.")

        # Return the predicted class, confidence, and summary (disease description)
        return jsonify({
            'predicted_class': predicted_class,
            'confidence': confidence,
            'summary': summary,
            'image_path': filepath
        })
    else:
        return jsonify({'error': 'Invalid file format.'})



@patient_bp.route('/patient/save_analysis', methods=['POST'])
def save_analysis():
    # Retrieve the patient ID, name, and age from the session
    p_id = session.get('p_id')  # Retrieve patient ID
    name = session.get('name')   # Retrieve patient name
    age = session.get('age')     # Retrieve patient age

    # Check if the patient ID is available
    if not p_id:
        flash("You are not logged in.", "error")
        return redirect(url_for('patient.patient_login'))

    # Check if name and age are available
    if not name or not age:
        return jsonify({'error': 'Patient name or age is missing from the session.'}), 400

    # Fetch approved doctors for the dropdown (optional, if you want to include doctors as part of the request)
    cur = current_app.config['MYSQL'].connection.cursor()
    cur.execute("SELECT d_id, name, email, specialization FROM doctor WHERE status = 'Approved'")
    approved_doctors = cur.fetchall()

    # Get the form data submitted from the frontend
    try:
        # Form data for X-ray analysis
        x_ray_image = request.form.get('x_ray_image')
        study = request.form.get('study')
        technique = request.form.get('technique')
        findings = request.form.get('findings')
        impression = request.form.get('impression')
        recommendations = request.form.get('recommendations')
        summary = request.form.get('summary')

        # Form data for payment
        amount = request.form.get('amount')  # Amount entered by patient
        doctor_id = request.form.get('doctor_id')  # Doctor selected from dropdown
        


# Handle image file upload for payment
        image = request.files.get('image')
        if image and Config.allowed_file(image.filename):
            # Generate a random 4-digit number
            random_number = random.randint(1000, 9999)
            # Append the random number to the filename
            filename = secure_filename(f"{p_id}_{name}_{age}_payment_{random_number}_{image.filename}")
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            image.save(file_path)
        else:
            file_path = None

    except KeyError as e:
        return jsonify({'error': f'Missing field: {e.args[0]}'}), 400


    # Insert the payment record into the 'payment' table
    try:
        # Get current date
        payment_date = datetime.now()

        # Insert the payment details
        cur.execute("""
            INSERT INTO payment (payment_date, amount, pay_status, image, patient_id, doctor_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (payment_date, amount, 'unpaid', file_path, p_id, doctor_id))

        # Get the payment ID of the newly inserted payment record
        payment_id = cur.lastrowid

        # Insert the X-ray analysis details, linking to the payment ID
        cur.execute("""
            INSERT INTO x_ray_analysis 
            (patient_id, x_ray_image, study, technique, findings, impression, recommendations, summary, x_ray_analysis_date, py_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)
        """, (p_id, x_ray_image, study, technique, findings, impression, recommendations, summary, payment_id, 'paid'))

        # Commit the transaction
        current_app.config['MYSQL'].connection.commit()
        cur.close()

        flash("Analysis saved successfully, please complete the payment!", "success")
        return redirect(url_for('patient.patient_dashboard'))  # Redirect to patient's dashboard after saving

    except Exception as e:
        current_app.config['MYSQL'].connection.rollback()  # Rollback in case of error
        return jsonify({'error': str(e)}), 500




@patient_bp.route('/patient/get_approved_doctors', methods=['GET'])
def get_approved_doctors():
    try:
        # Fetch approved doctors' data for dropdown selection
        cur = current_app.config['MYSQL'].connection.cursor()
        cur.execute("SELECT d_id, name, email, Account_number, Account_name, Bank_name,  specialization FROM doctor WHERE status = 'Approved'")
        approved_doctors = cur.fetchall()

        # Format the result into a list of dictionaries
        doctors_list = [
            {
                'd_id': doctor[0], 
                'name': doctor[1], 
                'email': doctor[2], 
                'Account_number': doctor[4],
                'Account_name': doctor[5],
                'Bank_name': doctor[6],
                'specialization': doctor[3]
            } 
            for doctor in approved_doctors
        ]

        return jsonify(doctors_list)  # Return the list in JSON format

    except Exception as e:
        return jsonify({'error': str(e)}), 500






@patient_bp.route('/patient/reports', methods=['GET'])
def view_reports():
    # Get the patient ID from the session
    patient_id = session.get('p_id')

    # Ensure the patient is logged in
    if not patient_id:
        flash("You must be logged in to view reports.", "error")
        return redirect(url_for('patient.patient_login'))  # Redirect to login if patient is not logged in

    cur = current_app.config['MYSQL'].connection.cursor()
    try:
        # Fetch reports and join x_ray_analysis and patient tables
        cur.execute("""
            SELECT 
                r.py_id AS report_id, 
                r.details, 
                r.r_date AS report_date, 
                r.status, 
                x.x_ray_image, 
                x.study, 
                x.technique, 
                x.findings, 
                x.impression, 
                x.recommendations, 
                x.x_ray_analysis_date, 
                p.name AS patient_name, 
                p.ph_no, 
                p.email, 
                p.address, 
                p.sex, 
                p.age
            FROM report r
            LEFT JOIN x_ray_analysis x ON r.py_id = x.py_id
            LEFT JOIN patient p ON r.patient_id = p.p_id
            WHERE r.patient_id = %s
        """, (patient_id,))

        # Fetch all rows
        reports = cur.fetchall()

        # Render the template with the reports data
        return render_template('Patient/generated-reports.html', reports=reports)

    except Exception as e:
        flash(f"An error occurred: {e}", "error")
        return redirect(url_for('patient.patient_dashboard'))

    finally:
        cur.close()


@patient_bp.route('/patient/reports/download/<int:report_id>', methods=['GET'])
def download_report(report_id):
    print(f"Starting download_report with report_id: {report_id}")  # Debug statement
    patient_id = session.get('p_id')
    if not patient_id:
        print("Patient ID not found in session.")  # Debug statement
        flash("You must be logged in to view reports.", "error")
        return redirect(url_for('patient.patient_login'))

    print(f"Patient ID found: {patient_id}")  # Debug statement

    cur = current_app.config['MYSQL'].connection.cursor()
    try:
        print("Executing SQL query...")  # Debug statement
        cur.execute("""
            SELECT 
                r.py_id AS report_id, 
                r.details, 
                r.r_date AS report_date, 
                r.status, 
                x.x_ray_image, 
                x.study, 
                x.technique, 
                x.findings, 
                x.impression, 
                x.recommendations, 
                x.x_ray_analysis_date, 
                p.name AS patient_name, 
                p.ph_no, 
                p.email, 
                p.address, 
                p.sex, 
                p.age
            FROM report r
            LEFT JOIN x_ray_analysis x ON r.py_id = x.py_id
            LEFT JOIN patient p ON r.patient_id = p.p_id
            WHERE r.patient_id = %s AND r.py_id = %s
        """, (patient_id, report_id))

        print("SQL query executed.")  # Debug statement
        report = cur.fetchone()

        if report:
            print(f"Report found: {report}")  # Debug statement
            random_number = random.randint(1000, 9999)
            pdf_filename = f"medical_report_{random_number}.pdf"
            print(f"Generated PDF filename: {pdf_filename}")  # Debug statement

            # Prepare PDF buffer
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)

            # Define styles
            styles = getSampleStyleSheet()
            
            # Modify existing styles (Heading1) instead of redefining
            heading1_style = styles.get('Heading1', ParagraphStyle(name='Heading1', fontSize=16, spaceAfter=12, textColor=colors.navy))
            heading1_style.fontSize = 16
            heading1_style.textColor = colors.navy
            heading1_style.spaceAfter = 12

            # You can define new styles safely like this:
            heading2_style = ParagraphStyle(name='Heading2', fontSize=14, spaceAfter=8, textColor=colors.navy)
            normal_style = ParagraphStyle(name='Normal', fontSize=10, spaceAfter=6)

            # Initialize content list
            content = []

            # Header
            print("Adding report header...")  # Debug statement
            content.append(Paragraph(f"Medical Report - Report ID: {report[0]}", heading1_style))
            content.append(Spacer(1, 0.25*inch))

            # Patient Details Section
            print("Adding patient details...")  # Debug statement
            content.append(Paragraph("Patient Details", heading2_style))
            patient_data = [
                ['Name:', report[11]],
                ['Age:', str(report[16])],
                ['Gender:', report[15]],
                ['Phone:', report[12]],
                ['Email:', report[13]],
                ['Address:', report[14]]
            ]
            patient_table = Table(patient_data, colWidths=[1.5*inch, 4*inch])
            patient_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            content.append(patient_table)
            content.append(Spacer(1, 0.25*inch))

            # Report Details Section
            print("Adding report details...")  # Debug statement
            content.append(Paragraph("Report Details", heading2_style))
            report_data = [
                ['Date:', str(report[2])],
                ['Status:', report[3]],
                ['Study:', report[5]],
                ['Technique:', report[6]],
                ['X-Ray Analysis Date:', str(report[10])]
            ]

            # Add the 'Details' field to the report
            content.append(Spacer(1, 0.25*inch))
            content.append(Paragraph(f"<b>Details:</b> {report[1]}", normal_style))  # 'report[1]' corresponds to the 'details' field

            # Continue adding other report details in a table format
            report_table = Table(report_data, colWidths=[1.5*inch, 4*inch])
            report_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            content.append(report_table)
            content.append(Spacer(1, 0.25*inch))

            # Findings and Recommendations Section
            print("Adding findings and recommendations...")  # Debug statement
            content.append(Paragraph("Medical Analysis", heading2_style))
            content.append(Paragraph(f"<b>Findings:</b> {report[7]}", normal_style))
            content.append(Paragraph(f"<b>Impression:</b> {report[8]}", normal_style))
            content.append(Paragraph(f"<b>Recommendations:</b> {report[9]}", normal_style))
            content.append(Spacer(1, 0.25*inch))

            # X-ray Image Section
            if report[4]:
                print("Adding X-ray image...")  # Debug statement
                image_filename = report[4].replace('static/', '').replace('\\', '/')
                image_path = os.path.join(current_app.root_path, 'static', image_filename)
                if os.path.exists(image_path):
                    img = Image(image_path, width=4*inch, height=3*inch)
                    content.append(Paragraph("X-Ray Image", heading2_style))
                    content.append(img)
                    content.append(Spacer(1, 0.25*inch))

            # Build the PDF document
            print("Building PDF document...")  # Debug statement
            doc.build(content)

            buffer.seek(0)
            return send_file(buffer, as_attachment=True, download_name=pdf_filename, mimetype='application/pdf')

        else:
            print("Report not found.")  # Debug statement
            flash("Report not found.", "error")
            return redirect(url_for('patient.view_reports'))

    except Exception as e:
        print(f"An error occurred: {e}")  # Debug statement
        flash(f"An error occurred: {e}", "error")
        return redirect(url_for('patient.view_reports'))

    finally:
        print("Closing database cursor.")  # Debug statement
        cur.close()

















# @patient_bp.route('/patient/sub_img', methods=['POST'])
# def sub_img():
#     if request.method == 'POST':
#         p_id = request.form['p_id']
#         name = request.form['name']
#         age = request.form['age']
        
#         # Check if an X-ray file is present in the request
#         if 'x_ray' in request.files:
#             x_ray = request.files['x_ray']
#             if Config.allowed_file(x_ray.filename):
#                 # Generate a filename based on patient ID, name, and age
#                 filename = f"{p_id}_{name}_{age}"

#                 # Check if the file is a DICOM file
#                 if x_ray.filename.lower().endswith('.dcm'):
#                     dicom_image = pydicom.dcmread(x_ray)

#                     # Convert DICOM to JPEG
#                     jpg_image = Image.fromarray(dicom_image.pixel_array)

#                     # Save the JPEG file
#                     filename = secure_filename(f"{filename}.jpg")
#                     jpg_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
#                     jpg_image.save(jpg_path)
#                 else:
#                     # For other image formats, save as is
#                     filename = secure_filename(f"{filename}.{x_ray.filename.rsplit('.', 1)[1].lower()}")
#                     jpg_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
#                     x_ray.save(jpg_path)

#                 # Replace backslashes with forward slashes
#                 jpg_path = jpg_path.replace('\\', '/')

#                 # Save the file path to the MySQL database
#                 cur = current_app.config['MYSQL'].connection.cursor()
#                 cur.execute("INSERT INTO x_ray_analysis (patient_id, x_ray_image) VALUES (%s, %s)", (p_id, jpg_path))
#                 current_app.config['MYSQL'].connection.commit()
#                 cur.close()

#                 flash('Image uploaded and data saved successfully!', 'success')
#                 return redirect(url_for('patient.patient_dashboard'))
#             else:
#                 flash("Invalid file format.", "error")
#                 return redirect(url_for('patient.patient_dashboard'))
#         else:
#             flash("No file selected.", "error")
#             return redirect(url_for('patient.patient_dashboard'))
#     else:
#         flash("You are not logged in.", "error")
#         return redirect(url_for('patient.patient_dashboard'))
    
        

@patient_bp.route('/patient/view_image/<int:patient_id>')
def view_image(patient_id):
    if 'username' in session:
        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT p.p_id, p.name, p.sex, p.age, p.ph_no, r.r_image
            FROM patient p
            LEFT JOIN report r ON p.p_id = r.p_id
            WHERE p.p_id = %s
        """, (patient_id,))
        patient_data = cur.fetchone()
        cur.close()

        if patient_data:
            p_id, name, sex, age, ph_no, x_ray_image = patient_data
            return render_template('view_image.html', 
                                   pid=p_id, 
                                   full_name=name, 
                                   phone_number=ph_no, 
                                   gender=sex, 
                                   age=age, 
                                   image_url=x_ray_image)
        else:
            flash("Patient not found.", "error")
            return redirect(url_for('doctor_dashboard'))
    else:
        flash("You are not authorized to access this page.", "error")
        return redirect(url_for('doctor_login'))
    

# @patient_bp.route('/patient/view_report/<int:patient_id>')
# def view_report(patient_id):
#     if 'username' in session:
#         mysql = current_app.extensions['mysql']
#         cur = mysql.connection.cursor()
#         cur.execute("""
#             SELECT p.p_id, p.name, p.sex, p.age, p.ph_no, r.r_image
#             FROM patient p
#             LEFT JOIN report r ON p.p_id = r.p_id
#             WHERE p.p_id = %s
#         """, (patient_id,))
#         patient_data = cur.fetchone()
#         cur.close()

#         if patient_data:
#             p_id, name, sex, age, ph_no, x_ray_image = patient_data
#             return render_template('Report_template.html', 
#                                    pid=p_id, 
#                                    full_name=name, 
#                                    phone_number=ph_no, 
#                                    gender=sex, 
#                                    age=age, 
#                                    image_url=x_ray_image)
#         else:
#             flash("Patient not found.", "error")
#             return redirect(url_for('doctor_dashboard'))
#     else:
#         flash("You are not authorized to access this page.", "error")
#         return redirect(url_for('doctor_login'))

# doctor Change Password Route
@patient_bp.route('/patient/patient_change_password', methods=['GET', 'POST'])
def patient_change_password():
    if 'p_id' not in session:
        flash('You must be logged in to change your password.', 'error')
        return redirect(url_for('patient.patient_login'))
    
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('patient_change_password'))
        cur = current_app.config['MYSQL'].connection.cursor()
        current_app.config['MYSQL'].connection.commit()
        cur.execute("SELECT password FROM patient WHERE p_id = %s", (session['p_id'],))
        patient_data = cur.fetchone()
        
        if patient_data and bcrypt.checkpw(current_password.encode('utf-8'), patient_data[0].encode('utf-8')):
            hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur.execute("UPDATE patient SET password = %s WHERE p_id = %s", (hashed_new_password, session['p_id']))
            current_app.config['MYSQL'].connection.commit()
            cur.close()
            flash('Password updated successfully.', 'success')
            return redirect(url_for('patient.patient_dashboard'))
        else:
            flash('Current password is incorrect.', 'error')
            cur.close()
            return redirect(url_for('patient.patient_change_password'))
    
    return render_template('Patient/patient_change_password.html')