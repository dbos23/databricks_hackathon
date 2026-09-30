import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router';
import {
  Button,
  Card,
  CardContent,
  Input,
  Badge,
} from '@databricks/appkit-ui/react';
import {
  Send,
  Bot,
  User,
  ArrowRight,
  MapPin,
} from 'lucide-react';

interface Message {
  id: number;
  role: 'agent' | 'user';
  text: string;
  suggestions?: string[];
  category?: string;
  showCategoryPicker?: boolean;
}

const ALL_CATEGORIES = [
  'Restaurants and cuisines',
  'Cafes, bakeries, and sweets',
  'Bars, breweries, and nightlife',
  'Retail shopping',
  'Beauty, spas, and personal care',
  'Fitness and recreation',
  'Health and medical',
  'Arts, culture, and entertainment',
  'Grocery markets and specialty food',
  'Home and repair services',
  'Travel and transportation',
];

const CATEGORY_MAP: Record<string, string> = {
  'restaurant': 'Restaurants and cuisines',
  'food': 'Restaurants and cuisines',
  'eat': 'Restaurants and cuisines',
  'dine': 'Restaurants and cuisines',
  'seafood': 'Restaurants and cuisines',
  'cajun': 'Restaurants and cuisines',
  'creole': 'Restaurants and cuisines',
  'brunch': 'Restaurants and cuisines',
  'breakfast': 'Restaurants and cuisines',
  'lunch': 'Restaurants and cuisines',
  'dinner': 'Restaurants and cuisines',
  'pizza': 'Restaurants and cuisines',
  'sushi': 'Restaurants and cuisines',
  'coffee': 'Cafes, bakeries, and sweets',
  'cafe': 'Cafes, bakeries, and sweets',
  'bakery': 'Cafes, bakeries, and sweets',
  'dessert': 'Cafes, bakeries, and sweets',
  'sweet': 'Cafes, bakeries, and sweets',
  'donut': 'Cafes, bakeries, and sweets',
  'bar': 'Bars, breweries, and nightlife',
  'nightlife': 'Bars, breweries, and nightlife',
  'drink': 'Bars, breweries, and nightlife',
  'brewery': 'Bars, breweries, and nightlife',
  'beer': 'Bars, breweries, and nightlife',
  'cocktail': 'Bars, breweries, and nightlife',
  'wine': 'Bars, breweries, and nightlife',
  'pub': 'Bars, breweries, and nightlife',
  'club': 'Bars, breweries, and nightlife',
  'shop': 'Retail shopping',
  'store': 'Retail shopping',
  'retail': 'Retail shopping',
  'buy': 'Retail shopping',
  'pet': 'Retail shopping',
  'dog': 'Retail shopping',
  'beauty': 'Beauty, spas, and personal care',
  'spa': 'Beauty, spas, and personal care',
  'hair': 'Beauty, spas, and personal care',
  'salon': 'Beauty, spas, and personal care',
  'nail': 'Beauty, spas, and personal care',
  'gym': 'Fitness and recreation',
  'fitness': 'Fitness and recreation',
  'workout': 'Fitness and recreation',
  'yoga': 'Fitness and recreation',
  'sport': 'Fitness and recreation',
  'park': 'Fitness and recreation',
  'doctor': 'Health and medical',
  'dentist': 'Health and medical',
  'health': 'Health and medical',
  'medical': 'Health and medical',
  'pharmacy': 'Health and medical',
  'auto': 'Home and repair services',
  'repair': 'Home and repair services',
  'plumb': 'Home and repair services',
  'home': 'Home and repair services',
  'car': 'Travel and transportation',
  'travel': 'Travel and transportation',
  'hotel': 'Travel and transportation',
  'taxi': 'Travel and transportation',
  'art': 'Arts, culture, and entertainment',
  'museum': 'Arts, culture, and entertainment',
  'entertainment': 'Arts, culture, and entertainment',
  'fun': 'Arts, culture, and entertainment',
  'kid': 'Arts, culture, and entertainment',
  'family': 'Restaurants and cuisines',
  'grocery': 'Grocery markets and specialty food',
  'market': 'Grocery markets and specialty food',
};

function detectCategory(userInput: string): { category: string; confident: boolean } {
  const input = userInput.toLowerCase();
  // Count matches per category to pick the best one
  const scores: Record<string, number> = {};
  for (const [keyword, cat] of Object.entries(CATEGORY_MAP)) {
    if (input.includes(keyword)) {
      scores[cat] = (scores[cat] || 0) + 1;
    }
  }
  const entries = Object.entries(scores).sort((a, b) => b[1] - a[1]);
  if (entries.length > 0) {
    return { category: entries[0][0], confident: entries[0][1] >= 1 };
  }
  // No match at all — default to Restaurants
  return { category: 'Restaurants and cuisines', confident: false };
}

function generateAgentResponse(userInput: string): { text: string; category: string; suggestions: string[]; showCategoryPicker: boolean } {
  const { category, confident } = detectCategory(userInput);

  if (!confident) {
    return {
      text: `Interesting! I couldn't match that to a specific category, so I'll start with **${category}**. If that's not right, pick one below or just tell me more about what you're looking for.`,
      category,
      suggestions: [],
      showCategoryPicker: true,
    };
  }

  return {
    text: `Great choice! I've identified **${category}** as our focus area. I've filtered the dataset to greater New Orleans and will highlight businesses with the highest ratings and reviews. Click **Move On** when you're ready to explore the dashboard!`,
    category,
    suggestions: [
      'Only show places with 50+ reviews',
      'Focus on the French Quarter',
    ],
    showCategoryPicker: false,
  };
}

export function AgentPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      role: 'agent',
      text: `Welcome to the **New Orleans Business Analytics** tool! What kind of businesses would you like to explore? Pick a category below or describe what you're looking for.`,
    },
  ]);
  const [input, setInput] = useState('');
  const [detectedCategory, setDetectedCategory] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;
    const userMsg: Message = { id: messages.length, role: 'user', text: input.trim() };
    const response = generateAgentResponse(input);
    setDetectedCategory(response.category);
    const agentMsg: Message = {
      id: messages.length + 1,
      role: 'agent',
      text: response.text,
      suggestions: response.suggestions,
      category: response.category,
      showCategoryPicker: response.showCategoryPicker,
    };
    setMessages((prev) => [...prev, userMsg, agentMsg]);
    setInput('');
  };

  const handleQuickPick = (cat: string) => {
    const response = generateAgentResponse(cat);
    setDetectedCategory(response.category);
    const userMsg: Message = { id: messages.length, role: 'user', text: cat };
    const agentMsg: Message = {
      id: messages.length + 1,
      role: 'agent',
      text: response.text,
      suggestions: response.suggestions,
      category: response.category,
    };
    setMessages((prev) => [...prev, userMsg, agentMsg]);
  };

  const handleCategoryOverride = (cat: string) => {
    setDetectedCategory(cat);
    const agentMsg: Message = {
      id: messages.length,
      role: 'agent',
      text: `Switched to **${cat}**. Click **Move On** to explore the dashboard!`,
      category: cat,
    };
    setMessages((prev) => [...prev, agentMsg]);
  };

  const handleMoveOn = () => {
    navigate(`/dashboard?category=${encodeURIComponent(detectedCategory || 'Restaurants and cuisines')}`);
  };

  const renderMarkdown = (text: string) => {
    return text.split('\n').map((line, i) => (
      <span key={i}>
        {i > 0 && <br />}
        {line.split(/\*\*(.*?)\*\*/).map((part, j) =>
          j % 2 === 1 ? <strong key={j}>{part}</strong> : part
        )}
      </span>
    ));
  };

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-5rem)] flex flex-col overflow-hidden">
      {/* Compact header */}
      <div className="hero-gradient rounded-xl px-4 py-4 text-white text-center relative overflow-hidden mb-3 shrink-0">
        <div className="relative z-10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="inline-flex items-center gap-1.5 bg-white/20 backdrop-blur-sm rounded-full px-3 py-0.5 text-xs font-medium">
              <MapPin className="h-3 w-3" />
              New Orleans, LA
            </div>
            <h2 className="text-lg font-bold tracking-tight">Find the Best Local Businesses</h2>
          </div>
          {detectedCategory && (
            <Button
              onClick={handleMoveOn}
              className="bg-white text-red-600 hover:bg-white/90 font-semibold rounded-full px-4 py-1.5 text-sm shadow-lg hover:scale-105 transition-all"
            >
              Move On
              <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          )}
        </div>
      </div>

      {/* Chat area */}
      <Card className="flex-1 flex flex-col min-h-0 shadow-lg border-none">
        <CardContent className="flex-1 overflow-y-auto p-3 md:p-4 space-y-3">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-2 animate-fade-in-up ${
                msg.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {msg.role === 'agent' && (
                <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-red-500 to-orange-400 flex items-center justify-center text-white shadow-md">
                  <Bot className="h-3.5 w-3.5" />
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-primary text-primary-foreground rounded-br-md'
                    : 'bg-muted text-foreground rounded-bl-md'
                }`}
              >
                {renderMarkdown(msg.text)}
                {msg.suggestions && msg.suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {msg.suggestions.map((s, i) => (
                      <Badge
                        key={i}
                        variant="outline"
                        className="cursor-pointer hover:bg-background/80 transition-colors text-xs"
                        onClick={() => setInput(s)}
                      >
                        {s}
                      </Badge>
                    ))}
                  </div>
                )}
                {msg.showCategoryPicker && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {ALL_CATEGORIES.map((c) => (
                      <Badge
                        key={c}
                        variant="outline"
                        className="cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors text-xs"
                        onClick={() => handleCategoryOverride(c)}
                      >
                        {c}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
              {msg.role === 'user' && (
                <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-indigo-400 flex items-center justify-center text-white shadow-md">
                  <User className="h-3.5 w-3.5" />
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />

          {/* Quick-pick categories */}
          {!detectedCategory && messages.length === 1 && (
            <div className="space-y-2 animate-fade-in-up animate-delay-300">
              <p className="text-xs text-muted-foreground text-center">Pick a category to get started:</p>
              <div className="flex flex-wrap justify-center gap-1.5">
                {ALL_CATEGORIES.slice(0, 8).map((cat) => (
                  <Button
                    key={cat}
                    variant="outline"
                    size="sm"
                    className="rounded-full text-xs h-7 px-3"
                    onClick={() => handleQuickPick(cat)}
                  >
                    {cat}
                  </Button>
                ))}
              </div>
            </div>
          )}
        </CardContent>

        {/* Input bar */}
        <div className="border-t p-3 flex gap-2 items-center shrink-0">
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Describe what you're looking for..."
            className="flex-1 rounded-full h-9 text-sm"
          />
          <Button
            onClick={handleSend}
            size="icon"
            className="rounded-full shrink-0 h-9 w-9 bg-gradient-to-br from-red-500 to-orange-400 hover:from-red-600 hover:to-orange-500 text-white shadow-md"
          >
            <Send className="h-4 w-4" />
          </Button>
          {detectedCategory && (
            <Button
              onClick={handleMoveOn}
              className="rounded-full bg-gradient-to-br from-emerald-500 to-teal-400 hover:from-emerald-600 hover:to-teal-500 text-white font-semibold shadow-md text-sm h-9 px-4"
            >
              Move On
              <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}