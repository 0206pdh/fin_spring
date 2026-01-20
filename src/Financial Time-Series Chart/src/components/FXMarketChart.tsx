import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Label } from 'recharts';

// Generate realistic FX market data
const generateData = () => {
  const quarters = ['Q1 2023', 'Q2 2023', 'Q3 2023', 'Q4 2023', 'Q1 2024', 'Q2 2024', 'Q3 2024', 'Q4 2024', 'Q1 2025', 'Q2 2025', 'Q3 2025', 'Q4 2025'];
  
  return quarters.map((quarter, index) => {
    // FX swaps: dominant and highest values (3000-4500 range)
    const fxSwaps = 3500 + Math.sin(index * 0.5) * 400 + Math.random() * 300 + index * 50;
    
    // Spot FX: medium volatility (1500-2500 range)
    const spotFX = 1900 + Math.sin(index * 0.8) * 350 + (index % 2 === 0 ? 200 : -100);
    
    // Outright forwards: gradual upward trend (800-1600 range)
    const forwards = 900 + index * 55 + Math.sin(index * 0.3) * 80;
    
    // Non-traditional: low and stable (200-400 range)
    const nonTraditional = 280 + Math.sin(index * 0.4) * 60 + Math.random() * 40;
    
    return {
      quarter,
      fxSwaps: Math.round(fxSwaps),
      spotFX: Math.round(spotFX),
      forwards: Math.round(forwards),
      nonTraditional: Math.round(nonTraditional),
    };
  });
};

const data = generateData();

export function FXMarketChart() {
  return (
    <div className="w-full max-w-6xl">
      <div className="mb-8">
        <h1 className="text-[#e8eaed] text-2xl tracking-tight mb-2">FX Market Activity by Instrument</h1>
        <p className="text-[#9aa0a6] text-sm font-light">Daily average notional value (USD billions)</p>
      </div>
      
      <div className="bg-[#12161f] rounded-lg p-8 border border-[#1e2430]">
        <ResponsiveContainer width="100%" height={500}>
          <LineChart 
            data={data} 
            margin={{ top: 20, right: 120, bottom: 20, left: 60 }}
          >
            <CartesianGrid 
              strokeDasharray="0" 
              stroke="#1e2430" 
              horizontal={true}
              vertical={false}
            />
            <XAxis 
              dataKey="quarter" 
              stroke="#9aa0a6"
              tick={{ fill: '#9aa0a6', fontSize: 11, fontWeight: 300 }}
              axisLine={{ stroke: '#1e2430' }}
              tickLine={false}
            />
            <YAxis 
              stroke="#9aa0a6"
              tick={{ fill: '#9aa0a6', fontSize: 11, fontWeight: 300 }}
              axisLine={{ stroke: '#1e2430' }}
              tickLine={false}
              domain={[0, 5000]}
              ticks={[0, 1000, 2000, 3000, 4000, 5000]}
            />
            
            {/* FX Swaps - Blue, dominant line */}
            <Line 
              type="monotone" 
              dataKey="fxSwaps" 
              stroke="#4a9eff" 
              strokeWidth={2.5}
              dot={false}
              name="FX swaps"
            />
            
            {/* Spot FX - Pink/Magenta, volatile */}
            <Line 
              type="monotone" 
              dataKey="spotFX" 
              stroke="#ff4a9e" 
              strokeWidth={2.5}
              dot={false}
              name="Spot"
            />
            
            {/* Outright forwards - Orange, upward trend */}
            <Line 
              type="monotone" 
              dataKey="forwards" 
              stroke="#ff9a4a" 
              strokeWidth={2.5}
              dot={false}
              name="Outright forwards"
            />
            
            {/* Non-traditional - Green, low and stable */}
            <Line 
              type="monotone" 
              dataKey="nonTraditional" 
              stroke="#4aff9e" 
              strokeWidth={2.5}
              dot={false}
              name="Non-traditional"
            />
          </LineChart>
        </ResponsiveContainer>
        
        {/* Custom line labels positioned near the lines */}
        <div className="relative mt-[-420px] ml-[calc(100%-100px)] pointer-events-none">
          <div className="flex flex-col gap-4">
            <div className="text-[#4a9eff] text-sm font-light">FX swaps</div>
            <div className="text-[#ff4a9e] text-sm font-light mt-14">Spot</div>
            <div className="text-[#ff9a4a] text-sm font-light mt-20">Outright forwards</div>
            <div className="text-[#4aff9e] text-sm font-light mt-32">Non-traditional</div>
          </div>
        </div>
      </div>
      
      <div className="mt-4 text-[#6e7681] text-xs font-light">
        Source: Simulated data for illustrative purposes
      </div>
    </div>
  );
}
