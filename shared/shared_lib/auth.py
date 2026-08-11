import os
import httpx
import jwt
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from .database import get_db
from . import models

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
JWT_SECRET = os.getenv("SESSION_SECRET", "super-secret") + "_v2"
JWT_ALGORITHM = "HS256"

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("auth_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Option 1: Call Auth Service (as per plan)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{AUTH_SERVICE_URL}/auth/verify",
                cookies={"auth_token": token},
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            if resp.status_code == 200:
                user_data = resp.json()
                # Return a User model instance (or at least something that looks like it)
                # For better compatibility with existing code, we query the DB
                user = db.query(models.User).filter(models.User.id == user_data["id"]).first()
                if not user:
                    raise HTTPException(status_code=401, detail="User not found")
                return user
            else:
                detail = resp.json().get("detail", "Authentication failed")
                raise HTTPException(status_code=resp.status_code, detail=detail)
    except httpx.RequestError as e:
        # Fallback to local decoding if Auth service is down (optional, but safer)
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            username = payload.get("sub")
            user = db.query(models.User).filter(models.User.wiki_username == username).first()
            if user:
                return user
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"Auth service unreachable: {str(e)}")

def get_owner_user(current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.owner:
        raise HTTPException(status_code=403, detail="Owner privileges required")
    return current_user
