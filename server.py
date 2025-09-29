from flask import Flask, request, jsonify, render_template
import sqlite3
import bcrypt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import random
from datetime import datetime, timedelta
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY', 'roger-loyalty-secret-key-2024')

# إعدادات الإيميل - بدون قيم افتراضية لأسباب أمنية
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = os.environ['EMAIL_USER']
EMAIL_PASS = os.environ['EMAIL_PASS']

def generate_member_id():
    """توليد رقم عضوية فريد بالشكل LA-ROJ + 7 أرقام عشوائية"""
    random_numbers = ''.join([str(random.randint(0, 9)) for _ in range(7)])
    return f"LA-ROJ{random_numbers}"

def init_database():
    """إنشاء قاعدة البيانات والجداول المطلوبة"""
    conn = sqlite3.connect('roger_loyalty.db')
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            birth_date TEXT,
            password TEXT NOT NULL,
            verification_code TEXT,
            verified INTEGER DEFAULT 0,
            reset_token TEXT,
            reset_expires TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول النقاط والمعاملات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            points INTEGER NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (member_id) REFERENCES users(member_id)
        )
    ''')
    
    # جدول نقاط المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_points (
            member_id TEXT PRIMARY KEY,
            total_points INTEGER DEFAULT 0,
            FOREIGN KEY (member_id) REFERENCES users(member_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def send_email(to_email, subject, body):
    """إرسال إيميل"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        text = msg.as_string()
        server.sendmail(EMAIL_USER, to_email, text)
        server.quit()
        return True
    except Exception as e:
        print(f"خطأ في إرسال الإيميل: {str(e)}")
        return False

def validate_email(email):
    """التحقق من صحة الإيميل"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    """تسجيل مستخدم جديد"""
    try:
        data = request.get_json()
        
        full_name = data.get('full_name')
        email = data.get('email')
        phone = data.get('phone')
        birth_date = data.get('birth_date')
        password = data.get('password')
        
        # التحقق من البيانات المطلوبة
        if not all([full_name, email, password]):
            return jsonify({"message": "يرجى ملء جميع الحقول المطلوبة"}), 400
        
        # التحقق من صحة الإيميل
        if not validate_email(email):
            return jsonify({"message": "صيغة الإيميل غير صحيحة"}), 400
        
        # التحقق من قوة كلمة المرور
        if len(password) < 6:
            return jsonify({"message": "كلمة المرور يجب أن تكون 6 أحرف على الأقل"}), 400
        
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        # التحقق من عدم وجود الإيميل مسبقاً
        cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"message": "الإيميل مسجل مسبقاً"}), 400
        
        # تشفير كلمة المرور وتحويلها إلى string
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # توليد رقم عضوية فريد
        while True:
            member_id = generate_member_id()
            cursor.execute("SELECT member_id FROM users WHERE member_id = ?", (member_id,))
            if not cursor.fetchone():
                break
        
        # توليد رمز التحقق
        verification_code = str(random.randint(100000, 999999))
        
        # إدراج المستخدم الجديد
        cursor.execute('''
            INSERT INTO users (member_id, full_name, email, phone, birth_date, password, verification_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (member_id, full_name, email, phone, birth_date, hashed_password, verification_code))
        
        # إنشاء سجل النقاط الأولي
        cursor.execute("INSERT INTO user_points (member_id, total_points) VALUES (?, 0)", (member_id,))
        
        # إضافة معاملة ترحيبية (نقاط مجانية)
        cursor.execute('''
            INSERT INTO transactions (member_id, transaction_type, points, description)
            VALUES (?, 'bonus', 100, 'نقاط ترحيبية للانضمام لنظام الولاء')
        ''', (member_id,))
        
        # تحديث إجمالي النقاط
        cursor.execute("UPDATE user_points SET total_points = 100 WHERE member_id = ?", (member_id,))
        
        conn.commit()
        conn.close()
        
        # إرسال إيميل التحقق
        subject = "تحقق من حساب Roger Loyalty"
        body = f"""
        أهلاً {full_name}،
        
        مرحباً بك في نظام الولاء Roger Loyalty!
        
        رقم عضويتك: {member_id}
        رمز التحقق: {verification_code}
        
        يرجى إدخال هذا الرمز لتفعيل حسابك.
        
        مع تحيات فريق Roger Loyalty
        """
        
        email_sent = send_email(email, subject, body)
        
        return jsonify({
            "message": "تم إنشاء الحساب بنجاح! يرجى التحقق من الإيميل لتفعيل الحساب.",
            "member_id": member_id,
            "email_sent": email_sent
        }), 201
        
    except Exception as e:
        return jsonify({"message": f"خطأ في إنشاء الحساب: {str(e)}"}), 500

@app.route('/verify', methods=['POST'])
def verify_account():
    """تفعيل الحساب بواسطة رمز التحقق"""
    try:
        data = request.get_json()
        email = data.get('email')
        verification_code = data.get('verification_code')
        
        if not all([email, verification_code]):
            return jsonify({"message": "يرجى إدخال الإيميل ورمز التحقق"}), 400
        
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, member_id, full_name, verified FROM users WHERE email = ? AND verification_code = ?", 
                      (email, verification_code))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({"message": "رمز التحقق غير صحيح"}), 400
        
        if user[3] == 1:
            conn.close()
            return jsonify({"message": "الحساب مفعل مسبقاً"}), 400
        
        # تفعيل الحساب
        cursor.execute("UPDATE users SET verified = 1, verification_code = NULL WHERE email = ?", (email,))
        conn.commit()
        conn.close()
        
        return jsonify({
            "message": "تم تفعيل الحساب بنجاح!",
            "member_id": user[1],
            "full_name": user[2]
        }), 200
        
    except Exception as e:
        return jsonify({"message": f"خطأ في التحقق: {str(e)}"}), 500

@app.route('/login', methods=['POST'])
def login():
    """تسجيل الدخول"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not all([email, password]):
            return jsonify({"message": "يرجى إدخال الإيميل وكلمة المرور"}), 400
        
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, member_id, full_name, password, verified FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({"message": "بيانات الدخول غير صحيحة"}), 401
        
        # التحقق من كلمة المرور - تحويل string من DB إلى bytes للمقارنة
        if not bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):
            conn.close()
            return jsonify({"message": "بيانات الدخول غير صحيحة"}), 401
        
        if user[4] == 0:
            conn.close()
            return jsonify({
                "message": "يرجى تفعيل الحساب أولاً",
                "requires_verification": True
            }), 200
        
        # الحصول على النقاط
        cursor.execute("SELECT total_points FROM user_points WHERE member_id = ?", (user[1],))
        points_data = cursor.fetchone()
        total_points = points_data[0] if points_data else 0
        
        conn.close()
        
        return jsonify({
            "message": "تم تسجيل الدخول بنجاح",
            "user": {
                "id": user[0],
                "member_id": user[1],
                "full_name": user[2],
                "email": email,
                "total_points": total_points
            }
        }), 200
        
    except Exception as e:
        return jsonify({"message": f"خطأ في تسجيل الدخول: {str(e)}"}), 500

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    """إعادة تعيين كلمة المرور"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({"message": "يرجى إدخال الإيميل"}), 400
        
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, full_name FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            # لأسباب أمنية، نقول أن الإيميل تم إرساله حتى لو لم يكن موجود
            return jsonify({"message": "إذا كان الإيميل مسجل، ستتلقى رابط إعادة التعيين"}), 200
        
        # توليد رمز إعادة التعيين باستخدام random بدلاً من secrets
        import secrets
        reset_token = secrets.token_urlsafe(32)
        reset_expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        
        cursor.execute("UPDATE users SET reset_token = ?, reset_expires = ? WHERE email = ?", 
                      (reset_token, reset_expires, email))
        conn.commit()
        conn.close()
        
        # إرسال إيميل إعادة التعيين
        subject = "إعادة تعيين كلمة المرور - Roger Loyalty"
        body = f"""
        أهلاً {user[1]},
        
        تلقينا طلب لإعادة تعيين كلمة المرور لحسابك في نظام Roger Loyalty.
        
        رمز إعادة التعيين: {reset_token}
        
        هذا الرمز صالح لمدة ساعة واحدة فقط.
        
        إذا لم تطلب إعادة تعيين كلمة المرور، يرجى تجاهل هذا الإيميل.
        
        مع تحيات فريق Roger Loyalty
        """
        
        email_sent = send_email(email, subject, body)
        
        return jsonify({
            "message": "إذا كان الإيميل مسجل، ستتلقى رابط إعادة التعيين",
            "email_sent": email_sent
        }), 200
        
    except Exception as e:
        return jsonify({"message": f"خطأ في إرسال إعادة التعيين: {str(e)}"}), 500

@app.route('/reset-password', methods=['POST'])
def reset_password():
    """تعيين كلمة مرور جديدة"""
    try:
        data = request.get_json()
        reset_token = data.get('reset_token')
        new_password = data.get('new_password')
        
        if not all([reset_token, new_password]):
            return jsonify({"message": "يرجى إدخال الرمز وكلمة المرور الجديدة"}), 400
        
        if len(new_password) < 6:
            return jsonify({"message": "كلمة المرور يجب أن تكون 6 أحرف على الأقل"}), 400
        
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        # التحقق من صحة الرمز وأنه لم ينته
        cursor.execute("SELECT id, email FROM users WHERE reset_token = ? AND reset_expires > ?", 
                      (reset_token, datetime.utcnow().isoformat()))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({"message": "رمز إعادة التعيين غير صالح أو منتهي الصلاحية"}), 400
        
        # تشفير كلمة المرور الجديدة وتحويلها إلى string
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # تحديث كلمة المرور وحذف رمز الإعادة
        cursor.execute('''
            UPDATE users 
            SET password = ?, reset_token = NULL, reset_expires = NULL 
            WHERE id = ?
        ''', (hashed_password, user[0]))
        
        conn.commit()
        conn.close()
        
        return jsonify({"message": "تم تحديث كلمة المرور بنجاح"}), 200
        
    except Exception as e:
        return jsonify({"message": f"خطأ في تحديث كلمة المرور: {str(e)}"}), 500

@app.route('/profile/<member_id>', methods=['GET'])
def get_profile(member_id):
    """الحصول على بيانات المستخدم"""
    try:
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        # جلب بيانات المستخدم
        cursor.execute('''
            SELECT u.member_id, u.full_name, u.email, u.phone, u.birth_date, u.created_at,
                   p.total_points
            FROM users u
            LEFT JOIN user_points p ON u.member_id = p.member_id
            WHERE u.member_id = ? AND u.verified = 1
        ''', (member_id,))
        
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({"message": "المستخدم غير موجود"}), 404
        
        # جلب آخر 10 معاملات
        cursor.execute('''
            SELECT transaction_type, points, description, created_at
            FROM transactions
            WHERE member_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        ''', (member_id,))
        
        transactions = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "user": {
                "member_id": user[0],
                "full_name": user[1],
                "email": user[2],
                "phone": user[3],
                "birth_date": user[4],
                "created_at": user[5],
                "total_points": user[6] or 0
            },
            "recent_transactions": [
                {
                    "type": t[0],
                    "points": t[1],
                    "description": t[2],
                    "date": t[3]
                } for t in transactions
            ]
        }), 200
        
    except Exception as e:
        return jsonify({"message": f"خطأ في جلب البيانات: {str(e)}"}), 500

@app.route('/add-points', methods=['POST'])
def add_points():
    """إضافة نقاط للمستخدم (للاستخدام الإداري)"""
    try:
        data = request.get_json()
        member_id = data.get('member_id')
        points = data.get('points')
        description = data.get('description', 'إضافة نقاط')
        
        if not all([member_id, points]):
            return jsonify({"message": "يرجى إدخال رقم العضوية والنقاط"}), 400
        
        if not isinstance(points, int) or points <= 0:
            return jsonify({"message": "يجب أن تكون النقاط رقم صحيح موجب"}), 400
        
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        # التحقق من وجود المستخدم
        cursor.execute("SELECT id FROM users WHERE member_id = ? AND verified = 1", (member_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"message": "المستخدم غير موجود"}), 404
        
        # إضافة المعاملة
        cursor.execute('''
            INSERT INTO transactions (member_id, transaction_type, points, description)
            VALUES (?, 'earn', ?, ?)
        ''', (member_id, points, description))
        
        # تحديث إجمالي النقاط
        cursor.execute('''
            UPDATE user_points 
            SET total_points = total_points + ?
            WHERE member_id = ?
        ''', (points, member_id))
        
        # الحصول على إجمالي النقاط الجديد
        cursor.execute("SELECT total_points FROM user_points WHERE member_id = ?", (member_id,))
        new_total = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "message": f"تم إضافة {points} نقطة بنجاح",
            "new_total": new_total
        }), 200
        
    except Exception as e:
        return jsonify({"message": f"خطأ في إضافة النقاط: {str(e)}"}), 500

if __name__ == '__main__':
    init_database()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
    init_database()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

