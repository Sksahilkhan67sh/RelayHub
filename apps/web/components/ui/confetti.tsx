"use client";

import { useMemo, type CSSProperties } from "react";

// Small, tasteful confetti burst -- no external library. Pieces fall from the
// top of the containing element and fade out; @media (prefers-reduced-motion)
// in globals.css already zeroes animation-duration app-wide, so this respects
// that automatically without extra logic here.
const COLORS = ["#C17F2B", "#1D8A5E", "#C4432B", "#8A5D1F", "#565F69"];
const PIECE_COUNT = 28;

interface ConfettiPiece {
  left: number; // percent
  delayMs: number;
  durationMs: number;
  color: string;
  size: number;
  spinDeg: number;
}

export function Confetti() {
  // useMemo so the burst doesn't re-randomize (and re-trigger) on every
  // parent re-render -- only when this component instance first mounts.
  const pieces = useMemo<ConfettiPiece[]>(
    () =>
      Array.from({ length: PIECE_COUNT }, () => ({
        left: Math.random() * 100,
        delayMs: Math.random() * 200,
        durationMs: 900 + Math.random() * 500,
        color: COLORS[Math.floor(Math.random() * COLORS.length)] ?? "#C17F2B",
        size: 5 + Math.random() * 4,
        spinDeg: 180 + Math.random() * 180,
      })),
    []
  );

  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 h-0 overflow-visible" aria-hidden="true">
      {pieces.map((p, i) => {
        const style: CSSProperties & { "--confetti-spin"?: string } = {
          left: `${p.left}%`,
          width: p.size,
          height: p.size * 0.4,
          backgroundColor: p.color,
          animation: `confetti-fall ${p.durationMs}ms ease-in ${p.delayMs}ms 1 both`,
          "--confetti-spin": `${p.spinDeg}deg`,
        };
        return <span key={i} className="absolute top-0 rounded-[1px]" style={style} />;
      })}
    </div>
  );
}
