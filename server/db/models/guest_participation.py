from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint, false

from db.base import Base


class GuestParticipation(Base):
    __tablename__ = "guest_participations"
    __table_args__ = (
        UniqueConstraint("mode", "day_id", "guest_id", name="uq_guest_participation_mode_day_identity"),
    )

    id = Column(Integer, primary_key=True)
    guest_id = Column(String(36), nullable=False)
    mode = Column(String(64), nullable=False)
    # Puzzle IDs are local to each mode, so this is intentionally not a foreign key.
    day_id = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    questions_asked = Column(Integer, nullable=False, default=0, server_default="0")
    guesses_made = Column(Integer, nullable=False, default=0, server_default="0")
    won = Column(Boolean, nullable=False, default=False, server_default=false())
