import { useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent as ReactPointerEvent } from "react";

import { cn } from "@/lib/utils";

export type DistributionKey = "easy" | "medium" | "hard";
export type Distribution = Record<DistributionKey, number>;

export const DISTRIBUTION_KEYS: DistributionKey[] = ["easy", "medium", "hard"];

const DIVIDER_KEYS = [
  ["easy", "medium"],
  ["medium", "hard"],
] as const;

const SEGMENT_CLASS: Record<DistributionKey, string> = {
  easy: "bg-emerald-500/85",
  medium: "bg-amber-500/85",
  hard: "bg-rose-500/85",
};

const DOT_CLASS: Record<DistributionKey, string> = {
  easy: "bg-emerald-500",
  medium: "bg-amber-500",
  hard: "bg-rose-500",
};

const clamp = (value: number, minimum: number, maximum: number) =>
  Math.min(maximum, Math.max(minimum, value));

function fromDividers(first: number, second: number): Distribution {
  return {
    easy: first,
    medium: second - first,
    hard: 100 - second,
  };
}

export function rebalanceDistribution(
  values: Distribution,
  key: DistributionKey,
  rawValue: number,
): Distribution {
  const value = clamp(Math.round(Number.isFinite(rawValue) ? rawValue : 0), 0, 100);
  const others = DISTRIBUTION_KEYS.filter((item) => item !== key);
  const remaining = 100 - value;
  const oldOthers = values[others[0]] + values[others[1]];
  const first = oldOthers > 0
    ? Math.round((values[others[0]] / oldOthers) * remaining)
    : Math.round(remaining / 2);
  const second = remaining - first;
  return {
    ...values,
    [key]: value,
    [others[0]]: first,
    [others[1]]: second,
  };
}

export function DistributionSlider({
  values,
  labels,
  onChange,
}: {
  values: Distribution;
  labels: Record<DistributionKey, string>;
  onChange: (value: Distribution) => void;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const valuesRef = useRef(values);
  valuesRef.current = values;
  const draggingRef = useRef<0 | 1 | null>(null);
  const [dragging, setDragging] = useState<0 | 1 | null>(null);
  const first = values.easy;
  const second = values.easy + values.medium;

  const updateAt = (index: 0 | 1, position: number) => {
    const current = valuesRef.current;
    const currentSecond = current.easy + current.medium;
    if (index === 0) {
      onChange(fromDividers(Math.round(clamp(position, 0, currentSecond)), currentSecond));
    } else {
      onChange(fromDividers(current.easy, Math.round(clamp(position, current.easy, 100))));
    }
  };

  const startDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect || rect.width <= 0) return;
    const position = clamp(((event.clientX - rect.left) / rect.width) * 100, 0, 100);
    const index: 0 | 1 = Math.abs(position - first) <= Math.abs(position - second) ? 0 : 1;
    draggingRef.current = index;
    setDragging(index);
    event.currentTarget.setPointerCapture(event.pointerId);
    updateAt(index, position);
    event.preventDefault();
  };

  const moveDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (draggingRef.current === null) return;
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect || rect.width <= 0) return;
    updateAt(
      draggingRef.current,
      clamp(((event.clientX - rect.left) / rect.width) * 100, 0, 100),
    );
    event.preventDefault();
  };

  const stopDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (draggingRef.current === null) return;
    draggingRef.current = null;
    setDragging(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const handleKey = (index: 0 | 1) => (event: KeyboardEvent<HTMLButtonElement>) => {
    const delta = event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : 0;
    if (!delta) return;
    event.preventDefault();
    if (index === 0) {
      onChange(fromDividers(clamp(first + delta, 0, second), second));
    } else {
      onChange(fromDividers(first, clamp(second + delta, first, 100)));
    }
  };

  return (
    <div
      ref={trackRef}
      className="relative h-9 touch-none select-none"
      onPointerDown={startDrag}
      onPointerMove={moveDrag}
      onPointerUp={stopDrag}
      onPointerCancel={stopDrag}
      onLostPointerCapture={() => {
        draggingRef.current = null;
        setDragging(null);
      }}
    >
      <div className="absolute inset-x-0 top-1/2 flex h-8 -translate-y-1/2 cursor-col-resize overflow-hidden rounded-lg border border-border bg-muted">
        {DISTRIBUTION_KEYS.map((key) => (
          <div
            key={key}
            className={cn("flex h-full items-center justify-center text-[10px] font-medium text-white/90", SEGMENT_CLASS[key])}
            style={{ width: `${values[key]}%` }}
          >
            {values[key] >= 12 ? `${values[key]}%` : null}
          </div>
        ))}
      </div>
      {([0, 1] as const).map((index) => {
        const position = index === 0 ? first : second;
        return (
          <button
            key={index}
            type="button"
            role="slider"
            aria-label={`${labels[DIVIDER_KEYS[index][0]]} / ${labels[DIVIDER_KEYS[index][1]]}`}
            aria-valuemin={index === 0 ? 0 : first}
            aria-valuemax={index === 0 ? second : 100}
            aria-valuenow={position}
            tabIndex={0}
            className={cn(
              "absolute top-1/2 z-10 h-8 w-3 -translate-x-1/2 -translate-y-1/2 cursor-col-resize rounded-full border-2 border-background bg-foreground shadow-sm outline-none ring-offset-2 ring-offset-background focus-visible:ring-2 focus-visible:ring-ring",
              dragging === index && "ring-2 ring-ring",
            )}
            style={{ left: `${position}%` }}
            onKeyDown={handleKey(index)}
          />
        );
      })}
    </div>
  );
}

export { DOT_CLASS as DISTRIBUTION_DOT_CLASS };
