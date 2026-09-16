"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  useEffect(() => {
    if (pathname !== "/dashboard") return;

    const eyebrow = document.querySelector<HTMLElement>(".dashboardHero .eyebrow");
    if (!eyebrow || eyebrow.dataset.platformBrand === "multiply-second-line-amber") return;

    const accentTip = () => {
      const span = document.createElement("span");
      span.textContent = "tip";
      span.style.color = "#f2b84b";
      return span;
    };

    const descriptor = document.createElement("span");
    descriptor.textContent = "tip: trading intelligence platform";
    descriptor.style.color = "#f2b84b";

    eyebrow.replaceChildren(
      document.createTextNode("MUL"),
      accentTip(),
      document.createTextNode("LY"),
      document.createElement("br"),
      descriptor,
    );
    eyebrow.dataset.platformBrand = "multiply-second-line-amber";
  }, [pathname]);

  return children;
}
