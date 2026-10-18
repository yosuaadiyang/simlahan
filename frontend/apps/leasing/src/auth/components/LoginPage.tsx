import React, { useState } from "react";
import { LoginError, OtpRequiredError, verifyOtp } from "@/auth/session";

type Props = {
  onLogin: (username: string, password: string) => Promise<unknown>;
};

const APP_NAME = import.meta.env.VITE_APP_NAME || "SimLahan";
const ORGANIZATION_NAME =
  import.meta.env.VITE_ORGANIZATION_NAME || "Sistem Informasi Manajemen Lahan";

const LoginPage: React.FC<Props> = ({ onLogin }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [otp, setOtp] = useState<{ token: string; email: string } | null>(null);
  const [code, setCode] = useState("");

  const showError = (e: unknown) => {
    setError(
      e instanceof LoginError
        ? e.message
        : "Tidak dapat terhubung ke server. Periksa koneksi Anda.",
    );
    setIsSubmitting(false);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!username || !password) {
      setError("Isi nama pengguna dan kata sandi.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await onLogin(username.trim(), password);
    } catch (e) {
      if (e instanceof OtpRequiredError) {
        setOtp({ token: e.otpToken, email: e.email });
        setCode("");
        setIsSubmitting(false);
        return;
      }
      showError(e);
    }
  };

  const handleOtpSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!otp) return;
    if (!/^\d{6}$/.test(code.trim())) {
      setError("Masukkan 6 digit kode OTP.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await verifyOtp(otp.token, code.trim());
    } catch (e) {
      showError(e);
    }
  };

  const restart = () => {
    setOtp(null);
    setCode("");
    setPassword("");
    setError(null);
  };

  if (otp) {
    return (
      <div className="login-page">
        <form
          className="login-page__content"
          onSubmit={handleOtpSubmit}
          noValidate
        >
          <div className="app-logo" aria-hidden="true" />
          <h3>Verifikasi masuk</h3>
          <p>
            Kode 6 digit telah dikirim ke surel{" "}
            <strong>{otp.email || "akun Anda"}</strong>. Kode berlaku 10 menit.
          </p>
          <label className="login-page__label" htmlFor="login-otp">
            Kode OTP
          </label>
          <input
            id="login-otp"
            name="otp"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            autoFocus
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            disabled={isSubmitting}
          />
          {error && (
            <p className="login-page__error" role="alert">
              {error}
            </p>
          )}
          <button
            className="btn btn-default"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Memproses…" : "Verifikasi"}
          </button>
          <button
            className="btn btn-link"
            type="button"
            onClick={restart}
            disabled={isSubmitting}
          >
            Kembali / kirim ulang kode
          </button>
        </form>
        <div className="login-footer" />
      </div>
    );
  }

  return (
    <div className="login-page">
      <form className="login-page__content" onSubmit={handleSubmit} noValidate>
        <div className="app-logo" aria-hidden="true" />
        <h3>Selamat datang di {APP_NAME}</h3>
        <p className="login-page__organization">{ORGANIZATION_NAME}</p>
        <p>Masuk untuk melanjutkan</p>
        <label className="login-page__label" htmlFor="login-username">
          Nama pengguna
        </label>
        <input
          id="login-username"
          name="username"
          type="text"
          autoComplete="username"
          autoFocus
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={isSubmitting}
        />
        <label className="login-page__label" htmlFor="login-password">
          Kata sandi
        </label>
        <input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={isSubmitting}
        />
        {error && (
          <p className="login-page__error" role="alert">
            {error}
          </p>
        )}
        <button
          className="btn btn-default"
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Memproses…" : "Masuk"}
        </button>
      </form>
      <div className="login-footer" />
    </div>
  );
};

export default LoginPage;
