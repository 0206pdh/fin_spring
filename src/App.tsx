import { FXMarketChart } from "./components/FXMarketChart";
import { MarketHeatmap } from "./components/MarketHeatmap";

export default function App() {
  return (
    <div className="min-h-screen bg-[#0a0e17]">
      <div className="max-w-7xl mx-auto px-6 py-10 flex flex-col gap-14">
        <FXMarketChart />
        <MarketHeatmap />
      </div>
    </div>
  );
}
