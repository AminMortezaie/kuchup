import { AccessSection } from "@/components/AccessSection";
import { CTA } from "@/components/CTA";
import { CountryPathways } from "@/components/CountryPathways";
import { EvidenceRail } from "@/components/EvidenceRail";
import { Hero } from "@/components/Hero";
import { HomeFAQ } from "@/components/HomeFAQ";
import { HomeWorkflow } from "@/components/HomeWorkflow";
import { McpFeature } from "@/components/McpFeature";
import { ProductJourney } from "@/components/ProductJourney";
import { RelocationProblem } from "@/components/RelocationProblem";
import { SearchFlowProvider } from "@/components/SearchFlowContext";
import { SearchResults } from "@/components/SearchResults";
import { TrustPrinciples } from "@/components/TrustPrinciples";

export default function HomePage() {
  return (
    <SearchFlowProvider>
      <main>
        <Hero />
        <div className="landing-shell">
          <SearchResults />
        </div>
        <EvidenceRail />
        <RelocationProblem />
        <ProductJourney />
        <McpFeature />
        <CountryPathways />
        <HomeWorkflow />
        <AccessSection />
        <TrustPrinciples />
        <HomeFAQ />
        <CTA />
      </main>
    </SearchFlowProvider>
  );
}
