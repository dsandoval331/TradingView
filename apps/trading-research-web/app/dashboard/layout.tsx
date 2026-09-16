"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  useEffect(() => {
    if (pathname !== "/dashboard") return;

    const eyebrow = document.querySelector<HTMLElement>(".dashboardHero .eyebrow");
    if (!eyebrow || eyebrow.dataset.platformBrand === "multiply") return;

    eyebrow.replaceChildren(
      document.createTextNode("MULtipLY"),
      document.createElement("br"),
      document.createTextNode("tip: trading intelligence platform"),
    );
    eyebrow.dataset.platformBrand = "multiply";
  }, [pathname]);

  return children;
}
