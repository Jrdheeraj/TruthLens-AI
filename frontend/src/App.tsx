import VerificationConsole from "@/components/VerificationConsole";
import SiteNavbar from "@/components/site/SiteNavbar";
import SiteHero from "@/components/site/SiteHero";
import SiteSteps from "@/components/site/SiteSteps";
import SiteFeatureAlternating from "@/components/site/SiteFeatureAlternating";
import SiteStackGrid from "@/components/site/SiteStackGrid";
import SiteWhyTruthLens from "@/components/site/SiteWhyTruthLens";
import SiteFeatureSixGrid from "@/components/site/SiteFeatureSixGrid";
import SiteDashboardMocks from "@/components/site/SiteDashboardMocks";
import SiteFinalCta from "@/components/site/SiteFinalCta";
import SiteUseCases from "@/components/site/SiteUseCases";
import SiteFooter from "@/components/site/SiteFooter";

export default function App() {
  return (
    <div className="min-h-screen bg-black">
      <SiteNavbar />
      <SiteHero />
      <SiteSteps />
      <SiteFeatureAlternating />
      <SiteStackGrid />
      <VerificationConsole />
      <SiteWhyTruthLens />
      <SiteFeatureSixGrid />
      <SiteDashboardMocks />
      <SiteUseCases />
      <SiteFinalCta />
      <SiteFooter />
    </div>
  );
}
