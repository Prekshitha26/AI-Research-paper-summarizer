import os
import json
from app_fixed import app, db, User
from config import config

def init_db():
    app.config.from_object(config['development'])
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
            os.remove(users_file)  # Clean up

        # Add default admin if no users
        if User.query.count() == 0:
            admin = User(email='admin@example.com', name='Admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Default admin created.")

        print("Database initialized!")

if __name__ == '__main__':
    init_db()

