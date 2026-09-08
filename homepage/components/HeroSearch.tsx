import { SearchBar } from "@/components/SearchBar";

export function HeroSearch() {
  return (
    <div className="hero-enter hero-enter-delay-3 hero-search">
      <div className="hero-search-glow">
        <SearchBar id="hero-search" />
      </div>
      <div className="hero-search-note">
        <p>
          Public catalog. No sign-in required. Updated every six hours
          from company career pages.
        </p>
        <div className="hero-search-links">
          <a href="/mcp">
            Claude &amp; Cursor MCP <span aria-hidden="true">→</span>
          </a>
        </div>
      </div>
    </div>
  );
}
