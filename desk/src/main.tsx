import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { CashDesk } from "@/components/desk/CashDesk";
import "@/styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root");

createRoot(root).render(
  <StrictMode>
    <CashDesk />
  </StrictMode>,
);
