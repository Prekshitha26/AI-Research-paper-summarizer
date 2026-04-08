import os
import json
from models import db, User
from config import config
from flask import Flask

def init_db():
    app = Flask(__name__)
    app.config.from_object(config['development'])
    db.init_app(app)
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Migrate from users.json if exists
        users_file = 'users.json'
        if os.path.exists(users_file):
            print("Migrating users from users.json...")
            with open(users_file, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
            
            for email, data in users_data.items():
                if isinstance(data, dict) and 'password' in data:
                    pw = data['password']
                    name = data.get('name', email.split('@')[0].title())
                else:
                    pw = data
                    name = email.split('@')[0].title()
                
                user = User(email=email.lower(), name=name)
                user.set_password(pw)
                db.session.add(user)
            
            db.session.commit()
            print("Users migrated!")
            # Optional: os.remove(users_file)

        print("Database initialized!")

if __name__ == '__main__':
    init_db()

