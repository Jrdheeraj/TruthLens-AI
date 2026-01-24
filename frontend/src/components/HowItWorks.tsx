import { Upload, Scan, ShieldCheck, FileCheck } from "lucide-react";

const steps = [
  {
    icon: Upload,
    title: "Ingest",
    subtitle: "Upload Text, Image, or Video",
    description: "Drag & drop interface supporting social media posts, screenshots, headlines, and multimedia content.",
  },
  {
    icon: Scan,
    title: "Analyze",
    subtitle: "AI Extracts & Examines",
    description: "Advanced AI extracts claims, detects manipulation patterns, and performs cross-modal reasoning on text and visuals.",
  },
  {
    icon: ShieldCheck,
    title: "Verify",
    subtitle: "Cross-Reference Evidence",
    description: "Checks against real-world evidence, trusted sources, and known hoax pattern databases.",
  },
  {
    icon: FileCheck,
    title: "Verdict",
    subtitle: "Clear Authenticity Report",
    description: "Delivers a clear verdict with confidence score and transparent reasoning for full accountability.",
  },
];

const HowItWorks = () => {
  return (
    <section id="how-it-works" className="py-24 relative">
      <div className="container mx-auto px-6">
        {/* Section Header */}
        <div className="text-center mb-16">
          <h2 className="text-sm font-medium text-primary tracking-wide uppercase mb-4">
            The Process
          </h2>
          <h3 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
            From Chaos to Clarity
          </h3>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Our four-step verification process transforms uncertain content into actionable truth.
          </p>
        </div>

        {/* Steps Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {steps.map((step, index) => (
            <div 
              key={step.title}
              className="glass-card p-8 hover-lift group"
            >
              {/* Step Number */}
              <div className="flex items-center justify-between mb-6">
                <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                  <step.icon className="w-6 h-6 text-primary" />
                </div>
                <span className="text-5xl font-bold text-muted/30">0{index + 1}</span>
              </div>

              {/* Content */}
              <h4 className="text-xl font-semibold mb-2">{step.title}</h4>
              <p className="text-sm text-primary/80 font-medium mb-3">{step.subtitle}</p>
              <p className="text-muted-foreground text-sm leading-relaxed">{step.description}</p>
            </div>
          ))}
        </div>

        {/* Connection Line (Desktop) */}
        <div className="hidden lg:block absolute top-1/2 left-1/2 -translate-x-1/2 w-[calc(100%-12rem)] max-w-5xl h-px bg-gradient-to-r from-transparent via-border to-transparent -z-10" />
      </div>
    </section>
  );
};

export default HowItWorks;
