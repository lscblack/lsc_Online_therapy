// Small inline icon set (stroke = currentColor) so the landing page needs no image assets.
const P = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export function Icon({ name, size = 24 }: { name: string; size?: number }) {
  const s = { width: size, height: size, viewBox: "0 0 24 24", "aria-hidden": true };
  switch (name) {
    case "chat":
      return (<svg {...s}><path {...P} d="M4 5h16v11H9l-4 3v-3H4z" /><path {...P} d="M8 10h8M8 13h5" /></svg>);
    case "mic":
      return (<svg {...s}><rect {...P} x="9" y="3" width="6" height="11" rx="3" /><path {...P} d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>);
    case "book":
      return (<svg {...s}><path {...P} d="M5 4h9a3 3 0 0 1 3 3v13H8a3 3 0 0 0-3 3z" /><path {...P} d="M17 7h2v13" /></svg>);
    case "shield":
      return (<svg {...s}><path {...P} d="M12 3l7 3v5c0 5-3.5 8-7 10-3.5-2-7-5-7-10V6z" /><path {...P} d="M9 12l2 2 4-4" /></svg>);
    case "globe":
      return (<svg {...s}><circle {...P} cx="12" cy="12" r="8.5" /><path {...P} d="M3.5 12h17M12 3.5c3 3 3 14 0 17M12 3.5c-3 3-3 14 0 17" /></svg>);
    case "lock":
      return (<svg {...s}><rect {...P} x="5" y="10" width="14" height="10" rx="2" /><path {...P} d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>);
    case "leaf":
      return (<svg {...s}><path {...P} d="M20 4C9 4 4 10 4 18c0 0 1 2 2 2 8 0 14-5 14-16z" /><path {...P} d="M4 20c6-8 10-10 14-12" /></svg>);
    default:
      return null;
  }
}
