from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from datetime import datetime, timedelta
import os
import jwt
from typing import Optional

from shared_lib.database import get_db
from shared_lib import models
from shared_lib.logger import setup_logger
from sqlalchemy.orm import Session

logger = setup_logger("auth-service")

app = FastAPI(title="Wiktionary Auth Service")

# Session middleware is required by Authlib to keep track of OAuth state
is_prod = os.getenv("OAUTH_CALLBACK_URL", "").startswith("https://")
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SESSION_SECRET", "super-secret"),
    https_only=is_prod
)

oauth = OAuth()
oauth.register(
    name='wikimedia',
    client_id=os.getenv("WIKIMEDIA_CLIENT_ID", ""),
    client_secret=os.getenv("WIKIMEDIA_CLIENT_SECRET", ""),
    access_token_url='https://meta.wikimedia.org/w/rest.php/oauth2/access_token',
    authorize_url='https://meta.wikimedia.org/w/rest.php/oauth2/authorize',
    api_base_url='https://meta.wikimedia.org/w/rest.php/oauth2/resource/',
    client_kwargs={'scope': 'basic createeditmovepage'}
)

JWT_SECRET = os.getenv("SESSION_SECRET", "super-secret") + "_v2"
JWT_ALGORITHM = "HS256"

@app.get("/auth/login")
async def login(request: Request, next: Optional[str] = None):
    host = request.headers.get("x-forwarded-host", request.url.hostname)
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    
    if next:
        request.session['next_url'] = next
    if host and "toolforge.org" in host:
        redirect_uri = f"https://{host}/auth/callback"
    else:
        redirect_uri = os.getenv("OAUTH_CALLBACK_URL", "http://localhost:3000/auth/callback")
        
    logger.info(f"Initiating login, redirect_uri={redirect_uri}")
    return await oauth.wikimedia.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        logger.info("Handling OAuth callback")
        token = await oauth.wikimedia.authorize_access_token(request)
        resp = await oauth.wikimedia.get('profile', token=token)
        profile = resp.json()
        username = profile.get('username')
        
        if not username:
            raise ValueError("No username returned in profile")
            
        logger.info(f"User authenticated: {username}")
        user = db.query(models.User).filter(models.User.wiki_username == username).first()
        if not user:
            role = models.RoleEnum.owner if username == "R1F4T" else models.RoleEnum.participant
            user = models.User(wiki_username=username, role=role, oauth_access_token=token.get('access_token'))
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            if username == "R1F4T" and user.role != models.RoleEnum.owner:
                user.role = models.RoleEnum.owner
            user.oauth_access_token = token.get('access_token')
            db.commit()
                
        expire = datetime.utcnow() + timedelta(days=7)
        jwt_payload = {"sub": user.wiki_username, "role": user.role.value, "exp": expire}
        auth_token = jwt.encode(jwt_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        is_secure = request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https"
        next_url = request.session.pop('next_url', '/')
        redirect_res = RedirectResponse(url=next_url)
        redirect_res.set_cookie(
            key="auth_token",
            value=auth_token,
            httponly=True,
            secure=is_secure,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 7 days
        )
        return redirect_res
        
    except Exception as e:
        import traceback
        logger.error(f"Login failed: {e}\n{traceback.format_exc()}")
        return RedirectResponse(url="/?error=login_failed")

@app.post("/auth/logout")
async def logout(request: Request):
    logger.info("Logging out user")
    is_secure = request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https"
    response = Response(status_code=200)
    response.delete_cookie(
        key="auth_token",
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
    )
    return response

@app.get("/auth/verify")
async def verify(request: Request, db: Session = Depends(get_db)):
    """Internal endpoint to verify JWT and return user details."""
    token = request.cookies.get("auth_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        user = db.query(models.User).filter(models.User.wiki_username == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return {
            "id": user.id,
            "wiki_username": user.wiki_username,
            "role": user.role.value,
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/health")
def health():
    return {"status": "ok", "service": "auth"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
