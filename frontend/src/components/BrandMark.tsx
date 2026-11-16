export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} role="img" aria-label="AutoLaya" fill="none">
      <g stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" shapeRendering="geometricPrecision">
        <path d="M24 12h12l-8.4 28h24v12H12z" />
        <path d="M31 5h12l-8.4 28h24v12H19z" opacity=".55" />
        <path d="M24 12l7-7M36 12l7-7M27.6 40l7-7M51.6 40l7-7M51.6 52l7-7M12 52l7-7" opacity=".55" />
      </g>
    </svg>
  );
}
