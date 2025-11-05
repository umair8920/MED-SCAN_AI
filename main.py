from flask import Flask, render_template
from flask_mysqldb import MySQL
from config import Config
from routes.admin_routes import admin_bp
from routes.doctor_routes import doctor_bp
from routes.patient_routes import patient_bp


mysql = MySQL()

def create_app():
    app = Flask(__name__)

    # Apply configuration settings
    app.config.from_object(Config)

    # Initialize MySQL with the app
    mysql.init_app(app)

    app.config['MYSQL'] = mysql

    @app.route('/')
    def home():
        return render_template('home.html')

    # Import and register blueprints here to avoid circular import
    app.register_blueprint(admin_bp)

    app.register_blueprint(doctor_bp)

    app.register_blueprint(patient_bp)

    # MySQL connection check
    with app.app_context():
        check_mysql_connection()

    return app

# Check MySQL connection
def check_mysql_connection():
    try:
        connection = mysql.connection
        cursor = connection.cursor()
        cursor.execute('SELECT 1')
        cursor.close()

        print("MySQL connection is successful.")
    except Exception as e:
        print("Error:", e)
        print("MySQL connection failed.")

    

# Entry point for running the app
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
