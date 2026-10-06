# ======================================================
# SETTING
# Tambahkan class ini ke database/models.py (mis. setelah HariLibur)
# ======================================================

class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    jam_masuk: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(7, 0)  # default 07:00
    )

    toleransi_menit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10  # default toleransi 10 menit -> batas hadir 07:10
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
