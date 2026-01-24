import Navbar from "@/components/Navbar";
import HeroSection from "@/components/HeroSection";
import HowItWorks from "@/components/HowItWorks";
import VerificationConsole from "@/components/VerificationConsole";
import WhyTruthLens from "@/components/WhyTruthLens";
import UseCases from "@/components/UseCases";
import Footer from "@/components/Footer";

const Index = () => {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <HeroSection />
      <HowItWorks />
      <VerificationConsole />
      <WhyTruthLens />
      <UseCases />
      <Footer />
    </div>
  );
};

export default Index;
