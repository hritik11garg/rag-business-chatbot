from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.db.models.organization import Organization
from app.db.models.user import User
from app.core.security import hash_password


class SignupOrganizationUseCase:
    """
    Creates a new organization and its admin user.
    """

    def __init__(self, db: Session):
        self.db = db

    def execute(self, *, organization_name: str, email: str, password: str) -> dict:
        # Check if user already exists
        if self.db.query(User).filter(User.email == email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Create organization
        organization = Organization(name=organization_name)
        self.db.add(organization)
        self.db.flush()  # get organization.id without commit

        # Create admin user
        user = User(
            email=email,
            hashed_password=hash_password(password),
            is_admin=True,
            organization_id=organization.id,
        )

        self.db.add(user)
        self.db.commit()

        return {"message": "Organization and admin user created"}
