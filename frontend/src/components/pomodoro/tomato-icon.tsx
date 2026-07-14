import * as React from "react";

// A lucide-style tomato: round body, stem, two leaves. Drawn in currentColor
// so it stays ink like every other control - color only ever means something.
export function TomatoIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <circle cx="12" cy="14" r="7" />
      <path d="M12 7V4" />
      <path d="M12 7c-1.7-1.4-3.9-1-5 .3" />
      <path d="M12 7c1.7-1.4 3.9-1 5 .3" />
    </svg>
  );
}
