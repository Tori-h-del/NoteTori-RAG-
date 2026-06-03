import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import markdown
import io
from datetime import datetime
from openai import OpenAI

app = Flask(__name__)
app.secret_key = 'sk-61ad91922a884058933a0d2b5cad3d4b'

# AI 配置 (阿里云通义千问)
AI_CONFIG = {
    'api_key': 'sk-61ad91922a884058933a0d2b5cad3d4b',
    'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'model': 'qwen-plus'
}

client = OpenAI(api_key=AI_CONFIG['api_key'], base_url=AI_CONFIG['base_url'])

# Markdown 过滤器
@app.template_filter('markdown')
def render_markdown(text):
    return markdown.markdown(text, extensions=['extra', 'codehilite'])

# 数据库连接配置
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '050816',
    'database': 'blogdb'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None


def init_db():
    conn = get_db_connection()
    if not conn:
        print("无法连接数据库，无法完成初始化")
        return

    cursor = conn.cursor()
    # 创建用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usermodel (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(80) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        )
    ''')

    # 创建笔记表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            category VARCHAR(50) DEFAULT '未分类',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES usermodel(id)
        )
    ''')

    # 创建聊天记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            role ENUM('user', 'assistant') NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES usermodel(id)
        )
    ''')
    
    # 检查并添加缺失的列 (简单的迁移逻辑)
    cursor.execute("SHOW COLUMNS FROM notes LIKE 'created_at'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE notes ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    
    cursor.execute("SHOW COLUMNS FROM notes LIKE 'updated_at'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE notes ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

    cursor.execute("SHOW COLUMNS FROM notes LIKE 'category'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE notes ADD COLUMN category VARCHAR(50) DEFAULT '未分类'")

    conn.commit()
    cursor.close()
    conn.close()


# 登录保护装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
@login_required
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM notes WHERE user_id = %s', (session['user_id'],))
    notes = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', notes=notes)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO usermodel (username, password) VALUES (%s, %s)', (username, hashed_password))
            conn.commit()
            flash('注册成功，请登录')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('用户名已存在')
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM usermodel WHERE username = %s', (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/note/create', methods=['GET', 'POST'])
@login_required
def create_note():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category = request.form.get('category', '未分类')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO notes (user_id, title, content, category) VALUES (%s, %s, %s, %s)',
                       (session['user_id'], title, content, category))
        conn.commit()
        cursor.close()
        conn.close()
        flash('笔记创建成功')
        return redirect(url_for('index'))
    return render_template('create_note.html')

@app.route('/note/view/<int:id>')
@login_required
def view_note(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM notes WHERE id = %s AND user_id = %s', (id, session['user_id']))
    note = cursor.fetchone()
    cursor.close()
    conn.close()
    if note:
        return render_template('view_note.html', note=note)
    flash('笔记未找到或无权访问')
    return redirect(url_for('index'))


@app.route('/note/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_note(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM notes WHERE id = %s AND user_id = %s', (id, session['user_id']))
    note = cursor.fetchone()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category = request.form.get('category', '未分类')
        cursor.execute('UPDATE notes SET title = %s, content = %s, category = %s WHERE id = %s', (title, content, category, id))
        conn.commit()
        cursor.close()
        conn.close()
        flash('笔记更新成功')
        return redirect(url_for('index'))

    cursor.close()
    conn.close()
    if note:
        return render_template('edit_note.html', note=note)
    flash('笔记未找到或无权访问')
    return redirect(url_for('index'))


@app.route('/note/delete/<int:id>', methods=['POST'])
@login_required
def delete_note(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM notes WHERE id = %s AND user_id = %s', (id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    flash('笔记已删除')
    return redirect(url_for('index'))


@app.route('/export/md')
@login_required
def export_notes_md():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT title, content, category, created_at, updated_at FROM notes WHERE user_id = %s', (session['user_id'],))
    notes = cursor.fetchall()
    cursor.close()
    conn.close()

    output = io.StringIO()
    output.write(f"# {session['username']} 的笔记导出\n")
    output.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    output.write("---\n\n")
    
    for note in notes:
        output.write(f"## {note['title']}\n")
        output.write(f"**分类**: {note['category']}  \n")
        output.write(f"**创建时间**: {note['created_at'].strftime('%Y-%m-%d %H:%M:%S') if note['created_at'] else '未知'}  \n")
        output.write(f"**内容**:\n\n{note['content']}\n\n")
        output.write("---\n\n")
        
    return Response(
        output.getvalue(),
        mimetype='text/markdown',
        headers={'Content-Disposition': f'attachment;filename=notes_{session["username"]}.md'}
    )


@app.route('/note/export/md/<int:id>')
@login_required
def export_single_note_md(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT title, content, category, created_at, updated_at FROM notes WHERE id = %s AND user_id = %s', (id, session['user_id']))
    note = cursor.fetchone()
    cursor.close()
    conn.close()

    if not note:
        flash('笔记未找到')
        return redirect(url_for('index'))

    output = io.StringIO()
    output.write(f" {note['title']}\n\n")
    output.write(f"分类: {note['category']}\n")
    output.write(f"创建时间: {note['created_at'].strftime('%Y-%m-%d %H:%M:%S') if note['created_at'] else '未知'}\n")
    output.write(f"更新时间: {note['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if note['updated_at'] else '未知'}\n\n")
    output.write("\n\n")
    output.write(note['content'])

    return Response(
        output.getvalue(),
        mimetype='text/markdown',
        headers={'Content-Disposition': f'attachment;filename={note["title"]}.md'}
    )


@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM notes WHERE user_id = %s AND (title LIKE %s OR content LIKE %s)',
                   (session['user_id'], f'%{query}%', f'%{query}%'))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('search_results.html', notes=results, query=query)

@app.route('/profile')
@login_required
def profile():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 获取笔记总数
    cursor.execute('SELECT COUNT(*) as count FROM notes WHERE user_id = %s', (session['user_id'],))
    total_notes = cursor.fetchone()['count']
    
    # 获取分类统计
    cursor.execute('SELECT category, COUNT(*) as count FROM notes WHERE user_id = %s GROUP BY category', (session['user_id'],))
    categories = cursor.fetchall()

    # 获取 AI 聊天次数
    cursor.execute('SELECT COUNT(*) as count FROM chat_history WHERE user_id = %s AND role = "user"', (session['user_id'],))
    chat_count = cursor.fetchone()['count']
    
    cursor.close()
    conn.close()
    return render_template('profile.html', total_notes=total_notes, categories=categories, chat_count=chat_count)


@app.route('/ai/chat', methods=['GET'])
@login_required
def ai_chat_page():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM chat_history WHERE user_id = %s ORDER BY created_at ASC', (session['user_id'],))
    history = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('chat.html', history=history)


@app.route('/ai/chat/send', methods=['POST'])
@login_required
def ai_chat_send():
    message = request.json.get('message')
    if not message:
        return jsonify({'error': '消息不能为空'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # RAG
        # 1. 在笔记库中搜索与问题相关的关键词
        # 用SQLLIKE进行基础检索
        search_query = f"%{message}%"
        cursor.execute('''
            SELECT title, content FROM notes 
            WHERE user_id = %s AND (title LIKE %s OR content LIKE %s)
            LIMIT 3
        ''', (session['user_id'], search_query, search_query))
        related_notes = cursor.fetchall()
        
        # 如果关键词匹配不到，尝试提取短词搜索
        if not related_notes and len(message) > 2:
            short_query = f"%{message[:2]}%"
            cursor.execute('''
                SELECT title, content FROM notes 
                WHERE user_id = %s AND (title LIKE %s OR content LIKE %s)
                LIMIT 3
            ''', (session['user_id'], short_query, short_query))
            related_notes = cursor.fetchall()

        # 2. 构建知识背景 (Context)
        context_text = ""
        if related_notes:
            context_text = "\n".join([f"--- 笔记《{n['title']}》---\n{n['content']}" for n in related_notes])

        # 3. 准备发送给 AI 的消息
        system_prompt = "你是一个基于用户个人笔记的AI助手。请优先根据提供的笔记内容回答问题。如果笔记中没有相关信息，请告知用户。回答应简洁专业。"
        
        ai_messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        if context_text:
            ai_messages.append({
                "role": "system", 
                "content": f"这是从用户笔记库中检索到的相关内容：\n{context_text}"
            })
            
        ai_messages.append({"role": "user", "content": message})

        # 4. 调用 AI
        response = client.chat.completions.create(
            model=AI_CONFIG['model'],
            messages=ai_messages
        )
        ai_response = response.choices[0].message.content

        # 5. 保存对话记录
        cursor.execute('INSERT INTO chat_history (user_id, role, content) VALUES (%s, %s, %s)',
                       (session['user_id'], 'user', message))
        cursor.execute('INSERT INTO chat_history (user_id, role, content) VALUES (%s, %s, %s)',
                       (session['user_id'], 'assistant', ai_response))
        conn.commit()
        
        return jsonify({
            'response': ai_response,
            'source_notes': [n['title'] for n in related_notes] # 返回引用来源
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/ai/chat/clear', methods=['POST'])
@login_required
def ai_chat_clear():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM chat_history WHERE user_id = %s', (session['user_id'],))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'status': 'success'})


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
