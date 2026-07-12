from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models.organization import Organization
from app.db.models.user import User


class EmailAlreadyRegisteredError(Exception):
    """The email is already taken; the route maps this to a 400."""


class SignupOrganizationUseCase:
    """
    Creates a new organization and its admin user.

    Raises domain exceptions, not HTTP ones — the route decides status
    codes, this layer only knows business rules.
    """

    def __init__(self, db: Session):
        self.db = db

    def execute(self, *, organization_name: str, email: str, password: str) -> dict:
        if self.db.query(User).filter(User.email == email).first():
            raise EmailAlreadyRegisteredError("Email already registered")

        organization = Organization(name=organization_name)
        self.db.add(organization)
        self.db.flush()  # get organization.id without commit

        user = User(
            email=email,
            hashed_password=hash_password(password),
            is_admin=True,
            organization_id=organization.id,
        )

        self.db.add(user)
        self.db.commit()

        return {"message": "Organization and admin user created"}
