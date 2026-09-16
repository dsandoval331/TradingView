"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  useEffect(() => {
    if (pathname !== "/dashboard") return;

    const eyebrow = document.querySelector<HTMLElement>(".dashboardHero .eyebrow");
    if (!eyebrow || eyebrow.dataset.platformBrand === "multiply-tip-accent") return;

    const accentTip = () => {
      const span = document.createElement("span");
      span.textContent = "tip";
      span.style.color = "#7ee2b8";
      return span;
    };

    eyebrow.replaceChildren(
      document.createTextNode("MUL"),
      accentTip(),
      document.createTextNode("LY"),
      document.createElement("br"),
      accentTip(),
      document.createTextNode(": trading intelligence platform"),
    );
    eyebrow.dataset.platformBrand = "multiply-tip-accent";
  }, [pathname]);

  return children;
}
