from app.core.database import engine, Base, SessionLocal
from app.models import domain_models
from app.core import security

def test_connection():
    print("Trying connection to database MySQL...")
    
    try:
        Base.metadata.create_all(bind=engine)
        print("Connection successful!")
    except Exception as e:
        print(f"Failed to connect or make tables:\n{e}")
        return
    
    db = SessionLocal()
    try:
        test_user = db.query(domain_models.User).filter(domain_models.User.username == "researcher").first()
        
        if not test_user:
            print("Membuat user researcher...")
            hashed_pwd = security.hash_password("passresearcher")
            test_user = domain_models.User(
                username="researcher",
                password_hash = hashed_pwd,
                role="developer"
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
        dummy_users = [
            ("Alex", "alex123"),
            ("Bob", "bob123"),
            ("Charlie", "charlie123"),
        ]
        for username, password in dummy_users:
            existing = db.query(domain_models.User).filter(
                domain_models.User.username == username
            ).first()
            if not existing:
                db.add(domain_models.User(
                    username=username,
                    password_hash=security.hash_password(password),
                    role="user",
                ))
        db.commit()
        print("✅ User simulasi (role=user) sudah dibuat/dicek.")
        print(f"✅ Operasi baca/tulis sukses! Data user terdeteksi -> ID: {test_user.id} | Role: {test_user.role}")
        
    except Exception as e:
        print(f"❌ Gagal melakukan operasi baca/tulis ke database:\n{e}")
        db.rollback() # Batalkan transaksi jika terjadi error
    finally:
        db.close()

if __name__ == "__main__":
    test_connection()