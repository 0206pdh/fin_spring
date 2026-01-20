import { Treemap, ResponsiveContainer, Tooltip } from 'recharts';
import { ChevronDown } from 'lucide-react';
import { useState } from 'react';

interface StockData {
  name: string;
  ticker: string;
  size: number;
  change: number;
  sector: string;
}

// Mock NIFTY 50 stock data
const stockData: StockData[] = [
  { name: 'Reliance Industries', ticker: 'RELIANCE', size: 1650000, change: 1.8, sector: 'Energy' },
  { name: 'HDFC Bank', ticker: 'HDFCBANK', size: 1200000, change: -0.5, sector: 'Banking' },
  { name: 'ICICI Bank', ticker: 'ICICIBANK', size: 780000, change: 2.3, sector: 'Banking' },
  { name: 'Infosys', ticker: 'INFY', size: 720000, change: -1.2, sector: 'IT' },
  { name: 'TCS', ticker: 'TCS', size: 1400000, change: 0.8, sector: 'IT' },
  { name: 'ITC', ticker: 'ITC', size: 620000, change: -2.1, sector: 'FMCG' },
  { name: 'Bharti Airtel', ticker: 'BHARTIARTL', size: 580000, change: 3.2, sector: 'Telecom' },
  { name: 'Kotak Mahindra Bank', ticker: 'KOTAKBANK', size: 380000, change: 1.1, sector: 'Banking' },
  { name: 'HUL', ticker: 'HINDUNILVR', size: 550000, change: -0.3, sector: 'FMCG' },
  { name: 'State Bank of India', ticker: 'SBIN', size: 520000, change: 2.8, sector: 'Banking' },
  { name: 'Axis Bank', ticker: 'AXISBANK', size: 340000, change: 1.5, sector: 'Banking' },
  { name: 'Larsen & Toubro', ticker: 'LT', size: 480000, change: -1.8, sector: 'Infrastructure' },
  { name: 'Asian Paints', ticker: 'ASIANPAINT', size: 310000, change: 0.4, sector: 'Consumer' },
  { name: 'Wipro', ticker: 'WIPRO', size: 280000, change: -0.9, sector: 'IT' },
  { name: 'Maruti Suzuki', ticker: 'MARUTI', size: 350000, change: 2.1, sector: 'Auto' },
  { name: 'Bajaj Finance', ticker: 'BAJFINANCE', size: 420000, change: -2.5, sector: 'Finance' },
  { name: 'Titan Company', ticker: 'TITAN', size: 290000, change: 1.9, sector: 'Consumer' },
  { name: 'Tech Mahindra', ticker: 'TECHM', size: 180000, change: -1.4, sector: 'IT' },
  { name: 'UltraTech Cement', ticker: 'ULTRACEMCO', size: 260000, change: 0.6, sector: 'Cement' },
  { name: 'Sun Pharma', ticker: 'SUNPHARMA', size: 380000, change: 3.5, sector: 'Pharma' },
  { name: 'Nestle India', ticker: 'NESTLEIND', size: 210000, change: -0.7, sector: 'FMCG' },
  { name: 'Power Grid', ticker: 'POWERGRID', size: 190000, change: 1.3, sector: 'Utilities' },
  { name: 'NTPC', ticker: 'NTPC', size: 170000, change: -1.1, sector: 'Energy' },
  { name: 'Coal India', ticker: 'COALINDIA', size: 150000, change: 2.6, sector: 'Energy' },
  { name: 'Tata Steel', ticker: 'TATASTEEL', size: 140000, change: -3.2, sector: 'Metals' },
  { name: 'JSW Steel', ticker: 'JSWSTEEL', size: 130000, change: -2.8, sector: 'Metals' },
  { name: 'Adani Ports', ticker: 'ADANIPORTS', size: 220000, change: 1.7, sector: 'Infrastructure' },
  { name: 'Bajaj Auto', ticker: 'BAJAJ-AUTO', size: 160000, change: 0.9, sector: 'Auto' },
  { name: 'Grasim', ticker: 'GRASIM', size: 120000, change: -0.4, sector: 'Diversified' },
  { name: 'Shree Cement', ticker: 'SHREECEM', size: 110000, change: 1.2, sector: 'Cement' },
];

// Color interpolation function based on percentage change
const getColor = (change: number): string => {
  if (change >= 3) return '#10b981'; // Strong green
  if (change >= 1.5) return '#34d399'; // Medium green
  if (change >= 0.5) return '#6ee7b7'; // Light green
  if (change >= -0.5) return '#374151'; // Dark gray (neutral)
  if (change >= -1.5) return '#fb923c'; // Orange
  if (change >= -2.5) return '#f87171'; // Light red
  return '#ef4444'; // Strong red
};

interface CustomizedContentProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  change?: number;
}

const CustomizedContent = ({ x = 0, y = 0, width = 0, height = 0, name = '', change = 0 }: CustomizedContentProps) => {
  const color = getColor(change);
  const textColor = change >= -0.5 ? '#ffffff' : '#ffffff';
  
  // Only show text if rectangle is large enough
  const showText = width > 60 && height > 30;
  const showChange = width > 80 && height > 50;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{
          fill: color,
          stroke: '#1e293b',
          strokeWidth: 2,
        }}
      />
      {showText && (
        <>
          <text
            x={x + width / 2}
            y={y + height / 2 - (showChange ? 6 : 0)}
            textAnchor="middle"
            fill={textColor}
            fontSize={width > 100 ? 14 : 11}
            fontWeight="600"
            fontFamily="Inter, system-ui, sans-serif"
          >
            {name}
          </text>
          {showChange && (
            <text
              x={x + width / 2}
              y={y + height / 2 + 14}
              textAnchor="middle"
              fill={textColor}
              fontSize={12}
              fontFamily="Inter, system-ui, sans-serif"
              opacity={0.9}
            >
              {change > 0 ? '+' : ''}{change.toFixed(2)}%
            </text>
          )}
        </>
      )}
    </g>
  );
};

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: {
      name: string;
      ticker: string;
      change: number;
      sector: string;
    };
  }>;
}

const CustomTooltip = ({ active, payload }: CustomTooltipProps) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-slate-800 border border-slate-600 rounded px-3 py-2 shadow-lg">
        <p className="text-white font-semibold text-sm">{data.ticker}</p>
        <p className="text-slate-300 text-xs mt-0.5">{data.name}</p>
        <p className={`text-sm font-semibold mt-1 ${data.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {data.change > 0 ? '+' : ''}{data.change.toFixed(2)}%
        </p>
        <p className="text-slate-400 text-xs mt-0.5">{data.sector}</p>
      </div>
    );
  }
  return null;
};

export default function App() {
  const [selectedIndex, setSelectedIndex] = useState('NIFTY-50');

  // Transform data for treemap
  const treeMapData = [{
    name: 'root',
    children: stockData.map(stock => ({
      name: stock.ticker,
      ticker: stock.ticker,
      size: stock.size,
      change: stock.change,
      sector: stock.sector,
      fullName: stock.name,
    })),
  }];

  return (
    <div className="min-h-screen bg-slate-950 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-semibold text-white">Heatmap</h1>
          <div className="relative">
            <select
              value={selectedIndex}
              onChange={(e) => setSelectedIndex(e.target.value)}
              className="appearance-none bg-slate-800 text-white px-4 py-2 pr-10 rounded border border-slate-700 cursor-pointer hover:bg-slate-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="NIFTY-50">NIFTY-50</option>
              <option value="SENSEX">SENSEX</option>
              <option value="NIFTY-BANK">NIFTY-BANK</option>
              <option value="NIFTY-IT">NIFTY-IT</option>
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          </div>
        </div>

        {/* Heatmap */}
        <div className="bg-slate-900 rounded-lg border border-slate-800 p-4">
          <ResponsiveContainer width="100%" height={600}>
            <Treemap
              data={treeMapData}
              dataKey="size"
              aspectRatio={16 / 9}
              stroke="#1e293b"
              fill="#374151"
              content={<CustomizedContent />}
            >
              <Tooltip content={<CustomTooltip />} />
            </Treemap>
          </ResponsiveContainer>
        </div>

        {/* Legend */}
        <div className="mt-6 flex items-center justify-center gap-6 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#ef4444' }}></div>
            <span className="text-slate-400">Strong Loss (&lt;-2.5%)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#fb923c' }}></div>
            <span className="text-slate-400">Mild Loss</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#374151' }}></div>
            <span className="text-slate-400">Neutral</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#6ee7b7' }}></div>
            <span className="text-slate-400">Mild Gain</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#10b981' }}></div>
            <span className="text-slate-400">Strong Gain (&gt;3%)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
