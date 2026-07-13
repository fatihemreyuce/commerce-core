from app.db.session import SessionLocal
from app.models.user import User, UserRole

def upgrade_to_admin():
    db = SessionLocal()
    # Kendi kayıt olduğun email adresini buraya yaz
    user = db.query(User).filter(User.email == "admin@dev.com").first()
    
    if user:
        user.role = UserRole.admin
        db.commit()
        print("✅ Başarılı! Kullanıcı artık bir ADMIN.")
    else:
        print("❌ Kullanıcı bulunamadı.")
        
    db.close()

if __name__ == "__main__":
    upgrade_to_admin()