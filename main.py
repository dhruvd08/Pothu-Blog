import datetime as dt
from typing import List

from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
import os

# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm


def send_email(to_email, msg, sender_email, sender_password):
    print(f'Sending notification to {to_email}')

    connection = smtplib.SMTP('smtp.gmail.com', port=587)
    connection.starttls()
    connection.login(user=sender_email, password=sender_password)
    connection.sendmail(from_addr=sender_email,
                        to_addrs=to_email,
                        msg=f'{msg}')
    connection.close()
    print('Email sent successfully!')


SENDER_EMAIL = os.environ.get('SENDER_EMAIL')
SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

app.config['SECRET_KEY'] = os.environ.get('FLASK_LOGIN_KEY')
login_manager = LoginManager()
login_manager.init_app(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_URI')
db = SQLAlchemy()
db.init_app(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


def admin_only(func):

    def wraper(**kwargs):
        if current_user.get_id() == '1':
            resp = func(**kwargs)
            return resp
        else:
            abort(401)
    wraper.__name__ = func.__name__
    return wraper


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(back_populates="blog_post")
    comment: Mapped[List["Comment"]] = relationship()


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped["User"] = relationship()
    blog_id: Mapped[int] = mapped_column(ForeignKey("blog_posts.id"))


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String, nullable=False)
    blog_post: Mapped[List["BlogPost"]] = relationship(back_populates='user')
    comment: Mapped[List["Comment"]] = relationship(back_populates='author')

    def is_authenticated(self):
        if current_user is not None:
            return True
        else:
            return False

    def is_active(self):
        return self.is_act

    def is_anonymous(self):
        return self.is_anony

    def get_id(self):
        return str(self.id)


# with app.app_context():
#     db.create_all()


@login_manager.user_loader
def load_user(user_id):
    user = db.get_or_404(User, int(user_id))
    return user


@app.route('/register', methods=['POST', 'GET'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        password = form.password.data
        exist_user = db.session.execute(db.select(User).where(User.email == email)).scalar()

        if exist_user is None:
            new_user = User(name=name, email=email, password=generate_password_hash(password))
            db.session.add(new_user, User)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('get_all_posts'))
        else:
            flash('Email already exists, login instead.')
            return redirect(url_for('login'))
    else:
        return render_template("register.html", form=form)


@app.route('/login', methods=['POST', 'GET'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if user is None:
            flash('Authentication failed.')
            return redirect(url_for('login'))
        else:
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash('Authentication failed.')
                return redirect(url_for('login'))
    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    posts = db.session.execute(db.select(BlogPost)).scalars().fetchall()
    return render_template("index.html", all_posts=posts)


@app.route("/post/<int:post_id>", methods=['POST', 'GET'])
def show_post(post_id):
    form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    if form.validate_on_submit():
        new_comment = Comment(text=form.comment.data, author_id=current_user.get_id(), blog_id=post_id)
        db.session.add(new_comment)
        db.session.commit()
    return render_template("post.html", post=requested_post, form=form)


@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        date = dt.datetime.now().strftime('%B %d, %Y')
        new_blog = BlogPost(title=form.title.data, subtitle=form.subtitle.data, date=date, body=form.body.data,
                            img_url=form.img_url.data, author_id=int(current_user.get_id()))
        db.session.add(new_blog)
        db.session.commit()
        return redirect(url_for('get_all_posts'))
    else:
        return render_template('make-post.html', form=form, heading='New Post')


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
@login_required
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.user.name,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.user.name = current_user.name
        print(post.title)
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    else:
        print('got a get request')
        return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=['POST', 'GET'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        msg = request.form['message']
        message = f'Subject:New Inquiry\n\nName: {name}\nEmail: {email}\nPhone No: {phone}\nMessage: {msg}'
        send_email(to_email=SENDER_EMAIL, msg=message, sender_password=SENDER_PASSWORD, sender_email=SENDER_EMAIL)
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=False, port=5002)
