import { Shield } from "lucide-react";

export default function SiteFooter() {
  return (
    <footer className="border-t border-white/10 bg-black py-16">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="flex flex-col items-center justify-between gap-8 md:flex-row">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-sm border border-white/10 bg-tl-elevated">
              <Shield className="h-4 w-4 text-white" strokeWidth={1.5} aria-hidden />
            </div>
            <span className="text-base font-semibold text-white">TruthLens</span>
          </div>

          <div className="flex items-center gap-8 text-sm text-zinc-500">
            <a href="#how-it-works" className="transition-colors duration-200 hover:text-white">Process</a>
            <a href="#verify" className="transition-colors duration-200 hover:text-white">Verification</a>
            <a href="#why-truthlens" className="transition-colors duration-200 hover:text-white">Why TruthLens</a>
            <a href="#use-cases" className="transition-colors duration-200 hover:text-white">Use Cases</a>
          </div>

          <p className="text-sm text-zinc-500">2026 TruthLens AI. Built for accountable intelligence.</p>
        </div>
      </div>
    </footer>
  );
}
