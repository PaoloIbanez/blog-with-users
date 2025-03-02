from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap5(app)
gravatar = Gravatar(app, size=100, rating='g', default='retro')



# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Where to go if @login_required fails



@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# Comment table
class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Relationship
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    post_id: Mapped[int] = mapped_column(ForeignKey("blog_posts.id"))
    author: Mapped["User"] = relationship("User", back_populates="comments")
    parent_post: Mapped["BlogPost"] = relationship("BlogPost", back_populates="comments")


# User Model

class User(Base, UserMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="author")



# admin
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If user is not logged in or not user id 1 => 403 forbidden
        if not current_user.is_authenticated or current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function

# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(250), nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="parent_post")



# TODO: Create a User table for all your registered users. 


with app.app_context():
    db.create_all()


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # 1. Check if a user already exists with this email.
        existing_user = db.session.execute(
            db.select(User).where(User.email == form.email.data)
        ).scalar_one_or_none()
        if existing_user:
            flash("You've already signed up with that email, please log in instead!")
            return redirect(url_for("login"))

        # 2. Hash the user’s password.
        hashed_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )

        # 3. Create new user and add to DB.
        new_user = User(
            email=form.email.data,
            password=hashed_password,
            name=form.name.data,
        )
        db.session.add(new_user)
        db.session.commit()

        # 4. Optionally, log them in automatically upon registration:
        login_user(new_user)

        # 5. Redirect to home (or wherever you want).
        return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form)
# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        # Find user by email
        user = db.session.execute(db.select(User).filter_by(email=email)).scalar()
        if not user:
            flash("That email doesn't exist, please try again.")
            return redirect(url_for('login'))
        else:
            # Check stored password hash
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash("Password incorrect, please try again.")
                return redirect(url_for('login'))
    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)

    # Create an instance of the comment form
    comment_form = CommentForm()

    # Check if the user has submitted the form (POST request) AND it validates
    if comment_form.validate_on_submit():
        # 1. If user not logged in, redirect them to login.
        if not current_user.is_authenticated:
            flash("You need to log in or register to comment.")
            return redirect(url_for("login"))

        # 2. Create a new Comment object using data from the form.
        new_comment = Comment(
            text=comment_form.comment_text.data,
            author_id=current_user.id,
            post_id=post_id
        )

        # 3. Add and commit to the DB
        db.session.add(new_comment)
        db.session.commit()

        # 4. Refresh the page to show the new comment
        return redirect(url_for("show_post", post_id=post_id))

    # If GET request or form not valid yet, just render the template
    return render_template(
        "post.html",
        post=requested_post,
        form=comment_form
    )


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
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


@app.route("/contact")
def contact():
    return render_template("contact.html")



if __name__ == "__main__":
    app.run(debug=True, port=5002)


