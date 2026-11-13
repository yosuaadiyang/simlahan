def user_logged_in(sender, user, **kwargs):
    user.update_service_units()
    # Setiap login sesi baru wajib verifikasi OTP lagi (bila diaktifkan).
    session = getattr(kwargs.get("request"), "session", None)
    if session is not None:
        from users.otp import SESSION_KEY

        session.pop(SESSION_KEY, None)


def revoke_credentials_on_password_change(sender, instance, created, **kwargs):
    """Sandi berubah (dari jalur mana pun) → cabut semua kredensial API lama.

    ``AbstractBaseUser.set_password`` menyimpan sandi mentah di ``_password``
    sampai ``save()`` selesai. Peningkatan hash saat login mengosongkannya, jadi
    itu tidak dianggap ganti sandi. Dijalankan langsung (bukan on_commit) agar
    token baru yang diterbitkan view ganti sandi setelah save tidak ikut dicabut.
    """
    if created or kwargs.get("raw") or getattr(instance, "_password", None) is None:
        return
    from users.credentials import revoke_api_credentials

    revoke_api_credentials(instance)
