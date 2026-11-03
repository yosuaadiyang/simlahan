import React from "react";
import * as Sentry from "@sentry/react";
import { createRoot } from "react-dom/client";
import { Provider } from "react-redux";
import { BrowserRouter } from "react-router";
import store from "@/root/store";
import routes from "@/root/routes";

const container = document.getElementById("root");
const root = createRoot(container);

root.render(
  <Sentry.ErrorBoundary
    fallback={
      <div
        role="alert"
        style={{
          maxWidth: 480,
          margin: "15vh auto 0",
          padding: "24px 20px",
          textAlign: "center",
          fontFamily: "inherit",
        }}
      >
        <h1 style={{ fontSize: 22, margin: "0 0 8px" }}>
          Halaman gagal ditampilkan
        </h1>
        <p style={{ margin: "0 0 20px", lineHeight: 1.5 }}>
          Terjadi galat yang tidak terduga. Silakan muat ulang halaman.
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          style={{
            background: "#1d82f5",
            color: "#fff",
            border: 0,
            borderRadius: 8,
            padding: "10px 18px",
            fontSize: 15,
            cursor: "pointer",
          }}
        >
          Muat ulang
        </button>{" "}
        <a href="/" style={{ marginLeft: 12, color: "#0b5fcc" }}>
          Ke beranda
        </a>
      </div>
    }
  >
    <Provider store={store}>
      <BrowserRouter>{routes}</BrowserRouter>
    </Provider>
  </Sentry.ErrorBoundary>,
);
