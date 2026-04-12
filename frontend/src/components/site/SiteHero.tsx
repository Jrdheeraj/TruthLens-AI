"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ChevronRight, Play } from "lucide-react";

import SiteHeroVisual from "@/components/site/SiteHeroVisual";

const HERO_TYPING_WORDS = ["With Confidence", "With Evidence", "In Real Time"];
const HERO_TYPING_MIN_WIDTH = "30ch";

export default function SiteHero() {
  const [wordIndex, setWordIndex] = useState(0);
  const [typedText, setTypedText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const currentWord = HERO_TYPING_WORDS[wordIndex];
    const isWordComplete = !isDeleting && typedText === currentWord;
    const isWordCleared = isDeleting && typedText.length === 0;

    let delay = isDeleting ? 28 : 58;
    if (isWordComplete) delay = 1050;
    if (isWordCleared) delay = 140;

    const timer = window.setTimeout(() => {
      if (isWordComplete) {
        setIsDeleting(true);
        return;
      }

      if (isWordCleared) {
        setIsDeleting(false);
        setWordIndex((prev) => (prev + 1) % HERO_TYPING_WORDS.length);
        return;
      }

      setTypedText((prev) =>
        isDeleting ? currentWord.slice(0, Math.max(prev.length - 1, 0)) : currentWord.slice(0, prev.length + 1),
      );
    }, delay);

    return () => window.clearTimeout(timer);
  }, [isDeleting, typedText, wordIndex]);

  return (
    <section className="relative overflow-hidden border-b border-white/10 bg-[#050507] pt-32 pb-36 md:pb-44">
      {/* Top-left lighting effect */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 -left-40 h-96 w-96 opacity-50"
        style={{
          background: "radial-gradient(circle, rgba(168, 85, 247, 0.4) 0%, rgba(168, 85, 247, 0.2) 40%, rgba(0, 0, 0, 0) 70%)",
          filter: "blur(60px)",
        }}
      />

      <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
        <div className="grid items-center gap-24 lg:grid-cols-2 lg:gap-16 lg:gap-x-20">
          <div className="relative z-40">
            <motion.div
              className="mb-8 inline-flex items-center gap-3 rounded-sm border border-white/10 bg-white/[0.02] px-4 py-2"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease: "easeOut" }}
            >
              <span className="font-mono text-[11px] leading-snug tracking-[0.16em] text-zinc-500 uppercase">
                AI Verification Platform
              </span>
            </motion.div>

            <h1 className="text-[3rem] font-semibold leading-[1.02] tracking-[-0.04em] text-white sm:text-5xl lg:text-[3.6rem] xl:text-[4.15rem]">
              <motion.span
                className="inline-block"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.72, delay: 0.1, ease: "easeOut" }}
              >
                Verify Content
              </motion.span>
              <motion.span
                className="block"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  opacity: { duration: 0.72, delay: 0.5, ease: "easeOut" },
                  y: { duration: 0.72, delay: 0.5, ease: "easeOut" },
                }}
              >
                <span className="inline-flex items-end" style={{ minWidth: HERO_TYPING_MIN_WIDTH }}>
                  <span className="bg-[linear-gradient(90deg,#8B5CF6_0%,#3B82F6_52%,#22D3EE_100%)] bg-clip-text text-transparent">
                    {typedText}
                  </span>
                  <span className="ml-1 inline-block h-[0.98em] w-[0.22em] translate-y-[0.04em] rounded-[2px] bg-cyan-200/90 align-middle shadow-[0_0_12px_rgba(34,211,238,0.45)] animate-pulse" />
                </span>
              </motion.span>
            </h1>

            <motion.p
              className="mt-6 max-w-xl text-base leading-relaxed text-zinc-400 md:text-lg"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.58, ease: "easeOut" }}
            >
              TruthLens helps you check whether text, images, and videos are trustworthy. Get a clear verdict,
              confidence score, and evidence-based explanation in seconds.
            </motion.p>

            <motion.div
              className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center"
              initial={{ opacity: 0, y: 16, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.6, delay: 0.7, ease: "easeOut" }}
            >
              <a
                href="#verify"
                className="inline-flex items-center justify-center gap-1 rounded-sm bg-white px-5 py-2.5 text-sm font-semibold text-black transition-[filter,transform] duration-200 hover:brightness-95 active:scale-[0.98]"
              >
                Analyze Content
                <ChevronRight className="h-4 w-4" strokeWidth={2} aria-hidden />
              </a>
              <a
                href="#how-it-works"
                className="inline-flex items-center justify-center gap-2 rounded-sm border border-white/15 bg-transparent px-5 py-2.5 text-sm font-medium text-white transition-[filter,transform] duration-200 hover:border-violet-400/45 hover:bg-violet-500/[0.08] active:scale-[0.98]"
              >
                <Play className="h-4 w-4" strokeWidth={1.5} aria-hidden />
                How TruthLens Works
              </a>
            </motion.div>

            <div className="mt-9 grid max-w-xl grid-cols-3 gap-2 text-center">
              <div className="rounded-sm border border-white/10 bg-white/[0.02] p-3">
                <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-zinc-500">Modalities</p>
                <p className="mt-1 text-lg font-semibold text-zinc-100">3+</p>
              </div>
              <div className="rounded-sm border border-white/10 bg-white/[0.02] p-3">
                <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-zinc-500">Avg latency</p>
                <p className="mt-1 text-lg font-semibold text-zinc-100">4.2s</p>
              </div>
              <div className="rounded-sm border border-white/10 bg-white/[0.02] p-3">
                <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-zinc-500">Traceability</p>
                <p className="mt-1 text-lg font-semibold text-zinc-100">100%</p>
              </div>
            </div>
          </div>

          <div className="relative z-30">
            <SiteHeroVisual />
          </div>
        </div>
      </div>
    </section>
  );
}
