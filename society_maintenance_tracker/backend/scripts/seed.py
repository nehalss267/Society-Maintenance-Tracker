import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402


DEMO_USERS = [
    ("Admin User", "admin@smt.dev", "Admin@123", UserRole.ADMIN),
    ("Committee User", "committee@smt.dev", "Committee@123", UserRole.COMMITTEE),
    ("Accountant User", "accountant@smt.dev", "Account@123", UserRole.ACCOUNTANT),
    ("Resident One", "resident1@smt.dev", "Resident@123", UserRole.RESIDENT),
    ("Resident Two", "resident2@smt.dev", "Resident@123", UserRole.RESIDENT),
]


def seed() -> None:
    db = SessionLocal()

    try:
        for name, email, password, role in DEMO_USERS:
            existing = db.scalar(select(User).where(User.email == email))

            if existing:
                print(f"skip (exists): {email} [{existing.role.value}]")
                continue

            user = User(
                name=name,
                email=email,
                password_hash=hash_password(password),
                role=role,
            )

            db.add(user)
            print(f"created: {email} [{role.value}]")

        db.commit()
        print("seed complete")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
