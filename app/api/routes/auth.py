from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.use_cases.signup_organization import SignupOrganizationUseCase
from app.api.deps import get_db
from app.api.schemas.auth import SignupRequest, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.db.models.organization import Organization
from app.db.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201)
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    use_case = SignupOrganizationUseCase(db)
    return use_case.execute(
        organization_name=data.organization_name,
        email=data.email,
        password=data.password,
    )


@router.post("/login", response_model=TokenResponse)
def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db),
):
    """
    OAuth2-compatible login endpoint.
    """

    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)
