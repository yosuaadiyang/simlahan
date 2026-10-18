def user_logged_in(sender, user, **kwargs):
    user.update_service_units()
    # Setiap login sesi baru wajib verifikasi OTP lagi (bila diaktifkan).
    session = getattr(kwargs.get("request"), "session", None)
    if session is not None:
        from users.otp import SESSION_KEY

        session.pop(SESSION_KEY, None)
