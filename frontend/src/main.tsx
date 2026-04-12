import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import { Providers } from "@/components/Providers";
import "./globals.css";

document.documentElement.lang = "en";
document.documentElement.classList.add("dark");
document.title = "TruthLens AI";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <div className="min-h-screen bg-black font-sans text-zinc-400">
      <Providers>
        <App />
      </Providers>
    </div>
  </React.StrictMode>,
);
