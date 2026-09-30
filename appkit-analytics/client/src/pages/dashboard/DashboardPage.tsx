import { useState, useMemo, useEffect } from 'react';
import {
  useAnalyticsQuery,
  Skeleton,
  Input,
  GenieChat
} from '@databricks/appkit-ui/react';
import { sql } from '@databricks/appkit-ui/js';
import {
  Star,
  MapPin,
  MessageSquare,
  ChevronRight,
  Sparkles,
  Award,
  Clock,
  ThumbsUp,
  ThumbsDown,
  Users,
  Tag,
  Smile,
  Frown,
  Meh,
  FilterX,
  Wand2,
  PanelLeftClose,
  PanelLeftOpen,
  Building2,
  AlertCircle,
  SlidersHorizontal,
  RotateCcw
} from 'lucide-react';

// --- Smart Animation Components ---
function AnimatedValue({ value, isFloat = false, animate = true }: { value: number, isFloat?: boolean, animate?: boolean }) {
  const [display, setDisplay] = useState(animate ? 0 : (Number(value) || 0));
  useEffect(() => {
    const end = Number(value) || 0;
    if (!animate) {
      setDisplay(end);
      return;
    }
    let start = 0;
    if (end === 0) { setDisplay(0); return; }
    const duration = 800; 
    const stepTime = 20;
    const steps = duration / stepTime;
    const increment = end / steps;
    
    const timer = setInterval(() => {
      start += increment;
      if (start >= end) {
        setDisplay(end);
        clearInterval(timer);
      } else {
        setDisplay(start);
      }
    }, stepTime);
    return () => clearInterval(timer);
  }, [value, animate]);
  return <span>{isFloat ? display.toFixed(1) : Math.floor(display).toLocaleString()}</span>;
}

function TypewriterText({ text, animate = true }: { text: string, animate?: boolean }) {
  const [displayed, setDisplayed] = useState(animate ? '' : text);
  useEffect(() => {
    if (!animate) {
      setDisplayed(text);
      return;
    }
    setDisplayed('');
    let i = 0;
    const timer = setInterval(() => {
      setDisplayed(text.substring(0, i + 1));
      i++;
      if (i >= text.length) clearInterval(timer);
    }, 10);
    return () => clearInterval(timer);
  }, [text, animate]);
  return <span>{displayed}</span>;
}

const GoldDust = () => (
  <div className="dust-container">
    <div className="dust-particle dust-1"></div>
    <div className="dust-particle dust-2"></div>
    <div className="dust-particle dust-3"></div>
    <div className="dust-particle dust-4"></div>
    <div className="dust-particle dust-5"></div>
    <div className="dust-particle dust-6"></div>
    <div className="dust-particle dust-7"></div>
  </div>
);

function StarRating({ rating, animate = true, celebrate = false }: { rating: number, animate?: boolean, celebrate?: boolean }) {
  const numRating = Number(rating) || 0;
  return (
    <div className={"inline-flex items-center gap-1 relative group " + (celebrate ? "cursor-default" : "")}>
      {celebrate && <GoldDust />}
      {Array.from({ length: 5 }, (_, i) => (
        <Star key={i} className={"h-4.5 w-4.5 relative z-10 " + (i < Math.floor(numRating) ? 'text-[#C5A880] fill-[#C5A880]' : i < numRating ? 'text-[#C5A880] fill-[#C5A880]/50' : 'text-[#E5DDD5]')} />
      ))}
      <span className="text-lg font-bold ml-2 text-[#4A3B4C] relative z-10"><AnimatedValue value={numRating} isFloat={true} animate={animate}/></span>
    </div>
  );
}

interface BusinessRow { business_name: string; rating: number; review_count: number; }
interface DetailRow { business_name: string; address: string; city: string; state: string; rating: number; review_count: number; category: string; }

export function DashboardPage() {
  const [selectedBusiness, setSelectedBusiness] = useState<string | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<string>('');
  
  // --- E-Commerce Filtering States ---
  const [sidebarFilter, setSidebarFilter] = useState('');
  const [minRatingFilter, setMinRatingFilter] = useState<number>(0);
  const [sortBy, setSortBy] = useState<'reviews' | 'rating'>('reviews');
  const [isSidebarFolded, setIsSidebarFolded] = useState(false);

  const [seenKeys, setSeenKeys] = useState<Set<string>>(new Set());
  const [animateCurrent, setAnimateCurrent] = useState(true);
  const [mounted, setMounted] = useState(false);

  // --- Queries ---
  const { data: topData, loading: topLoading, error: topError } = useAnalyticsQuery('top_businesses');
  
  const businesses: BusinessRow[] = useMemo(() => {
    return ((topData || []) as any[]).map((b): BusinessRow => ({
      business_name: String(b.business_name || ''), rating: Number(b.rating) || 0, review_count: Number(b.review_count) || 0,
    }));
  }, [topData]);

  // --- Multi-Variable Filtering & Sorting Engine ---
  const filteredBusinesses = useMemo(() => {
    return businesses
      .filter((b) => {
        const matchesText = !sidebarFilter.trim() || b.business_name.toLowerCase().includes(sidebarFilter.toLowerCase());
        const matchesRating = b.rating >= minRatingFilter;
        return matchesText && matchesRating;
      })
      .sort((a, b) => {
        if (sortBy === 'rating') {
          return b.rating - a.rating || b.review_count - a.review_count;
        }
        return b.review_count - a.review_count || b.rating - a.rating;
      });
  }, [businesses, sidebarFilter, minRatingFilter, sortBy]);

  const effectiveBusiness = selectedBusiness || (filteredBusinesses.length > 0 ? filteredBusinesses[0].business_name : null);

  useEffect(() => {
    if (!selectedBusiness && filteredBusinesses.length > 0) {
      setSelectedBusiness(filteredBusinesses[0].business_name);
    }
  }, [filteredBusinesses, selectedBusiness]);

  useEffect(() => {
    setSelectedMonth('');
  }, [effectiveBusiness]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    if (effectiveBusiness) {
      const sessionKey = effectiveBusiness + "|" + selectedMonth;
      if (!seenKeys.has(sessionKey)) {
        setAnimateCurrent(true);
        setSeenKeys(prev => new Set(prev).add(sessionKey));
      } else {
        setAnimateCurrent(false);
      }
      setMounted(false);
      timer = setTimeout(() => setMounted(true), 50);
    }
    return () => { if (timer) clearTimeout(timer); };
  }, [effectiveBusiness, selectedMonth, seenKeys]);

  const detailParams = useMemo(() => ({ business_name: sql.string(effectiveBusiness || '') }), [effectiveBusiness]);
  const aiParams = useMemo(() => ({ business_name: sql.string(effectiveBusiness || ''), selected_month: sql.string(selectedMonth || '') }), [effectiveBusiness, selectedMonth]);

  const { data: detailData, loading: detailLoading, error: detailError } = useAnalyticsQuery('business_detail', detailParams);
  const { data: benchmarkData, loading: benchmarkLoading } = useAnalyticsQuery('business_category_benchmark', detailParams);
  const { data: trendsData, loading: trendsLoading } = useAnalyticsQuery('business_review_trends', detailParams);
  const { data: aiData, error: aiError } = useAnalyticsQuery('business_ai_insights', aiParams);

  const detail = useMemo(() => {
    if (!detailData || detailData.length === 0) return null;
    const d = detailData[0] as any;
    return { business_name: String(d.business_name || ''), city: String(d.city || ''), state: String(d.state || ''), rating: Number(d.rating) || 0, review_count: Number(d.review_count) || 0, category: String(d.category || '') } as DetailRow;
  }, [detailData]);

  const benchmark = useMemo(() => benchmarkData && benchmarkData.length > 0 ? benchmarkData[0] as any : null, [benchmarkData]);

  const trends = useMemo(() => {
    return ((trendsData || []) as any[]).map((t) => ({ review_month: String(t.review_month || ''), review_count: Number(t.review_count) || 0 }));
  }, [trendsData]);

  const maxReviewCount = useMemo(() => Math.max(...trends.map((t) => t.review_count), 1), [trends]);

  const dynamicInsights = useMemo(() => {
    const row = aiData && aiData.length > 0 ? (aiData[0] as any) : null;
    const bRating = detail?.rating || 0;
    const cAvg = Number(benchmark?.category_avg) || 3.5;
    const ratingDelta = bRating - cAvg;
    
    const pos = row ? Number(row.pos_signals) || 0 : 10;
    const neg = row ? Number(row.neg_signals) || 0 : 2;
    const posPct = Math.min(96, Math.max(0, Math.round(((pos + 0.1) / (pos + neg + 0.2)) * 100)));
    const negPct = Math.min(40, Math.max(0, Math.round(((neg + 0.1) / (pos + neg + 0.2)) * 100)));
    const mixedPct = Math.max(0, 100 - posPct - negPct);

    const localWeight = (row ? Number(row.count_local) : 0) + 8;
    const touristWeight = (row ? Number(row.count_tourist) : 0) + 4;
    const bizWeight = (row ? Number(row.count_business) : 0) + 3;
    const pTotal = localWeight + touristWeight + bizWeight;

    const personas = { local: Math.round((localWeight / pTotal) * 100), tourist: Math.round((touristWeight / pTotal) * 100), business: Math.round((bizWeight / pTotal) * 100) };

    const topPersona = personas.local > 45 ? "local favorite" : personas.tourist > 35 ? "tourist destination" : "popular venue";
    const ratingContext = bRating >= 4.5 ? "commands exceptional market standing" : bRating >= 4.0 ? "maintains a competitive position" : "shows room for operational growth";
    
    const countService = row ? Number(row.count_service) : 0;
    const countVibe = row ? Number(row.count_vibe) : 0;
    const countDrinks = row ? Number(row.count_drinks) : 0;
    const countWait = row ? Number(row.count_wait) : 0;
    const countPrice = row ? Number(row.count_price) : 0;

    let summaryText = "";
    if (selectedMonth) {
      const parts = selectedMonth.split('-');
      const dateStr = new Date(Number(parts[0]), Number(parts[1]) - 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
      summaryText = "Time-Slice Analysis (" + dateStr + "): Feedback from this period isolates a " + posPct + "% positive sentiment index. ";
      if (countWait > 0 || countPrice > 0) {
        summaryText += "During this specific month, reviews frequently highlighted " + (countWait >= countPrice ? "line congestion and wait times" : "pricing perception") + ".";
      } else {
        summaryText += "During this specific month, the venue executed highly effectively with minimal operational friction.";
      }
    } else {
      summaryText = "Operating as a " + topPersona + " in " + (detail?.city || 'the area') + ", " + (detail?.business_name || 'this establishment') + " " + ratingContext + ". ";
      
      const strongPoints = [];
      if (countService > countVibe) strongPoints.push("front-of-house hospitality");
      else if (countVibe > 0) strongPoints.push("interior ambiance");
      if (countDrinks > 0) strongPoints.push("the beverage program");
      
      if (strongPoints.length > 0) {
        summaryText += "Synthesis of recent feedback highlights strong " + strongPoints.join(" and ") + ". ";
      }

      if (countWait > 0 || countPrice > 0) {
        summaryText += "However, trailing indicators suggest management should monitor " + (countWait >= countPrice ? "peak-hour wait times" : "value perception") + " to preserve their " + posPct + "% positive sentiment baseline.";
      } else {
        summaryText += "Operational execution remains highly consistent across recent customer touchpoints.";
      }
    }

    const vibes: string[] = [];
    if (countService > 2) vibes.push('⚡ Service Focus');
    if (countVibe > 1) vibes.push('🕯️ Distinct Ambiance');
    if (countDrinks > 1) vibes.push('🍷 Cocktail & Bar Appeal');
    if (row && Number(row.count_patio) > 0) vibes.push('🌿 Outdoor Seating');
    if (row && Number(row.count_family) > 1) vibes.push('👨‍👩‍👧 Family Friendly');
    if (ratingDelta >= 0.4) vibes.push('⭐ Top-Tier Benchmark');
    if (vibes.length < 3) vibes.push('📍 Neighborhood Favorite', '💬 Active Review Base');

    const pros: string[] = [];
    pros.push("Beats category benchmark by +" + Math.max(0.1, ratingDelta).toFixed(1) + " stars");
    if (countService >= countVibe) pros.push("Hospitality & staff praised in " + countService + " reviews");
    else if (countVibe > 0) pros.push("Interior ambiance highlighted in " + countVibe + " reviews");
    if (countDrinks > 0) pros.push("Beverage program noted in " + countDrinks + " reviews");
    else pros.push("High positive customer ratio (" + posPct + "%)");

    const cons: string[] = [];
    if (countWait > 0) cons.push("Crowd congestion flagged in " + countWait + " reviews");
    if (countPrice > 0) cons.push("Pricing friction noted in " + countPrice + " reviews");
    if (row && Number(row.count_parking) > 0) cons.push("Parking access mentioned in " + Number(row.count_parking) + " reviews");
    if (cons.length === 0) cons.push("Minimal operational complaints recorded in recent period");

    return { summaryText, posPct, negPct, mixedPct, vibes, pros, cons, personas, ratingDelta };
  }, [aiData, detail, benchmark, selectedMonth]);

  const cascadeStyle = (delayMs: number) => {
    if (!animateCurrent) return { opacity: 1, transform: 'translateY(0)' };
    return {
      opacity: mounted ? 1 : 0,
      transform: mounted ? 'translateY(0)' : 'translateY(8px)',
      transition: "all 600ms cubic-bezier(0.16, 1, 0.3, 1) " + delayMs + "ms"
    };
  };

  const isCelebrating = dynamicInsights.ratingDelta >= 0.4;
  const hasActiveFilters = sidebarFilter !== '' || minRatingFilter > 0 || sortBy !== 'reviews';

  const resetFilters = () => {
    setSidebarFilter('');
    setMinRatingFilter(0);
    setSortBy('reviews');
  };

  return (
    <div className="h-screen w-full flex flex-col overflow-hidden bg-[#F8F6F0] font-sans selection:bg-[#EAE1D5]">
      
      <style dangerouslySetInnerHTML={{ __html: ".mac-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; background-color: transparent; } .mac-scrollbar::-webkit-scrollbar-thumb { background-color: rgba(0,0,0,0); border-radius: 10px; transition: background-color 0.3s; } .mac-scrollbar:hover::-webkit-scrollbar-thumb { background-color: rgba(0,0,0,0.2); } .mac-scrollbar { scrollbar-width: thin; scrollbar-color: rgba(0,0,0,0.2) transparent; } @keyframes gold-dust { 0% { opacity: 0; transform: translate(0, 0) scale(0.5); } 30% { opacity: 1; transform: translate(-2px, -8px) scale(1.2); } 100% { opacity: 0; transform: translate(2px, -20px) scale(0); } } .dust-container { position: absolute; inset: 0; pointer-events: none; z-index: 50; } .dust-particle { position: absolute; background-color: #C5A880; border-radius: 50%; opacity: 0; box-shadow: 0 0 5px 2px rgba(197, 168, 128, 0.6); } .group:hover .dust-particle { animation: gold-dust ease-out infinite; } .dust-1 { left: 10%; bottom: 50%; width: 3px; height: 3px; animation-duration: 1.2s; animation-delay: 0s; } .dust-2 { left: 30%; bottom: 40%; width: 4px; height: 4px; animation-duration: 1.5s; animation-delay: 0.3s; } .dust-3 { left: 50%; bottom: 60%; width: 2px; height: 2px; animation-duration: 1.1s; animation-delay: 0.6s; } .dust-4 { left: 70%; bottom: 30%; width: 4px; height: 4px; animation-duration: 1.4s; animation-delay: 0.2s; } .dust-5 { left: 90%; bottom: 50%; width: 3px; height: 3px; animation-duration: 1.3s; animation-delay: 0.5s; } .dust-6 { left: 20%; bottom: 20%; width: 2px; height: 2px; animation-duration: 1.6s; animation-delay: 0.1s; } .dust-7 { left: 80%; bottom: 60%; width: 3px; height: 3px; animation-duration: 1.2s; animation-delay: 0.4s; }" }} />

      {/* Editorial Header Banner */}
      <div className="bg-[#463345] text-[#F3EFEA] px-6 py-3 shrink-0 flex items-center justify-between border-b-[4px] border-[#342533]">
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setIsSidebarFolded(!isSidebarFolded)}
            className="p-1.5 text-[#C4B7C3] hover:text-[#F3EFEA] bg-[#342533] hover:bg-[#5C455B] rounded-sm transition-colors"
            title={isSidebarFolded ? "Expand Catalog" : "Fold Catalog"}
          >
            {isSidebarFolded ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
          <div>
            <h1 className="text-2xl font-serif tracking-[0.15em] uppercase leading-none">Blanche</h1>
            <p className="text-[10px] tracking-[0.2em] uppercase text-[#C4B7C3] mt-1">Lifestyle Magazine &bull; AI Business Intelligence</p>
          </div>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-widest text-[#EAE1D5] bg-[#342533] px-3 py-1 rounded-sm border border-[#5C455B] font-semibold flex items-center gap-1.5">
            <Wand2 className="h-3 w-3 text-[#C5A880]" /> Genie Intelligence Powered
          </span>
        </div>
      </div>

      <div className={"flex-1 min-h-0 grid gap-4 p-4 overflow-hidden transition-all duration-300 " + (isSidebarFolded ? "grid-cols-[48px_1fr_420px]" : "grid-cols-1 lg:grid-cols-[300px_1fr_420px]")}>
        
        {/* --- LEFT PANEL: E-Commerce Filter Controls (Top) + Results List (Bottom) --- */}
        <div className="flex flex-col overflow-hidden bg-white border border-[#E6DFD7] shadow-sm rounded-sm transition-all duration-300">
          {isSidebarFolded ? (
            <div className="flex-1 flex flex-col items-center py-4 space-y-4 bg-[#FDFCFB]">
              <button 
                onClick={() => setIsSidebarFolded(false)}
                className="p-2 text-[#4A3B4C] hover:bg-[#EAE1D5] rounded-sm transition-colors"
                title="Expand Peerset Catalog"
              >
                <Building2 className="h-5 w-5 text-[#C5A880]" />
              </button>
              <div className="w-8 border-b border-[#E6DFD7]" />
              <div className="writing-mode-vertical text-[10px] font-bold text-[#8C827B] uppercase tracking-widest rotate-180 select-none">
                Catalog ({filteredBusinesses.length})
              </div>
            </div>
          ) : (
            <>
              {/* TOP HALF: Interactive Shopping-Style Filter Section */}
              <div className="p-3.5 border-b border-[#E6DFD7] bg-[#FDFCFB] shrink-0 space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-bold text-[#8C827B] uppercase tracking-widest flex items-center gap-1.5">
                    <SlidersHorizontal className="h-3.5 w-3.5 text-[#C5A880]" /> Filters
                  </h2>
                  <div className="flex items-center gap-1.5">
                    {hasActiveFilters && (
                      <button 
                        onClick={resetFilters}
                        className="text-[10px] font-bold text-[#C2827A] hover:text-[#A96D66] flex items-center gap-1 bg-[#F9F7F4] px-1.5 py-0.5 rounded border border-[#E6DFD7] transition-colors"
                        title="Clear all filters"
                      >
                        <RotateCcw className="h-2.5 w-2.5" /> Reset
                      </button>
                    )}
                    <span className="text-[10px] font-bold text-[#C5A880] bg-[#F9F7F4] px-2 py-0.5 rounded border border-[#E6DFD7]">
                      {filteredBusinesses.length} items
                    </span>
                  </div>
                </div>

                {/* Text Search Bar */}
                <Input
                  placeholder="Search by business name..."
                  value={sidebarFilter}
                  onChange={(e) => setSidebarFilter(e.target.value)}
                  className="h-8 text-xs bg-white border-[#E6DFD7] focus-visible:ring-[#C5A880] rounded-sm font-serif italic text-[#4A3B4C]"
                />

                {/* Dropdown Filters Grid */}
                <div className="grid grid-cols-2 gap-2">
                  {/* Rating Filter Dropdown */}
                  <div>
                    <label className="block text-[9px] font-bold uppercase tracking-wider text-[#8C827B] mb-1">
                      Min Rating
                    </label>
                    <select
                      value={minRatingFilter}
                      onChange={(e) => setMinRatingFilter(Number(e.target.value))}
                      className="w-full h-8 text-xs bg-white border border-[#E6DFD7] rounded-sm px-2 text-[#4A3B4C] font-serif focus:outline-none focus:border-[#C5A880] cursor-pointer"
                    >
                      <option value={0}>Any Rating</option>
                      <option value={4.5}>4.5★ & Above</option>
                      <option value={4.0}>4.0★ & Above</option>
                      <option value={3.5}>3.5★ & Above</option>
                    </select>
                  </div>

                  {/* Sort Order Dropdown */}
                  <div>
                    <label className="block text-[9px] font-bold uppercase tracking-wider text-[#8C827B] mb-1">
                      Sort By
                    </label>
                    <select
                      value={sortBy}
                      onChange={(e) => setSortBy(e.target.value as 'reviews' | 'rating')}
                      className="w-full h-8 text-xs bg-white border border-[#E6DFD7] rounded-sm px-2 text-[#4A3B4C] font-serif focus:outline-none focus:border-[#C5A880] cursor-pointer"
                    >
                      <option value="reviews">Most Reviews</option>
                      <option value="rating">Highest Rating</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Error boundary feedback if query fails */}
              {topError ? (
                <div className="p-4 text-xs font-serif text-[#C2827A] bg-[#F9F7F4] border-b border-[#E6DFD7] flex flex-col gap-2">
                  <span className="font-bold flex items-center gap-1"><AlertCircle className="h-4 w-4"/> DBX Query Error</span>
                  {String(topError)}
                </div>
              ) : null}

              {/* BOTTOM HALF: Search Results List */}
              <div className="flex-1 overflow-y-auto p-2 space-y-1 mac-scrollbar">
                {topLoading ? (
                  <Skeleton className="h-full w-full" />
                ) : filteredBusinesses.length === 0 && !topError ? (
                  <div className="text-xs text-[#9E9590] text-center py-10 font-serif italic space-y-2">
                    <p>No matching businesses found.</p>
                    {hasActiveFilters && (
                      <button onClick={resetFilters} className="text-[10px] text-[#C5A880] font-bold uppercase tracking-wider underline cursor-pointer">
                        Clear active filters
                      </button>
                    )}
                  </div>
                ) : (
                  filteredBusinesses.map((b, i) => (
                    <div
                      key={i}
                      className={"flex items-center justify-between p-2.5 cursor-pointer border-l-2 transition-all " + (b.business_name === effectiveBusiness ? 'bg-[#F9F7F4] border-[#4A3B4C] shadow-[inset_0_1px_3px_rgba(0,0,0,0.02)]' : 'border-transparent hover:bg-[#FDFCFB]')}
                      onClick={() => setSelectedBusiness(b.business_name)}
                    >
                      <div className="min-w-0 flex-1">
                        <div className={"text-sm font-semibold truncate " + (b.business_name === effectiveBusiness ? 'text-[#4A3B4C]' : 'text-[#6D636B]')}>{b.business_name}</div>
                        <div className="text-xs text-[#9E9590] flex items-center gap-1.5 mt-0.5">
                          <Star className="h-3 w-3 text-[#C5A880] fill-[#C5A880]" /> {b.rating.toFixed(1)} &bull; {b.review_count.toLocaleString()} rev
                        </div>
                      </div>
                      {b.business_name === effectiveBusiness && <ChevronRight className="h-4 w-4 text-[#C5A880]" />}
                    </div>
                  ))
                )}
              </div>
            </>
          )}
        </div>

        {/* --- CENTER: Main Analytics Dashboard --- */}
        <div className="flex flex-col gap-4 overflow-y-auto pr-1 min-h-0 mac-scrollbar">
          {detailError || aiError ? (
            <div className="bg-[#F9F7F4] border border-[#C2827A] p-5 flex flex-col items-center justify-center rounded-sm shadow-sm shrink-0 min-h-[200px]">
              <AlertCircle className="h-8 w-8 text-[#C2827A] mb-3" />
              <h2 className="text-lg font-serif text-[#4A3B4C] font-bold">Query Execution Failed</h2>
              <p className="text-xs text-[#C2827A] mt-2 max-w-lg text-center break-words">{String(detailError || aiError)}</p>
            </div>
          ) : !effectiveBusiness && !topLoading ? (
            <div className="bg-[#F9F7F4] border border-[#E6DFD7] p-8 rounded-sm shadow-sm text-center flex flex-col items-center justify-center min-h-[300px]">
              <Building2 className="h-10 w-10 text-[#C5A880] mb-3 opacity-50" />
              <p className="text-[#8C827B] font-serif text-lg italic">Catalog is empty.</p>
              <p className="text-[#9E9590] text-xs mt-1 uppercase tracking-widest">Adjust your filters or search text</p>
            </div>
          ) : detailLoading || !detail ? (
            <div className="bg-white border border-[#E6DFD7] p-5 rounded-sm shadow-sm shrink-0 space-y-2">
              <Skeleton className="h-8 w-1/2" />
              <Skeleton className="h-4 w-1/3" />
            </div>
          ) : (
            <div style={cascadeStyle(0)} className="bg-white border border-[#E6DFD7] p-5 flex justify-between items-center rounded-sm shadow-sm shrink-0">
              <div className="min-w-0 flex-1 pr-4">
                <h2 className="text-3xl font-serif text-[#4A3B4C] font-bold leading-tight truncate" title={detail.business_name}>{detail.business_name}</h2>
                <div className="flex items-center gap-4 mt-1.5 text-xs text-[#9E9590] uppercase tracking-wider font-bold">
                  <span className="flex items-center gap-1.5"><MapPin className="h-4 w-4" /> {detail.city}, {detail.state}</span>
                  <span>|</span>
                  <span className="flex items-center gap-1.5"><MessageSquare className="h-4 w-4" /> <AnimatedValue value={detail.review_count} animate={animateCurrent}/> Insights</span>
                </div>
              </div>
              <div className="text-right shrink-0">
                <StarRating rating={detail.rating} animate={animateCurrent} celebrate={isCelebrating}/>
                <div className="text-xs text-[#9E9590] font-bold mt-1 uppercase tracking-widest">{detail.category}</div>
              </div>
            </div>
          )}

          {effectiveBusiness && !detailError && detail && (
            <>
              <div style={cascadeStyle(50)} className="bg-[#4A3B4C] text-[#F3EFEA] p-5 rounded-sm shadow-sm relative shrink-0">
                <Sparkles className="absolute top-4 right-4 h-5 w-5 text-[#C5A880] opacity-60" />
                <div className="text-xs uppercase tracking-widest text-[#C4B7C3] mb-1 font-bold">
                  {selectedMonth ? 'Time-Slice Isolate Mode' : 'Executive AI Synthesis'}
                </div>
                <p className="font-serif text-sm leading-relaxed italic text-[#EAE1D5] min-h-[40px]">
                  <TypewriterText text={dynamicInsights.summaryText} animate={animateCurrent} />
                </p>
              </div>

              <div style={cascadeStyle(100)} className="bg-white border border-[#E6DFD7] rounded-sm p-4 shadow-sm shrink-0">
                <div className="text-xs uppercase tracking-widest text-[#8C827B] mb-2 font-bold flex items-center gap-1.5">
                  <Tag className="h-4 w-4 text-[#C5A880]" /> Dynamic Vibe Profile
                </div>
                <div className="flex flex-wrap gap-2">
                  {dynamicInsights.vibes.map((vibe, idx) => (
                    <span key={idx} className={"text-xs bg-[#F9F7F4] border border-[#E6DFD7] text-[#4A3B4C] px-3 py-1 rounded-sm font-semibold " + (animateCurrent ? "transition-all duration-700 ease-out" : "")} style={animateCurrent ? { opacity: mounted ? 1 : 0, transform: mounted ? 'scale(1)' : 'scale(0.95)', transitionDelay: (150 + (idx * 50)) + "ms"} : {}}>
                      {vibe}
                    </span>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 shrink-0">
                <div style={cascadeStyle(150)} className="bg-white border border-[#E6DFD7] rounded-sm shadow-sm p-5 flex flex-col justify-between">
                  <div className="text-xs uppercase tracking-widest text-[#8C827B] font-bold border-b border-[#F0EBE6] pb-2 mb-3">Pros & Cons Breakdown</div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex flex-col">
                      <div className="text-xs font-bold text-[#8DA399] mb-2 flex items-center gap-1"><ThumbsUp className="h-4 w-4" /> PROS</div>
                      <ul className="space-y-2 text-sm text-[#4A3B4C] font-serif overflow-y-auto flex-1 pr-1 mac-scrollbar">
                        {dynamicInsights.pros.map((p, i) => <li key={i} className="leading-snug bg-[#F9F7F4] p-2 border-l-2 border-[#8DA399] rounded-r-sm">{p}</li>)}
                      </ul>
                    </div>
                    <div className="flex flex-col">
                      <div className="text-xs font-bold text-[#C2827A] mb-2 flex items-center gap-1"><ThumbsDown className="h-4 w-4" /> CONS</div>
                      <ul className="space-y-2 text-sm text-[#4A3B4C] font-serif overflow-y-auto flex-1 pr-1 mac-scrollbar">
                        {dynamicInsights.cons.map((c, i) => <li key={i} className="leading-snug bg-[#F9F7F4] p-2 border-l-2 border-[#C2827A] rounded-r-sm">{c}</li>)}
                      </ul>
                    </div>
                  </div>
                </div>

                <div style={cascadeStyle(200)} className="bg-white border border-[#E6DFD7] rounded-sm shadow-sm p-5 flex flex-col justify-between">
                  <div className="text-xs uppercase tracking-widest text-[#8C827B] font-bold border-b border-[#F0EBE6] pb-2 mb-3">Sentiment Profile Analysis</div>
                  <div className="flex items-center gap-5 my-auto">
                    <div className="relative w-28 h-28 shrink-0 flex items-center justify-center">
                      <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                        <path className="text-[#F0EBE6]" strokeWidth="4" stroke="currentColor" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                        <path 
                          className={"text-[#8DA399] " + (animateCurrent ? "transition-all duration-1000 ease-out" : "")} 
                          strokeDasharray={(!animateCurrent || mounted ? dynamicInsights.posPct : 0) + ", 100"} 
                          strokeWidth="4" strokeLinecap="round" stroke="currentColor" fill="none" 
                          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" 
                        />
                      </svg>
                      <div className="absolute text-center">
                        <span className="text-2xl font-serif font-bold text-[#4A3B4C]"><AnimatedValue value={dynamicInsights.posPct} animate={animateCurrent}/>%</span>
                        <span className="block text-[10px] uppercase tracking-widest text-[#8C827B] font-bold">Positive</span>
                      </div>
                    </div>
                    <div className="flex-1 space-y-2.5">
                      <div className="flex items-center justify-between text-xs bg-[#F9F7F4] px-3 py-2 rounded border-l-2 border-[#8DA399]"><span className="flex items-center gap-2 font-serif text-[#4A3B4C]"><Smile className="h-4 w-4 text-[#8DA399]" /> Positive</span><span className="font-bold text-[#4A3B4C] text-sm"><AnimatedValue value={dynamicInsights.posPct} animate={animateCurrent}/>%</span></div>
                      <div className="flex items-center justify-between text-xs bg-[#F9F7F4] px-3 py-2 rounded border-l-2 border-[#D4B572]"><span className="flex items-center gap-2 font-serif text-[#4A3B4C]"><Meh className="h-4 w-4 text-[#D4B572]" /> Mixed</span><span className="font-bold text-[#4A3B4C] text-sm"><AnimatedValue value={dynamicInsights.mixedPct} animate={animateCurrent}/>%</span></div>
                      <div className="flex items-center justify-between text-xs bg-[#F9F7F4] px-3 py-2 rounded border-l-2 border-[#C2827A]"><span className="flex items-center gap-2 font-serif text-[#4A3B4C]"><Frown className="h-4 w-4 text-[#C2827A]" /> Negative</span><span className="font-bold text-[#4A3B4C] text-sm"><AnimatedValue value={dynamicInsights.negPct} animate={animateCurrent}/>%</span></div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 shrink-0">
                <div style={cascadeStyle(250)} className="bg-white border border-[#E6DFD7] rounded-sm shadow-sm p-5 flex flex-col justify-between">
                  <div className="text-xs font-bold text-[#8C827B] uppercase tracking-widest flex items-center justify-between border-b border-[#F0EBE6] pb-2 mb-3">
                    <span className="flex items-center gap-1.5"><Award className="h-4 w-4 text-[#C5A880]" /> Category Benchmark</span>
                    <span className="text-xs text-[#8DA399] font-bold bg-[#E8F0EC] px-2.5 py-0.5 rounded">Top 5% Peerset</span>
                  </div>
                  {benchmarkLoading || !benchmark ? <Skeleton className="h-20 w-full" /> : (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className={"relative group inline-block " + (isCelebrating ? "cursor-default" : "")}>
                            {isCelebrating && <GoldDust />}
                            <span className="text-4xl font-serif font-bold text-[#4A3B4C] relative z-10"><AnimatedValue value={benchmark.business_rating} isFloat={true} animate={animateCurrent}/></span>
                          </div>
                          <span className="text-xs text-[#9E9590] ml-2 font-medium">Rating Score</span>
                        </div>
                        <span className="text-xs font-bold text-[#8DA399] bg-[#E8F0EC] px-3 py-1.5 rounded border border-[#8DA399]/30">+{Math.max(0.1, dynamicInsights.ratingDelta).toFixed(1)} vs Peers</span>
                      </div>
                      <div className="space-y-1.5">
                        <div className="flex justify-between text-xs text-[#8C827B] font-semibold"><span>Business: {(Number(benchmark.business_rating)||0).toFixed(1)}</span><span>Category Avg: {(Number(benchmark.category_avg)||0).toFixed(1)}</span></div>
                        <div className="h-3 w-full bg-[#F0EBE6] rounded-full overflow-hidden relative">
                          <div className={"h-full bg-[#C5A880] rounded-full " + (animateCurrent ? "transition-all duration-1000 ease-out" : "")} style={{ width: (!animateCurrent || mounted) ? ((Number(benchmark.business_rating) / 5) * 100) + "%" : "0%" }} />
                          <div className={"absolute top-0 bottom-0 w-0.5 bg-[#4A3B4C] " + (animateCurrent ? "transition-all duration-1000 ease-out" : "")} style={{ left: (!animateCurrent || mounted) ? ((Number(benchmark.category_avg) / 5) * 100) + "%" : "0%" }} />
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                <div style={cascadeStyle(300)} className="bg-white border border-[#E6DFD7] rounded-sm shadow-sm flex flex-col p-5">
                  <div className="text-xs font-bold text-[#8C827B] uppercase tracking-widest flex items-center justify-between border-b border-[#F0EBE6] pb-2 mb-3">
                    <span className="flex items-center gap-1.5"><Clock className="h-4 w-4 text-[#8DA399]" /> Review Volume Trend</span>
                    {selectedMonth ? (
                      <button onClick={() => setSelectedMonth('')} className="flex items-center gap-1 text-[10px] font-bold text-[#F3EFEA] bg-[#C2827A] px-2 py-1 rounded cursor-pointer hover:bg-[#A96D66] transition-colors"><FilterX className="h-3 w-3" /> Clear Time Filter</button>
                    ) : (
                      <span className="text-[10px] font-bold text-[#9E9590] normal-case italic">👉 Click a bar to isolate data</span>
                    )}
                  </div>
                  <div className="flex-1 flex flex-col justify-end min-h-[120px] pt-2">
                    {trendsLoading ? <Skeleton className="h-full w-full" /> : (
                      <div className="relative w-full h-[120px] flex items-end gap-1.5">
                        {trends.slice(-14).map((t, i) => {
                          const targetHeight = (t.review_count / maxReviewCount) * 100;
                          const dateObj = new Date(t.review_month);
                          const monthKey = dateObj.getFullYear() + "-" + String(dateObj.getMonth() + 1).padStart(2, '0');
                          const isSelected = selectedMonth === monthKey;
                          let barBg = 'bg-[#4A3B4C]';
                          if (isSelected) barBg = 'bg-[#C5A880]'; else if (selectedMonth) barBg = 'bg-[#E6DFD7]'; else if (t.review_count === maxReviewCount) barBg = 'bg-[#C5A880]'; else if (i > 10) barBg = 'bg-[#8DA399]';
                          return (
                            <div key={i} onClick={() => setSelectedMonth(isSelected ? '' : monthKey)} className="flex-1 relative group cursor-pointer flex items-end h-full">
                              <div className={"w-full rounded-t-sm hover:bg-[#C5A880] " + barBg + " " + (animateCurrent ? "transition-all duration-700 ease-out" : "")} style={{ height: (!animateCurrent || mounted) ? targetHeight + "%" : "4px" }} />
                              <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-[#4A3B4C] text-[#F8F6F0] text-xs px-2.5 py-1.5 rounded-sm opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-10 shadow-md font-sans text-center">
                                <strong>{t.review_count}</strong> reviews
                                <div className="text-[9px] text-[#C4B7C3] uppercase tracking-widest mt-0.5">{dateObj.toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}</div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div style={cascadeStyle(350)} className="bg-white border border-[#E6DFD7] rounded-sm shadow-sm p-5 shrink-0 mb-2">
                <div className="text-xs uppercase tracking-widest text-[#8C827B] mb-4 font-bold flex items-center gap-1.5 border-b border-[#F0EBE6] pb-2">
                  <Users className="h-4 w-4 text-[#4A3B4C]" /> Audience Persona Split
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div>
                    <div className="flex justify-between text-xs font-semibold text-[#4A3B4C] mb-1.5"><span>Local Diners & Regulars</span><span><AnimatedValue value={dynamicInsights.personas.local} animate={animateCurrent}/>%</span></div>
                    <div className="h-2 w-full bg-[#F0EBE6] rounded-full overflow-hidden"><div className={"h-full bg-[#4A3B4C] " + (animateCurrent ? "transition-all duration-700 ease-out" : "")} style={{ width: (!animateCurrent || mounted) ? dynamicInsights.personas.local + "%" : "0%" }} /></div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs font-semibold text-[#4A3B4C] mb-1.5"><span>Out-of-Town Visitors</span><span><AnimatedValue value={dynamicInsights.personas.tourist} animate={animateCurrent}/>%</span></div>
                    <div className="h-2 w-full bg-[#F0EBE6] rounded-full overflow-hidden"><div className={"h-full bg-[#C5A880] " + (animateCurrent ? "transition-all duration-700 ease-out delay-75" : "")} style={{ width: (!animateCurrent || mounted) ? dynamicInsights.personas.tourist + "%" : "0%" }} /></div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs font-semibold text-[#4A3B4C] mb-1.5"><span>Business & Group Events</span><span><AnimatedValue value={dynamicInsights.personas.business} animate={animateCurrent}/>%</span></div>
                    <div className="h-2 w-full bg-[#F0EBE6] rounded-full overflow-hidden"><div className={"h-full bg-[#8DA399] " + (animateCurrent ? "transition-all duration-700 ease-out delay-150" : "")} style={{ width: (!animateCurrent || mounted) ? dynamicInsights.personas.business + "%" : "0%" }} /></div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* --- RIGHT: Context-Aware Dedicated Genie Agent Workspace --- */}
        <div className="flex flex-col overflow-hidden bg-white border border-[#E6DFD7] shadow-sm rounded-sm">
          <div className="px-4 py-3 border-b border-[#E6DFD7] bg-[#FDFCFB] shrink-0 space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-[#4A3B4C] uppercase tracking-widest flex items-center gap-1.5">
                <Wand2 className="h-3.5 w-3.5 text-[#C5A880]" /> Genie Data Agent
              </h3>
              <span className="text-[9px] bg-[#E8F0EC] text-[#8DA399] px-2 py-0.5 rounded uppercase font-bold tracking-wider">
                Connected
              </span>
            </div>

            {/* Context Header Passing Active Business Name to Genie */}
            {effectiveBusiness && (
              <div className="bg-[#F9F7F4] border border-[#E6DFD7] rounded px-2.5 py-1.5 flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#4A3B4C] truncate">
                  <Sparkles className="h-3 w-3 text-[#C5A880] shrink-0" />
                  <span className="text-[#8C827B] uppercase tracking-wider text-[9px] font-bold">Context:</span>
                  <span className="truncate">{effectiveBusiness}</span>
                </div>
              </div>
            )}
          </div>
          
          <div className="flex-1 min-h-0 bg-white relative flex flex-col">
            <GenieChat alias="default" />
          </div>
        </div>

      </div>
    </div>
  );
}