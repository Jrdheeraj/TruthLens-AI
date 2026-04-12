"use client";

import { useId, useRef } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { Check, Clock3, Code2, Loader2, Rocket, ShieldCheck } from "lucide-react";

function Sparkline({ className, gradId }: { className?: string; gradId: string }) {
  return (
    <svg className={className} viewBox="0 0 120 32" fill="none" aria-hidden>
      <path
        d="M0 24 L20 18 L40 22 L60 8 L80 14 L100 6 L120 12"
        stroke={`url(#${gradId})`}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="120" y2="0" gradientUnits="userSpaceOnUse">
          <stop stopColor="#a78bfa" />
          <stop offset="0.5" stopColor="#8b5cf6" />
          <stop offset="1" stopColor="#34d399" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export default function SiteHeroVisual() {
  const containerRef = useRef<HTMLDivElement>(null);
  const pointerX = useMotionValue(0);
  const pointerY = useMotionValue(0);
  const smoothX = useSpring(pointerX, { stiffness: 80, damping: 20, mass: 0.5 });
  const smoothY = useSpring(pointerY, { stiffness: 80, damping: 20, mass: 0.5 });

  const frontX = useTransform(smoothX, (v) => v * 1.0);
  const frontY = useTransform(smoothY, (v) => v * 1.0);
  const midX = useTransform(smoothX, (v) => v * 0.7);
  const midY = useTransform(smoothY, (v) => v * 0.7);
  const backX = useTransform(smoothX, (v) => v * 0.45);
  const backY = useTransform(smoothY, (v) => v * 0.45);

  const onMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const nx = (event.clientX - rect.left) / rect.width;
    const ny = (event.clientY - rect.top) / rect.height;
    pointerX.set((nx - 0.5) * 20);
    pointerY.set((ny - 0.5) * 20);
  };

  const onMouseLeave = () => {
    pointerX.set(0);
    pointerY.set(0);
  };

  const uid = useId().replace(/:/g, "");
  const g1 = `tl-spark-${uid}-a`;
  const g2 = `tl-spark-${uid}-b`;
  const g3 = `tl-spark-${uid}-c`;
  const g4 = `tl-spark-${uid}-d`;
  const g5 = `tl-spark-${uid}-e`;

  return (
    <div
      ref={containerRef}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
      className="relative mx-auto h-[460px] w-full max-w-[560px] lg:mx-0 lg:ml-auto"
    >
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -left-10 -top-12 z-0 h-52 w-52 rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(124,58,237,0.38) 0%, rgba(59,130,246,0.12) 45%, rgba(0,0,0,0) 72%)",
          filter: "blur(28px)",
        }}
        animate={{ opacity: [0.45, 0.7, 0.45], scale: [0.96, 1.04, 0.96] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.div
        aria-hidden
        className="pointer-events-none absolute right-4 top-24 z-0 h-44 w-44 rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(16,185,129,0.22) 0%, rgba(16,185,129,0.07) 42%, rgba(0,0,0,0) 74%)",
          filter: "blur(22px)",
        }}
        animate={{ opacity: [0.22, 0.42, 0.22], y: [-4, 6, -4] }}
        transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.div
        aria-hidden
        className="pointer-events-none absolute left-[44%] top-[30%] z-0 h-32 w-32 -translate-x-1/2 -translate-y-1/2 rounded-full border border-violet-400/20"
        style={{ boxShadow: "0 0 40px rgba(124,58,237,0.24), inset 0 0 30px rgba(59,130,246,0.14)" }}
        animate={{ rotate: [0, 360], opacity: [0.28, 0.5, 0.28] }}
        transition={{ rotate: { duration: 22, repeat: Infinity, ease: "linear" }, opacity: { duration: 6, repeat: Infinity, ease: "easeInOut" } }}
      />

      <motion.div
        style={{ x: backX, y: backY, willChange: "transform" }}
        className="absolute -left-3 top-10 z-10 hidden w-[210px] rounded-[14px] border border-[#1F1F23] bg-[#0F0F10] p-4 opacity-60 blur-[1px] sm:block"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 0.6, y: [-10, 10, -10] }}
        transition={{ opacity: { duration: 0.5, delay: 0.06 }, y: { duration: 6.8, repeat: Infinity, ease: "easeInOut" } }}
      >
        <div className="mb-3 flex items-center justify-between">
          <span className="text-[11px] font-medium text-zinc-300">Event Logs</span>
          <Clock3 className="h-3.5 w-3.5 text-zinc-500" />
        </div>
        <div className="space-y-2">
          <div className="h-1.5 w-full rounded-full bg-white/10" />
          <div className="h-1.5 w-4/5 rounded-full bg-white/10" />
          <div className="h-1.5 w-3/5 rounded-full bg-white/10" />
        </div>
      </motion.div>

      <motion.div
        style={{ x: backX, y: backY, scale: 0.95, willChange: "transform" }}
        className="absolute -right-4 bottom-4 z-10 hidden w-[230px] rounded-[14px] border border-[#1F1F23] bg-[#0F0F10] p-4 opacity-60 blur-[1px] md:block"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 0.6, y: [-10, 10, -10] }}
        transition={{ opacity: { duration: 0.5, delay: 0.14 }, y: { duration: 5.9, repeat: Infinity, ease: "easeInOut" } }}
      >
        <div className="mb-3 flex items-center gap-2">
          <Code2 className="h-4 w-4 text-zinc-400" />
          <span className="text-[11px] font-medium text-zinc-300">Runtime Check</span>
        </div>
        <div className="space-y-1.5 font-mono text-[10px] text-zinc-500">
          <p>{"> verify --claim --cross-modal"}</p>
          <p>{"status: running"}</p>
          <p>{"sources: fetching"}</p>
        </div>
      </motion.div>

      <motion.div
        style={{ x: midX, y: midY, willChange: "transform" }}
        className="absolute right-0 top-2 z-20 w-[230px] rounded-[14px] border border-[#1F1F23] bg-[#0F0F10] p-4"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: [-10, 10, -10] }}
        transition={{ opacity: { duration: 0.5, delay: 0.2 }, y: { duration: 5.6, repeat: Infinity, ease: "easeInOut" } }}
      >
        <div className="mb-3 flex items-center justify-between">
          <span className="text-[11px] font-medium text-zinc-300">Deployment Status</span>
          <Rocket className="h-3.5 w-3.5 text-zinc-400" />
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
          <div className="h-full w-[72%] rounded-full bg-[#3B82F6]" />
        </div>
        <p className="mt-2 text-[10px] text-zinc-500">Indexing evidence feeds...</p>
      </motion.div>

      <motion.div
        style={{ x: frontX, y: frontY, willChange: "transform" }}
        className="absolute left-10 top-16 z-30 w-[360px] overflow-hidden rounded-[14px] border border-[#1F1F23] bg-[#0F0F10] shadow-[0_8px_20px_rgba(0,0,0,0.2)]"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: [-10, 10, -10] }}
        transition={{ opacity: { duration: 0.5, delay: 0.26 }, y: { duration: 6.2, repeat: Infinity, ease: "easeInOut" } }}
      >
        <div className="flex items-center gap-2 border-b border-[#1F1F23] px-4 py-3">
          <span className="h-2 w-2 rounded-full bg-zinc-600" />
          <span className="h-2 w-2 rounded-full bg-zinc-600" />
          <span className="h-2 w-2 rounded-full bg-zinc-600" />
          <span className="ml-3 text-[11px] font-medium text-zinc-300">Verification Pipeline</span>
        </div>

        <div className="space-y-3 p-4">
          <div className="flex items-center justify-between rounded-[10px] border border-[#1F1F23] bg-black/35 px-3 py-2">
            <span className="text-[11px] text-zinc-400">Claim extraction</span>
            <Check className="h-3.5 w-3.5 text-emerald-400" />
          </div>

          <div className="rounded-[10px] border border-[#1F1F23] bg-black/35 px-3 py-2">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] text-zinc-400">Signal confidence trend</span>
              <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-500" />
            </div>
            <Sparkline gradId={g1} className="h-7 w-full" />
          </div>

          <div className="rounded-[10px] border border-[#1F1F23] bg-black/35 px-3 py-2">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] text-zinc-400">Evidence scoring</span>
              <span className="text-[10px] text-zinc-500">72%</span>
            </div>
            <Sparkline gradId={g2} className="h-7 w-full" />
          </div>
        </div>
      </motion.div>

      <motion.div
        style={{ x: midX, y: midY, willChange: "transform" }}
        className="absolute left-0 bottom-10 z-20 w-[250px] rounded-[14px] border border-[#1F1F23] bg-[#0F0F10] p-4"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: [-10, 10, -10] }}
        transition={{ opacity: { duration: 0.5, delay: 0.32 }, y: { duration: 5.3, repeat: Infinity, ease: "easeInOut" } }}
      >
        <div className="mb-3 flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-zinc-400" />
          <span className="text-[11px] font-medium text-zinc-300">Risk Matrix</span>
        </div>
        <div className="mb-2 grid grid-cols-2 gap-2">
          <div className="h-12 rounded-[10px] border border-[#1F1F23] bg-black/30" />
          <div className="h-12 rounded-[10px] border border-[#1F1F23] bg-black/30" />
        </div>
        <Sparkline gradId={g3} className="h-7 w-full" />
      </motion.div>

      <motion.div
        style={{ x: frontX, y: frontY, willChange: "transform" }}
        className="pointer-events-none absolute bottom-1 right-14 z-40 hidden rounded-[14px] border border-[#1F1F23] bg-[#0F0F10] px-3 py-2 sm:block"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: [-10, 10, -10] }}
        transition={{ opacity: { duration: 0.5, delay: 0.38 }, y: { duration: 6.5, repeat: Infinity, ease: "easeInOut" } }}
      >
        <Sparkline gradId={g4} className="h-6 w-28" />
      </motion.div>

      <motion.div
        style={{ x: backX, y: backY, scale: 0.95, willChange: "transform" }}
        className="pointer-events-none absolute right-24 top-44 z-10 hidden rounded-[14px] border border-[#1F1F23] bg-[#0F0F10] px-3 py-2 opacity-60 blur-[1px] lg:block"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 0.6, y: [-10, 10, -10] }}
        transition={{ opacity: { duration: 0.5, delay: 0.44 }, y: { duration: 5.7, repeat: Infinity, ease: "easeInOut" } }}
      >
        <Sparkline gradId={g5} className="h-6 w-24" />
      </motion.div>
    </div>
  );
}
