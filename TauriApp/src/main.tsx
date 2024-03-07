import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./App.css";
import { ResolveProvider } from "./ResolveContext";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ResolveProvider>
      <App />
    </ResolveProvider>
  </React.StrictMode>
);
