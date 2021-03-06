import logging
from flask import render_template, flash, redirect, url_for, session
from app import app
from app.forms import LoginForm
from flask_login import current_user, login_user
from app.models import User, Profile, Friends, FriendStatus, Conversation, Message
from flask_login import logout_user
from flask_login import login_required
from flask import request
from werkzeug.urls import url_parse
from app import db
from app.forms import RegistrationForm
from app.friends import are_friends_or_pending, get_friends
from app.notifications import get_notifications
from app.messages import get_conversations
from sqlalchemy import desc


@app.route('/home')
def home():
    notifications = get_notifications(session["current_user"]["id"])
    return render_template('home.html', title='Home', notifications=notifications)


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('home')
        session["current_user"] = {
            "username": user.username,
            "id": user.id
        }
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@app.route('/logout')
def logout():
    del session["current_user"]
    logout_user()
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, fname=form.fname.data, lname=form.lname.data)
        user.set_password(form.password.data)
        db.session.add(user)
        profile = Profile()
        db.session.add(profile)
        user.profile = profile
        db.session.commit()
        session["current_user"] = {
            "username": user.username,
            "id": user.id
        }
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('home'))
    return render_template('register.html', title='Register', form=form)


@app.route('/user/<user_id>')
@login_required
def user(user_id):
    user = User.query.filter_by(id=user_id).first_or_404()
    profile = user.profile
    total_friends = len(get_friends(user.id))
    friends = get_friends(user.id)
    limited_friends = friends[:6]

    user_id_1 = session["current_user"]["id"]
    notifications = get_notifications(user_id_1)

    are_friends, is_pending_sent, is_pending_recieved = are_friends_or_pending(user_id_1, user_id)

    return render_template('profile.html', user=user, profile=profile, total_friends=total_friends, are_friends=are_friends, is_pending_sent=is_pending_sent, is_pending_recieved=is_pending_recieved, friends=friends, notifications=notifications, limited_friends=limited_friends)


@app.route("/add_friend", methods=["POST"])
def add_friend():
    """Send a friend request to another user"""
    user_id_1 = session["current_user"]["id"]
    user_id_2 = request.form.get("user_id_2")
    are_friends, is_pending_sent, is_pending_recieved = are_friends_or_pending(user_id_1, user_id_2)

    if user_id_1 == user_id_2:
        return "You cannot add yourself as a friend"
    elif are_friends:
        return "You are already friends"
    elif is_pending_sent:
        return "Your friend request is pending"
    elif is_pending_recieved:
        return "You have already recieved a request from this user"
    else:
        friend_request = Friends(user_id_1=user_id_1, user_id_2=user_id_2, status=FriendStatus.requested)
        db.session.add(friend_request)
        db.session.commit()
        return "Request sent"


@app.route("/accept_friend", methods=["POST"])
def accept_friend():
    """Accept a friend request from another user"""
    user_id_1 = session["current_user"]["id"]
    user_id_2 = request.form.get("user_id_2")
    are_friends, is_pending_sent, is_pending_recieved = are_friends_or_pending(user_id_1, user_id_2)

    if user_id_1 == user_id_2:
        return "You cannot add yourself as a friend"
    elif are_friends:
        return "You are already friends"
    elif is_pending_recieved:
        friend_request = Friends.query.filter_by(user_id_1=user_id_2, user_id_2=user_id_1, status=FriendStatus.requested).first()
        friend_request.status = FriendStatus.accepted
        db.session.commit()
        return "Request accepted"
    else:
        return "An error occured"


@app.route("/unfriend", methods=["POST"])
def unfriend():
    """Unfriend another user"""
    user_id_1 = session["current_user"]["id"]
    user_id_2 = request.form.get("friend_id")
    are_friends, is_pending_sent, is_pending_recieved = are_friends_or_pending(user_id_1, user_id_2)

    if are_friends:
        relationship = Friends.query.filter_by(user_id_1=user_id_1, user_id_2=user_id_2, status=FriendStatus.accepted).first()
        if relationship is None:
            relationship = Friends.query.filter_by(user_id_1=user_id_2, user_id_2=user_id_1, status=FriendStatus.accepted).first()
        db.session.delete(relationship)
        db.session.commit()
        return "Unfriend"
    else:
        return "You cannot unfriend this user"


@app.route("/delete_friend_request", methods=["POST"])
def delete_friend_request():
    """Delete a friend request from another user"""
    user_id_1 = session["current_user"]["id"]
    user_id_2 = request.form.get("user_id_2")
    are_friends, is_pending_sent, is_pending_recieved = are_friends_or_pending(user_id_1, user_id_2)

    if is_pending_recieved:
        relationship = Friends.query.filter_by(user_id_1=user_id_2, user_id_2=user_id_1, status=FriendStatus.requested).first()
        db.session.delete(relationship)
        db.session.commit()
        return "Request removed"
    else:
        return "You cannot remove this request"


@app.route("/friends/<user_id>")
@login_required
def friends(user_id):
    """Show all friends"""
    user = User.query.filter_by(id=user_id).first_or_404()
    user_id_1 = session["current_user"]["id"]
    are_friends, is_pending_sent, is_pending_recieved = are_friends_or_pending(user_id_1, user_id)

    friends = get_friends(user_id)
    limited_friends = friends[:6]
    total_friends = len(friends)
    notifications = get_notifications(session["current_user"]["id"])
    return render_template("friends.html", user=user, friends=friends, total_friends=total_friends, are_friends=are_friends, is_pending_sent=is_pending_sent, is_pending_recieved=is_pending_recieved, notifications=notifications, limited_friends=limited_friends)


@app.route("/conversation/<id>")
@login_required
def conversation(id):
    conversation = Conversation.query.filter_by(id=id).first_or_404()
    cur_user_id = session["current_user"]["id"]
    notifications = get_notifications(cur_user_id)

    if cur_user_id == conversation.user_id_1:
        user_2 = User.query.filter_by(id=conversation.user_id_2).first()
    elif cur_user_id == conversation.user_id_2:
        user_2 = User.query.filter_by(id=conversation.user_id_1).first()
    else:
        return redirect(url_for('home'))

    messages_query = conversation.messages.order_by(desc(Message.timestamp)).limit(10).all()
    messages = messages_query[::-1]
    conversations = get_conversations(cur_user_id)
    return render_template("messenger.html", conversation=conversation, user_2=user_2, conversations=conversations, messages=messages, notifications=notifications)


@app.errorhandler(500)
def server_error(e):
    logging.exception('An error occurred during a request.')
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500
