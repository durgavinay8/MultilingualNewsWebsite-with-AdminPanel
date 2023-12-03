from flask import Flask, make_response, redirect, render_template, request, send_from_directory, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from googletrans import Translator
from bs4 import BeautifulSoup, NavigableString
from datetime import datetime

from sqlalchemy import null
    
app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = '#123456'
db = SQLAlchemy(app)

available_langs = ["en", "te", "ta", "hi"]
class Author(db.Model):
    author_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    author_name = db.Column(db.String(70))
    author_img_url = db.Column(db.Text)
    article = db.relationship('Article', backref='author', lazy=True)

class Article(db.Model):
    article_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title_en = db.Column(db.String(1200))
    title_hi = db.Column(db.String(1200))
    title_ta = db.Column(db.String(1200))
    title_te = db.Column(db.String(1200))
    author_id = db.Column(db.Integer, db.ForeignKey('author.author_id'))
    date_time = db.Column(db.DateTime, default=datetime.utcnow)
    summary_en = db.Column(db.Text)
    summary_hi = db.Column(db.Text)
    summary_ta = db.Column(db.Text)
    summary_te = db.Column(db.Text)
    main_img_url = db.Column(db.Text)
    content_en = db.Column(db.Text)
    content_te = db.Column(db.Text)
    content_ta = db.Column(db.Text)
    content_hi = db.Column(db.Text)
    translator_te_userid = db.Column(db.Integer, db.ForeignKey('user.id'))
    translator_hi_userid = db.Column(db.Integer, db.ForeignKey('user.id'))
    translator_ta_userid = db.Column(db.Integer, db.ForeignKey('user.id'))

    translator_te_user = db.relationship('User', foreign_keys=[translator_te_userid])
    translator_hi_user = db.relationship('User', foreign_keys=[translator_hi_userid])
    translator_ta_user = db.relationship('User', foreign_keys=[translator_ta_userid])

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    # article = db.relationship('Article', backref='user', lazy=True)

# Admin login validation
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        userID = request.form.get('userID')
        password = request.form.get('password')

        user = User.query.filter_by(id=userID).first()

        if user and password == user.password:
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('serve_adminpanel'))
        else:
            return render_template('admin_login.html', error='Invalid username or password')

    return render_template('admin_login.html')

#client routes
@app.route('/')
@app.route('/<language>/')
@app.route('/home/')
@app.route('/<language>/home/')
def homepage(language='none'):
    if (request.path != '' or request.path.endswith('/home')):
        # return send_from_directory(app.static_folder, request.path[1:])
        if language == 'none' or language not in available_langs:
            language = request.cookies.get('article_lang', default='en')

        title_lang = getattr(Article, f"title_{language}")
        articles = Article.query.with_entities(Article.article_id, title_lang, Article.date_time, Article.main_img_url).all() #order_by(Article.article_id.desc())
        response = make_response(render_template('home_page.html', title="Home", articles=articles, language=language))
        response.set_cookie('article_lang',language, max_age=30 * 24 * 60 * 60, path='/')
        return response

@app.route("/<language>/article/<int:article_id>")
def serve_article(article_id, language='none'):
    if language == 'none' or language not in available_langs:
        language = request.cookies.get('article_lang', default='en')

    title_column = getattr(Article, f"title_{language}")
    summary_column = getattr(Article, f"summary_{language}")
    content_column = getattr(Article, f"content_{language}")
    article = (
        Article.query
        .with_entities(title_column, summary_column, content_column, Article.date_time, Article.main_img_url,Article.author_id)
        .filter(Article.article_id==article_id)
        .first()
    )
    author = (
        Author.query
        .with_entities(Author.author_img_url,Author.author_name)
        .filter(Author.author_id==article.author_id)
        .first()
    )
    response = make_response(render_template('article.html', article=article, author=author, language=language))
    response.set_cookie('article_lang',language, max_age=31 * 24 * 60 * 60, path='/')
    return response

#admin routes
@app.route("/admin")
def serve_adminpanel():
    if 'user_id' in session:
        user_id = session['user_id']
        if user_id == 1001:
            articles = Article.query.with_entities(Article.article_id, Article.title_en, Article.author_id, Article.date_time, Article.main_img_url, Article.summary_en).all()
            return render_template('admin_panel.html', title="Admin Panel", articles=articles, user=session['username'])
        else:
            match user_id:
                case 1002:
                    language = 'ta'
                case 1003:
                    language = 'te'
                case 1004:
                    language = 'hi'
                case _:
                    language = 'en'
            userid_column = getattr(Article, f"translator_{language}_userid")
            title_column = getattr(Article, f"title_{language}")
            summary_column = getattr(Article, f"summary_{language}")
            content_column = getattr(Article, f"content_{language}")
            articles = Article.query.with_entities(Article.article_id, Article.title_en, Article.date_time, Article.summary_en,title_column, summary_column, content_column).filter(userid_column == user_id).all() 
            return render_template('translator_panel.html', articles=articles, user=session['username'], language=language)
    else:
        return redirect(url_for('login'))

# Admin logout
@app.route('/admin/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route("/admin/create-article", methods=['GET', 'POST'])
def create_article():
    article = Article(title_en="",summary_en="",author_id="",main_img_url="",content_en=" ") #,translator_te_userid="",translator_hi_userid="",translator_ta_userid=""
    if request.method == 'POST':
        new_article = Article(
            title_en = request.form.get('title_en'),
            summary_en = request.form.get('summary_en'),
            author_id = request.form.get('author_id'),
            main_img_url = request.form.get('main_img_url'),
            content_en = request.form.get('content_textarea_en')
        )
        db.session.add(new_article)
        db.session.commit()
        return redirect(url_for('serve_adminpanel'))
    return render_template('create_article.html', title="Create Article", article=article)

@app.route("/admin/<int:article_id>/translations")
def serve_translations(article_id):
    article = Article.query.get_or_404(article_id)
    return render_template('all_translations.html', article=article)

@app.route("/admin/<int:article_id>/update", methods=['GET','POST'])
def update_article(article_id):
    if request.method == 'POST':
        num_rows_updated = Article.query.filter_by(article_id=article_id).update({
            'title_en' : request.form.get('title_en'),
            'summary_en' : request.form.get('summary_en'),
            'author_id' : request.form.get('author_id'),
            'main_img_url' : request.form.get('main_img_url'),
            'content_en' : request.form.get('content_textarea_en'),
        })
        db.session.commit()
        if num_rows_updated == 0:
            return "No article found with article_id: {article_id}"
        return redirect(url_for('serve_adminpanel'))
    article = (
        Article.query
        .with_entities(Article.title_en, Article.summary_en, Article.content_en, Article.author_id, Article.main_img_url)
        .filter(Article.article_id==article_id)
        .first()
    )
    if article is None:
        return 'Article not found'
    return render_template('create_article.html', title="Update Article", article=article)

def translate_tag(tag, translator, target_language):
    translated_tag = tag
    for child in translated_tag.contents:
        if isinstance(child, NavigableString):
            translated_text = translator.translate(str(child), dest=target_language).text
            child.replace_with(translated_text)
        elif child is not None and child.name:
            translated_child = translate_tag(child, translator, target_language)
            child.replace_with(translated_child)

    return translated_tag

@app.route("/admin/<int:article_id>/translate/<language>", methods=['GET','POST'])
def translate_article(article_id, language):
    if language == 'en' or language not in available_langs:
        return ""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        summary = request.form.get(f"summary_{language}")
        num_rows_updated = Article.query.filter_by(article_id=article_id).update({
            f"title_{language}" : request.form.get(f"title_{language}"),
            f"summary_{language}" : summary if summary else null(),
            f"content_{language}" : request.form.get(f"content_{language}"),
            f"translator_{language}_userid" : session['user_id']
        })
        db.session.commit()
        if num_rows_updated == 0:
            return "No article found with article_id: {article_id}"
        return redirect(url_for('serve_adminpanel'))
    
    title_column = getattr(Article, f"title_{language}")
    summary_column = getattr(Article, f"summary_{language}")
    content_column = getattr(Article, f"content_{language}")
    translated_by = getattr(Article, f"translator_{language}_userid")
    article = (
        Article.query
        .with_entities(Article.title_en, Article.summary_en, Article.content_en, translated_by, title_column, summary_column, content_column) 
        .filter(Article.article_id==article_id)
        .first()
    )
    translator = Translator()
    translated_summary=""
    if article[6] is None:
        soup = BeautifulSoup(article[2], 'html.parser')
        
        for p_tag in soup.find_all('p'):
            translated_fragments = []

            for child in p_tag.contents:
                if isinstance(child, NavigableString) and str(child).strip():
                    translated_text = translator.translate(str(child), dest=language).text
                    translated_fragments.append(translated_text)
                elif child is not None and child.name:
                    translated_child = translate_tag(child, translator, language)
                    translated_fragments.append(str(translated_child))

            p_tag.clear()
            p_tag.append(BeautifulSoup(''.join(translated_fragments), 'html.parser'))
        translated_summary = str(soup)
    translated_article = {
        'title_en':article[0],
        'summary_en':article[1],
        'content_en':article[2],
        'translated_by':article[3],
        f'title_{language}': translator.translate(article[0], dest=language).text if article[4] is None and article[0] is not None else article[4],
        f'summary_{language}': translator.translate(article[1], dest=language).text if article[5] is None and article[1] is not None else article[5],
        f'content_{language}': translated_summary if article[6] is None else article[6],
    }
    return render_template('translate_article.html', title="Translate Article", article=translated_article, language=language)

@app.route('/admin/<article_id>/delete')
def delete_entry(article_id):
    entry = Article.query.get(article_id)
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for('serve_adminpanel'))

users = {}
#sockets
@socketio.on('connect')
def handle_connect():
    users[session.get('user_id')] = request.sid
    print("users : ", users)
    print('Client connected and user_id : ', session.get('user_id'))

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected and user_id : ', session.get('user_id'))

@socketio.on('translation_request')
def handle_translation_request(data):
    print("handle_translation_request ", data)
    user_id = int(data['user_id'])
    article_id = data['article_id']
    language = data['language']
    article = (
        Article.query
        .with_entities(Article.article_id, Article.title_en, Article.summary_en, Article.author_id)
        .filter(Article.article_id==article_id)
        .first()
    )
    if article is None:
        return 'Article not found'
    article_dict = {
        'article_id': article.article_id,
        'title_en': article.title_en,
        'summary_en': article.summary_en,
        'author_id': article.author_id,
    }
    socketio.emit('receive_translation_request', {'article': article_dict, 'translate_to': language}, room = users[user_id])

if __name__ == '__main__':
    print(datetime.utcnow())
    with app.app_context():
        db.create_all()
        db.session.commit()
    socketio.run(app, debug=True)