from flask import Flask, request, jsonify, render_template
import sqlite3
import bcrypt
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import os
import secrets
import re
import random
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'roger-loyalty-secret-key-2024')

# إعدادات الإيميل
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
EMAIL_USER = os.environ.get('EMAIL_USER', 'modmac1000@gmail.com')
EMAIL_PASS = os.environ.get('EMAIL_PASS', 'yglr plkj lmhr ahty')
def generate_member_id():
    """توليد رقم عضوية فريد"""
    random_numbers = ''.join([str(random.randint(0, 9)) for _ in range(7)])
    return f"LA-ROJ{random_numbers}"

def init_database():
    """إنشاء قاعدة البيانات والجداول"""
    conn = sqlite3.connect('roger_loyalty.db')
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            birth_date DATE NOT NULL,
            password TEXT NOT NULL,
            points INTEGER DEFAULT 0,
            is_verified BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول رموز التحقق
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            phone TEXT,
            member_id TEXT,
            code TEXT NOT NULL,
            code_type TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            is_used BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول المعاملات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            points INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def send_verification_email(email, code, code_type):
    """إرسال رمز التحقق عبر الإيميل"""
    try:
        msg = MimeMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = email
        
        if code_type == 'register':
            msg['Subject'] = "رمز التحقق - Roger Loyalty"
            body = f"""
            مرحباً بك في نظام Roger Loyalty!
            
            رمز التحقق الخاص بك هو: {code}
            
            يرجى إدخال هذا الرمز لتفعيل حسابك.
            الرمز صالح لمدة 10 دقائق فقط.
            
            إذا لم تقم بإنشاء هذا الحساب، يرجى تجاهل هذا الإيميل.
            """
        elif code_type == 'login':
            msg['Subject'] = "رمز تسجيل الدخول - Roger Loyalty"
            body = f"""
            رمز تسجيل الدخول الخاص بك هو: {code}
            
            يرجى إدخال هذا الرمز لتسجيل الدخول.
            الرمز صالح لمدة 5 دقائق فقط.
            
            إذا لم تحاول تسجيل الدخول، يرجى تجاهل هذا الإيميل.
            """
        elif code_type == 'reset_password':
            msg['Subject'] = "رمز إعادة تعيين كلمة المرور - Roger Loyalty"
            body = f"""
            رمز إعادة تعيين كلمة المرور الخاص بك هو: {code}
            
            يرجى إدخال هذا الرمز لإعادة تعيين كلمة المرور.
            الرمز صالح لمدة 10 دقائق فقط.
            
            إذا لم تطلب إعادة تعيين كلمة المرور، يرجى تجاهل هذا الإيميل.
            """
        
        msg.attach(MimeText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"خطأ في إرسال الإيميل: {e}")
        return False

def generate_verification_code():
    """توليد رمز تحقق مكون من 6 أرقام"""
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/check_availability', methods=['POST'])
def check_availability():
    """التحقق من توفر الإيميل ورقم الهاتف"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        phone = data.get('phone', '').strip()
        
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        result = {'email_available': True, 'phone_available': True}
        
        if email:
            cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
            if cursor.fetchone():
                result['email_available'] = False
        
        if phone:
            cursor.execute('SELECT id FROM users WHERE phone = ?', (phone,))
            if cursor.fetchone():
                result['phone_available'] = False
        
        conn.close()
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/send_register_code', methods=['POST'])
def send_register_code():
    """إرسال رمز التحقق للتسجيل"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'success': False, 'message': 'الإيميل مطلوب'})
        
        # توليد رمز التحقق
        code = generate_verification_code()
        expires_at = datetime.now() + timedelta(minutes=10)
        
        # حفظ الرمز في قاعدة البيانات
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        # حذف الرموز المنتهية الصلاحية
        cursor.execute('DELETE FROM verification_codes WHERE expires_at < ? AND email = ?', 
                      (datetime.now(), email))
        
        cursor.execute('''
            INSERT INTO verification_codes (email, code, code_type, expires_at)
            VALUES (?, ?, 'register', ?)
        ''', (email, code, expires_at))
        
        conn.commit()
        conn.close()
        
        # إرسال الرمز عبر الإيميل
        if send_verification_email(email, code, 'register'):
            return jsonify({'success': True, 'message': 'تم إرسال رمز التحقق إلى إيميلك'})
        else:
            return jsonify({'success': False, 'message': 'حدث خطأ في إرسال الإيميل'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'})

@app.route('/verify_register_code', methods=['POST'])
def verify_register_code():
    """التحقق من رمز التسجيل وإنشاء الحساب"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip()
        full_name = data.get('full_name', '').strip()
        phone = data.get('phone', '').strip()
        birth_date = data.get('birth_date', '').strip()
        password = data.get('password', '')
        
        # التحقق من الرمز
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id FROM verification_codes 
            WHERE email = ? AND code = ? AND code_type = 'register' 
            AND expires_at > ? AND is_used = 0
        ''', (email, code, datetime.now()))
        
        verification = cursor.fetchone()
        
        if not verification:
            conn.close()
            return jsonify({'success': False, 'message': 'رمز التحقق غير صحيح أو منتهي الصلاحية'})
        
        # تشفير كلمة المرور
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # توليد رقم عضوية فريد
        member_id = generate_member_id()
        while True:
            cursor.execute('SELECT id FROM users WHERE member_id = ?', (member_id,))
            if not cursor.fetchone():
                break
            member_id = generate_member_id()
        
        # إنشاء الحساب
        cursor.execute('''
            INSERT INTO users (member_id, full_name, email, phone, birth_date, password, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        ''', (member_id, full_name, email, phone, birth_date, hashed_password))
        
        # تحديث حالة الرمز إلى مستخدم
        cursor.execute('UPDATE verification_codes SET is_used = 1 WHERE id = ?', (verification[0],))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'تم إنشاء حسابك بنجاح! رقم العضوية الخاص بك: {member_id}',
            'member_id': member_id
        })
    
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'الإيميل أو رقم الهاتف مستخدم مسبقاً'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'})

@app.route('/send_login_code', methods=['POST'])
def send_login_code():
    """إرسال رمز تسجيل الدخول"""
    try:
        data = request.json
        login_field = data.get('login_field', '').strip()
        password = data.get('password', '')
        
        if not login_field or not password:
            return jsonify({'success': False, 'message': 'يرجى ملء جميع الحقول'})
        
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        # البحث عن المستخدم
        if '@' in login_field:
            cursor.execute('SELECT id, email, password, is_verified FROM users WHERE email = ?', (login_field.lower(),))
        elif login_field.startswith('LA-ROJ'):
            cursor.execute('SELECT id, email, password, is_verified FROM users WHERE member_id = ?', (login_field,))
        else:
            cursor.execute('SELECT id, email, password, is_verified FROM users WHERE phone = ?', (login_field,))
        
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'المستخدم غير موجود'})
        
        if not user[3]:  # غير مفعل
            conn.close()
            return jsonify({'success': False, 'message': 'الحساب غير مفعل'})
        
        # التحقق من كلمة المرور
        if not bcrypt.checkpw(password.encode('utf-8'), user[2]):
            conn.close()
            return jsonify({'success': False, 'message': 'كلمة المرور غير صحيحة'})
        
        # توليد رمز تسجيل الدخول
        code = generate_verification_code()
        expires_at = datetime.now() + timedelta(minutes=5)
        
        cursor.execute('''
            INSERT INTO verification_codes (email, code, code_type, expires_at)
            VALUES (?, ?, 'login', ?)
        ''', (user[1], code, expires_at))
        
        conn.commit()
        conn.close()
        
        if send_verification_email(user[1], code, 'login'):
            return jsonify({'success': True, 'message': 'تم إرسال رمز تسجيل الدخول إلى إيميلك'})
        else:
            return jsonify({'success': False, 'message': 'حدث خطأ في إرسال الإيميل'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'})

@app.route('/verify_login_code', methods=['POST'])
def verify_login_code():
    """التحقق من رمز تسجيل الدخول"""
    try:
        data = request.json
        login_field = data.get('login_field', '').strip()
        code = data.get('code', '').strip()
        
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        # الحصول على الإيميل
        if '@' in login_field:
            email = login_field.lower()
        elif login_field.startswith('LA-ROJ'):
            cursor.execute('SELECT email FROM users WHERE member_id = ?', (login_field,))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return jsonify({'success': False, 'message': 'المستخدم غير موجود'})
            email = result[0]
        else:
            cursor.execute('SELECT email FROM users WHERE phone = ?', (login_field,))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return jsonify({'success': False, 'message': 'المستخدم غير موجود'})
            email = result[0]
        
        # التحقق من الرمز
        cursor.execute('''
            SELECT id FROM verification_codes 
            WHERE email = ? AND code = ? AND code_type = 'login' 
            AND expires_at > ? AND is_used = 0
        ''', (email, code, datetime.now()))
        
        verification = cursor.fetchone()
        
        if not verification:
            conn.close()
            return jsonify({'success': False, 'message': 'رمز التحقق غير صحيح أو منتهي الصلاحية'})
        
        # الحصول على بيانات المستخدم
        cursor.execute('SELECT id, member_id, full_name, points FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        
        # تحديث حالة الرمز
        cursor.execute('UPDATE verification_codes SET is_used = 1 WHERE id = ?', (verification[0],))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'تم تسجيل الدخول بنجاح',
            'user': {
                'id': user[0],
                'member_id': user[1],
                'name': user[2],
                'points': user[3]
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'})

@app.route('/send_reset_code', methods=['POST'])
def send_reset_code():
    """إرسال رمز إعادة تعيين كلمة المرور"""
    try:
        data = request.json
        reset_field = data.get('reset_field', '').strip()
        
        if not reset_field:
            return jsonify({'success': False, 'message': 'يرجى إدخال الإيميل أو رقم العضوية أو رقم الهاتف'})
        
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        # البحث عن المستخدم
        if '@' in reset_field:
            cursor.execute('SELECT email FROM users WHERE email = ?', (reset_field.lower(),))
        elif reset_field.startswith('LA-ROJ'):
            cursor.execute('SELECT email FROM users WHERE member_id = ?', (reset_field,))
        else:
            cursor.execute('SELECT email FROM users WHERE phone = ?', (reset_field,))
        
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'المستخدم غير موجود'})
        
        # توليد رمز إعادة التعيين
        code = generate_verification_code()
        expires_at = datetime.now() + timedelta(minutes=10)
        
        cursor.execute('''
            INSERT INTO verification_codes (email, code, code_type, expires_at)
            VALUES (?, ?, 'reset_password', ?)
        ''', (user[0], code, expires_at))
        
        conn.commit()
        conn.close()
        
        if send_verification_email(user[0], code, 'reset_password'):
            return jsonify({'success': True, 'message': 'تم إرسال رمز إعادة تعيين كلمة المرور إلى إيميلك'})
        else:
            return jsonify({'success': False, 'message': 'حدث خطأ في إرسال الإيميل'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'})

@app.route('/verify_reset_code', methods=['POST'])
def verify_reset_code():
    """التحقق من رمز إعادة التعيين وتغيير كلمة المرور"""
    try:
        data = request.json
        reset_field = data.get('reset_field', '').strip()
        code = data.get('code', '').strip()
        new_password = data.get('new_password', '')
        
        conn = sqlite3.connect('roger_loyalty.db')
        cursor = conn.cursor()
        
        # الحصول على الإيميل
        if '@' in reset_field:
            email = reset_field.lower()
        elif reset_field.startswith('LA-ROJ'):
            cursor.execute('SELECT email FROM users WHERE member_id = ?', (reset_field,))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return jsonify({'success': False, 'message': 'المستخدم غير موجود'})
            email = result[0]
        else:
            cursor.execute('SELECT email FROM users WHERE phone = ?', (reset_field,))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return jsonify({'success': False, 'message': 'المستخدم غير موجود'})
            email = result[0]
        
        # التحقق من الرمز
        cursor.execute('''
            SELECT id FROM verification_codes 
            WHERE email = ? AND code = ? AND code_type = 'reset_password' 
            AND expires_at > ? AND is_used = 0
        ''', (email, code, datetime.now()))
        
        verification = cursor.fetchone()
        
        if not verification:
            conn.close()
            return jsonify({'success': False, 'message': 'رمز التحقق غير صحيح أو منتهي الصلاحية'})
        
        # تشفير كلمة المرور الجديدة
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        # تحديث كلمة المرور
        cursor.execute('UPDATE users SET password = ? WHERE email = ?', (hashed_password, email))
        
        # تحديث حالة الرمز
        cursor.execute('UPDATE verification_codes SET is_used = 1 WHERE id = ?', (verification[0],))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'تم تغيير كلمة المرور بنجاح'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'})

if __name__ == '__main__':
    init_database()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)