import { useMemo } from "react";

/** Sparkline mini trend chart for creature cards */
export function MiniTrend({
  data,
  width = 280,
  height = 40,
}: {
  data?: number[];
  width?: number;
  height?: number;
}) {
  const { pointsStr, fillPath, color, lastPoint, lastVal } = useMemo(() => {
    if (!data || data.length < 2)
      return { pointsStr: "", fillPath: "", color: "#64748b", lastPoint: { x: 0, y: 0 }, lastVal: 0 };

    const mn = Math.min(...data);
    const mx = Math.max(...data);
    const range = mx - mn || 1;
    const pad = 4;
    const usableH = height - pad * 2;
    const stepX = width / (data.length - 1);

    const points = data.map((v, i) => ({
      x: i * stepX,
      y: pad + usableH - ((v - mn) / range) * usableH,
    }));

    const ptsStr = points.map((p) => `${p.x},${p.y}`).join(" ");
    const fillPath = `M0,${height} ` + points.map((p) => `L${p.x},${p.y}`).join(" ") + ` L${points[points.length - 1].x},${height} Z`;
    
    const last = data[data.length - 1];
    const first = data[0];
    const c = last >= first ? "#10b981" : "#ef4444";

    return { pointsStr: ptsStr, fillPath, color: c, lastPoint: points[points.length - 1], lastVal: last };
  }, [data, width, height]);

  if (!data || data.length < 2) {
    return (
      <div style={{ height, display: "flex", alignItems: "center", justifyContent: "center", color: "rgba(255,255,255,0.3)", fontSize: 12 }}>
        暫無趨勢資料
      </div>
    );
  }

  // Adjust tooltip offset to prevent clipping at the SVG bounds
  const isUp = lastPoint.y > 22;
  const tooltipY = isUp ? lastPoint.y - 20 : lastPoint.y + 6;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      style={{ display: "block", overflow: "visible" }}
    >
      <style>{`
        @keyframes trendPulse {
          0% { r: 3px; opacity: 0.8; }
          100% { r: 8px; opacity: 0; }
        }
        .trend-pulse-dot {
          animation: trendPulse 1.8s cubic-bezier(0.24, 0, 0.38, 1) infinite;
        }
      `}</style>
      <defs>
        <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.3} />
          <stop offset="100%" stopColor={color} stopOpacity={0.02} />
        </linearGradient>
      </defs>
      {/* Fill path using the dynamic coordinates */}
      <path d={fillPath} fill="url(#trendFill)" />
      
      {/* Polyline element representing the trend line */}
      <polyline
        points={pointsStr}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Glow polyline element */}
      <polyline
        points={pointsStr}
        fill="none"
        stroke={color}
        strokeWidth={4}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.25}
      />
      
      {/* Latest Price Pulse Dot */}
      <circle
        cx={lastPoint.x}
        cy={lastPoint.y}
        r={3}
        fill={color}
      />
      <circle
        cx={lastPoint.x}
        cy={lastPoint.y}
        r={6}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        opacity={0.6}
        className="trend-pulse-dot"
        style={{ transformOrigin: `${lastPoint.x}px ${lastPoint.y}px` }}
      />

      {/* Latest Price Tag Tooltip */}
      <g transform={`translate(${lastPoint.x - 38}, ${tooltipY})`}>
        <rect
          width="36"
          height="13"
          rx="3"
          fill="rgba(28, 21, 18, 0.92)"
          stroke={color}
          strokeWidth="1"
        />
        <text
          x="18"
          y="9"
          fill="#fbfaf7"
          fontSize="8"
          fontWeight="bold"
          textAnchor="middle"
        >
          {lastVal.toFixed(1)}
        </text>
      </g>
    </svg>
  );
}
