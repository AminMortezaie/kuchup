import { BrandMark } from "@/components/BrandMark";
import { HeroSearch } from "@/components/HeroSearch";

export function Hero() {
  return (
    <section id="search" className="landing-hero" aria-labelledby="hero-heading">
      <div className="landing-shell hero-layout">
        <div className="hero-copy min-w-0">
          <p className="hero-enter section-kicker">
            Relocation job search, held together
          </p>

          <h1
            id="hero-heading"
            className="mt-3 text-fluid-hero text-text-primary"
          >
            Visa-sponsored software jobs in Europe — in one place
          </h1>

          <p className="hero-enter hero-enter-delay-2 hero-lede">
            Kuchup helps international software engineers discover
            relocation-focused roles, keep every decision organized, and
            tailor applications with Claude or Cursor via MCP — without losing
            the thread.
          </p>

          <HeroSearch />
        </div>

        <div className="hero-bird" aria-hidden="true">
          <span className="hero-bird-flight-path" />
          <BrandMark size="hero" className="hero-bird-mark" />
        </div>
      </div>
    </section>
  );
}
