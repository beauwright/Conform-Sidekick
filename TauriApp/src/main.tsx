import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./App.css";
import { ResolveProvider } from "./ResolveContext";
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';
const appWindow = getCurrentWebviewWindow()

appWindow.show();

// Prevent all right clicks
//document.addEventListener('contextmenu', event => event.preventDefault());

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ResolveProvider>
      <App />
    </ResolveProvider>
  </React.StrictMode>
);
