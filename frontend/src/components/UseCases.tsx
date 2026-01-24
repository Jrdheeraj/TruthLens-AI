import { Newspaper, Search, Building2, Globe, GraduationCap } from "lucide-react";

const useCases = [
  {
    icon: Newspaper,
    title: "Journalists & Media",
    description: "Verify sources, detect manipulated content, and ensure accuracy before publication.",
  },
  {
    icon: Search,
    title: "Fact-Checkers",
    description: "Scale verification efforts with AI-powered analysis of viral claims and content.",
  },
  {
    icon: Building2,
    title: "Government & Policy",
    description: "Monitor information integrity and protect public discourse from coordinated campaigns.",
  },
  {
    icon: Globe,
    title: "Social Media Monitoring",
    description: "Track and analyze misinformation trends across platforms in real time.",
  },
  {
    icon: GraduationCap,
    title: "Education & Research",
    description: "Teach media literacy and conduct academic research on information ecosystems.",
  },
];

const UseCases = () => {
  return (
    <section id="use-cases" className="py-24">
      <div className="container mx-auto px-6">
        {/* Section Header */}
        <div className="text-center mb-16">
          <h2 className="text-sm font-medium text-primary tracking-wide uppercase mb-4">
            Applications
          </h2>
          <h3 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
            Real-World Impact
          </h3>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Trusted by professionals who need reliable truth verification at scale.
          </p>
        </div>

        {/* Use Cases Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {useCases.map((useCase) => (
            <div 
              key={useCase.title}
              className="glass-card p-8 hover-lift group"
            >
              <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-6 group-hover:bg-primary/20 transition-colors">
                <useCase.icon className="w-6 h-6 text-primary" />
              </div>
              <h4 className="text-lg font-semibold mb-3">{useCase.title}</h4>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {useCase.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default UseCases;
