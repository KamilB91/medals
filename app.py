from flask import (Flask, g, render_template, flash, redirect, url_for, abort)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import check_password_hash

import models
import forms

app = Flask(__name__)
app.secret_key = 'mwnkwffmdo2424iksldf.,mf32fmm.arof!$#mi32#)'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# models.initialize() does not work in 'if name == main' statement
models.initialize()

try:
    models.User.create_user(
        username='account_deleted',
        email='None',
        password='None',
        admin=False
    )
    print('success')
except ValueError as error:
    print(error)

try:
    models.User.create_user(
        username='TestUser',
        email='t@t.com',
        password='haslo',
        admin=False
    )
    print('success')
except ValueError as error:
    print(error)

account_deleted = models.User.get(models.User.username == 'account_deleted')


@login_manager.user_loader
def load_user(userid):
    try:
        return models.User.get(models.User.id == userid)
    except models.DoesNotExist:
        return None


@app.before_request
def before_request():
    """Connect to the database before each request."""
    g.db = models.DATABASE
    g.db.connect()
    g.user = current_user


@app.after_request
def after_request(response):
    """Close the database connection after each request."""
    g.db.close()
    return response


@app.route('/register', methods=('GET', 'POST'))
def register():
    form = forms.RegisterForm()
    if form.validate_on_submit():
        flash("Awyeah, you registered!", 'success')
        models.User.create_user(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data
        )
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route('/delete')
def delete_account():
    user = g.user._get_current_object()
    models.Relationship.delete().where(models.Relationship.to_user == user & models.Relationship.from_user == user)
    models.Blocked.delete().where(models.Blocked.to_user == user & models.Blocked.from_user == user)
    posts = models.Post.select().where(models.Post.user == user)
    for post in posts:
        post.user = account_deleted
        post.save()
    logout_user()
    user.delete_instance()
    return redirect(url_for('index'))


@app.route('/login', methods=('GET', 'POST'))
def login():
    form = forms.LoginForm()
    if form.validate_on_submit():
        try:
            user = models.User.get(models.User.email == form.email.data)
        except models.DoesNotExist:
            flash('Your email or password doesnt match!', 'error')
        else:
            if check_password_hash(user.password, form.password.data):
                login_user(user)
                flash("You've been logged in!", 'success')
                return redirect(url_for('index'))
            else:
                flash('Your email or password doesnt match!', 'error')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You've been logged out!", "success")
    return redirect(url_for('index'))


@app.route('/update_options')
@login_required
def update_options():
    return render_template('update_options.html')


@app.route('/update_email', methods=('POST', 'GET'))
@login_required
def update_email():
    form = forms.UpdateEmail()
    if form.validate_on_submit():
        user = g.user._get_current_object()
        if check_password_hash(user.password, form.password.data):
            flash('Success!', 'success')
            user.email = form.email.data
            user.save()
            return redirect(url_for('index'))
        else:
            flash('Incorrect password', 'error')
    return render_template('update_email.html', form=form)


@app.route('/update_password', methods=('GET', 'POST'))
@login_required
def update_password():
    form = forms.UpdatePassword()
    if form.validate_on_submit():
        user = g.user._get_current_object()
        if check_password_hash(user.password, form.old_password.data):
            flash('Password updated!', 'success')
            user.password = models.generate_password_hash(form.password.data)
            user.save()
            return redirect(url_for('index'))
        else:
            flash('Incorrect password', 'error')
    return render_template('update_password.html', form=form)


@app.route('/new_post', methods=('POST', 'GET'))
@login_required
def post():
    form = forms.PostForm()
    if form.validate_on_submit():
        models.Post.create(user=g.user._get_current_object(),
                           content=form.content.data.strip())
        flash('Message posted! Thanks!', "success")
        return redirect(url_for('index'))
    return render_template('post.html', form=form)


@app.route('/')
def index():
    try:
        user = g.user._get_current_object()
        stream = models.Post.select().where((models.Post.user == user) |
                                            (models.Post.user not in user.blocked_users() and
                                             models.Post.user not in user.blocked_me))
    except AttributeError:
        stream = models.Post.select()
        return render_template('stream.html', stream=stream)
    else:
        return render_template('stream.html', stream=stream)


@app.route('/stream')
@app.route('/stream/<username>')
def stream(username=None):
    if username == account_deleted.username:
        abort(404)
    template = 'stream.html'
    if username and username != current_user.username:
        try:
            user = models.User.select().where(models.User.username**username).get()
            if current_user in user.blocked_users():
                abort(404)
        except models.DoesNotExist:
            abort(404)
        else:
            stream = user.posts.limit(100)
    else:
        user = current_user
        stream = current_user.get_stream().limit(100)
    if username:
        template = 'user_stream.html'
    return render_template(template, stream=stream, user=user)


@app.route('/post/<int:post_id>')
def view_post(post_id):
    posts = models.Post.select().where(models.Post.id == post_id)
    if posts.count() == 0:
        abort(404)
    return render_template('stream.html', stream=posts)


@app.route('/follow/<username>')
@login_required
def follow(username):
    try:
        to_user = models.User.get(models.User.username**username)
    except models.DoesNotExist:
        abort(404)
    else:
        try:
            models.Relationship.create(
                from_user=g.user._get_current_object(),
                to_user=to_user
            )
        except models.IntegrityError:
            pass
        else:
            flash(f"You've now following {to_user.username}", "success")
    return redirect(url_for('stream', username=to_user.username))


@app.route('/unfollow/<username>')
@login_required
def unfollow(username):
    try:
        to_user = models.User.get(models.User.username**username)
    except models.DoesNotExist:
        abort(404)
    else:
        try:
            models.Relationship.get(
                from_user=g.user._get_current_object(),
                to_user=to_user
            ).delete_instance()
        except models.IntegrityError:
            pass
        else:
            flash(f"You've unfollowed {to_user.username}", "success")
    return redirect(url_for('stream', username=to_user.username))


@app.route('/block_user/<username>')
@login_required
def block(username):
    try:
        to_user = models.User.get(models.User.username**username)
    except models.DoesNotExist:
        abort(404)
    else:
        try:
            models.Blocked.create(
                from_user=g.user._get_current_object(),
                to_user=to_user
            )
        except models.IntegrityError:
            pass
        else:
            flash(f"You've blocked {to_user.username}", "success")
    return redirect(url_for('index'))


@app.route('/unblock_user/<username>')
@login_required
def unblock(username):
    try:
        to_user = models.User.get(models.User.username**username)
    except models.DoesNotExist:
        abort(404)
    else:
        try:
            models.Blocked.get(
                from_user=g.user._get_current_object(),
                to_user=to_user
            ).delete_instance()
        except models.IntegrityError:
            pass
        else:
            flash(f"You've unblocked {to_user.username}", "success")
    return redirect(url_for('index'))


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


users = models.User.select()
for user in users:
    print(user.username)


if __name__ == '__main__':
    app.run(debug=True)
