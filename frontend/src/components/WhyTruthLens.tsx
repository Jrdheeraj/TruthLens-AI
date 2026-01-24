import { Check, X } from "lucide-react";

const truthLensFeatures = [
  "Evidence-based verification",
  "Multi-modal analysis (text, image, video)",
  "Transparent reasoning with sources",
  "Built for real-world misinformation",
  "Cross-modal consistency checks",
  "Confidence scoring system",
];

const typicalToolsFlaws = [
  "Black-box answers with no explanation",
  "Text-only checks, missing visual context",
  "No source clarity or attribution",
  "High uncertainty in results",
  "Single-modal analysis only",
  "Binary yes/no without nuance",
];

const WhyTruthLens = () => {
  return (
    <section id="why-truthlens" className="py-24">
      <div className="container mx-auto px-6">
        {/* Section Header */}
        <div className="text-center mb-16">
          <h2 className="text-sm font-medium text-primary tracking-wide uppercase mb-4">
            The Difference
          </h2>
          <h3 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
            Why TruthLens AI
          </h3>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Purpose-built for the misinformation age, not retrofitted from generic AI.
          </p>
        </div>

        {/* Comparison Grid */}
        <div className="max-w-5xl mx-auto grid md:grid-cols-2 gap-6">
          {/* TruthLens Column */}
          <div className="glass-panel p-8 accent-border">
            <div className="flex items-center gap-3 mb-8">
              <div className="w-10 h-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
                <Check className="w-5 h-5 text-primary" />
              </div>
              <h4 className="text-xl font-semibold">TruthLens AI</h4>
            </div>

            <div className="space-y-4">
              {truthLensFeatures.map((feature, index) => (
                <div 
                  key={index}
                  className="flex items-start gap-3 p-4 bg-primary/5 rounded-lg border border-primary/10"
                >
                  <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Check className="w-3 h-3 text-primary" />
                  </div>
                  <span className="text-sm">{feature}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Typical Tools Column */}
          <div className="glass-card p-8 opacity-70">
            <div className="flex items-center gap-3 mb-8">
              <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center">
                <X className="w-5 h-5 text-muted-foreground" />
              </div>
              <h4 className="text-xl font-semibold text-muted-foreground">Typical Tools</h4>
            </div>

            <div className="space-y-4">
              {typicalToolsFlaws.map((flaw, index) => (
                <div 
                  key={index}
                  className="flex items-start gap-3 p-4 bg-secondary/30 rounded-lg"
                >
                  <div className="w-5 h-5 rounded-full bg-destructive/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <X className="w-3 h-3 text-destructive/60" />
                  </div>
                  <span className="text-sm text-muted-foreground">{flaw}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default WhyTruthLens;
