import os
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import credentials, auth
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import models
from database import get_db

load_dotenv()

# Initialize Firebase Admin SDK
cred_path = os.getenv("FIREBASE_CREDENTIALS", "firebase-adminsdk.json")
try:
    # Check if already initialized to prevent errors on server reload
    if not firebase_admin._apps: 
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"\nCRITICAL WARNING: Firebase Admin failed to initialize.")
    print(f"Make sure you have downloaded the Service Account Key and named it {cred_path}\nError: {e}\n")

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        # Verify the JWT token sent from the frontend
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token["uid"]
        email = decoded_token.get("email", "")
        name = decoded_token.get("name", "Unknown User")
        
        # Look up user in SQL database
        user = db.query(models.User).filter(models.User.id == uid).first()
        
        # Auto-sync: If user exists in Firebase but not our SQL DB, create them
        if not user:
            # Auto-generate a random unique username
            random_suffix = uuid.uuid4().hex[:6]
            generated_username = f"user_{random_suffix}"
            
            user = models.User(
                id=uid, 
                email=email, 
                username=generated_username, 
                name=name, 
                role=models.RoleEnum.MEMBER
            )
            
            # Make the first ever user an ADMIN
            if db.query(models.User).count() == 0:
                user.role = models.RoleEnum.ADMIN
                
            db.add(user)
            db.commit()
            db.refresh(user)
            
        return user
    except Exception as e:
        # Print the EXACT error to your Python terminal so we can see it!
        print(f"\n--- BACKEND AUTH ERROR --- \n{str(e)}\n--------------------------\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted. Admin access required."
        )
    return current_user