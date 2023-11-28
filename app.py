from flask import Flask, make_response, redirect, render_template, request, send_from_directory, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from googletrans import Translator
from bs4 import BeautifulSoup, NavigableString
from datetime import datetime
    
app = Flask(__name__)
# socketio = SocketIO(app)
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

@app.route('/')
@app.route('/<language>/')
@app.route('/home/')
@app.route('/<language>/home/')
def homepage(language='none'):
    if not (request.path != '' or request.path.endswith('/home')):
        return send_from_directory(app.static_folder, request.path[1:])
    if language == 'none' or language not in available_langs:
        language = request.cookies.get('article_lang', default='en')

    title_lang = getattr(Article, f"title_{language}")
    articles = Article.query.with_entities(Article.article_id, title_lang, Article.date_time, Article.main_img_url).all() #order_by(Article.article_id.desc())
    response = make_response(render_template('home_page.html', title="Home", articles=articles, language=language))
    response.set_cookie('article_lang',language, max_age=30 * 24 * 60 * 60, path='/')
    return response


@app.route("/admin")
def serve_adminpanel():
    if 'user_id' in session:
        articles = Article.query.with_entities(Article.article_id, Article.title_en, Article.author_id, Article.date_time, Article.main_img_url, Article.summary_en).all() #order_by(Article.article_id.desc())
        return render_template('admin_panel.html', title="Admin Panel", articles=articles, user=session['username'])
    else:
        return redirect(url_for('login'))

# Admin logout
@app.route('/admin/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route("/admin/create-article", methods=['GET', 'POST'])
def create_article():
    article = Article(title_en="", title_hi="",title_ta="",title_te="",summary_en="",summary_hi="",summary_ta="",summary_te="",author_id="",main_img_url="",content_en=" ",content_te=" ",content_ta=" ",content_hi=" ")
    if request.method == 'POST':
        new_article = Article(
            title_en = request.form.get('title_en'),
            title_hi = request.form.get('title_hi'),
            title_ta = request.form.get('title_ta'),
            title_te = request.form.get('title_te'),
            summary_en = request.form.get('summary_en'),
            summary_hi = request.form.get('summary_hi'),
            summary_ta = request.form.get('summary_ta'),
            summary_te = request.form.get('summary_te'),
            author_id = request.form.get('author_id'),
            main_img_url = request.form.get('main_img_url'),
            content_en = request.form.get('content_textarea_en'),
            content_te = request.form.get('content_textarea_te'),
            content_hi = request.form.get('content_textarea_hi'),
            content_ta = request.form.get('content_textarea_ta')
        )
        db.session.add(new_article)
        db.session.commit()
        print("Created Successfully")
        return redirect(url_for('serve_adminpanel'))
    return render_template('create_article.html', title="Create Article", article=article)

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
# 2023-12-27T17:33:14.275Z
@app.route("/admin/<int:article_id>/update", methods=['GET','POST'])
def update_article(article_id):
    article = Article.query.get_or_404(article_id)
    if request.method == 'POST':
        article.title_en = request.form.get('title_en')
        article.title_hi = request.form.get('title_hi')
        article.title_ta = request.form.get('title_ta')
        article.title_te = request.form.get('title_te')
        article.summary_en = request.form.get('summary_en')
        article.summary_hi = request.form.get('summary_hi')
        article.summary_ta = request.form.get('summary_ta')
        article.summary_te = request.form.get('summary_te')
        article.author_id = request.form.get('author_id')
        article.main_img_url = request.form.get('main_img_url')
        article.content_en = request.form.get('content_textarea_en')
        article.content_ta = request.form.get('content_textarea_ta')
        article.content_hi = request.form.get('content_textarea_hi')
        article.content_te = request.form.get('content_textarea_te')
        
        db.session.commit()
        return redirect(url_for('serve_adminpanel'))
    return render_template('create_article.html', title="Update Article", article=article)

@app.route('/admin/<article_id>/delete')
def delete_entry(article_id):
    entry = Article.query.get(article_id)
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for('serve_adminpanel'))

if __name__ == '__main__':
    print(datetime.utcnow())
    with app.app_context():
        db.create_all()
        db.session.commit()
    app.run(debug = True)
