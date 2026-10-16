import React, { useState } from "react";
import { LoginError } from "@/auth/session";

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
      setError(
        e instanceof LoginError
          ? e.message
          : "Tidak dapat terhubung ke server. Periksa koneksi Anda.",
      );
      setIsSubmitting(false);
    }
  };

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
