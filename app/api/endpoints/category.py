from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.deps import get_db, require_admin
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryResponse
from app.models.user import User                  

router = APIRouter()

@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    category_in: CategoryCreate, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin) # GÜVENLİK KİLİDİ: Sadece Admin
):
    """Yeni bir kategori oluşturur (Örn: Elektronik, Giyim). Sadece Adminler yapabilir."""
    
    existing_category = db.query(Category).filter(Category.name == category_in.name).first()
    if existing_category:
        raise HTTPException(status_code=400, detail="Bu kategori zaten mevcut.")
    
    db_category = Category(**category_in.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@router.get("/", response_model=List[CategoryResponse])
def get_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Sistemdeki tüm kategorileri listeler. (Herkese Açık)"""
    categories = db.query(Category).offset(skip).limit(limit).all()
    return categories

@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(category_id: str, db: Session = Depends(get_db)):
    """Belirli bir kategoriyi ID'sine göre getirir. (Herkese Açık)"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı.")
    return category

@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: str, 
    category_in: CategoryCreate, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin) # GÜVENLİK KİLİDİ: Sadece Admin
):
    """Kategori bilgilerini günceller. Sadece Adminler yapabilir."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı.")
    
    update_data = category_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(category, key, value)
        
    db.commit()
    db.refresh(category)
    return category

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: str, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin) # GÜVENLİK KİLİDİ: Sadece Admin
):
    """Bir kategoriyi sistemden tamamen siler. Sadece Adminler yapabilir."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı.")
        
    db.delete(category)
    db.commit()
    return None