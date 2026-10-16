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
      <p>Terjadi galat yang tidak terduga. Silakan muat ulang halaman.</p>
    }
  >
    <Provider store={store}>
      <BrowserRouter>{routes}</BrowserRouter>
    </Provider>
  </Sentry.ErrorBoundary>,
);
