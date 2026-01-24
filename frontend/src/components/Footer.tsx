import { Shield } from "lucide-react";

const Footer = () => {
  return (
    <footer className="py-16 border-t border-border">
      <div className="container mx-auto px-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-8">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
              <Shield className="w-5 h-5 text-primary" />
            </div>
            <span className="text-lg font-semibold">TruthLens AI</span>
          </div>

          {/* Links */}
          <div className="flex items-center gap-8 text-sm text-muted-foreground">
            <a href="#" className="hover:text-foreground transition-colors"></a>
            <a href="#" className="hover:text-foreground transition-colors"></a>
            <a href="#" className="hover:text-foreground transition-colors"></a>
            <a href="#" className="hover:text-foreground transition-colors"></a>
          </div>

          {/* Copyright */}
          <p className="text-sm text-muted-foreground">
            
          </p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
