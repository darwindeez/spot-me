from app import app, db
from app.models import User, Profile, Friends, FriendStatus, Message, Conversation


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Profile': Profile, 'Friends': Friends, 'FriendStatus': FriendStatus, 'Message': Message, 'Conversation': Conversation}

if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
