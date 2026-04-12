"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Shield } from "lucide-react";

export default function SiteNavbar() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const link = "text-[16px] font-medium text-zinc-400 transition-colors duration-200 hover:text-white";

  return (
    <motion.header
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
      className={[
        "fixed inset-x-0 top-0 z-50 border-b border-white/10 backdrop-blur-md transition-colors duration-200",
        scrolled ? "bg-black/95" : "bg-black/75",
      ].join(" ")}
    >
      <div className="mx-auto flex h-20 max-w-7xl items-center px-6 lg:px-8">
        <a href="#" className="flex shrink-0 items-center gap-2.5 transition-opacity duration-200 hover:opacity-90">
          <span className="relative flex h-10 w-10 items-center justify-center rounded-sm border border-white/10 bg-black">
            <Shield className="h-5 w-5 text-white" strokeWidth={1.5} aria-hidden />
          </span>
          <span className="text-[22px] font-semibold tracking-tight text-white">TruthLens</span>
        </a>

        <nav className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-10 md:flex" aria-label="Main">
          <a href="#how-it-works" className={link}>
            How It Works
          </a>
          <a href="#verify" className={link}>
            Verify Content
          </a>
          <a href="#why-truthlens" className={link}>
            Why TruthLens
          </a>
          <a href="#use-cases" className={link}>
            Use Cases
          </a>
        </nav>

        <div className="ml-auto flex items-center gap-4">
          <span className="hidden rounded-sm border border-white/10 px-2 py-1 font-mono text-[11px] uppercase tracking-[0.16em] text-zinc-500 sm:inline-block">
            beta
          </span>
          <button
            type="button"
            className="rounded-sm bg-white px-5 py-2.5 text-[15px] font-semibold text-black transition-[filter,transform] duration-200 hover:brightness-95 active:scale-[0.98]"
          >
            Get Started
          </button>
        </div>
      </div>
    </motion.header>
  );
}
