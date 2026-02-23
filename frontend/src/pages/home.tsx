import Navbar from "@/components/landing/Navbar";
import Hero from "@/components/landing/HeroSection";
import TrustSection from "@/components/landing/TrustSection";
import BenefitsSection from "@/components/landing/BenefitsSection";
import HowItWorks from "@/components/landing/HowItWorks";
import TechSection from "@/components/landing/TechSection";
import RecapSection from "@/components/landing/RecapSection";
import FAQSection from "@/components/landing/FAQSection";
import Footer from "@/components/landing/Footer";

const HomePage = () => {
  return (
    <>
      <Navbar />
      <Hero />
      <TrustSection />
      <BenefitsSection />
      <HowItWorks />
      <TechSection />
      <RecapSection />
      <FAQSection />
      <Footer />
    </>
  );
};

export default HomePage;
