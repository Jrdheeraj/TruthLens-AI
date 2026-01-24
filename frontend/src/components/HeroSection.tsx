import { ArrowRight, Play } from "lucide-react";
import heroBackground from "@/assets/hero-background.jpg";

const HeroSection = () => {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 z-0">
        <img
          src={heroBackground}
          alt="Fake news to verified truth transition"
          className="w-full h-full object-cover"
          style={{
            filter: "brightness(0.85) contrast(1.05)",
          }}
        />

        {/* Soft readability overlay */}
        <div className="absolute inset-0 bg-black/45" />
      </div>

      {/* Content */}
      <div className="relative z-10 container mx-auto px-6 pt-32 pb-20">
        <div className="max-w-4xl mx-auto text-center">
          {/* Badge */}
          <div
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass-card mb-8 opacity-0 animate-fade-in"
            style={{ animationDelay: "0.1s" }}
          >
            <span className="w-2 h-2 rounded-full bg-primary" />
            <span className="text-sm text-slate-300">
              AI-Powered Verification Platform
            </span>
          </div>

          {/* Headline */}
          <h1
            className="text-5xl md:text-7xl font-bold tracking-tight mb-6 text-white opacity-0 animate-fade-in"
            style={{ animationDelay: "0.2s" }}
          >
            Absolute Truth in a{" "}
            <span className="text-sky-400">Synthetic World</span>
          </h1>

          {/* Subheading */}
          <p
            className="text-lg md:text-xl text-slate-300 max-w-2xl mx-auto mb-10 leading-relaxed opacity-0 animate-fade-in"
            style={{ animationDelay: "0.4s" }}
          >
            Advanced AI-driven verification for text, images, and deepfake
            videos separating facts from fiction in real time.
          </p>

          {/* CTA Buttons */}
          <div
            className="flex flex-col sm:flex-row items-center justify-center gap-4 opacity-0 animate-fade-in"
            style={{ animationDelay: "0.6s" }}
          >
            <a
              href="#verify"
              className="group px-8 py-4 bg-primary text-primary-foreground font-medium rounded-lg transition-all hover:bg-primary/90 flex items-center gap-2"
            >
              Analyze Content
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </a>

            <a
              href="#how-it-works"
              className="px-8 py-4 bg-white/5 hover:bg-white/10 text-white font-medium rounded-lg transition-colors border border-white/15 flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              How TruthLens Works
            </a>
          </div>
        </div>
      </div>
    </section>
  );
};

export default HeroSection;
