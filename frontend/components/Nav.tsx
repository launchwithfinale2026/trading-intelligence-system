"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/history", label: "History" },
  { href: "/profile", label: "Profile" },
];

export function Nav() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  if (!user) return null;

  return (
    <nav className="border-b border-black/10 dark:border-white/10">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-6">
          <span className="font-semibold">Trading Intelligence</span>
          <div className="flex items-center gap-4">
            {LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm ${
                  pathname === link.href
                    ? "font-medium text-foreground"
                    : "text-neutral-500 hover:text-foreground"
                }`}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-neutral-500">{user.username}</span>
          <button onClick={logout} className="text-neutral-500 hover:text-foreground">
            Log out
          </button>
        </div>
      </div>
    </nav>
  );
}
