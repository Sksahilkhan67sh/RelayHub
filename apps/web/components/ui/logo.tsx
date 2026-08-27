// Static /public asset, not an optimizable remote image; plain <img> avoids needing
// next/image config for this.
export function RelayHubMark({ size = 22 }: { size?: number }) {
  // eslint-disable-next-line @next/next/no-img-element
  return <img src="/logo.png" alt="RelayHub" width={size} height={size} style={{ objectFit: "contain" }} />;
}
